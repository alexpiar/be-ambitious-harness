# Аудит: воспроизведение GBM, сплит, метрики, состав положительных, краевой эффект конца года,
# нулевое распределение для теста перемешанных меток.
import sys, os, zlib, json, pickle
os.environ["OMP_NUM_THREADS"] = "2"
import numpy as np, pandas as pd
OUT = sys.argv[1]
AUD = os.path.join(OUT, "tmp", "audit")
sys.path.insert(0, OUT)
from features import load_events, build_snapshot, add_labels, day, FEATURES, CAT_COLS, FAMILIES
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score

df, users, _ = load_events(os.path.join(OUT, "..", "data", "events_2025.csv"))
CAT_LEVELS = {c: sorted(users[c].unique()) for c in CAT_COLS}
snaps = []
for T in pd.date_range("2025-01-06", "2025-12-29", freq="7D"):
    F = build_snapshot(df, users, day(T)); F["date"] = T
    F["y30"] = add_labels(F, users, 0, 30); F["y30_60"] = add_labels(F, users, 30, 60)
    snaps.append(F)
S = pd.concat(snaps, ignore_index=True); del snaps
for c in CAT_COLS:
    S[c] = pd.Categorical(S[c], categories=CAT_LEVELS[c]).codes.astype(float)
tu = np.array([zlib.crc32(u.encode()) % 10 < 3 for u in users["user_id"]])
S["test_user"] = tu[S.uid.to_numpy()]
ct = users["cancel_t"].to_numpy()
S["d_cancel"] = ct[S.uid.to_numpy()] - S["T"]
# механизм итогового ухода пользователя (знание из будущего, только для разбивки!)
pf_users = set(df.loc[df.event == "payment_failed", "uid"])
S["inv_user"] = S.uid.isin(pf_users)
tr = S[(~S.test_user) & (S.date <= "2025-08-01")]
te = S[(S.test_user) & (S.date >= "2025-09-01") & (S.date <= "2025-12-01")].reset_index(drop=True)
print("users: train", tr.uid.nunique(), "test", te.uid.nunique(), "overlap", len(set(tr.uid) & set(te.uid)),
      "test share of all users", round(tu.mean(), 4))
print("train T max", tr.date.max().date(), "-> label window ends", (tr.date.max() + pd.Timedelta(days=30)).date(),
      "| test T min", te.date.min().date())
print("train rows", len(tr), "base", round(tr.y30.mean(), 4), "| test rows", len(te), "base", round(te.y30.mean(), 4))
print("test: positive rows", int(te.y30.sum()), "distinct churners among positives", te.loc[te.y30 == 1, "uid"].nunique(),
      "rows per test user mean", round(len(te) / te.uid.nunique(), 2))

best = json.load(open(os.path.join(OUT, "results", "tuning.json")))[0]
P = dict(learning_rate=best["learning_rate"], max_leaf_nodes=best["max_leaf_nodes"], min_samples_leaf=best["min_samples_leaf"],
         l2_regularization=1.0, max_iter=600, early_stopping=True, validation_fraction=0.15, n_iter_no_change=30, random_state=7)
cat = [FEATURES.index(c) for c in CAT_COLS]
m = HistGradientBoostingClassifier(categorical_features=cat, **P).fit(tr[FEATURES], tr.y30)
p = m.predict_proba(te[FEATURES])[:, 1]
y = te.y30.to_numpy(); dts = te.date.to_numpy()
print("REPRO gbm: roc", round(roc_auc_score(y, p), 4), "pr", round(average_precision_score(y, p), 4), "(author 0.9207 / 0.5784)")
np.save(os.path.join(AUD, "p_test.npy"), p)

# --- метрики независимо
def rec_by_snap(y, s, d):
    t = pd.DataFrame({"y": y, "s": s, "d": d})
    t["r"] = t.groupby("d")["s"].rank(ascending=False, method="first")
    t["n"] = t.groupby("d")["s"].transform("size")
    top = t[t.r <= np.round(t.n * 0.10)]
    return top.y.sum() / t.y.sum(), top.groupby("d").y.mean().mean()
