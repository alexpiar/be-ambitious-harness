# Скоринг оттока по сохранённой модели (эталоны evals/reference/T2, T2-pass, L2; файл одинаковый).
#
#   python -I score.py <events.csv> <points.csv> <out.csv> [--model model.json]
#
# events.csv — сырые события в формате генератора (ts, user_id, event, value, plan, device,
# country, channel); points.csv — пары user_id,asof (момент прогноза в формате ts,
# 2025-06-01T00:00:00); out.csv — user_id,asof,score, строки в порядке points.csv.
# Модель — коэффициенты логистической регрессии в JSON рядом (по умолчанию model.json):
# без переобучения и без меток. Признаки точки (u, asof) — только из событий u с
# ts(signup) <= ts <= asof; cancel и exit_survey признаками не бывают никогда.
# Зависимости: numpy, pandas (sklearn не нужен).
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

DAY = 86400
KINDS = ['export', 'tags', 'search', 'share']
STATIC = ['plan', 'device', 'country', 'channel']
NEVER_FEATURE = ('cancel', 'exit_survey')
EVENTS = ['signup', 'session_start', 'feature_used', 'payment', 'payment_failed', 'support_ticket',
          'plan_downgrade']
EV = {e: i for i, e in enumerate(EVENTS)}
EPOCH = pd.Timestamp('2025-01-01')
TS_FORMAT = '%Y-%m-%dT%H:%M:%S'
# Окно признаков первых D суток (рабочие определения L2-A, раздел 5): всё за [signup, asof].
BEHAV = ['n_sessions', 'sess_value_sum', 'sess_value_mean', 'sess_value_max', 'active_days',
         'n_feature_used', 'n_fu_export', 'n_fu_tags', 'n_fu_search', 'n_fu_share',
         'n_payment', 'n_payment_failed', 'n_support_ticket', 'had_downgrade',
         'days_since_last_event', 'days_to_first_session']
# История на дату среза: давность, частота, тренд, оплата, поддержка.
HIST = ['tenure_days', 'n_sessions', 'sessions_per_week', 'sessions_last7', 'sessions_last28',
        'sessions_prev28', 'active_days_last28', 'feature_used_last28', 'days_since_last_session',
        'n_payment', 'n_payment_failed_last30', 'unrecovered_failure', 'n_support_ticket_last30',
        'had_downgrade']


