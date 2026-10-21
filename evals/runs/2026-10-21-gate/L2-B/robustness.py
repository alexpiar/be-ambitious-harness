"""Проверка устойчивости рейтинга важности: тот же групповой перестановочный тест,
но на логистической регрессии (другое семейство моделей). Если ранги семей
совпадают — важность принадлежит данным, а не конкретной модели.

Запуск: OMP_NUM_THREADS=2 python -I robustness.py → results/importance_robustness.json
"""
import json
import os
import sys
import zlib

os.environ.setdefault("OMP_NUM_THREADS", "2")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import CAT_COLS, FAMILIES, FEATURES, add_labels, build_snapshot, day, load_events

HERE = os.path.dirname(os.path.abspath(__file__))
RNG = np.random.default_rng(7)
df, users, _ = load_events(os.path.join(HERE, "..", "data", "events_2025.csv"))
rows = []
for T in pd.date_range("2025-01-06", "2025-12-01", freq="7D"):
    F = build_snapshot(df, users, day(T))
    F["date"], F["y30"] = T, add_labels(F, users, 0, 30)
    rows.append(F)
S = pd.concat(rows, ignore_index=True)
tu = np.array([zlib.crc32(u.encode()) % 10 < 3 for u in users["user_id"]])
S["test_user"] = tu[S.uid.to_numpy()]
tr = S[(~S.test_user) & (S.date <= "2025-08-01")]
te = S[(S.test_user) & (S.date >= "2025-09-01")].reset_index(drop=True)

num = [c for c in FEATURES if c not in CAT_COLS]
med = tr[num].median()


def mat(X):
    X = X[FEATURES].copy()
    for c in num:
        X[c + "_na"] = X[c].isna().astype(float)
        X[c] = X[c].fillna(med[c])
    for c in CAT_COLS:
        X[c] = pd.Categorical(X[c], categories=sorted(users[c].unique()))
    return pd.get_dummies(X, columns=CAT_COLS, dtype=float)


m = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000)).fit(mat(tr), tr.y30)
y = te.y30.to_numpy()
base = average_precision_score(y, m.predict_proba(mat(te))[:, 1])
out = []
for fam, cols in FAMILIES.items():
    d = []
    for _ in range(5):
        Xp = te.copy()
        Xp[cols] = te[cols].to_numpy()[RNG.permutation(len(te))]
        d.append(base - average_precision_score(y, m.predict_proba(mat(Xp))[:, 1]))
    out.append({"family": fam, "lr_perm_drop_pr_auc": round(float(np.mean(d)), 4)})
gbm = pd.read_csv(os.path.join(HERE, "results", "importance_families.csv"))
R = pd.DataFrame(out).merge(gbm[["family", "perm_drop_pr_auc"]].rename(columns={"perm_drop_pr_auc": "gbm_perm_drop_pr_auc"}))
rho = spearmanr(R.lr_perm_drop_pr_auc, R.gbm_perm_drop_pr_auc).statistic
res = {"lr_pr_auc_test": round(float(base), 4), "spearman_rank_corr_families": round(float(rho), 3),
       "table": R.sort_values("lr_perm_drop_pr_auc", ascending=False).to_dict("records")}
json.dump(res, open(os.path.join(HERE, "results", "importance_robustness.json"), "w"), ensure_ascii=False, indent=2)
print(json.dumps(res, ensure_ascii=False, indent=1))
