# Аудит look-ahead:
# (A) повтор: build_snapshot на логе, обрезанном строго до T (будущего нет физически), против полного лога.
#     Любое расхождение признаков = признак видит события ts >= T.
# (B) независимая реализация 12 признаков по сырым событиям для случайных (user, T) и сверка.
import sys, os
import numpy as np, pandas as pd
OUT = sys.argv[1]
sys.path.insert(0, OUT)
from features import load_events, build_snapshot, day, FEATURES, CAT_COLS
df, users, q = load_events(os.path.join(OUT, "..", "data", "events_2025.csv"))
print("quality", q)

def users_from(dft, n):
    u = pd.DataFrame(index=pd.RangeIndex(n, name="uid"))
    u["user_id"] = users["user_id"]
    g = dft.groupby("uid", sort=True)
    first_t = g["t"].min().reindex(u.index)
    signup_t = dft.loc[dft.event == "signup"].groupby("uid")["t"].min().reindex(u.index)
    u["signup_t"] = signup_t
    u["start_t"] = np.fmin(signup_t, first_t)
    u["cancel_t"] = dft.loc[dft.event == "cancel"].groupby("uid")["t"].min().reindex(u.index)
    for c in CAT_COLS:
        u[c] = g[c].first().reindex(u.index).astype(str)
    return u

num = [f for f in FEATURES if f not in CAT_COLS]
for Ts in ["2025-02-03", "2025-05-05", "2025-07-28", "2025-09-01", "2025-10-20", "2025-12-01"]:
    T = day(Ts)
    full = build_snapshot(df, users, T).set_index("uid")
    dft = df[df["t"] < T]
    ut = users_from(dft, len(users))
    tr = build_snapshot(dft, ut, T).set_index("uid")
    same_pop = full.index.equals(tr.index)
    a, b = full[num].to_numpy(float), tr.loc[full.index, num].to_numpy(float)
    diff = ~((a == b) | (np.isnan(a) & np.isnan(b)) | np.isclose(a, b, rtol=0, atol=1e-9, equal_nan=True))
    cat_diff = int((full[CAT_COLS].astype(str) != tr.loc[full.index, CAT_COLS].astype(str)).to_numpy().sum())
    bad = {num[j]: int(diff[:, j].sum()) for j in range(len(num)) if diff[:, j].any()}
    print(f"T={Ts} active={len(full)} same_population={same_pop} numeric_cells_differ={int(diff.sum())} {bad} cat_cells_differ={cat_diff}")

# (B) независимая реализация
raw = pd.read_csv(os.path.join(OUT, "..", "data", "events_2025.csv"), dtype={"value": "string"})
raw["ts"] = pd.to_datetime(raw["ts"])
raw = raw.drop_duplicates()
byu = {u: x.sort_values("ts") for u, x in raw.groupby("user_id")}
rng = np.random.default_rng(12345)
mondays = pd.date_range("2025-01-06", "2025-12-29", freq="7D")
checks, mism = 0, {}
for Ts in rng.choice(mondays, 12, replace=False):
    T = pd.Timestamp(Ts)
    snap = build_snapshot(df, users, day(T))
    rows = snap.sample(min(40, len(snap)), random_state=int(rng.integers(1e9)))
    for _, r in rows.iterrows():
        u = users.loc[int(r.uid), "user_id"]
        x = byu[u]
        start = min(x.loc[x.event == "signup", "ts"].min(), x.ts.min())
        p = x[(x.ts < T) & ~x.event.isin(["cancel", "exit_survey"])]
        D = lambda a, b: (a - b).total_seconds() / 86400
        s = p[p.event == "session_start"]
        ten = D(T, start)
        mine = {
            "tenure": ten,
            "sess_7": (s.ts >= T - pd.Timedelta(days=7)).sum(),
            "sess_28": (s.ts >= T - pd.Timedelta(days=28)).sum(),
            "days_since_session": D(T, s.ts.max()) if len(s) else ten,
            "sess_first14": ((s.ts - start) < pd.Timedelta(days=14)).sum() if ten >= 14 else np.nan,
            "feat_distinct_first14": p[(p.event == "feature_used") & ((p.ts - start) < pd.Timedelta(days=14))].value.nunique() if ten >= 14 else np.nan,
            "n_pay": (p.event == "payment").sum(),
            "days_since_pf": D(T, p.loc[p.event == "payment_failed", "ts"].max()) if (p.event == "payment_failed").any() else np.nan,
            "days_since_ticket": D(T, p.loc[p.event == "support_ticket", "ts"].max()) if (p.event == "support_ticket").any() else np.nan,
            "dg_ever": float((p.event == "plan_downgrade").any()),
        }
        prior_len = ten - 28
        if prior_len >= 14:
            prior = (s.ts < T - pd.Timedelta(days=28)).sum() / (prior_len / 7)
            mine["decay_28"] = (mine["sess_28"] / 4) / max(prior, 0.25)
        else:
            mine["decay_28"] = np.nan
        # реальная дата следующего списания по расписанию signup + 30k (проверено: все платежи в день 30k)
        k = np.floor(ten / 30) + 1
        mine["days_to_bill_true"] = D(start + pd.Timedelta(days=30 * k), T)
        for f, v in mine.items():
            fv = r["days_to_bill"] if f == "days_to_bill_true" else r[f]
            ok = (np.isnan(v) and np.isnan(fv)) if (isinstance(v, float) and np.isnan(v)) or (isinstance(fv, float) and np.isnan(fv)) else abs(float(v) - float(fv)) < 1e-6
            checks += 1
            if not ok:
                mism.setdefault(f, []).append((u, str(T.date()), v, fv))
print("independent checks:", checks, "mismatches:", {k: len(v) for k, v in mism.items()})
for k, v in mism.items():
    print(k, v[:5])
