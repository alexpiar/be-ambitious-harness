# Калибровка профиля t2pass генератора gen_events.py: входная проверка по определению
# L2-A на нескольких seed, альтернативные определения оттока, запас для более сильной
# модели на скрытых пользователях, проверки целостности и утечек.
#
# Зависимости: Python >= 3.10, numpy, pandas, scikit-learn
# (проверено: Python 3.10.12, numpy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2).
# Сам генератор — только стандартная библиотека; скрипт запускает его тем же интерпретатором.
#
# Запуск (по умолчанию около 4 минут, пик памяти около 330 МБ). CSV пишутся в --workdir и после работы
# удаляются, если не указан --keep; итог — calibration_t2pass.json там же и таблицы в stdout:
#   OMP_NUM_THREADS=2 python -I calibrate_t2pass.py --workdir <каталог>
#   OMP_NUM_THREADS=2 python -I calibrate_t2pass.py --workdir <каталог> --seeds 2026 2027 2028 101 102
# Первый seed в --seeds — канонические данные: на них обучаются модели для скрытых пользователей.
#
# Определения (как у исполнителя L2-A 21.10, evals/runs/2026-10-21-gate/L2-A/prompt-to-worker.md, разделы 4–5):
#   T = ts(signup) + D суток; популяция — без cancel с ts <= T; метка — cancel в (T, T + H суток];
#   признаки — только события с ts(signup) <= ts <= T, кроме cancel и exit_survey.
import argparse
import json
import os
import subprocess
import sys
import time

os.environ.setdefault('OMP_NUM_THREADS', '2')

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, 'gen_events.py')
SEED = 42
N_BOOT = 1000
DATA_END = pd.Timestamp('2025-12-31 23:59:59')
DAY = pd.Timedelta(days=1)
STATIC = ['plan', 'device', 'country', 'channel']
NEVER_FEATURE = {'cancel', 'exit_survey'}
KINDS = ['export', 'tags', 'search', 'share']
# поведенческие признаки входной проверки L2-A (раздел 5 промпта)
BEHAV = ['n_sessions', 'sess_value_sum', 'sess_value_mean', 'sess_value_max', 'active_days',
         'n_feature_used', 'n_fu_export', 'n_fu_tags', 'n_fu_search', 'n_fu_share',
         'n_payment', 'n_payment_failed', 'n_support_ticket', 'had_downgrade',
         'days_since_last_event', 'days_to_first_session']
# дополнительные признаки «по смыслу» на тот же момент T и из тех же событий
EXTRA = ['n_kinds', 'active_days_last3', 'sessions_last3', 'events_last7']
# срезы по датам (как у одиночного скилла 21.10): история пользователя до даты среза
SNAP_DATES = pd.date_range('2025-06-01', '2025-11-30', freq='14D')
SNAP_H = 30
RECENT = ['tenure_days', 'n_sessions_total', 'sessions_per_week', 'sessions_last7', 'sessions_last28',
          'active_days_last28', 'days_since_last_session', 'n_payment', 'n_payment_failed_last30',
          'unrecovered_failure', 'n_support_ticket_last30', 'had_downgrade']


# ---------------------------------------------------------------------------
# Данные
# ---------------------------------------------------------------------------
def generate(path, seed, n_users, profile='t2pass'):
    r = subprocess.run([sys.executable, '-I', GEN, path, str(seed), str(n_users), '--profile', profile],
                       check=True, capture_output=True, text=True)
    return r.stdout.strip()


def load_events(path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[''])
    df['ts'] = pd.to_datetime(df['ts'], format='%Y-%m-%dT%H:%M:%S')
    return df


def signup_ts(df):
    return df[df['event'] == 'signup'].groupby('user_id')['ts'].min()


def cancel_ts(df):
    return df[df['event'] == 'cancel'].groupby('user_id')['ts'].min()


