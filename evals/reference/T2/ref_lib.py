# Общие функции эталонов T2, T2-pass, L2 (файл одинаковый в трёх папках, как и score.py):
# данные и holdout, точки и метки, метрики с бутстрэпом по пользователям, логистическая
# регрессия с выгрузкой в JSON, входная проверка L2-A, перестановочная важность, проверки.
# Признаки считает score.py — тот же код при обучении и при скоринге.
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, train_test_split

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
GEN = os.path.join(ROOT, 'evals', 'fixtures', 'gen_events.py')
# профиль → (seed, пользователей, sha256 CSV из evals/fixtures/README.md)
DATA = {'l2': (2025, 6000, '2284d9bc94351ba7a362d45a52b3b83e534bb0a342446a5321cc78568b1d93f1'),
        't2pass': (2026, 6000, '683bfcf7193566fa076ecd9782d5c4593d49a3b688a7ecadd6a06c30c46fb470')}
SEED, N_BOOT, DAY = 42, 1000, 86400
DATA_END = 365 * DAY - 1  # 2025-12-31T23:59:59 в секундах от 2025-01-01

_spec = importlib.util.spec_from_file_location('ref_score', os.path.join(HERE, 'score.py'))
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256(path):
    with open(path, 'rb') as fh:
        return sha256_bytes(fh.read())


# ---------------------------------------------------------------------------- данные и holdout
def generate(profile, work):
    seed, n, want = DATA[profile]
    path = os.path.join(work, f'events_{profile}_{seed}.csv')
    if not (os.path.exists(path) and sha256(path) == want):
        os.makedirs(work, exist_ok=True)
        subprocess.run([sys.executable, '-I', GEN, path, str(seed), str(n), '--profile', profile],
                       check=True, capture_output=True)
    got = sha256(path)
    if got != want:
        sys.exit(f'sha256 данных {got} не совпадает с evals/fixtures/README.md ({want})')
    return path, got


def seal_holdout(path, out_file):
    """Первое действие: 20 % пользователей, страта — месяц регистрации, seed 42. Читаются только
    строки signup (user_id и ts); список сохраняется, повторный запуск сверяет его побайтно."""
    s = pd.read_csv(path, usecols=['ts', 'user_id', 'event'], dtype=str)
    su = s[s['event'] == 'signup'].groupby('user_id')['ts'].min().sort_index()
    _, ho = train_test_split(su.index.to_numpy(), test_size=0.2, stratify=su.str[5:7].to_numpy(),
                             random_state=SEED)
    text = ''.join(f'{u}\n' for u in sorted(ho)).encode()
    if os.path.exists(out_file):
        with open(out_file, 'rb') as fh:
            if fh.read() != text:
                sys.exit(f'{out_file} не совпадает с воспроизведённым сплитом')
    else:
        with open(out_file, 'wb') as fh:
            fh.write(text)
    return set(ho), sha256_bytes(text), len(su)


def load(path):
    df = sc.load_events(path)
    df['t'] = sc.to_sec(df['ts'])
    return df


def users_table(df):
    su = df[df['event'] == 'signup'].groupby('user_id')['t'].min()
    can = df[df['event'] == 'cancel'].groupby('user_id')['t'].min().reindex(su.index)
    return pd.DataFrame({'signup': su, 'cancel': can}).sort_index()


# ---------------------------------------------------------------------------- точки и метки
def d_points(U, D, H=60):
    """T = signup + D суток; популяция — без cancel с ts <= T; метка — cancel в (T, T + H суток]."""
    T = U['signup'] + D * DAY
    keep = ~(U['cancel'] <= T)
    c = U['cancel'][keep]
    y = ((c > T[keep]) & (c <= T[keep] + H * DAY)).astype(int)
    return pd.DataFrame({'user_id': U.index[keep], 'asof': T[keep].to_numpy(np.int64), 'y': y.to_numpy()})