def rec_global(y, s):
    k = int(round(len(s) * 0.1)); o = np.argsort(-s, kind="mergesort")[:k]; return y[o].sum() / y.sum()
r1, pr1 = rec_by_snap(y, p, dts)
print("recall@10 by snapshot (indep.)", round(r1, 4), "precision", round(pr1, 4), "| pooled global top10%", round(rec_global(y, p), 4))
def ece_q(y, p, b):
    q = pd.qcut(p, b, labels=False, duplicates="drop"); t = pd.DataFrame({"y": y, "p": p, "q": q}).groupby("q")
    return float((t.size() / len(y) * (t.y.mean() - t.p.mean()).abs()).sum())
def ece_w(y, p, b):
    q = np.minimum((p * b).astype(int), b - 1); t = pd.DataFrame({"y": y, "p": p, "q": q}).groupby("q")
    return float((t.size() / len(y) * (t.y.mean() - t.p.mean()).abs()).sum())
print("ECE quantile20", round(ece_q(y, p, 20), 4), "quantile10", round(ece_q(y, p, 10), 4), "equal-width10", round(ece_w(y, p, 10), 4),
      "| relative to base", round(ece_q(y, p, 20) / y.mean(), 3), "| mean p", round(p.mean(), 4), "mean y", round(y.mean(), 4))
top = p >= np.quantile(p, 0.9)
print("top decile: predicted", round(p[top].mean(), 4), "observed", round(y[top].mean(), 4))

# бутстреп по пользователям: та же метрика, что в точечной оценке (по срезам) против pooled (как у автора)
rng = np.random.default_rng(1)
uids = te.uid.to_numpy(); uq = np.unique(uids); pos = {u: np.flatnonzero(uids == u) for u in uq}
bs, bg, bp = [], [], []
for _ in range(300):
    idx = np.concatenate([pos[u] for u in rng.choice(uq, len(uq))])
    bs.append(rec_by_snap(y[idx], p[idx], dts[idx])[0]); bg.append(rec_global(y[idx], p[idx]))
    bp.append(average_precision_score(y[idx], p[idx]))
print("boot CI recall per-snapshot", np.percentile(bs, [2.5, 97.5]).round(4), "| pooled (author's CI metric)", np.percentile(bg, [2.5, 97.5]).round(4),
      "| P(recall_by_snap < 0.60)", round(float(np.mean(np.array(bs) < 0.60)), 3), "| PR-AUC CI", np.percentile(bp, [2.5, 97.5]).round(4))

# --- состав положительных: насколько тест состоит из «уход уже идёт»
flow30 = (te.days_since_pf <= 30) | (te.days_since_dg <= 30) | (te.days_since_ticket <= 30)
pfr = te.pf_ever == 1
print("test rows pf_ever=1:", int(pfr.sum()), "their y30 rate", round(te.y30[pfr].mean(), 4),
      "| share of test positives with pf_ever=1", round(te.y30[pfr].sum() / y.sum(), 3))
print("share of test positives with any flow signal <=30d (pf/dg/ticket)", round(te.y30[flow30].sum() / y.sum(), 3),
      "| y30 rate in flow rows", round(te.y30[flow30].mean(), 3), "| rows", int(flow30.sum()))
trpf = tr.pf_ever == 1
print("train rows pf_ever=1:", int(trpf.sum()), "y30 rate", round(tr.y30[trpf].mean(), 4))
def mm(mask, name):
    yy, pp = y[mask], p[mask]
    print(f"  {name:55s} rows={mask.sum():6d} base={yy.mean():.4f} roc={roc_auc_score(yy, pp):.4f} pr={average_precision_score(yy, pp):.4f} rec10={rec_by_snap(yy, pp, dts[mask])[0]:.4f}")