# ---------------------------------------------------------------------------
# Признаки и метки
# ---------------------------------------------------------------------------
def build_features(df, D):
    su = signup_ts(df)
    T = su + D * DAY
    attrs = df.groupby('user_id')[STATIC].first()
    x = df.merge(T.rename('T'), left_on='user_id', right_index=True).merge(
        su.rename('signup_ts'), left_on='user_id', right_index=True)
    canc_before = x.loc[(x['event'] == 'cancel') & (x['ts'] <= x['T']), 'user_id'].unique()
    w = x[(x['ts'] >= x['signup_ts']) & (x['ts'] <= x['T']) & ~x['event'].isin(NEVER_FEATURE)].copy()
    w['dd'] = (w['ts'] - w['signup_ts']) / DAY
    w['date'] = w['ts'].dt.normalize()
    out = attrs.copy()
    ss = w[w['event'] == 'session_start'].copy()
    ss['v'] = ss['value'].astype(float)
    g = ss.groupby('user_id')['v']
    out['n_sessions'] = g.size()
    out['sess_value_sum'] = g.sum()
    out['sess_value_mean'] = g.mean()
    out['sess_value_max'] = g.max()
    out['active_days'] = w.groupby('user_id')['date'].nunique()
    fu = w[w['event'] == 'feature_used']
    out['n_feature_used'] = fu.groupby('user_id').size()
    for k in KINDS:
        out[f'n_fu_{k}'] = fu[fu['value'] == k].groupby('user_id').size()
    for name, e in [('n_payment', 'payment'), ('n_payment_failed', 'payment_failed'),
                    ('n_support_ticket', 'support_ticket')]:
        out[name] = w[w['event'] == e].groupby('user_id').size()
    out['had_downgrade'] = (w[w['event'] == 'plan_downgrade'].groupby('user_id').size() > 0).astype(float)
    out['days_since_last_event'] = (T - w.groupby('user_id')['ts'].max()) / DAY
    out['days_to_first_session'] = (ss.groupby('user_id')['ts'].min() - su) / DAY
    out['n_kinds'] = fu.groupby('user_id')['value'].nunique()
    last3 = w[w['dd'] > D - 3]
    out['active_days_last3'] = last3.groupby('user_id')['date'].nunique()
    out['sessions_last3'] = last3[last3['event'] == 'session_start'].groupby('user_id').size()
    out['events_last7'] = w[(w['dd'] > D - 7) & (w['event'] != 'signup')].groupby('user_id').size()
    # белый ящик: правило активации генератора (дни жизни 0..6 с сессиями >= 3 и >= 2 видов функций).
    # Исполнителю оно неизвестно; нужно только чтобы оценить потолок модели на 7-й день.
    wk = w[w['dd'] < 7]
    life_days = wk[wk['event'] == 'session_start'].assign(d=lambda t: t['dd'].astype(int)).groupby('user_id')['d'].nunique()
    kinds7 = wk[wk['event'] == 'feature_used'].groupby('user_id')['value'].nunique()
    out['wb_activated'] = ((life_days.reindex(out.index).fillna(0) >= 3)
                           & (kinds7.reindex(out.index).fillna(0) >= 2)).astype(float)
    fill0 = [c for c in BEHAV + EXTRA if c not in ('days_since_last_event', 'days_to_first_session')]
    out[fill0] = out[fill0].fillna(0.0)
    out['days_to_first_session'] = out['days_to_first_session'].fillna(float(D))
    out[BEHAV + EXTRA] = out[BEHAV + EXTRA].astype(float)
    out['signup_ts'] = su
    return out[~out.index.isin(canc_before)].sort_index()


def build_label(df, F, D, H):
    """H — горизонт в сутках или None: «отмена когда-либо после T в выгрузке»."""
    T = F['signup_ts'] + D * DAY
    can = cancel_ts(df).reindex(F.index)
    end = T + H * DAY if H is not None else DATA_END
    return ((can > T) & (can <= end)).astype(int).to_numpy()