def to_sec(ts):
    return ((pd.to_datetime(ts, format=TS_FORMAT) - EPOCH) // pd.Timedelta(seconds=1)).to_numpy(np.int64)


def from_sec(sec):
    return (EPOCH + pd.to_timedelta(np.asarray(sec, np.int64), unit='s')).strftime(TS_FORMAT)


def load_events(path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    need = {'ts', 'user_id', 'event', 'value', *STATIC}
    if not need <= set(df.columns):
        sys.exit(f'score.py: в {path} нет колонок {sorted(need - set(df.columns))}')
    return df


class Events:
    """События, отсортированные по (пользователь, время); окна считаются через searchsorted."""

    K = np.int64(1) << 40
    OFF = np.int64(1) << 38

    def __init__(self, df):
        su = df[df['event'] == 'signup'].sort_values('ts').drop_duplicates('user_id')
        self.users = pd.Index(su['user_id'].to_numpy())
        self.signup = to_sec(su['ts'])
        self.static = su.set_index('user_id')[STATIC]
        x = df[df['event'].isin(EVENTS) & df['user_id'].isin(self.users)]
        code = self.users.get_indexer(x['user_id']).astype(np.int64)
        t = to_sec(x['ts'])
        order = np.lexsort((t, code))
        self.code, self.t = code[order], t[order]
        self.ev = x['event'].map(EV).to_numpy(np.int64)[order]
        val = x['value'].to_numpy()[order]
        self.key = self.code * self.K + self.t + self.OFF
        sess = self.ev == EV['session_start']
        self.cum = {e: np.r_[0, np.cumsum(self.ev == i)] for e, i in EV.items()}
        for k in KINDS:
            self.cum['fu_' + k] = np.r_[0, np.cumsum((self.ev == EV['feature_used']) & (val == k))]
        sval = np.where(sess, pd.to_numeric(pd.Series(val), errors='coerce').fillna(0).to_numpy(), 0.0)
        self.sval = np.r_[sval, 0.0]  # хвост — для reduceat на пустых окнах
        self.cum['sess_value'] = np.r_[0.0, np.cumsum(sval)]
        date = self.t // DAY
        newday = np.r_[True, (self.code[1:] != self.code[:-1]) | (date[1:] != date[:-1])]
        self.newday = newday
        self.cum['newday'] = np.r_[0, np.cumsum(newday)]
        self.pos_sess = np.flatnonzero(sess)
        self.pos_bill = np.flatnonzero((self.ev == EV['payment']) | (self.ev == EV['payment_failed']))

    def idx(self, code, sec, side):
        return np.searchsorted(self.key, code * self.K + sec + self.OFF, side=side)

    def count(self, name, lo, hi):
        return (self.cum[name][hi] - self.cum[name][lo]).astype(float)

    def days(self, lo, hi):
        """Число разных календарных дат среди событий [lo, hi)."""
        n = self.count('newday', lo, hi)
        first_mid = (hi > lo) & ~self.newday[np.minimum(lo, len(self.newday) - 1)]
        return n + first_mid


def build_features(E, user_ids, asof_sec):
    """Признаки обоих наборов (BEHAV, HIST) и статика для точек (user_id, asof)."""
    code = E.users.get_indexer(pd.Index(user_ids)).astype(np.int64)
    if (code < 0).any():
        sys.exit(f'score.py: {int((code < 0).sum())} точек без signup в событиях')
    A = np.asarray(asof_sec, np.int64)
    S = E.signup[code]
    lo = E.idx(code, S, 'left')
    hi = np.maximum(E.idx(code, A, 'right'), lo)

    def after(sec):  # начало окна (sec, asof], не раньше signup
        return np.maximum(lo, E.idx(code, sec, 'right'))

    f = {}
    f['n_sessions'] = E.count('session_start', lo, hi)
    f['sess_value_sum'] = E.count('sess_value', lo, hi)
    f['sess_value_mean'] = np.where(f['n_sessions'] > 0, f['sess_value_sum'] / np.maximum(f['n_sessions'], 1), 0.0)
    seg = np.ravel(np.column_stack([lo, hi]))
    mx = np.maximum.reduceat(E.sval, seg)[::2] if len(seg) else np.zeros(0)
    f['sess_value_max'] = np.where(hi > lo, mx, 0.0)
    f['active_days'] = E.days(lo, hi)
    f['n_feature_used'] = E.count('feature_used', lo, hi)
    for k in KINDS:
        f['n_fu_' + k] = E.count('fu_' + k, lo, hi)
    f['n_payment'] = E.count('payment', lo, hi)
    f['n_payment_failed'] = E.count('payment_failed', lo, hi)
    f['n_support_ticket'] = E.count('support_ticket', lo, hi)
    f['had_downgrade'] = (E.count('plan_downgrade', lo, hi) > 0).astype(float)
    last = np.where(hi > lo, E.t[np.maximum(hi - 1, 0)], S)
    f['days_since_last_event'] = (A - last) / DAY
    i = np.searchsorted(E.pos_sess, lo)
    has = (i < len(E.pos_sess)) & (E.pos_sess[np.minimum(i, len(E.pos_sess) - 1)] < hi)
    first_sess = E.t[E.pos_sess[np.minimum(i, len(E.pos_sess) - 1)]] if len(E.pos_sess) else S
    f['days_to_first_session'] = np.where(has, (first_sess - S) / DAY, (A - S) / DAY)

    tenure = (A - S) / DAY
    f['tenure_days'] = tenure
    f['sessions_per_week'] = f['n_sessions'] / np.maximum(tenure, 1.0) * 7
    w7, w28, w56 = after(A - 7 * DAY), after(A - 28 * DAY), after(A - 56 * DAY)
    f['sessions_last7'] = E.count('session_start', w7, hi)
    f['sessions_last28'] = E.count('session_start', w28, hi)
    f['sessions_prev28'] = E.count('session_start', w56, w28)
    f['active_days_last28'] = E.days(w28, hi)
    f['feature_used_last28'] = E.count('feature_used', w28, hi)
    j = np.searchsorted(E.pos_sess, hi) - 1
    hs = (j >= 0) & (E.pos_sess[np.maximum(j, 0)] >= lo) if len(E.pos_sess) else np.zeros(len(A), bool)
    last_sess = E.t[E.pos_sess[np.maximum(j, 0)]] if len(E.pos_sess) else S
    f['days_since_last_session'] = np.where(hs, (A - last_sess) / DAY, tenure)
    w30 = after(A - 30 * DAY)
    f['n_payment_failed_last30'] = E.count('payment_failed', w30, hi)
    b = np.searchsorted(E.pos_bill, hi) - 1
    hb = (b >= 0) & (E.pos_bill[np.maximum(b, 0)] >= lo) if len(E.pos_bill) else np.zeros(len(A), bool)
    last_bill = E.ev[E.pos_bill[np.maximum(b, 0)]] if len(E.pos_bill) else np.zeros(len(A), np.int64)
    f['unrecovered_failure'] = (hb & (last_bill == EV['payment_failed'])).astype(float)
    f['n_support_ticket_last30'] = E.count('support_ticket', w30, hi)

    out = pd.DataFrame(f)
    st = E.static.reindex(np.asarray(user_ids))
    for c in STATIC:
        out[c] = st[c].to_numpy()
    return out


def design_matrix(F, spec):
    """Числовые признаки (log1p — по списку) и one-hot статики, стандартизация по spec."""
    cols = []
    for c in spec['numeric']:
        v = F[c].to_numpy(float)
        cols.append(np.log1p(np.maximum(v, 0)) if c in spec['log1p'] else v)
    for c, levels in spec['categorical'].items():
        v = F[c].to_numpy()
        cols.extend((v == lv).astype(float) for lv in levels)
    X = np.column_stack(cols) if cols else np.zeros((len(F), 0))
    return (X - np.asarray(spec['mean'])) / np.asarray(spec['scale'])


def column_names(spec):
    return list(spec['numeric']) + [f'{c}={lv}' for c, levels in spec['categorical'].items() for lv in levels]


def logit(model, F):
    X = design_matrix(F, model['spec'])
    return X @ np.asarray(model['coef']) + model['intercept']


def score(model, F):
    return 1.0 / (1.0 + np.exp(-logit(model, F)))


def main(argv=None):
    ap = argparse.ArgumentParser(description='Скоринг оттока по сохранённой модели.')
    ap.add_argument('events')
    ap.add_argument('points')
    ap.add_argument('out')
    ap.add_argument('--model', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model.json'))
    a = ap.parse_args(argv)
    with open(a.model, encoding='utf-8') as fh:
        model = json.load(fh)
    pts = pd.read_csv(a.points, dtype=str, keep_default_na=False)
    if list(pts.columns[:2]) != ['user_id', 'asof']:
        sys.exit('score.py: points.csv должен начинаться с колонок user_id,asof')
    E = Events(load_events(a.events))
    F = build_features(E, pts['user_id'].to_numpy(), to_sec(pts['asof']))
    out = pd.DataFrame({'user_id': pts['user_id'], 'asof': pts['asof'], 'score': score(model, F)})
    out.to_csv(a.out, index=False, float_format='%.17g')
    print(f'score.py: {len(out)} точек, модель {os.path.basename(a.model)} ({model["name"]})')


if __name__ == '__main__':
    main()
