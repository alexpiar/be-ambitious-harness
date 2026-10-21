import sys, os, json, zlib; sys.path.insert(0,'.'); os.environ['OMP_NUM_THREADS']='2'
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
from features import *
df, users, _ = load_events('../data/events_2025.csv')
nc = users.index[users.cancel_t.isna()]
e = df[df.uid.isin(nc)]
print('неушедшие: payment', int((e.event=='payment').sum()), 'payment_failed', int((e.event=='payment_failed').sum()), 'plan_downgrade', int((e.event=='plan_downgrade').sum()))
rows=[]
for T in pd.date_range("2025-01-06","2025-12-01",freq="7D"):
    F=build_snapshot(df,users,day(T)); F["date"],F["y30"]=T,add_labels(F,users,0,30); rows.append(F)
S=pd.concat(rows,ignore_index=True)
for c in CAT_COLS: S[c]=pd.Categorical(S[c],categories=sorted(users[c].unique())).codes.astype(float)
tu=np.array([zlib.crc32(u.encode())%10<3 for u in users.user_id]); S["tu"]=tu[S.uid.to_numpy()]
tr=S[(~S.tu)&(S.date<="2025-08-01")]; te=S[(S.tu)&(S.date>="2025-09-01")].copy()
b=json.load(open('results/tuning.json'))[0]
P=dict(learning_rate=b["learning_rate"],max_leaf_nodes=b["max_leaf_nodes"],min_samples_leaf=b["min_samples_leaf"],l2_regularization=1.0,max_iter=600,early_stopping=True,validation_fraction=0.15,n_iter_no_change=30,random_state=7)
PROD=[f for f in FEATURES if f not in CAT_COLS]
for name, fs in (("all", FEATURES), ("prod_no_profile", PROD)):
    cat=[i for i,f in enumerate(fs) if f in CAT_COLS] or None
    m=HistGradientBoostingClassifier(categorical_features=cat,**P).fit(tr[fs],tr.y30); te["p"]=m.predict_proba(te[fs])[:,1]
    te["r"]=te.groupby("date").p.rank(ascending=False,method="first"); te["n"]=te.groupby("date").p.transform("size")
    for lab, mask in (("сен-окт", te.date<="2025-10-27"), ("ноя-дек", te.date>="2025-11-03")):
        t=te[mask]; rec=t[t.r<=np.round(t.n*.1)].y30.sum()/t.y30.sum()
        print(name, lab, 'base', round(t.y30.mean(),4), 'roc', round(roc_auc_score(t.y30,t.p),4), 'pr', round(average_precision_score(t.y30,t.p),4), 'recall@10', round(rec,4))