def build_snapshots(df, F7):
    """Срезы по датам A: пользователи с завершённой первой неделей (signup <= A − 7 сут) и без cancel до A;
    признаки — история до A; метка — cancel в (A, A + SNAP_H суток]. F7 — признаки первой недели."""
    su, can = signup_ts(df), cancel_ts(df)
    ev = df[~df['event'].isin(NEVER_FEATURE)]
    attrs = df.groupby('user_id')[STATIC].first()
    parts = []
    for A in SNAP_DATES:
        c = can.reindex(su.index)
        users = su.index[(su <= A - 7 * DAY).to_numpy() & ~(c <= A).to_numpy()]
        e = ev[(ev['ts'] <= A) & ev['user_id'].isin(users)]
        s = e[e['event'] == 'session_start']
        o = pd.DataFrame(index=pd.Index(users, name='user_id'))
        o['tenure_days'] = (A - su.reindex(users)) / DAY
        o['n_sessions_total'] = s.groupby('user_id').size()
        o['sessions_last7'] = s[s['ts'] > A - 7 * DAY].groupby('user_id').size()
        o['sessions_last28'] = s[s['ts'] > A - 28 * DAY].groupby('user_id').size()
        r28 = e[e['ts'] > A - 28 * DAY]
        o['active_days_last28'] = r28.assign(d=r28['ts'].dt.normalize()).groupby('user_id')['d'].nunique()
        o['days_since_last_session'] = (A - s.groupby('user_id')['ts'].max()) / DAY
        o['n_payment'] = e[e['event'] == 'payment'].groupby('user_id').size()
        pf = e[e['event'] == 'payment_failed']
        o['n_payment_failed_last30'] = pf[pf['ts'] > A - 30 * DAY].groupby('user_id').size()
        bill = e[e['event'].isin(['payment', 'payment_failed'])].sort_values('ts')
        o['unrecovered_failure'] = (bill.groupby('user_id')['event'].last() == 'payment_failed').astype(float)
        st = e[e['event'] == 'support_ticket']
        o['n_support_ticket_last30'] = st[st['ts'] > A - 30 * DAY].groupby('user_id').size()
        o['had_downgrade'] = (e[e['event'] == 'plan_downgrade'].groupby('user_id').size() > 0).astype(float)
        o = o.fillna({k: 0.0 for k in o.columns if k not in ('tenure_days', 'days_since_last_session')})
        o['days_since_last_session'] = o['days_since_last_session'].fillna(o['tenure_days'])
        o['sessions_per_week'] = o['n_sessions_total'] / o['tenure_days'] * 7
        o = o.join(attrs).join(F7[BEHAV].add_prefix('w1_'))
        cu = can.reindex(users)
        o['y'] = ((cu > A) & (cu <= A + SNAP_H * DAY)).astype(int).to_numpy()
        o['asof'] = A
        parts.append(o.reset_index())
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------------------
# Модели и метрики
# ---------------------------------------------------------------------------
def make_lr(num, cat=STATIC, log1p=False):
    steps = [('log1p', FunctionTransformer(np.log1p))] if log1p else []
    steps.append(('sc', StandardScaler()))
    tr = [('cat', Pipeline([('oh', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
                            ('sc', StandardScaler())]), cat)]
    if num:
        tr.insert(0, ('num', Pipeline(steps), num))
    return Pipeline([('pre', ColumnTransformer(tr)),
                     ('clf', LogisticRegression(C=1.0, max_iter=5000, random_state=SEED))])


def make_hgb(num, cat=STATIC):
    # конфигурация зафиксирована до прогона, без подбора
    tr = [('num', 'passthrough', num), ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cat)]
    return Pipeline([('pre', ColumnTransformer(tr)),
                     ('clf', HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
                                                            min_samples_leaf=40, l2_regularization=1.0,
                                                            early_stopping=False, random_state=SEED))])


BASELINE = 'LR · gate features (baseline)'
MODELS = {
    BASELINE: lambda: make_lr(BEHAV),
    'LR · static only': lambda: make_lr([]),
    'HGB · gate features': lambda: make_hgb(BEHAV),
    'LR · gate + extra, log1p': lambda: make_lr(BEHAV + EXTRA, log1p=True),
    'HGB · gate + extra': lambda: make_hgb(BEHAV + EXTRA),
    'white box: LR · gate + extra + activation rule of the generator': lambda: make_lr(BEHAV + EXTRA + ['wb_activated'],
                                                                                    log1p=True),
}
W1 = ['w1_' + c for c in BEHAV]
SNAP_BASELINE = 'LR · first-week features only'
SNAP_MODELS = {
    SNAP_BASELINE: lambda: make_lr(W1),
    'LR · history to as-of date': lambda: make_lr(RECENT),
    'HGB · history to as-of date': lambda: make_hgb(RECENT),
    'HGB · history + first week': lambda: make_hgb(RECENT + W1),
}


