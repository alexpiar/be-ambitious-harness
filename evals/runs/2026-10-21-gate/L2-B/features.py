"""Признаки на дату среза (point-in-time) из сырого лога событий.

Главное правило: для среза T используются только события с ts < T.
cancel и exit_survey в признаки не попадают никогда (cancel — метка,
exit_survey приходит через 28.8 мин после cancel).
Один и тот же код используется в обучении (churn_pipeline.py) и в
еженедельном скоринге (score.py), чтобы признаки не расходились.
"""
import numpy as np
import pandas as pd

EPOCH = pd.Timestamp("2025-01-01")
PRICE = {"basic": 9.99, "pro": 24.99}
CAT_COLS = ["plan", "device", "country", "channel"]

FAMILIES = {
    "recent_engagement": ["sess_7", "sess_14", "sess_28", "days_since_session", "decay_28", "feat_28"],
    "overall_engagement": ["sess_all", "sess_rate", "feat_all", "feat_distinct_all", "sess_value_28"],
    "onboarding_first14d": ["sess_first14", "feat_distinct_first14"],
    "payment_failed": ["pf_ever", "days_since_pf"],
    "support_ticket": ["n_ticket", "days_since_ticket"],
    "plan_downgrade": ["dg_ever", "days_since_dg"],
    "tenure_billing": ["tenure", "days_to_bill", "n_pay"],
    "profile": CAT_COLS,
}
FEATURES = [f for fam in FAMILIES.values() for f in fam]
FLOW_FAMILIES = ["payment_failed", "support_ticket", "plan_downgrade"]  # сигналы «процесс ухода уже идёт»


def load_events(path):
    """Чтение и чистка. Возвращает (events, users)."""
    df = pd.read_csv(path, dtype={"value": "string"})
    df["ts"] = pd.to_datetime(df["ts"])
    n0 = len(df)
    df = df.drop_duplicates()
    quality = {"rows": n0, "exact_duplicates_dropped": n0 - len(df)}
    df["t"] = (df["ts"] - EPOCH).dt.total_seconds().to_numpy() / 86400.0
    df = df.sort_values("t", kind="mergesort").reset_index(drop=True)
    for c in CAT_COLS + ["event"]:
        df[c] = df[c].astype("category")
    codes, uniq = pd.factorize(df["user_id"])
    df["uid"] = codes.astype(np.int32)

    g = df.groupby("uid", sort=True)
    users = pd.DataFrame(index=pd.RangeIndex(len(uniq), name="uid"))
    users["user_id"] = uniq
    first_t = g["t"].min()
    signup_t = df.loc[df.event == "signup"].groupby("uid")["t"].min()
    users["signup_t"] = signup_t.reindex(users.index)
    # 11 пользователей имеют события до signup (сбой часов): старт = самое раннее событие
    users["start_t"] = np.fmin(users["signup_t"], first_t.reindex(users.index))
    quality["users_with_events_before_signup"] = int((first_t.reindex(users.index) < users["signup_t"]).sum())
    users["cancel_t"] = df.loc[df.event == "cancel"].groupby("uid")["t"].min().reindex(users.index)
    for c in CAT_COLS:
        users[c] = g[c].first().reindex(users.index).astype(str)
        quality[f"users_with_changing_{c}"] = int((g[c].nunique() > 1).sum())
    users["price"] = users["plan"].map(PRICE)
    return df, users, quality


def _last_t(sub, n_users):
    out = np.full(n_users, np.nan)
    if len(sub):
        last = sub.groupby("uid", sort=False)["t"].max()
        out[last.index.to_numpy()] = last.to_numpy()
    return out


