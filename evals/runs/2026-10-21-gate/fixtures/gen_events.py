# Генератор фикстуры L2 (на базе T2): события пользователей за 2025 год.
# Ранний сигнал (первые 7 дней) слабый — AUC ~0.60; поздние сигналы сильные.
# Запуск: python3 -I gen_events.py <out.csv> <seed> <n_users> [--calibrate]
import csv, math, random, sys
from datetime import datetime, timedelta

out, seed, n_users = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
calibrate = '--calibrate' in sys.argv
rnd = random.Random(seed)
Y0 = datetime(2025, 1, 1)
END = datetime(2025, 12, 31, 23, 59)
RHO = 0.37  # связь раннего поведения с латентной вовлечённостью


def sig(x):
    return 1 / (1 + math.exp(-x))


def poisson(lam):
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= l:
            return k
        k += 1


def ts(day_float):
    return (Y0 + timedelta(days=day_float)).strftime('%Y-%m-%dT%H:%M:%S')


rows, early, labels = [], [], []
for i in range(n_users):
    uid = f'u{seed % 97:02d}{i:05d}'
    z = rnd.gauss(0, 1)
    z_early = RHO * z + math.sqrt(1 - RHO ** 2) * rnd.gauss(0, 1)
    signup = rnd.uniform(0, 272)  # 1 янв — 30 сен
    plan = 'pro' if rnd.random() < sig(-0.8 + 0.4 * z) else 'basic'
    device = rnd.choice(['ios', 'android', 'web'])
    country = rnd.choices(['US', 'DE', 'GB', 'BR', 'IN', 'FR'], [30, 15, 12, 15, 18, 10])[0]
    channel = rnd.choices(['ads', 'organic', 'referral'], [50, 35, 15])[0]
    ch_eff = {'ads': 0.15, 'organic': 0.0, 'referral': -0.25}[channel]
    churn_prob = sig(-0.2 - 1.4 * z + ch_eff)
    churn_day = None
    if rnd.random() < churn_prob:
        churn_day = signup + 18 + rnd.expovariate(1 / 70)
    horizon = 364.99
    stop = min(churn_day, horizon) if churn_day else horizon
    if churn_day and churn_day > horizon:
        churn_day = None
    base = dict(user_id=uid, plan=plan, device=device, country=country, channel=channel)

    def ev(day, name, **extra):
        r = dict(base, ts=ts(day), event=name, value='')
        r.update(extra)
        rows.append(r)

    ev(signup, 'signup')
    # первая неделя: слабая связь с z
    s7 = poisson(math.exp(1.5 + 0.45 * z_early))
    f7 = poisson(math.exp(0.6 + 0.5 * z_early))
    for _ in range(s7):
        ev(signup + rnd.uniform(0, 7), 'session_start', value=str(rnd.randint(1, 12)))
    for _ in range(f7):
        ev(signup + rnd.uniform(0, 7), 'feature_used', value=rnd.choice(['export', 'share', 'search', 'tags']))
    # дальше: активность по латентной вовлечённости, спад перед отменой
    day = signup + 7
    rate = math.exp(-1.5 + 0.55 * z)
    while day < stop:
        r = rate
        if churn_day and churn_day - day < 35:
            r *= 0.25
        day += rnd.expovariate(max(r, 0.02))
        if day >= stop:
            break
        ev(day, 'session_start', value=str(rnd.randint(1, 12)))
        if rnd.random() < 0.35:
            ev(day + 0.01, 'feature_used', value=rnd.choice(['export', 'share', 'search', 'tags']))
    # платежи раз в 30 дней
    pay = signup + 30
    while pay < stop:
        failed = churn_day and churn_day - pay < 30 and rnd.random() < 0.5
        ev(pay, 'payment_failed' if failed else 'payment', value='9.99' if plan == 'basic' else '24.99')
        pay += 30
    if churn_day:
        if rnd.random() < 0.35:
            ev(churn_day - rnd.uniform(2, 20), 'support_ticket')
        if plan == 'pro' and rnd.random() < 0.3:
            ev(churn_day - rnd.uniform(5, 25), 'plan_downgrade')
        ev(churn_day, 'cancel')
        if rnd.random() < 0.6:
            ev(churn_day + 0.02, 'exit_survey', value=rnd.choice(['price', 'missing_feature', 'not_using', 'other']))
    elif rnd.random() < 0.08:
        ev(rnd.uniform(signup + 7, horizon), 'support_ticket')
    if calibrate:
        early.append([math.log1p(s7), math.log1p(f7), plan == 'pro', device == 'ios', device == 'android',
                      channel == 'ads', channel == 'referral'])
        labels.append(1 if churn_day else 0)

rows.sort(key=lambda r: (r['ts'], r['user_id']))
with open(out, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=['ts', 'user_id', 'event', 'value', 'plan', 'device', 'country', 'channel'])
    w.writeheader()
    w.writerows(rows)
print('rows', len(rows), 'users', n_users)

if calibrate:
    # логистическая регрессия на ранних признаках, holdout 20 %
    def auc(scores, ys):
        pairs = sorted(zip(scores, ys))
        pos = sum(ys); neg = len(ys) - pos; rank_sum = 0
        for rank, (_, y) in enumerate(pairs, 1):
            if y:
                rank_sum += rank
        return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)
    X = [[1.0] + [float(v) for v in x] for x in early]
    idx = list(range(len(X))); rnd.shuffle(idx)
    cut = int(0.8 * len(idx)); tr, te = idx[:cut], idx[cut:]
    wts = [0.0] * len(X[0])
    for _ in range(300):
        g = [0.0] * len(wts)
        for j in tr:
            p = sig(sum(a * b for a, b in zip(wts, X[j])))
            for k in range(len(wts)):
                g[k] += (p - labels[j]) * X[j][k]
        wts = [a - 0.5 * b / len(tr) for a, b in zip(wts, g)]
    sc = [sum(a * b for a, b in zip(wts, X[j])) for j in te]
    print('churn rate', round(sum(labels) / len(labels), 3), 'early-7d logistic holdout AUC', round(auc(sc, [labels[j] for j in te]), 3))