def boot_ci(y, s, base=None, groups=None, n=N_BOOT, seed=SEED):
    """95% бутстрэп-ДИ ROC AUC (или разности AUC(s) − AUC(base)); повторы по пользователям (groups)."""
    rng = np.random.default_rng(seed)
    if groups is not None:
        uniq, inv = np.unique(groups, return_inverse=True)
        rows = np.split(np.argsort(inv, kind='stable'), np.cumsum(np.bincount(inv))[:-1])
    vals = []
    for _ in range(n):
        if groups is None:
            i = rng.integers(0, len(y), len(y))
        else:
            i = np.concatenate([rows[k] for k in rng.integers(0, len(uniq), len(uniq))])
        if y[i].min() == y[i].max():
            continue
        a = roc_auc_score(y[i], s[i])
        if base is not None:
            a -= roc_auc_score(y[i], base[i])
        vals.append(a)
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def holdout_split(F):
    """Как в L2-A: 20 % пользователей, страта — месяц регистрации, seed 42."""
    users = F.index.to_numpy()
    _, ho = train_test_split(users, test_size=0.2, stratify=F['signup_ts'].dt.month.to_numpy(), random_state=SEED)
    return ~np.isin(users, ho), np.isin(users, ho)


def holdout_auc(F, y, make):
    dev, ho = holdout_split(F)
    s = make().fit(F[dev], y[dev]).predict_proba(F[ho])[:, 1]
    return float(roc_auc_score(y[ho], s)), y[ho], s


def l2a_gate(F, y):
    """Входная проверка ровно как у L2-A: dev (80 %), 5-кратная CV, OOF, бутстрэп 1000 по пользователям."""
    dev, _ = holdout_split(F)
    X, yy = F[dev], y[dev]
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    oof = {}
    for name, make in [('A', lambda: make_lr([])), ('B', lambda: make_lr(BEHAV))]:
        o = np.zeros(len(yy))
        for tr, va in skf.split(X, yy):
            o[va] = make().fit(X.iloc[tr], yy[tr]).predict_proba(X.iloc[va])[:, 1]
        oof[name] = o
    auc_b = float(roc_auc_score(yy, oof['B']))
    diff_ci = boot_ci(yy, oof['B'], base=oof['A'])
    passed = auc_b >= 0.65 and diff_ci[0] > 0 and yy.sum() >= 100
    return dict(n_dev=int(len(yy)), pos_dev=int(yy.sum()), auc_B=auc_b, auc_B_ci=boot_ci(yy, oof['B']),
                diff=auc_b - float(roc_auc_score(yy, oof['A'])), diff_ci=diff_ci,
                outcome='passed' if passed else 'failed')