def snapshot_points(U, dates, H=30):
    """Срез на дату A: активные (signup <= A, нет cancel с ts <= A); метка — cancel в (A, A + H суток]."""
    parts = []
    for A in dates:
        a = int((pd.Timestamp(A) - sc.EPOCH) // pd.Timedelta(seconds=1))
        keep = (U['signup'] <= a) & ~(U['cancel'] <= a)
        c = U['cancel'][keep]
        parts.append(pd.DataFrame({'user_id': U.index[keep], 'asof': a,
                                   'y': ((c > a) & (c <= a + H * DAY)).astype(int).to_numpy()}))
    return pd.concat(parts, ignore_index=True)


def features(E, P):
    return sc.build_features(E, P['user_id'].to_numpy(), P['asof'].to_numpy())


# ---------------------------------------------------------------------------- метрики
def boot_chunks(groups, n=N_BOOT, seed=SEED, chunk=100):
    """Веса строк для бутстрэпа по пользователям: повтор пользователя k раз = вес k."""
    _, g = np.unique(groups, return_inverse=True)
    m = int(g.max()) + 1
    rng = np.random.default_rng(seed)
    for b in range(0, n, chunk):
        cnt = rng.multinomial(m, np.full(m, 1.0 / m), size=min(chunk, n - b))
        yield cnt[:, g].astype(float)


def _grouped(y, s, W, desc):
    o = np.argsort(-s if desc else s, kind='mergesort')
    ss = s[o]
    starts = np.flatnonzero(np.r_[True, ss[1:] != ss[:-1]])
    Wo = W[:, o]
    pos = np.add.reduceat(Wo * y[o], starts, axis=1)
    tot = np.add.reduceat(Wo, starts, axis=1)
    return pos, tot - pos


def auc_w(y, s, W):
    pos, neg = _grouped(y, s, W, desc=False)
    below = np.cumsum(neg, axis=1) - neg
    return (pos * (below + 0.5 * neg)).sum(1) / (pos.sum(1) * neg.sum(1))


def ap_w(y, s, W):
    pos, neg = _grouped(y, s, W, desc=True)
    tp, fp = np.cumsum(pos, axis=1), np.cumsum(neg, axis=1)
    return (pos * tp / np.maximum(tp + fp, 1e-12)).sum(1) / pos.sum(1)


def top_w(y, s, W, frac=0.2):
    """Доля уходящих среди frac пользователей с наибольшим риском (связки на границе — пропорционально)."""
    pos, neg = _grouped(y, s, W, desc=True)
    w = pos + neg
    cap = frac * w.sum(1, keepdims=True)
    prev = np.cumsum(w, axis=1) - w
    f = np.clip((cap - prev) / np.maximum(w, 1e-12), 0, 1)
    return (f * pos).sum(1) / cap[:, 0]


def ci(v):
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


def evaluate(y, scores, groups, pairs=(), full=True):
    """ROC AUC (и при full — PR AUC, доля уходящих в топ-20 %, лифт) с 95 % ДИ; разности ROC AUC пар."""
    y = np.asarray(y, float)
    one = np.ones((1, len(y)))
    kinds = {'auc': auc_w, 'ap': ap_w, 'top20': top_w} if full else {'auc': auc_w}
    acc = {(n, k): [] for n in scores for k in kinds}
    base = []
    for W in boot_chunks(groups):
        for n, s in scores.items():
            for k, fn in kinds.items():
                acc[(n, k)].append(fn(y, s, W))
        base.append((W * y).sum(1) / W.sum(1))
    base = np.concatenate(base)
    out = {}
    for n, s in scores.items():
        r = {}
        for k, fn in kinds.items():
            v = np.concatenate(acc[(n, k)])
            r[k], r[k + '_ci'] = float(fn(y, s, one)[0]), ci(v)
            if k == 'top20':
                r['lift'], r['lift_ci'] = r['top20'] / float(y.mean()), ci(v / base)
        out[n] = r
    for a, b in pairs:
        d = np.concatenate(acc[(a, 'auc')]) - np.concatenate(acc[(b, 'auc')])
        out[f'{a} − {b}'] = {'diff_auc': out[a]['auc'] - out[b]['auc'], 'diff_auc_ci': ci(d)}
    out['_base_rate'] = float(y.mean())
    return out


# ---------------------------------------------------------------------------- логистическая регрессия
def make_spec(F, numeric, log1p=(), categorical=sc.STATIC):
    spec = dict(numeric=list(numeric), log1p=sorted(set(log1p) & set(numeric)),
                categorical={c: sorted(F[c].unique().tolist()) for c in categorical})
    k = len(sc.column_names(spec))
    spec['mean'], spec['scale'] = [0.0] * k, [1.0] * k
    X = sc.design_matrix(F, spec)
    sd = X.std(0)
    spec['mean'], spec['scale'] = X.mean(0).tolist(), np.where(sd > 0, sd, 1.0).tolist()
    return spec


def fit_lr(F, y, numeric, log1p=(), C=1.0, categorical=sc.STATIC):
    spec = make_spec(F, numeric, log1p, categorical)
    clf = LogisticRegression(C=C, max_iter=5000, random_state=SEED).fit(sc.design_matrix(F, spec), y)
    return dict(spec=spec, coef=clf.coef_[0].tolist(), intercept=float(clf.intercept_[0]), C=C)


def user_folds(users, k=5, seed=SEED):
    """Фолд пользователя для срезов (у пользователя много строк): перестановка с seed."""
    uniq = np.unique(users)
    f = np.random.default_rng(seed).permutation(len(uniq)) % k
    return pd.Series(f, index=uniq).reindex(users).to_numpy()


def strat_folds(y, k=5, seed=SEED):
    f = np.zeros(len(y), int)
    for i, (_, va) in enumerate(StratifiedKFold(k, shuffle=True, random_state=seed).split(np.zeros(len(y)), y)):
        f[va] = i
    return f


def oof(F, y, folds, fit):
    """Out-of-fold логиты: fit(F_train, y_train) → модель-словарь для sc.logit."""
    o = np.zeros(len(y))
    models = []
    for k in np.unique(folds):
        tr, va = folds != k, folds == k
        m = fit(F[tr], y[tr])
        o[va] = sc.logit(m, F[va])
        models.append(m)
    return o, models


def gate_l2a(F, y, behav=sc.BEHAV):
    """Входная проверка ровно по разделу 4 L2-A: D = 7, ЛР со стандартизацией (C = 1, seed 42),
    (А) статика, (Б) статика + поведение behav; 5-кратная стратифицированная CV, OOF; бутстрэп 1000."""
    folds = strat_folds(y)
    oA, _ = oof(F, y, folds, lambda f, t: fit_lr(f, t, []))
    oB, _ = oof(F, y, folds, lambda f, t: fit_lr(f, t, list(behav)))
    ev = evaluate(y, {'A': oA, 'B': oB}, np.arange(len(y)), pairs=[('B', 'A')], full=False)
    res = dict(population=int(len(y)), positives=int(y.sum()), auc_A=ev['A']['auc'], auc_B=ev['B']['auc'],
               auc_B_ci=ev['B']['auc_ci'], diff=ev['B − A']['diff_auc'], diff_ci=ev['B − A']['diff_auc_ci'])
    res['applicable'] = res['positives'] >= 100
    res['passed'] = bool(res['applicable'] and res['auc_B'] >= 0.65 and res['diff_ci'][0] > 0)
    res['outcome'] = 'пройдена' if res['passed'] else ('не пройдена' if res['applicable'] else 'данных недостаточно')
    return res


# ---------------------------------------------------------------------------- важность
def permuted_logits(model, F, groups, n_perm, seed=SEED):
    """Логиты модели при перестановке строк каждой группы признаков (сырые колонки F)."""
    rng = np.random.default_rng(seed)
    out = {}
    for name, cols in groups.items():
        ss = []
        for _ in range(n_perm):
            Fp = F.copy()
            p = rng.permutation(len(F))
            for c in cols:
                Fp[c] = F[c].to_numpy()[p]
            ss.append(sc.logit(model, Fp))
        out[name] = ss
    return out


def perm_importance(model, F, y, users, groups, n_perm, with_ci=True):
    """Падение ROC AUC при перестановке; 95 % ДИ — бутстрэп по пользователям поверх перестановок."""
    y = np.asarray(y, float)
    s = sc.logit(model, F)
    perm = permuted_logits(model, F, groups, n_perm)
    one = np.ones((1, len(y)))
    base = auc_w(y, s, one)[0]
    res = {g: {'drop': float(base - np.mean([auc_w(y, sp, one)[0] for sp in ss]))} for g, ss in perm.items()}
    if with_ci:
        acc = {g: [] for g in perm}
        for W in boot_chunks(users):
            a = auc_w(y, s, W)
            for g, ss in perm.items():
                acc[g].append(a - np.mean([auc_w(y, sp, W) for sp in ss], axis=0))
        for g in perm:
            res[g]['ci'] = ci(np.concatenate(acc[g]))
            res[g]['zero_in_ci'] = bool(res[g]['ci'][0] <= 0 <= res[g]['ci'][1])
    return res


def ranks(imp):
    order = sorted(imp, key=lambda g: -imp[g]['drop'])
    return {g: i + 1 for i, g in enumerate(order)}


def stability(F, y, folds, fit, groups, segments, ref_imp, n_perm=5):
    """Ранги важности на OOF: в каждом фолде dev и в сегментах dev (модель фолда, перестановка
    в его валидационной части); пересечение топ-5 и ранговая корреляция Спирмена с holdout."""
    y = np.asarray(y, float)
    o = np.zeros(len(y))
    perm = {g: [np.zeros(len(y)) for _ in range(n_perm)] for g in groups}
    for k in np.unique(folds):
        tr, va = folds != k, folds == k
        m = fit(F[tr], y[tr])
        o[va] = sc.logit(m, F[va])
        pl = permuted_logits(m, F[va].reset_index(drop=True), groups, n_perm, seed=SEED + int(k))
        for g in groups:
            for p in range(n_perm):
                perm[g][p][va] = pl[g][p]
    subsets = {f'fold{int(k)}': folds == k for k in np.unique(folds)}
    subsets.update(segments)
    ref_rank = ranks(ref_imp)
    top_ref = {g for g, r in ref_rank.items() if r <= 5}
    one = None
    out = {}
    for name, mask in subsets.items():
        yy = y[mask]
        one = np.ones((1, int(mask.sum())))
        a = auc_w(yy, o[mask], one)[0]
        imp = {g: {'drop': float(a - np.mean([auc_w(yy, sp[mask], one)[0] for sp in perm[g]]))} for g in groups}
        r = ranks(imp)
        rr = np.array([ref_rank[g] for g in groups]), np.array([r[g] for g in groups])
        out[name] = dict(n=int(mask.sum()), ranks=r, top5_overlap=len(top_ref & {g for g, v in r.items() if v <= 5}),
                         spearman=float(pd.Series(rr[0]).corr(pd.Series(rr[1]), method='spearman')))
    return out


def correlated_groups(F, cols, thr=0.8):
    """Связные компоненты графа |Спирмен| >= thr на dev (порог задан до расчёта)."""
    R = F[cols].rank().corr().abs().to_numpy()
    seen, comps = set(), []
    for i in range(len(cols)):
        if i in seen:
            continue
        stack, comp = [i], set()
        while stack:
            j = stack.pop()
            if j in comp:
                continue
            comp.add(j)
            stack.extend(k for k in range(len(cols)) if k != j and R[j, k] >= thr and k not in comp)
        seen |= comp
        if len(comp) > 1:
            comps.append(sorted(cols[j] for j in comp))
    return comps


def direction(model):
    """Знак коэффициента стандартизованной ЛР: + — выше значение, выше риск."""
    names = sc.column_names(model['spec'])
    return {n: float(c) for n, c in zip(names, model['coef'])}


def single_feature_auc(F, y, cols):
    one = np.ones((1, len(y)))
    out = {}
    for c in cols:
        v = F[c].to_numpy(float)
        a = float(auc_w(np.asarray(y, float), v, one)[0]) if v.std() > 0 else 0.5
        out[c] = max(a, 1 - a)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------- проверки данных
def quality(df, U):
    """Качество данных на dev: целостность, события до signup и после cancel, сбор по месяцам,
    план и суммы списаний, предвестники у ушедших и у оставшихся."""
    x = df.merge(U, left_on='user_id', right_index=True)
    churned = x['cancel'].notna()
    q = dict(rows=int(len(df)), users=int(len(U)),
             signups_per_user=sorted(df[df['event'] == 'signup'].groupby('user_id').size().unique().tolist()),
             cancels_per_user_max=int(df[df['event'] == 'cancel'].groupby('user_id').size().max()),
             full_duplicates=int(df.duplicated(['ts', 'user_id', 'event', 'value']).sum()),
             sorted_by_ts=bool(df['ts'].is_monotonic_increasing),
             static_constant=bool((df.groupby('user_id')[sc.STATIC].nunique() == 1).all().all()))
    before = x[x['t'] < x['signup']]
    q['events_before_signup'] = before['event'].value_counts().to_dict()
    q['events_after_cancel_except_exit_survey'] = int(((x['t'] > x['cancel']) & (x['event'] != 'exit_survey')).sum())
    month = pd.to_datetime(x['ts'].str[:7]).dt.month
    ss = x[x['event'] == 'session_start']
    per_user = ss.groupby(month[ss.index]).size() / x.groupby(month)['user_id'].nunique()
    q['sessions_per_active_user_by_month'] = [round(float(v), 2) for v in per_user.to_numpy()]
    pay = x[x['event'].isin(['payment', 'payment_failed'])]
    exp = np.where(pay['plan'] == 'pro', '24.99', '9.99')
    q['charge_amount_matches_plan_column'] = float((pay['value'] == exp).mean())
    shares = {}
    for e in ['payment_failed', 'plan_downgrade', 'support_ticket']:
        base = U.index if e != 'plan_downgrade' else df.loc[df['plan'] == 'pro', 'user_id'].unique()
        has = set(df.loc[df['event'] == e, 'user_id'])
        ch = U.loc[U.index.isin(base), 'cancel'].notna()
        shares[e] = dict(base='pro' if e == 'plan_downgrade' else 'все',
                         churned_with=int(sum(u in has for u in ch.index[ch])), churned=int(ch.sum()),
                         retained_with=int(sum(u in has for u in ch.index[~ch])), retained=int((~ch).sum()))
        s = shares[e]
        s['p_cancel_given_event'] = s['churned_with'] / max(1, s['churned_with'] + s['retained_with'])
    q['precursors'] = shares
    # недостающие списания у оставшихся: списания раз в 30 суток с 30-го дня до конца выгрузки
    ret = U[U['cancel'].isna()]
    expected = np.floor((DATA_END - ret['signup']) / (30 * DAY)).astype(int)
    got = df[df['event'] == 'payment'].groupby('user_id').size().reindex(ret.index).fillna(0)
    q['retained_with_missing_payments'] = int((got < expected).sum())
    q['churned_in_data'] = int(churned.groupby(x['user_id']).first().sum())
    return q


def truncation_check(df, P, mode):
    """Признаки из событий, обрезанных по asof, совпадают с признаками из полного файла.
    mode='user' — у каждого пользователя один asof; mode='date' — срезы по датам."""
    E = sc.Events(df)
    full = features(E, P)
    num = [c for c in full.columns if c not in sc.STATIC]
    diffs, static_ok = [], True
    if mode == 'user':
        groups = [(df.merge(P[['user_id', 'asof']], on='user_id').query('t <= asof'), P)]
    else:
        groups = [(df[df['t'] <= a], P[P['asof'] == a]) for a in np.unique(P['asof'])]
    for d, pp in groups:
        cut = features(sc.Events(d.drop(columns=[c for c in ('asof',) if c in d.columns])), pp)
        ref = full.loc[pp.index].reset_index(drop=True)
        diffs.append(float(np.abs(cut[num].to_numpy() - ref[num].to_numpy()).max()))
        static_ok &= bool((cut[sc.STATIC].to_numpy() == ref[sc.STATIC].to_numpy()).all())
    return dict(points=int(len(P)), runs=len(groups), max_abs_diff=max(diffs), static_equal=static_ok)


# ---------------------------------------------------------------------------- вывод
def save_json(obj, path):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=False, default=float)
        fh.write('\n')


