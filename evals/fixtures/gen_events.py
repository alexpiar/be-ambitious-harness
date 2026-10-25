# Генератор синтетических событий пользователей за 2025 год (задачи T2, L2, T2-pass).
#
# Профили:
#   l2      (по умолчанию) — данные прогона 21.10.2026 байт в байт, как замороженный
#           evals/runs/2026-10-21-gate/fixtures/gen_events.py. Ранний сигнал слабый:
#           входная проверка на 7-й день почти, но не совсем проходит. Дефекты этого
#           профиля (события до регистрации; payment_failed и plan_downgrade только
#           у ушедших) оставлены намеренно: иначе прогон 21.10 не воспроизвести.
#   t2pass  — тест «двигателя»: сильный ранний сигнал (логистическая регрессия
#           на признаках первой недели — ROC AUC около 0,73, порог 0,65 проходит с запасом);
#           выиграть сверх неё можно, только глядя дальше первой недели. Дефекты l2 устранены.
#
# Запуск: python3 -I gen_events.py <out.csv> <seed> <n_users> [--profile l2|t2pass] [--calibrate]
# Только стандартная библиотека. Подробности, команды и калибровка — README.md рядом.
import argparse
import csv
import math
import random
from datetime import datetime, timedelta

Y0 = datetime(2025, 1, 1)
FIELDS = ['ts', 'user_id', 'event', 'value', 'plan', 'device', 'country', 'channel']
KINDS = ['export', 'share', 'search', 'tags']

# Параметры профиля t2pass (калибровка — calibrate_t2pass.py, таблица — README.md).
# Механизм: латентная вовлечённость z; вовлечённость первой недели e = rho*z + шум.
# Ранний уход (отмена в основном на 8–60-й день) решается по активации за первую неделю:
# активирован, кто был активен не меньше act_days разных дней И пользовался не меньше
# act_kinds разными функциями. Это и есть сильный ранний сигнал.
# Поздний уход решается по z и виден по спаду активности за 35 суток до отмены, по сбоям
# оплаты и предвестникам: на 7-й день его почти не видно, позже — хорошо. Отсюда запас
# для модели, которая смотрит дальше первой недели. На самом 7-м дне бустинг и признаки
# «по смыслу» к логистической регрессии почти ничего не добавляют (см. README.md).
# Предвестники (обращение, понижение, сбой оплаты) бывают и у тех, кто не уходит;
# событий раньше регистрации и после отмены (кроме exit_survey) нет.
T2PASS = dict(
    rho=0.6,              # связь вовлечённости первой недели с долгосрочной
    day_base=-0.3,        # вероятность активного дня на 2–7-й день: sig(day_base + day_e*e - day_decay*d)
    day_e=1.0,
    day_decay=0.12,
    sess_base=-0.7,       # сессий в активный день: 1 + Poisson(exp(sess_base + sess_e*e))
    sess_e=0.35,
    feat_base=-0.5,       # вероятность feature_used после сессии: sig(feat_base + feat_e*e)
    feat_e=0.6,
    act_days=3,           # порог активации: активных дней за первую неделю
    act_kinds=2,          # порог активации: разных функций за первую неделю
    early_base=-2.7,      # ранний уход: sig(early_base + early_noact*[не активирован] - early_z*z + канал)
    early_noact=2.2,
    early_z=0.3,
    early_min=1.0,        # отмена раннего ухода: signup + 7 + early_min + Exp(среднее early_mean)
    early_mean=18.0,
    late_base=-1.1,       # поздний уход (из оставшихся): sig(late_base - late_z*z + канал)
    late_z=1.2,
    late_min=30.0,        # отмена позднего ухода: signup + late_min + Exp(среднее late_mean)
    late_mean=70.0,
    pay_fail_base=0.04,   # сбой списания у любого пользователя; повтор через 1–5 суток,
    retry_fail=0.25,      # который сам не проходит с этой вероятностью; тогда второй повтор через 2–6 суток успешен
    pay_fail_near=0.5,    # сбой списания за 30 суток до отмены;
    near_recover=0.3,     # успешный повтор через 1–5 суток (если до отмены) с этой вероятностью
    ticket_base=0.10,     # обращение в поддержку у любого пользователя, в случайный момент жизни
    ticket_pre=0.35,      # обращение за 2–20 суток до отмены
    downgrade_base=0.10,  # понижение pro → basic у любого pro, в случайный момент жизни
    downgrade_pre=0.30,   # понижение pro → basic за 5–25 суток до отмены
)


def sig(x):
    return 1 / (1 + math.exp(-x))


def ts(day_float):
    return (Y0 + timedelta(days=day_float)).strftime('%Y-%m-%dT%H:%M:%S')


# ---------------------------------------------------------------------------
# Профиль l2 — дословно логика замороженного генератора 21.10 (тот же порядок
# вызовов rnd). Менять нельзя: sha256 выхода сверяется с данными прогона.
# ---------------------------------------------------------------------------
def gen_l2(seed, n_users, calibrate):
    rnd = random.Random(seed)
    RHO = 0.37  # связь раннего поведения с латентной вовлечённостью

    def poisson(lam):
        l, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= rnd.random()
            if p <= l:
                return k
            k += 1

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
    return rows, early, labels, rnd