def single_feature_aucs(X, y, cols):
    res = {}
    for c in cols:
        v = X[c].to_numpy(dtype=float)
        a = roc_auc_score(y, v) if np.nanstd(v) > 0 else 0.5
        res[c] = float(max(a, 1 - a))
    return dict(sorted(res.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------
# Проверки данных
# ---------------------------------------------------------------------------
def integrity(df):
    su, can = signup_ts(df), cancel_ts(df)
    x = df.merge(su.rename('su'), left_on='user_id', right_index=True).merge(
        can.rename('c'), left_on='user_id', right_index=True, how='left')
    dt = (x['ts'] - x['su']).dt.total_seconds()
    es = x[x['event'] == 'exit_survey']
    # послеотменные события в окне признаков популяции: cancel/exit_survey с ts <= T у тех, кто не отменил до T
    in_window = {}
    for D in (7, 14, 30):
        T = x['su'] + D * DAY
        pop = ~(x['c'] <= T)
        in_window[f'D{D}'] = int((pop & x['event'].isin(NEVER_FEATURE) & (x['ts'] <= T)).sum())
    return dict(
        rows=int(len(df)), users=int(df['user_id'].nunique()),
        signups_per_user=sorted(df[df['event'] == 'signup'].groupby('user_id').size().unique().tolist()),
        cancels_per_user_max=int(df[df['event'] == 'cancel'].groupby('user_id').size().max()),
        min_ts_minus_signup_sec=float(dt.min()), events_before_signup=int((dt < 0).sum()),
        events_after_cancel_not_exit_survey=int(((x['ts'] > x['c']) & (x['event'] != 'exit_survey')).sum()),
        exit_survey_without_or_before_cancel=int((es['c'].isna() | (es['ts'] < es['c'])).sum()),
        post_cancel_events_in_feature_window=in_window,
        ts_max=str(df['ts'].max()), events_after_2025=int((df['ts'] > DATA_END).sum()),
        churned_in_data_share=float(len(can) / df['user_id'].nunique()),
        event_counts=df['event'].value_counts().to_dict(),
    )


def event_shares(df):
    """Доля пользователей с хотя бы одним событием: оставшиеся (без cancel в выгрузке) и ушедшие."""
    users = df.groupby('user_id')['plan'].first()
    can_users = cancel_ts(df).index
    churned = users.index.isin(can_users)
    out = {}
    for e, mask in [('payment_failed', np.ones(len(users), bool)), ('plan_downgrade', (users == 'pro').to_numpy()),
                    ('support_ticket', np.ones(len(users), bool))]:
        has = users.index.isin(df.loc[df['event'] == e, 'user_id'].unique())
        ev_ch = df.loc[df['event'] == e, 'user_id'].isin(can_users)
        out[e] = dict(base='pro users' if e == 'plan_downgrade' else 'all users',
                      retained_users=int((mask & ~churned).sum()), retained_with=int((has & mask & ~churned).sum()),
                      churned_users=int((mask & churned).sum()), churned_with=int((has & mask & churned).sum()),
                      events_retained=int((~ev_ch).sum()), events_churned=int(ev_ch.sum()))
    return out


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workdir', required=True)
    ap.add_argument('--seeds', type=int, nargs='+', default=[2026, 2027, 2028])
    ap.add_argument('--n-users', type=int, default=6000)
    ap.add_argument('--hidden-seed', type=int, default=9002)
    ap.add_argument('--hidden-n', type=int, default=2000)
    ap.add_argument('--keep', action='store_true', help='не удалять CSV после работы')
    ap.add_argument('--skip-hidden', action='store_true', help='только seed: без скрытых пользователей и срезов')
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    t0 = time.time()
    rep = {'args': vars(a), 'seeds': {}}
    DEFS = [('D=7, H=60 (L2-A gate)', 7, 60), ('D=7, H=30', 7, 30), ('D=7, any later cancel in 2025', 7, None),
            ('D=3, H=60', 3, 60), ('D=14, H=60', 14, 60)]
    files, canon_snap = [], None
    for seed in a.seeds:
        path = os.path.join(a.workdir, f'events_t2pass_{seed}.csv')
        files.append(path)
        print(f'== seed {seed}: {generate(path, seed, a.n_users)}', flush=True)
        df = load_events(path)
        r = {'integrity': integrity(df), 'shares': event_shares(df)}
        F7 = build_features(df, 7)
        y7 = build_label(df, F7, 7, 60)
        r['l2a_gate'] = l2a_gate(F7, y7)
        r['defs'] = {}
        for name, D, H in DEFS:
            F = F7 if D == 7 else build_features(df, D)
            y = build_label(df, F, D, H)
            auc, yh, sh = holdout_auc(F, y, MODELS[BASELINE])
            r['defs'][name] = dict(population=int(len(F)), positives=int(y.sum()), pos_share=float(y.mean()),
                                   auc=auc, ci=boot_ci(yh, sh))
        if seed == a.seeds[0] and not a.skip_hidden:
            r['single_feature_auc_D7'] = single_feature_aucs(F7, y7, BEHAV + EXTRA)
            F30 = build_features(df, 30)
            r['single_feature_auc_D30'] = single_feature_aucs(F30, build_label(df, F30, 30, 60), BEHAV + EXTRA)
            S = canon_snap = build_snapshots(df, F7)
            r['single_feature_auc_snapshots'] = single_feature_aucs(S, S['y'].to_numpy(), RECENT)
        rep['seeds'][seed] = r
        g = r['l2a_gate']
        print(f"   holdout AUC {r['defs']['D=7, H=60 (L2-A gate)']['auc']:.3f}; L2-A gate OOF {g['auc_B']:.3f} "
              f"→ {g['outcome']}", flush=True)
        del df

    if not a.skip_hidden:
        hidden_part(rep, a, files, canon_snap)
    rep['elapsed_sec'] = round(time.time() - t0, 1)
    with open(os.path.join(a.workdir, 'calibration_t2pass.json'), 'w') as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1, default=str)
    print_tables(rep, a)
    if not a.keep:
        for p in files:
            os.remove(p)


def hidden_part(rep, a, files, canon_snap):
    """Запас: модели обучаются на всех пользователях канонического seed и оцениваются на скрытых."""
    hpath = os.path.join(a.workdir, f'hidden_t2pass_{a.hidden_seed}.csv')
    files.append(hpath)
    print(f'== hidden seed {a.hidden_seed}: {generate(hpath, a.hidden_seed, a.hidden_n)}', flush=True)
    dfh, dfc = load_events(hpath), load_events(files[0])
    rep['hidden'] = {'integrity': integrity(dfh), 'shares': event_shares(dfh), 'models': {}, 'snapshots': {}}
    for D in (7, 14, 30):
        Fc, Fh = build_features(dfc, D), build_features(dfh, D)
        yc, yh = build_label(dfc, Fc, D, 60), build_label(dfh, Fh, D, 60)
        sc = {name: make().fit(Fc, yc).predict_proba(Fh)[:, 1] for name, make in MODELS.items()
              if D == 7 or not name.startswith('white box')}
        for name, s in sc.items():
            rep['hidden']['models'][f'D={D} · {name}'] = dict(
                population=int(len(Fh)), pos_share=float(yh.mean()), auc=float(roc_auc_score(yh, s)),
                ci=boot_ci(yh, s), diff=float(roc_auc_score(yh, s) - roc_auc_score(yh, sc[BASELINE])),
                diff_ci=boot_ci(yh, s, base=sc[BASELINE]) if name != BASELINE else [0.0, 0.0])
    Sc, Sh = canon_snap, build_snapshots(dfh, build_features(dfh, 7))
    yc, yh, grp = Sc['y'].to_numpy(), Sh['y'].to_numpy(), Sh['user_id'].to_numpy()
    sc = {name: make().fit(Sc, yc).predict_proba(Sh)[:, 1] for name, make in SNAP_MODELS.items()}
    for name, s in sc.items():
        rep['hidden']['snapshots'][name] = dict(
            rows=int(len(Sh)), users=int(len(np.unique(grp))), pos_share=float(yh.mean()),
            auc=float(roc_auc_score(yh, s)), ci=boot_ci(yh, s, groups=grp),
            diff=float(roc_auc_score(yh, s) - roc_auc_score(yh, sc[SNAP_BASELINE])),
            diff_ci=boot_ci(yh, s, base=sc[SNAP_BASELINE], groups=grp) if name != SNAP_BASELINE else [0.0, 0.0])


def f3(v):
    return f'{v:.3f}'


def ci(c):
    return f'[{c[0]:.3f}; {c[1]:.3f}]'


def print_seed_tables(rep, a):
    seeds = rep['seeds']
    print('\n### Gate D=7, H=60, LR on gate features')
    print('| seed | population | positives (share) | holdout 20% ROC AUC [95% CI] | L2-A gate: OOF AUC(B) on dev '
          '[95% CI] | AUC(B) − AUC(A) [95% CI] | L2-A outcome |')
    print('|---|---|---|---|---|---|---|')
    for s, r in seeds.items():
        d, g = r['defs']['D=7, H=60 (L2-A gate)'], r['l2a_gate']
        print(f"| {s} | {d['population']} | {d['positives']} ({d['pos_share']:.3f}) | {f3(d['auc'])} {ci(d['ci'])} "
              f"| {f3(g['auc_B'])} {ci(g['auc_B_ci'])} | {g['diff']:+.3f} {ci(g['diff_ci'])} | {g['outcome']} |")
    print('\n### Other definitions of churn: LR on gate features, holdout 20% ROC AUC (positives share)')
    print('| definition | ' + ' | '.join(f'seed {s}' for s in seeds) + ' |')
    print('|---|' + '---|' * len(seeds))
    for n in next(iter(seeds.values()))['defs']:
        print(f'| {n} | ' + ' | '.join(f"{f3(r['defs'][n]['auc'])} ({r['defs'][n]['pos_share']:.3f})"
                                       for r in seeds.values()) + ' |')
    aucs = [r['defs']['D=7, H=60 (L2-A gate)']['auc'] for r in seeds.values()]
    print(f'\nholdout AUC over {len(aucs)} seeds: mean {np.mean(aucs):.3f}, min {min(aucs):.3f}, max {max(aucs):.3f}, '
          f'>= 0.70 on {sum(v >= 0.70 for v in aucs)} of {len(aucs)}')


def print_tables(rep, a):
    seeds = rep['seeds']
    print_seed_tables(rep, a)
    hidden = 'hidden' in rep
    print('\n### Integrity')
    print('| data | rows | users | min(ts − signup), s | events before signup | events after cancel except exit_survey '
          '| cancel/exit_survey in feature window (D=7/14/30) | events after 2025 | churned in 2025 |')
    print('|---|---|---|---|---|---|---|---|---|')
    items = [(f'seed {s}', r['integrity']) for s, r in seeds.items()]
    items += [(f'hidden {a.hidden_seed}', rep['hidden']['integrity'])] if hidden else []
    for n, q in items:
        w = q['post_cancel_events_in_feature_window']
        print(f"| {n} | {q['rows']} | {q['users']} | {q['min_ts_minus_signup_sec']:.0f} | {q['events_before_signup']} "
              f"| {q['events_after_cancel_not_exit_survey']} | {w['D7']}/{w['D14']}/{w['D30']} | {q['events_after_2025']} "
              f"| {q['churned_in_data_share']:.3f} |")
    print('\n### Users with at least one event: retained (no cancel in 2025) vs churned')
    print('| data | event | base | retained: with / all (share) | churned: with / all (share) | events retained / churned |')
    print('|---|---|---|---|---|---|')
    items = [(f'seed {s}', r['shares']) for s, r in seeds.items()]
    items += [(f'hidden {a.hidden_seed}', rep['hidden']['shares'])] if hidden else []
    for n, sh in items:
        for e, v in sh.items():
            print(f"| {n} | {e} | {v['base']} | {v['retained_with']} / {v['retained_users']} "
                  f"({v['retained_with'] / v['retained_users']:.3f}) | {v['churned_with']} / {v['churned_users']} "
                  f"({v['churned_with'] / v['churned_users']:.3f}) | {v['events_retained']} / {v['events_churned']} |")
    if not hidden:
        print(f"\nelapsed {rep['elapsed_sec']} s")
        return
    s0 = seeds[a.seeds[0]]
    print(f'\n### Strongest single features, max(AUC, 1 − AUC), seed {a.seeds[0]}')
    for key in ('single_feature_auc_D7', 'single_feature_auc_D30', 'single_feature_auc_snapshots'):
        print(f'- {key[19:]}: ' + ', '.join(f'{k} {v:.3f}' for k, v in list(s0[key].items())[:5]))
    print(f'\n### Hidden users (seed {a.hidden_seed}); models trained on all users of seed {a.seeds[0]}; H=60')
    print('| moment | model | population | positives share | ROC AUC [95% CI] | Δ vs LR baseline, same D [95% CI] |')
    print('|---|---|---|---|---|---|')
    for k, v in rep['hidden']['models'].items():
        d, m = k.split(' · ', 1)
        print(f"| {d} | {m} | {v['population']} | {v['pos_share']:.3f} | {f3(v['auc'])} {ci(v['ci'])} "
              f"| {v['diff']:+.3f} {ci(v['diff_ci'])} |")
    print(f'\n### Hidden users, as-of snapshots every 14 days {SNAP_DATES[0].date()}..{SNAP_DATES[-1].date()}, '
          f'label cancel in next {SNAP_H} days (CI: bootstrap over users)')
    print('| model | rows (users) | positives share | ROC AUC [95% CI] | Δ vs first-week-only LR [95% CI] |')
    print('|---|---|---|---|---|')
    for k, v in rep['hidden']['snapshots'].items():
        print(f"| {k} | {v['rows']} ({v['users']}) | {v['pos_share']:.3f} | {f3(v['auc'])} {ci(v['ci'])} "
              f"| {v['diff']:+.3f} {ci(v['diff_ci'])} |")
    print(f"\nelapsed {rep['elapsed_sec']} s")


if __name__ == '__main__':
    main()