def build_snapshot(df, users, T_day):
    """Признаки всех пользователей, активных на момент T (дни от 2025-01-01)."""
    n = len(users)
    hi = np.searchsorted(df["t"].to_numpy(), T_day, side="left")  # события строго до T
    past = df.iloc[:hi]
    past = past[~past.event.isin(["cancel", "exit_survey"])]
    start = users["start_t"].to_numpy()
    cancel = users["cancel_t"].to_numpy()
    active = (start < T_day) & ~(cancel <= T_day)
    uid = past["uid"].to_numpy()
    t = past["t"].to_numpy()
    ev = past["event"].astype(str).to_numpy()
    ten_at = t - start[uid]

    def cnt(mask):
        return np.bincount(uid[mask], minlength=n).astype(float)

    is_s = ev == "session_start"
    is_f = ev == "feature_used"
    tenure = T_day - start
    F = pd.DataFrame(index=users.index)
    F["tenure"] = tenure
    for w in (7, 14, 28):
        F[f"sess_{w}"] = cnt(is_s & (t >= T_day - w))
    F["sess_all"] = cnt(is_s)
    F["sess_rate"] = F["sess_all"] / np.maximum(tenure / 7.0, 1.0)
    s14 = cnt(is_s & (ten_at < 14))
    F["sess_first14"] = np.where(tenure >= 14, s14, np.nan)
    prior_len = (T_day - 28) - start
    prior_s = cnt(is_s & (t < T_day - 28))
    prior_rate = prior_s / np.maximum(prior_len / 7.0, 1e-9)
    F["decay_28"] = np.where(prior_len >= 14, (F["sess_28"] / 4.0) / np.maximum(prior_rate, 0.25), np.nan)
    last_s = _last_t(past[is_s], n)
    F["days_since_session"] = np.where(np.isnan(last_s), tenure, T_day - last_s)
    m28 = is_s & (t >= T_day - 28)
    sv = pd.to_numeric(past["value"].where(is_s), errors="coerce").to_numpy()
    sv_sum = np.bincount(uid[m28], weights=np.nan_to_num(sv[m28]), minlength=n)
    F["sess_value_28"] = np.where(F["sess_28"] > 0, sv_sum / np.maximum(F["sess_28"], 1), np.nan)
    F["feat_28"] = cnt(is_f & (t >= T_day - 28))
    F["feat_all"] = cnt(is_f)
    fv = past.loc[is_f, ["uid", "value"]]
    F["feat_distinct_all"] = fv.groupby("uid")["value"].nunique().reindex(users.index, fill_value=0).astype(float)
    fv14 = past.loc[is_f & (ten_at < 14), ["uid", "value"]]
    d14 = fv14.groupby("uid")["value"].nunique().reindex(users.index, fill_value=0).astype(float)
    F["feat_distinct_first14"] = np.where(tenure >= 14, d14, np.nan)
    F["n_pay"] = cnt(ev == "payment")
    lp = _last_t(past[ev == "payment_failed"], n)
    F["pf_ever"] = (~np.isnan(lp)).astype(float)
    F["days_since_pf"] = T_day - lp
    F["n_ticket"] = cnt(ev == "support_ticket")
    F["days_since_ticket"] = T_day - _last_t(past[ev == "support_ticket"], n)
    ld = _last_t(past[ev == "plan_downgrade"], n)
    F["dg_ever"] = (~np.isnan(ld)).astype(float)
    F["days_since_dg"] = T_day - ld
    F["days_to_bill"] = 30.0 - np.mod(tenure, 30.0)
    for c in CAT_COLS:
        F[c] = users[c].to_numpy()
    F["uid"] = users.index.to_numpy()
    F["T"] = T_day
    return F[active].reset_index(drop=True)


def add_labels(F, users, lo=0.0, hi=30.0):
    """1, если cancel попадает в (T+lo, T+hi]."""
    c = users["cancel_t"].to_numpy()[F["uid"].to_numpy()]
    d = c - F["T"].to_numpy()
    return ((d > lo) & (d <= hi)).astype(int)


def day(s):
    return (pd.Timestamp(s) - EPOCH).total_seconds() / 86400.0