def calibrate_l2(early, labels, rnd):
    # как в генераторе 21.10: логистическая регрессия на ранних признаках, holdout 20 %,
    # метка «отмена когда-либо в 2025 году» (не определение исполнителей L2-A)
    X = [[1.0] + [float(v) for v in x] for x in early]
    idx = list(range(len(X)))
    rnd.shuffle(idx)
    cut = int(0.8 * len(idx))
    tr, te = idx[:cut], idx[cut:]
    wts = gd_logistic(X, labels, tr)
    sc = [sum(a * b for a, b in zip(wts, X[j])) for j in te]
    print('churn rate', round(sum(labels) / len(labels), 3), 'early-7d logistic holdout AUC',
          round(auc(sc, [labels[j] for j in te]), 3))


# ---------------------------------------------------------------------------
# Профиль t2pass
# ---------------------------------------------------------------------------
def gen_t2pass(seed, n_users, calibrate, params=None):
    P = dict(T2PASS)
    if params:
        P.update(params)
    rnd = random.Random(seed)
    horizon = 364.99  # всё, что позже, в выгрузку 2025 года не попадает

    def poisson(lam):
        l, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= rnd.random()
            if p <= l:
                return k
            k += 1

    rows, early, labels = [], [], []
    for i in range(n_users):
        uid = f'u{seed % 97:02d}{i:05d}'
        z = rnd.gauss(0, 1)
        e = P['rho'] * z + math.sqrt(1 - P['rho'] ** 2) * rnd.gauss(0, 1)
        signup = rnd.uniform(0, 272)  # 1 янв — 30 сен
        plan = 'pro' if rnd.random() < sig(-0.8 + 0.4 * z) else 'basic'
        device = rnd.choice(['ios', 'android', 'web'])
        country = rnd.choices(['US', 'DE', 'GB', 'BR', 'IN', 'FR'], [30, 15, 12, 15, 18, 10])[0]
        channel = rnd.choices(['ads', 'organic', 'referral'], [50, 35, 15])[0]
        ch_eff = {'ads': 0.15, 'organic': 0.0, 'referral': -0.25}[channel]
        base = dict(user_id=uid, plan=plan, device=device, country=country, channel=channel)
        user_rows = []

        def ev(day, name, value=''):
            user_rows.append((day, name, value))

        ev(signup, 'signup')
        # первая неделя по дням: день регистрации активен всегда, дальше — по e
        active_days, kinds, n_sess, n_feat = 0, set(), 0, 0
        for d in range(7):
            if d > 0 and rnd.random() >= sig(P['day_base'] + P['day_e'] * e - P['day_decay'] * d):
                continue
            active_days += 1
            lo = signup + d
            for _ in range(1 + poisson(math.exp(P['sess_base'] + P['sess_e'] * e))):
                t = lo + rnd.uniform(0, 0.98)
                ev(t, 'session_start', str(rnd.randint(1, 12)))
                n_sess += 1
                if rnd.random() < sig(P['feat_base'] + P['feat_e'] * e):
                    k = rnd.choice(KINDS)
                    kinds.add(k)
                    n_feat += 1
                    ev(t + 0.01, 'feature_used', k)
        activated = active_days >= P['act_days'] and len(kinds) >= P['act_kinds']

        # уход: ранний (по активации) или поздний (по z); дата может выпасть за 2025 год
        churn_day = None
        if rnd.random() < sig(P['early_base'] + P['early_noact'] * (not activated) - P['early_z'] * z + ch_eff):
            churn_day = signup + 7 + P['early_min'] + rnd.expovariate(1 / P['early_mean'])
        elif rnd.random() < sig(P['late_base'] - P['late_z'] * z + ch_eff):
            churn_day = signup + P['late_min'] + rnd.expovariate(1 / P['late_mean'])
        stop = churn_day if churn_day else horizon
        life = stop - signup

        # понижение тарифа: предвестник отмены или обычное, у любого pro
        downgrade = None
        if plan == 'pro':
            if churn_day and rnd.random() < P['downgrade_pre']:
                downgrade = churn_day - rnd.uniform(min(5.0, life / 2), min(25.0, life))
            elif rnd.random() < P['downgrade_base']:
                downgrade = signup + rnd.uniform(0, life)
        if downgrade is not None:
            ev(downgrade, 'plan_downgrade')

        # после первой недели: активность по z, спад за 35 суток до отмены
        day = signup + 7
        rate = math.exp(-1.5 + 0.55 * z)
        while day < stop:
            r = rate
            if churn_day and churn_day - day < 35:
                r *= 0.25
            day += rnd.expovariate(max(r, 0.02))
            if day >= stop:
                break
            ev(day, 'session_start', str(rnd.randint(1, 12)))
            if rnd.random() < 0.35 and day + 0.01 < stop:
                ev(day + 0.01, 'feature_used', rnd.choice(KINDS))

        # списания раз в 30 суток; сумма — по тарифу на дату списания
        pay = signup + 30
        while pay < stop:
            amount = '9.99' if plan == 'basic' or (downgrade is not None and downgrade < pay) else '24.99'
            near = churn_day is not None and churn_day - pay < 30
            if rnd.random() < (P['pay_fail_near'] if near else P['pay_fail_base']):
                ev(pay, 'payment_failed', amount)
                retry = pay + rnd.uniform(1, 5)
                if not near:
                    if rnd.random() < P['retry_fail']:
                        ev(retry, 'payment_failed', amount)
                        retry += rnd.uniform(2, 6)
                    ev(retry, 'payment', amount)
                elif rnd.random() < P['near_recover'] and retry < churn_day:
                    ev(retry, 'payment', amount)
            else:
                ev(pay, 'payment', amount)
            pay += 30

        # обращения в поддержку: обычные у любого и предвестник у уходящих
        if rnd.random() < P['ticket_base']:
            ev(signup + rnd.uniform(0, life), 'support_ticket')
        if churn_day:
            if rnd.random() < P['ticket_pre']:
                ev(churn_day - rnd.uniform(2, min(20.0, life)), 'support_ticket')
            ev(churn_day, 'cancel')
            if rnd.random() < 0.6:
                ev(churn_day + 0.02, 'exit_survey', rnd.choice(['price', 'missing_feature', 'not_using', 'other']))

        for day_f, name, value in user_rows:
            if day_f <= horizon:
                rows.append(dict(base, ts=ts(day_f), event=name, value=value))
        if calibrate:
            early.append([math.log1p(n_sess), math.log1p(n_feat), active_days, len(kinds), plan == 'pro',
                          device == 'ios', device == 'android', channel == 'ads', channel == 'referral'])
            labels.append(1 if churn_day and signup + 7 < churn_day <= signup + 67 else 0)
    return rows, early, labels, rnd