def model_json(model, name, definition, trained_on):
    return dict(format='logistic-regression-v1', name=name, definition=definition, trained_on=trained_on,
                features=sc.column_names(model['spec']), spec=model['spec'], coef=model['coef'],
                intercept=model['intercept'], C=model['C'])


def f3(v):
    return f'{v:.3f}'


def fci(c):
    return f'[{c[0]:.3f}; {c[1]:.3f}]'

# ---------------------------------------------------------------------------- этапы
LR_GRID = [(C, lg) for C in (0.01, 0.1, 1.0) for lg in (False, True)]
HGB_GRID = [dict(learning_rate=0.05, max_iter=200, max_leaf_nodes=15, min_samples_leaf=40),
            dict(learning_rate=0.05, max_iter=200, max_leaf_nodes=31, min_samples_leaf=20),
            dict(learning_rate=0.1, max_iter=100, max_leaf_nodes=15, min_samples_leaf=40),
            dict(learning_rate=0.03, max_iter=300, max_leaf_nodes=7, min_samples_leaf=80)]
TIE = 0.005  # при разнице CV AUC не больше этой берётся ЛР: проще, сохраняется в JSON
LOG1P_BEHAV = [c for c in sc.BEHAV if c not in ('sess_value_mean', 'sess_value_max', 'had_downgrade')]
LOG1P_HIST = [c for c in sc.HIST if c not in ('unrecovered_failure', 'had_downgrade')]
SNAP_TRAIN = pd.date_range('2025-02-01', '2025-12-01', freq='7D')  # asof + 30 суток не позже 31.12
SNAP_H = 30


