"""Доп. проверки после первого прогона:
1) тест перемешанных меток дал AUC 0.438 (вне предрегистрированного 0.47–0.53).
   Утечка толкала бы AUC ВВЕРХ; гипотеза — артефакт бустинга на шуме при редком
   классе (в малочисленных листьях медиана доли единиц ниже среднего, а реальные
   уходящие живут именно в редких областях признаков). Проверяем: несколько сидов,
   логрегрессия, бустинг с крупными листьями.
2) время упреждения против базлайнов (правила, давность, случайный список) и
   нагрузка на команду: сколько разных людей попадает в списки.
Запуск: OMP_NUM_THREADS=2 python -I checks_extra.py → results/checks_extra.json
"""
import json
import os
import sys
import zlib

os.environ.setdefault("OMP_NUM_THREADS", "2")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import CAT_COLS, FEATURES, add_labels, build_snapshot, day, load_events

HERE = os.path.dirname(os.path.abspath(__file__))
df, users, _ = load_events(os.path.join(HERE, "..", "data", "events_2025.csv"))
rows = []
for T in pd.date_range("2025-01-06", "2025-12-29", freq="7D"):
    F = build_snapshot(df, users, day(T))
    F["date"], F["y30"] = T, add_labels(F, users, 0, 30)
    rows.append(F)
S = pd.concat(rows, ignore_index=True)
for c in CAT_COLS:
    S[c] = pd.Categorical(S[c], categories=sorted(users[c].unique())).codes.astype(float)
tu = np.array([zlib.crc32(u.encode()) % 10 < 3 for u in users["user_id"]])
S["test_user"] = tu[S.uid.to_numpy()]
tr = S[(~S.test_user) & (S.date <= "2025-08-01")]
te = S[(S.test_user) & (S.date >= "2025-09-01") & (S.date <= "2025-12-01")]
best = json.load(open(os.path.join(HERE, "results", "tuning.json")))[0]
P = dict(learning_rate=best["learning_rate"], max_leaf_nodes=best["max_leaf_nodes"],
         min_samples_leaf=best["min_samples_leaf"], l2_regularization=1.0, max_iter=600, early_stopping=True,
         validation_fraction=0.15, n_iter_no_change=30, random_state=7)
cat = [FEATURES.index(c) for c in CAT_COLS]
X, Xt, yt = tr[FEATURES], te[FEATURES], te.y30.to_numpy()
Xl, Xlt = X.fillna(X.median()), Xt.fillna(X.median())
R = {"label_permutation": {}}
for name, mk, a, b in (
        ("gbm_tuned", lambda: HistGradientBoostingClassifier(categorical_features=cat, **P), X, Xt),
        ("gbm_min_leaf_1000", lambda: HistGradientBoostingClassifier(categorical_features=cat, **{**P, "min_samples_leaf": 1000}), X, Xt),
        ("logreg", lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000)), Xl, Xlt)):
    aucs = []
    for seed in range(5):
        yp = tr.y30.to_numpy()[np.random.default_rng(100 + seed).permutation(len(tr))]
        m = mk().fit(a, yp)
        aucs.append(round(float(roc_auc_score(yt, m.predict_proba(b)[:, 1])), 4))
    R["label_permutation"][name] = {"aucs": aucs, "mean": round(float(np.mean(aucs)), 4)}
    print(name, aucs, flush=True)

# --- упреждение: модель против базлайнов при одинаковой ёмкости 10% в неделю
model = HistGradientBoostingClassifier(categorical_features=cat, **P).fit(X, tr.y30)
bt = S[(S.test_user) & (S.date >= "2025-08-04")].copy()
bt["gbm"] = model.predict_proba(bt[FEATURES])[:, 1]
bt["rules_sql"] = 3 * bt.pf_ever + 2 * bt.dg_ever + 2 * (bt.days_since_ticket <= 30) + bt.days_since_session / 100
bt["recency_only"] = bt.days_since_session
bt["random"] = np.random.default_rng(5).random(len(bt))
ct = users["cancel_t"]
ch = users[users.index.isin(np.flatnonzero(tu)) & (ct >= day("2025-10-01"))]
R["lead_time_vs_baselines"] = {}
for s in ("gbm", "rules_sql", "recency_only", "random"):
    r = bt.groupby("date")[s].rank(ascending=False, pct=True, method="first")
    fl = bt[r <= 0.10]
    lead = []
    for u, c in ch["cancel_t"].items():
        x = fl[(fl.uid == u) & (fl["T"] < c) & (fl["T"] >= c - 60)]
        lead.append(c - x["T"].min() if len(x) else np.nan)
    lead = pd.Series(lead)
    q4 = fl[(fl.date >= "2025-10-01") & (fl.date <= "2025-12-01")]
    cc = ct.to_numpy()[q4.uid.to_numpy()]
    R["lead_time_vs_baselines"][s] = {
        "flagged_within_60d_before_cancel": round(float(lead.notna().mean()), 3),
        "flagged_14d_ahead": round(float((lead >= 14).mean()), 3),
        "median_lead_days": round(float(lead.median()), 1),
        "distinct_users_flagged_oct_nov": int(q4.uid.nunique()),
        "distinct_flagged_who_cancel_within_60d": round(float(
            q4.assign(hit=(cc > q4["T"]) & (cc <= q4["T"] + 60)).groupby("uid").hit.max().mean()), 3)}
    print(s, R["lead_time_vs_baselines"][s], flush=True)
R["active_test_users_oct_nov_avg"] = int(bt[(bt.date >= "2025-10-01") & (bt.date <= "2025-12-01")].groupby("date").size().mean())
json.dump(R, open(os.path.join(HERE, "results", "checks_extra.json"), "w"), ensure_ascii=False, indent=2)
