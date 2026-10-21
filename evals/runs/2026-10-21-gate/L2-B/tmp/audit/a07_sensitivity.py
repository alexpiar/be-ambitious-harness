# Аудит: чувствительность метрик теста к сигналам, существующим только у уходящих (pf, dg; n_pay их дублирует),
# и проверка решения «убрать профиль» на внутренней валидации (как в tmp/chk_profile.py автора).
import sys, os, zlib, json
os.environ["OMP_NUM_THREADS"] = "2"
import numpy as np, pandas as pd
OUT = sys.argv[1]; sys.path.insert(0, OUT)
from features import load_events, build_snapshot, add_labels, day, FEATURES, CAT_COLS, FAMILIES
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
df, users, _ = load_events(os.path.join(OUT, "..", "data", "events_2025.csv"))
CL = {c: sorted(users[c].unique()) for c in CAT_COLS}
rows = []
for T in pd.date_range("2025-01-06", "2025-12-01", freq="7D"):
    F = build_snapshot(df, users, day(T)); F["date"] = T; F["y30"] = add_labels(F, users, 0, 30); rows.append(F)
S = pd.concat(rows, ignore_index=True); del rows
for c in CAT_COLS: S[c] = pd.Categorical(S[c], categories=CL[c]).codes.astype(float)
tu = np.array([zlib.crc32(u.encode()) % 10 < 3 for u in users["user_id"]]); S["tu"] = tu[S.uid.to_numpy()]
tr = S[(~S.tu) & (S.date <= "2025-08-01")]; te = S[(S.tu) & (S.date >= "2025-09-01")].reset_index(drop=True)
best = json.load(open(os.path.join(OUT, "results", "tuning.json")))[0]
P = dict(learning_rate=best["learning_rate"], max_leaf_nodes=best["max_leaf_nodes"], min_samples_leaf=best["min_samples_leaf"],
         l2_regularization=1.0, max_iter=600, early_stopping=True, validation_fraction=0.15, n_iter_no_change=30)
def rec10(y, s, d):
    t = pd.DataFrame({"y": y, "s": s, "d": d}); t["r"] = t.groupby("d").s.rank(ascending=False, method="first")
    t["n"] = t.groupby("d").s.transform("size"); return t[t.r <= np.round(t.n * .1)].y.sum() / t.y.sum()
def fit(feats, a, b, seed=7):
    cat = [i for i, f in enumerate(feats) if f in CAT_COLS] or None
    m = HistGradientBoostingClassifier(categorical_features=cat, random_state=seed, **P).fit(a[feats], a.y30)
    return m.predict_proba(b[feats])[:, 1]
y = te.y30.to_numpy(); d = te.date.to_numpy()
noflow = ~((te.days_since_pf <= 30) | (te.days_since_dg <= 30) | (te.days_since_ticket <= 30)).to_numpy()
sets = {
    "all features (author)": FEATURES,
    "minus payment_failed family, minus n_pay": [f for f in FEATURES if f not in FAMILIES["payment_failed"] + ["n_pay"]],
    "minus pf, n_pay, plan_downgrade": [f for f in FEATURES if f not in FAMILIES["payment_failed"] + FAMILIES["plan_downgrade"] + ["n_pay"]],
    "minus pf, n_pay, dg, support_ticket": [f for f in FEATURES if f not in FAMILIES["payment_failed"] + FAMILIES["plan_downgrade"] + FAMILIES["support_ticket"] + ["n_pay"]],
}
for nm, fs in sets.items():
    p = fit(fs, tr, te)
    print(f"{nm:42s} test roc={roc_auc_score(y, p):.4f} pr={average_precision_score(y, p):.4f} rec10={rec10(y, p, d):.4f} | no-flow rows pr={average_precision_score(y[noflow], p[noflow]):.4f}", flush=True)
# решение по профилю на внутренней валидации (обучающие пользователи), 3 сида
itr = S[(~S.tu) & (S.date <= "2025-06-02")]; iva = S[(~S.tu) & (S.date >= "2025-07-07") & (S.date <= "2025-08-01")]
for nm, fs in (("all", FEATURES), ("no_profile", [f for f in FEATURES if f not in CAT_COLS])):
    prs = [average_precision_score(iva.y30, fit(fs, itr, iva, seed=s)) for s in range(3)]
    tps = [average_precision_score(y, fit(fs, tr, te, seed=s)) for s in range(3)]
    print(f"profile check {nm:10s} inner-val PR-AUC {np.round(prs, 4)} mean {np.mean(prs):.4f} | test PR-AUC by seed {np.round(tps, 4)} mean {np.mean(tps):.4f}", flush=True)
print("inner-val rows", len(iva), "positives", int(iva.y30.sum()), "distinct churners", iva.loc[iva.y30 == 1, "uid"].nunique())