def _hgb_oof(F, y, folds, params):
    from sklearn.ensemble import HistGradientBoostingClassifier
    X = sc.design_matrix(F, make_spec(F, sc.BEHAV))
    o = np.zeros(len(y))
    for k in np.unique(folds):
        tr, va = folds != k, folds == k
        m = HistGradientBoostingClassifier(early_stopping=False, l2_regularization=1.0, random_state=SEED, **params)
        o[va] = m.fit(X[tr], y[tr]).predict_proba(X[va])[:, 1]
    return o


def _auc(y, s):
    return float(auc_w(np.asarray(y, float), s, np.ones((1, len(y))))[0])


def _importance_groups(F, numeric):
    groups = {c: [c] for c in numeric if F[c].std() > 0}
    groups.update({c: [c] for c in sc.STATIC})
    corr = correlated_groups(F, [c for c in numeric if F[c].std() > 0])
    for comp in corr:
        groups['группа: ' + ' + '.join(comp)] = comp
    return groups, corr


def stage_d14(out, df, E, U, dev_u, ho, holdout=True, D=14, H=60):
    """Базовая ветка (этап 2 L2-A): D = 14; ЛР и HGB, выбор по 5-кратной CV на dev; три бейзлайна;
    одна оценка на holdout; важность с ДИ, группами, направлением и устойчивостью; проверки раздела 6."""
    is_dev = df['user_id'].isin(dev_u)
    Pd = d_points(U.loc[dev_u], D, H)
    Fd, yd = features(E, Pd), Pd['y'].to_numpy()
    folds = strat_folds(yd)
    grid = {}
    for C, lg in LR_GRID:
        o, _ = oof(Fd, yd, folds, lambda f, t, C=C, lg=lg: fit_lr(f, t, sc.BEHAV, LOG1P_BEHAV if lg else (), C))
        grid[f'LR C={C} log1p={lg}'] = _auc(yd, o)
    for i, p in enumerate(HGB_GRID):
        grid[f'HGB {i}: ' + ', '.join(f'{k}={v}' for k, v in p.items())] = _auc(yd, _hgb_oof(Fd, yd, folds, p))
    best_lr = max((k for k in grid if k.startswith('LR')), key=grid.get)
    best = max(grid, key=grid.get)
    if best.startswith('HGB') and grid[best] - grid[best_lr] > TIE:
        sys.exit(f'по CV лучше HGB ({best}: {grid[best]:.4f} против {grid[best_lr]:.4f}) — '
                 'нужна выгрузка деревьев, в эталоне её нет')
    C = float(best_lr.split('C=')[1].split()[0])
    lg = best_lr.endswith('True')

    def fit(f, t):
        return fit_lr(f, t, sc.BEHAV, LOG1P_BEHAV if lg else (), C)

    out['stage2_cv'] = dict(grid=grid, chosen=best_lr, population=int(len(yd)), positives=int(yd.sum()))
    print(f'D={D} CV на dev: выбрана {best_lr} (OOF AUC {grid[best_lr]:.4f}); лучшая HGB '
          f"{max(v for k, v in grid.items() if k.startswith('HGB')):.4f}")
    # раздел 6: опровержение на перемешанных метках, одиночные AUC, обрезка по T
    rng = np.random.default_rng(SEED)
    ys = rng.permutation(yd)
    o_shuf, _ = oof(Fd, ys, strat_folds(ys), fit)
    P7 = d_points(U.loc[dev_u], 7, H)
    g_shuf = gate_l2a(features(E, P7), rng.permutation(P7['y'].to_numpy()))
    ev_s = evaluate(ys, {'shuf': o_shuf}, np.arange(len(ys)), full=False)['shuf']
    out['refute'] = dict(stage2_shuffled_oof_auc=ev_s['auc'], ci=ev_s['auc_ci'],
                         gate_shuffled_auc_B=g_shuf['auc_B'], gate_shuffled_ci=g_shuf['auc_B_ci'])
    out[f'single_feature_auc_dev_D{D}'] = single_feature_auc(Fd, yd, sc.BEHAV)
    out[f'truncation_dev_D{D}'] = truncation_check(df[is_dev], Pd, 'user')
    if not holdout:
        return None
    model = fit(Fd, yd)
    stat = fit_lr(Fd, yd, [])
    Ph = d_points(U.loc[sorted(ho)], D, H)
    Fh, yh = features(E, Ph), Ph['y'].to_numpy()
    assert not set(Pd['user_id']) & set(Ph['user_id'])
    name = f'модель D={D}'
    scores = {name: sc.logit(model, Fh), 'ЛР на статике': sc.logit(stat, Fh),
              'правило −n_sessions': -Fh['n_sessions'].to_numpy(), 'базовый уровень': np.zeros(len(yh))}
    out['holdout'] = evaluate(yh, scores, np.arange(len(yh)),
                              pairs=[(name, 'ЛР на статике'), (name, 'правило −n_sessions')])
    out['holdout']['population'], out['holdout']['positives'] = int(len(yh)), int(yh.sum())
    out[f'truncation_holdout_D{D}'] = truncation_check(df[~is_dev], Ph, 'user')
    out['holdout_ids_in_training'] = int(Pd['user_id'].isin(ho).sum())
    groups, corr = _importance_groups(Fd, sc.BEHAV)
    imp = perm_importance(model, Fh, yh, np.arange(len(yh)), groups, n_perm=30)
    single = {k: v for k, v in imp.items() if not k.startswith('группа')}
    seg = {'plan=basic': (Fd['plan'] == 'basic').to_numpy(), 'plan=pro': (Fd['plan'] == 'pro').to_numpy()}
    q = ((U.loc[Pd['user_id'], 'signup'].to_numpy() // DAY) // 91).clip(0, 2)
    seg.update({f'Q{i + 1} регистрации': q == i for i in range(3)})
    out['importance'] = dict(holdout=imp, correlated_groups=corr, coef=direction(model),
                             constant_at_T=[c for c in sc.BEHAV if Fd[c].std() == 0],
                             stability=stability(Fd, yd, folds, fit, {k: groups[k] for k in single}, seg, single))
    return model


def stage_snapshots(out, key, df, E, U, dev_u, ho, numeric, holdout=True, compare=None, n_perm=10):
    """Модель на срезах по датам: срез каждые 7 суток 2025-02-01…2025-12-01, активные на дату,
    метка — cancel в ближайшие 30 суток, признаки — история до даты. ЛР, C по CV на dev
    (фолды по пользователям); одна оценка на holdout с ДИ по пользователям; важность; проверки."""
    Pd = snapshot_points(U.loc[dev_u], SNAP_TRAIN, SNAP_H)
    Fd, yd, ud = features(E, Pd), Pd['y'].to_numpy(), Pd['user_id'].to_numpy()
    folds = user_folds(ud)
    lg = [c for c in LOG1P_HIST if c in numeric]
    grid = {}
    for C in (0.01, 0.1, 1.0):
        o, _ = oof(Fd, yd, folds, lambda f, t, C=C: fit_lr(f, t, numeric, lg, C))
        grid[f'LR C={C}'] = _auc(yd, o)
    best = max(grid, key=grid.get)
    C = float(best.split('C=')[1])

    def fit(f, t):
        return fit_lr(f, t, numeric, lg, C)

    rng = np.random.default_rng(SEED)
    ys = rng.permutation(yd)
    o_shuf, _ = oof(Fd, ys, folds, fit)
    ev_s = evaluate(ys, {'shuf': o_shuf}, ud, full=False)['shuf']
    r = out[key] = dict(numeric=list(numeric), cv=grid, chosen=best, rows=int(len(yd)),
                        users=int(len(np.unique(ud))), positives=int(yd.sum()),
                        refute=dict(shuffled_oof_auc=ev_s['auc'], ci=ev_s['auc_ci']),
                        single_feature_auc_dev=single_feature_auc(Fd, yd, numeric))
    print(f"{key}: срезы dev {r['rows']} строк ({r['users']} польз.), положительных {r['positives']}; "
          f"выбрана {best} (OOF AUC {grid[best]:.4f})")
    if not holdout:
        return None
    model = fit(Fd, yd)
    stat = fit_lr(Fd, yd, [])
    hu = sorted(ho)
    Ph = snapshot_points(U.loc[hu], SNAP_TRAIN, SNAP_H)
    Fh, yh, uh = features(E, Ph), Ph['y'].to_numpy(), Ph['user_id'].to_numpy()
    assert not set(ud) & set(uh)
    scores = {'модель на срезах': sc.logit(model, Fh), 'ЛР на статике': sc.logit(stat, Fh),
              'правило: дней с последней сессии': Fh['days_since_last_session'].to_numpy(),
              'базовый уровень': np.zeros(len(yh))}
    for name, m in (compare or {}).items():
        scores[name] = sc.logit(m, Fh)
    pairs = [('модель на срезах', n) for n in scores if n not in ('модель на срезах', 'базовый уровень')]
    r['holdout'] = evaluate(yh, scores, uh, pairs)
    r['holdout'].update(rows=int(len(yh)), users=int(len(hu)), positives=int(yh.sum()))
    r['truncation_holdout'] = truncation_check(df[df['user_id'].isin(hu)], Ph, 'date')
    r['holdout_ids_in_training'] = int(np.isin(ud, hu).sum())
    groups, corr = _importance_groups(Fd, numeric)
    imp = perm_importance(model, Fh, yh, uh, groups, n_perm=n_perm)
    single = {k: v for k, v in imp.items() if not k.startswith('группа')}
    seg = {'plan=basic': (Fd['plan'] == 'basic').to_numpy(), 'plan=pro': (Fd['plan'] == 'pro').to_numpy()}
    r['importance'] = dict(holdout=imp, correlated_groups=corr, coef=direction(model),
                           stability=stability(Fd, yd, folds, fit, {k: groups[k] for k in single}, seg, single,
                                               n_perm=3))
    return model


def print_metrics(h, names):
    print('| | ROC AUC | PR AUC | доля уходящих в топ-20 % | лифт |\n|---|---|---|---|---|')
    for n in names:
        r = h[n]
        print(f"| {n} | {f3(r['auc'])} {fci(r['auc_ci'])} | {f3(r['ap'])} {fci(r['ap_ci'])} | "
              f"{f3(r['top20'])} {fci(r['top20_ci'])} | {r['lift']:.2f} [{r['lift_ci'][0]:.2f}; {r['lift_ci'][1]:.2f}] |")
    for k in h:
        if ' − ' in k:
            print(f"{k}: {h[k]['diff_auc']:+.3f} {fci(h[k]['diff_auc_ci'])}")


def print_importance(imp):
    st = imp['stability']
    print('\n| ранг | признак | падение ROC AUC [95% ДИ] | знак коэф. | ранг в срезах dev |\n|---|---|---|---|---|')
    single = {k: v for k, v in imp['holdout'].items() if not k.startswith('группа')}
    for i, (k, v) in enumerate(sorted(single.items(), key=lambda kv: -kv[1]['drop']), 1):
        coef = imp['coef'].get(k)
        sgn = '—' if coef is None else ('+' if coef > 0 else '−')
        rr = [s['ranks'].get(k) for s in st.values()]
        print(f"| {i} | {k}{' (ДИ включает 0)' if v['zero_in_ci'] else ''} | {v['drop']:.4f} {fci(v['ci'])} | {sgn} | "
              f'{min(rr)}–{max(rr)} |')
    for k, v in imp['holdout'].items():
        if k.startswith('группа'):
            print(f"{k}: {v['drop']:.4f} {fci(v['ci'])}")
    print('устойчивость, пересечение топ-5 с holdout: ' + ', '.join(f"{k} {v['top5_overlap']}" for k, v in st.items()))


def main(argv=None):
    """python -I ref_lib.py seal <profile> <holdout_ids.txt> [--workdir DIR] — первое действие эталона."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['seal'])
    ap.add_argument('profile', choices=sorted(DATA))
    ap.add_argument('out')
    ap.add_argument('--workdir', help='куда сгенерировать CSV (по умолчанию временный каталог)')
    a = ap.parse_args(argv)
    import tempfile
    tmp = None if a.workdir else tempfile.TemporaryDirectory(prefix='ref-seal-')
    path, digest = generate(a.profile, a.workdir or tmp.name)
    ho, h, n = seal_holdout(path, a.out)
    print(f'данные {a.profile}: sha256 {digest}; holdout {len(ho)} из {n} пользователей, '
          f'sha256 {os.path.basename(a.out)} = {h}')


if __name__ == '__main__':
    main()