print("metrics by subset:")
mm(np.ones(len(y), bool), "all test")
mm(~pfr.to_numpy(), "rows without pf before T (known at T)")
mm(~flow30.to_numpy(), "rows without pf/dg/ticket in last 30d (known at T)")
mm(~te.inv_user.to_numpy(), "users never pf in 2025 (voluntary only, uses future)")
# --- краевой эффект конца года
te["p"] = p
g = te.groupby("date").apply(lambda x: pd.Series({"n": len(x), "y30": x.y30.mean(), "y30_60_among_neg": x.loc[x.y30 == 0, "y30_60"].mean(),
       "roc": roc_auc_score(x.y30, x.p), "pr": average_precision_score(x.y30, x.p),
       "mean_p_neg": x.loc[x.y30 == 0, "p"].mean()}))
print(g.round(4).to_string())
early = (te.date <= "2025-10-27").to_numpy()
mm(early, "test Sep01-Oct27 (T+60 inside 2025)")
mm(~early, "test Nov03-Dec01")
hn = (te.y30_60 == 1).to_numpy()
mm(early & ~hn, "Sep01-Oct27 minus negatives cancelling in 31-60d")
# AUC против «трудных» отрицательных
for nm, msk in (("Sep-Oct", early), ("Nov-Dec", ~early)):
    yy = y[msk]; pp = p[msk]; h = hn[msk]
    pos_ = pp[yy == 1]; neg_h = pp[(yy == 0) & h]; neg_e = pp[(yy == 0) & ~h]
    auc_h = roc_auc_score(np.r_[np.ones(len(pos_)), np.zeros(len(neg_h))], np.r_[pos_, neg_h]) if len(neg_h) else np.nan
    auc_e = roc_auc_score(np.r_[np.ones(len(pos_)), np.zeros(len(neg_e))], np.r_[pos_, neg_e])
    print(f"  {nm}: negatives cancelling 31-60d: {len(neg_h)} ({len(neg_h)/max((yy==0).sum(),1):.4f}); AUC pos vs those={auc_h:.4f}; AUC pos vs other neg={auc_e:.4f}")
# --- нулевое распределение для перемешанных меток: случайные направления в пространстве признаков
X = te[FEATURES].copy(); Xtr = tr[FEATURES]
med = Xtr.median(); 
Z = X.fillna(med); Ztr = Xtr.fillna(med)
for c in FEATURES:
    Z[c + "_na"] = X[c].isna().astype(float); Ztr[c + "_na"] = Xtr[c].isna().astype(float)
mu, sd = Ztr.mean(), Ztr.std().replace(0, 1)
Zs = ((Z - mu) / sd).fillna(0).to_numpy()
aucs_dir = [roc_auc_score(y, Zs @ rng.standard_normal(Zs.shape[1])) for _ in range(300)]
ru = rng.random((300, len(users)))
aucs_user = [roc_auc_score(y, ru[i][te.uid.to_numpy()]) for i in range(300)]
aucs_row = [roc_auc_score(y, rng.random(len(y))) for _ in range(300)]
for nm, a in (("random row score", aucs_row), ("random per-user score", aucs_user), ("random direction in feature space", aucs_dir)):
    a = np.array(a); print(f"null {nm:36s} mean={a.mean():.3f} sd={a.std():.3f} 2.5-97.5%={np.percentile(a,[2.5,97.5]).round(3)} P(<=0.438)={np.mean(a<=0.4378):.3f}")
author15 = [0.4969,0.5318,0.417,0.5236,0.5823,0.4773,0.5561,0.4587,0.4919,0.6125,0.6255,0.4391,0.4083,0.507,0.5453]
print("author 15 permuted-label runs: mean", round(np.mean(author15), 3), "sd", round(np.std(author15), 3))
te[["uid", "date", "y30", "y30_60", "p", "pf_ever", "inv_user"]].to_pickle(os.path.join(AUD, "te_pred.pkl"))
