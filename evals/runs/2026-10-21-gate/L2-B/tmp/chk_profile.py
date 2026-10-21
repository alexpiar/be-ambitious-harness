import sys, os, json, zlib; sys.path.insert(0,'.')
os.environ['OMP_NUM_THREADS']='2'
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from features import *
df, users, _ = load_events('../data/events_2025.csv')
rows=[]
for T in pd.date_range("2025-01-06", "2025-12-01", freq="7D"):
    F = build_snapshot(df, users, day(T)); F["date"], F["y30"] = T, add_labels(F, users, 0, 30); rows.append(F)
S = pd.concat(rows, ignore_index=True)
for c in CAT_COLS: S[c] = pd.Categorical(S[c], categories=sorted(users[c].unique())).codes.astype(float)
tu = np.array([zlib.crc32(u.encode()) % 10 < 3 for u in users["user_id"]]); S["tu"]=tu[S.uid.to_numpy()]
itr = S[(~S.tu)&(S.date<="2025-06-02")]; iva = S[(~S.tu)&(S.date>="2025-07-07")&(S.date<="2025-08-01")]
best = json.load(open('results/tuning.json'))[0]
P = dict(learning_rate=best["learning_rate"], max_leaf_nodes=best["max_leaf_nodes"], min_samples_leaf=best["min_samples_leaf"], l2_regularization=1.0, max_iter=600, early_stopping=True, validation_fraction=0.15, n_iter_no_change=30)
for name, feats in [("all", FEATURES), ("no_profile", [f for f in FEATURES if f not in CAT_COLS])]:
    pr, roc = [], []
    for seed in range(3):
        cat = [i for i,f in enumerate(feats) if f in CAT_COLS] or None
        m = HistGradientBoostingClassifier(categorical_features=cat, random_state=seed, **P).fit(itr[feats], itr.y30)
        p = m.predict_proba(iva[feats])[:,1]; pr.append(average_precision_score(iva.y30,p)); roc.append(roc_auc_score(iva.y30,p))
    print(name, 'inner-val PR-AUC', np.round(pr,4), 'ROC', np.round(roc,4))