def calibrate_t2pass(early, labels, rnd):
    # быстрая самопроверка без numpy: метка как у исполнителей L2-A (D = 7, отмена в (T, T+60 сут]),
    # логистическая регрессия на признаках первой недели, holdout 20 %. Канонические числа —
    # calibrate_t2pass.py (полный набор признаков, бустинг, скрытые пользователи).
    X = [[1.0] + [float(v) for v in x] for x in early]
    m = len(X[0])
    mu = [sum(x[k] for x in X) / len(X) for k in range(m)]
    sd = [max(1e-9, math.sqrt(sum((x[k] - mu[k]) ** 2 for x in X) / len(X))) for k in range(m)]
    X = [[1.0] + [(x[k] - mu[k]) / sd[k] for k in range(1, m)] for x in X]
    idx = list(range(len(X)))
    rnd.shuffle(idx)
    cut = int(0.8 * len(idx))
    tr, te = idx[:cut], idx[cut:]
    wts = gd_logistic(X, labels, tr)
    sc = [sum(a * b for a, b in zip(wts, X[j])) for j in te]
    print('D=7 population', len(labels), 'label share (T, T+60d]', round(sum(labels) / len(labels), 3),
          'early-7d logistic holdout AUC', round(auc(sc, [labels[j] for j in te]), 3))


def gd_logistic(X, labels, tr):
    wts = [0.0] * len(X[0])
    for _ in range(300):
        g = [0.0] * len(wts)
        for j in tr:
            p = sig(sum(a * b for a, b in zip(wts, X[j])))
            for k in range(len(wts)):
                g[k] += (p - labels[j]) * X[j][k]
        wts = [a - 0.5 * b / len(tr) for a, b in zip(wts, g)]
    return wts


def auc(scores, ys):
    pairs = sorted(zip(scores, ys))
    pos = sum(ys)
    neg = len(ys) - pos
    rank_sum = 0
    for rank, (_, y) in enumerate(pairs, 1):
        if y:
            rank_sum += rank
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


PROFILES = {'l2': (gen_l2, calibrate_l2), 't2pass': (gen_t2pass, calibrate_t2pass)}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Синтетические события пользователей за 2025 год.')
    ap.add_argument('out', help='куда записать CSV')
    ap.add_argument('seed', type=int)
    ap.add_argument('n_users', type=int)
    ap.add_argument('--profile', choices=sorted(PROFILES), default='l2')
    ap.add_argument('--calibrate', action='store_true', help='напечатать быструю самопроверку раннего сигнала')
    a = ap.parse_args(argv)
    gen, cal = PROFILES[a.profile]
    rows, early, labels, rnd = gen(a.seed, a.n_users, a.calibrate)
    rows.sort(key=lambda r: (r['ts'], r['user_id']))
    with open(a.out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print('rows', len(rows), 'users', a.n_users)
    if a.calibrate:
        cal(early, labels, rnd)


if __name__ == '__main__':
    main()
