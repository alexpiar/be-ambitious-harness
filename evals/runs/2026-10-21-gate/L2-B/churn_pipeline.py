"""Модель оттока: срезы во времени, отложенные пользователи и будущее, базлайны,
калибровка, важность признаков (перестановка + абляция), ранний сигнал,
бэктест времени упреждения, проверки на утечку.

Запуск: OMP_NUM_THREADS=2 python -I churn_pipeline.py
Результаты: results/*.json, results/*.csv, model.pkl
"""
import json
import os
import pickle
import sys
import time
import zlib

os.environ.setdefault("OMP_NUM_THREADS", "2")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from features import CAT_COLS, FAMILIES, FEATURES, FLOW_FAMILIES, add_labels, build_snapshot, day, load_events

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "events_2025.csv")
RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)
RNG = np.random.default_rng(20251)
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def dump(name, obj):
    with open(os.path.join(RES, name), "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=float)


# ---------------------------------------------------------------- данные и срезы
df, users, quality = load_events(DATA)
log("загружено", quality)
CAT_LEVELS = {c: sorted(users[c].unique()) for c in CAT_COLS}

mondays = pd.date_range("2025-01-06", "2025-12-29", freq="7D")
snaps = []
for T in mondays:
    F = build_snapshot(df, users, day(T))
    F["date"] = T
    F["y30"] = add_labels(F, users, 0, 30)
    F["y30_60"] = add_labels(F, users, 30, 60)
    snaps.append(F)
S = pd.concat(snaps, ignore_index=True)
del snaps
for c in CAT_COLS:
    S[c] = pd.Categorical(S[c], categories=CAT_LEVELS[c]).codes.astype(float)
# отложенные пользователи: 30% по стабильному хешу user_id
test_user = np.array([zlib.crc32(u.encode()) % 10 < 3 for u in users["user_id"]])
S["test_user"] = test_user[S["uid"].to_numpy()]
log("срезов", len(mondays), "строк", len(S))

D = lambda s: pd.Timestamp(s)
train = S[(~S.test_user) & (S.date <= D("2025-08-01"))]          # окна меток до 2025-08-31
test = S[(S.test_user) & (S.date >= D("2025-09-01")) & (S.date <= D("2025-12-01"))]
inner_tr = train[train.date <= D("2025-06-02")]                    # для подбора гиперпараметров
inner_va = train[train.date >= D("2025-07-07")]
log("train", train.shape, "base", round(train.y30.mean(), 4), "| test", test.shape, "base", round(test.y30.mean(), 4))


# ---------------------------------------------------------------- метрики
def ece(y, p, bins=20):
    q = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(q, p, side="right") - 1, 0, bins - 1)
    e = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            e += m.mean() * abs(y[m].mean() - p[m].mean())
    return e


def topk(y, s, frac=0.10):
    k = max(1, int(round(len(s) * frac)))
    o = np.argsort(-s, kind="mergesort")[:k]
    return y[o].sum() / max(y.sum(), 1), y[o].mean()


def topk_by_snapshot(y, s, dates, frac=0.10):
    """Топ-10% в каждом недельном срезе (так работает команда удержания)."""
    caught, total, prec = 0, 0, []
    for d in np.unique(dates):
        m = dates == d
        k = max(1, int(round(m.sum() * frac)))
        o = np.argsort(-s[m], kind="mergesort")[:k]
        caught += y[m][o].sum()
        total += y[m].sum()
        prec.append(y[m][o].mean())
    return caught / max(total, 1), float(np.mean(prec))


def metrics(y, s, dates, prob=True):
    r = {"roc_auc": roc_auc_score(y, s), "pr_auc": average_precision_score(y, s)}
    r["recall_top10"], r["precision_top10"] = topk_by_snapshot(y, s, dates)
    r["lift_top10"] = r["precision_top10"] / y.mean()
    if prob:
        p = np.clip(s, 1e-6, 1 - 1e-6)
        r.update(brier=brier_score_loss(y, p), logloss=log_loss(y, p), ece=ece(y, p))
    return {k: round(float(v), 4) for k, v in r.items()}


# ---------------------------------------------------------------- модели
CAT_IDX = [FEATURES.index(c) for c in CAT_COLS]


def hgb(feats=FEATURES, **kw):
    params = dict(learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=100, l2_regularization=1.0,
                  max_iter=600, early_stopping=True, validation_fraction=0.15, n_iter_no_change=30,
                  random_state=7)
    params.update(kw)
    cat = [i for i, f in enumerate(feats) if f in CAT_COLS]
    return HistGradientBoostingClassifier(categorical_features=cat or None, **params)


def lr_matrix(X, med=None):
    X = X.copy()
    num = [c for c in X.columns if c not in CAT_COLS]
    if med is None:
        med = X[num].median()
    for c in num:
        X[c + "_na"] = X[c].isna().astype(float)
        X[c] = X[c].fillna(med[c])
    X = pd.get_dummies(X, columns=[c for c in CAT_COLS if c in X.columns], dtype=float)
    return X, med


def fit_lr(tr, te, feats=FEATURES, y="y30"):
    Xtr, med = lr_matrix(tr[feats])
    Xte, _ = lr_matrix(te[feats], med)
    Xte = Xte.reindex(columns=Xtr.columns, fill_value=0.0)
    m = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000))
    m.fit(Xtr, tr[y])
    return m.predict_proba(Xte)[:, 1]


# --- подбор гиперпараметров на внутреннем временном разрезе (только обучающие пользователи)
grid = [dict(learning_rate=lr, max_leaf_nodes=lv, min_samples_leaf=ms)
        for lr in (0.05, 0.1) for lv in (15, 31) for ms in (50, 200)]
tune = []
for g in grid:
    m = hgb(**g).fit(inner_tr[FEATURES], inner_tr.y30)
    p = m.predict_proba(inner_va[FEATURES])[:, 1]
    tune.append({**g, "pr_auc": average_precision_score(inner_va.y30, p), "logloss": log_loss(inner_va.y30, p),
                 "n_iter": int(m.n_iter_)})
tune = sorted(tune, key=lambda r: -r["pr_auc"])
BEST = {k: tune[0][k] for k in ("learning_rate", "max_leaf_nodes", "min_samples_leaf")}
dump("tuning.json", tune)
log("лучшие гиперпараметры", BEST, round(tune[0]["pr_auc"], 4))

yte, dte = test.y30.to_numpy(), test.date.to_numpy()
model = hgb(**BEST).fit(train[FEATURES], train.y30)
p_hgb = model.predict_proba(test[FEATURES])[:, 1]
p_lr = fit_lr(train, test)
base_rate = np.full(len(test), train.y30.mean())
s_recency = test.days_since_session.to_numpy()
s_rules = (3 * test.pf_ever + 2 * test.dg_ever + 2 * (test.days_since_ticket <= 30)
           + test.days_since_session / 100).to_numpy()

scores = {"base_rate": base_rate, "recency_only": s_recency, "rules_sql": s_rules,
          "logreg_all_features": p_lr, "gbm": p_hgb}
res = {k: metrics(yte, v, dte, prob=k in ("base_rate", "logreg_all_features", "gbm")) for k, v in scores.items()}
res["base_rate"]["roc_auc"] = 0.5
dump("holdout_metrics.json", res)
log("отложенная выборка", json.dumps(res, ensure_ascii=False))

# --- бутстреп по пользователям (строки одного пользователя коррелированы)
uids = test.uid.to_numpy()
uniq = np.unique(uids)
pos = {u: np.flatnonzero(uids == u) for u in uniq}
best_base = max(("recency_only", "rules_sql", "logreg_all_features"), key=lambda k: res[k]["pr_auc"])
boot = {"gbm_roc": [], "gbm_pr": [], "gbm_recall10": [], "diff_pr_vs_" + best_base: [],
        "diff_roc_vs_" + best_base: []}
for _ in range(400):
    idx = np.concatenate([pos[u] for u in RNG.choice(uniq, len(uniq))])
    y, a, b = yte[idx], p_hgb[idx], scores[best_base][idx]
    boot["gbm_roc"].append(roc_auc_score(y, a))
    boot["gbm_pr"].append(average_precision_score(y, a))
    boot["gbm_recall10"].append(topk(y, a)[0])
    boot["diff_pr_vs_" + best_base].append(average_precision_score(y, a) - average_precision_score(y, b))
    boot["diff_roc_vs_" + best_base].append(roc_auc_score(y, a) - roc_auc_score(y, b))
ci = {k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)] for k, v in boot.items()}
ci["best_baseline"] = best_base
dump("bootstrap_ci.json", ci)
log("ДИ", ci)

# --- стабильность по срезам и калибровка
per = []
for d in np.unique(dte):
    m = dte == d
    per.append({"date": str(pd.Timestamp(d).date()), "n": int(m.sum()), "base": round(float(yte[m].mean()), 4),
                "roc_auc": round(roc_auc_score(yte[m], p_hgb[m]), 4),
                "pr_auc": round(average_precision_score(yte[m], p_hgb[m]), 4)})
pd.DataFrame(per).to_csv(os.path.join(RES, "per_snapshot.csv"), index=False)
dec = pd.qcut(p_hgb, 10, labels=False, duplicates="drop")
cal = pd.DataFrame({"decile": dec, "p": p_hgb, "y": yte}).groupby("decile").agg(
    n=("y", "size"), predicted=("p", "mean"), observed=("y", "mean")).round(4)
cal.to_csv(os.path.join(RES, "calibration_deciles.csv"))
log("калибровка\n", cal.to_string())

# ---------------------------------------------------------------- важность признаков
def perm_drop(m, X, y, cols, reps=5):
    base_pr, base_roc = average_precision_score(y, m.predict_proba(X)[:, 1]), roc_auc_score(y, m.predict_proba(X)[:, 1])
    dpr, droc = [], []
    for _ in range(reps):
        Xp = X.copy()
        o = RNG.permutation(len(X))
        Xp[cols] = X[cols].to_numpy()[o]          # семья переставляется целиком (признаки внутри коррелированы)
        p = m.predict_proba(Xp)[:, 1]
        dpr.append(base_pr - average_precision_score(y, p))
        droc.append(base_roc - roc_auc_score(y, p))
    return float(np.mean(dpr)), float(np.std(dpr)), float(np.mean(droc))


Xte = test[FEATURES].reset_index(drop=True)
imp_fam = []
for fam, cols in FAMILIES.items():
    a, sd, r = perm_drop(model, Xte, yte, cols)
    imp_fam.append({"family": fam, "perm_drop_pr_auc": round(a, 4), "sd": round(sd, 4), "perm_drop_roc_auc": round(r, 4)})
imp_feat = []
for f in FEATURES:
    a, sd, r = perm_drop(model, Xte, yte, [f], reps=3)
    imp_feat.append({"feature": f, "perm_drop_pr_auc": round(a, 4), "perm_drop_roc_auc": round(r, 4)})
# абляция: переобучение без семьи — сколько модель теряет, если этих данных нет совсем
for row in imp_fam:
    feats = [f for f in FEATURES if f not in FAMILIES[row["family"]]]
    m = hgb(feats, **BEST).fit(train[feats], train.y30)
    p = m.predict_proba(test[feats])[:, 1]
    row["ablation_drop_pr_auc"] = round(res["gbm"]["pr_auc"] - average_precision_score(yte, p), 4)
    row["ablation_drop_roc_auc"] = round(res["gbm"]["roc_auc"] - roc_auc_score(yte, p), 4)
imp_fam = sorted(imp_fam, key=lambda r: -r["perm_drop_pr_auc"])
pd.DataFrame(imp_fam).to_csv(os.path.join(RES, "importance_families.csv"), index=False)
pd.DataFrame(sorted(imp_feat, key=lambda r: -r["perm_drop_pr_auc"])).to_csv(
    os.path.join(RES, "importance_features.csv"), index=False)
log("важность семей\n", pd.DataFrame(imp_fam).to_string())

# только одна семья — сколько она даёт сама по себе
solo = []
for fam, cols in FAMILIES.items():
    m = hgb(cols, **BEST).fit(train[cols], train.y30)
    p = m.predict_proba(test[cols])[:, 1]
    solo.append({"family": fam, "solo_roc_auc": round(roc_auc_score(yte, p), 4),
                 "solo_pr_auc": round(average_precision_score(yte, p), 4)})
pd.DataFrame(solo).to_csv(os.path.join(RES, "importance_solo.csv"), index=False)

# ---------------------------------------------------------------- ранний сигнал: уход через 31-60 дней
early_feats = [f for f in FEATURES if not any(f in FAMILIES[x] for x in FLOW_FAMILIES)]
etr = S[(~S.test_user) & (S.date <= D("2025-06-30")) & (S.y30 == 0)]   # окна до 2025-08-29
ete = S[(S.test_user) & (S.date >= D("2025-09-01")) & (S.date <= D("2025-11-01")) & (S.y30 == 0)]
early = {"n_train": len(etr), "n_test": len(ete), "base_test": round(float(ete.y30_60.mean()), 4)}
for name, feats in (("no_flow_signals", early_feats), ("all_features", FEATURES)):
    m = hgb(feats, **BEST).fit(etr[feats], etr.y30_60)
    p = m.predict_proba(ete[feats])[:, 1]
    early[name] = metrics(ete.y30_60.to_numpy(), p, ete.date.to_numpy())
    if name == "no_flow_signals":
        ef = []
        for fam, cols in FAMILIES.items():
            if fam in FLOW_FAMILIES:
                continue
            a, sd, r = perm_drop(m, ete[feats].reset_index(drop=True), ete.y30_60.to_numpy(), cols)
            ef.append({"family": fam, "perm_drop_pr_auc": round(a, 4), "perm_drop_roc_auc": round(r, 4)})
        early["importance"] = sorted(ef, key=lambda r: -r["perm_drop_pr_auc"])
dump("early_signal.json", early)
log("ранний сигнал", json.dumps({k: v for k, v in early.items() if k != "importance"}, ensure_ascii=False))

# ---------------------------------------------------------------- время упреждения (бэктест еженедельной работы)
bt = S[(S.test_user) & (S.date >= D("2025-08-04"))].copy()
bt["p"] = model.predict_proba(bt[FEATURES])[:, 1]
bt["rank_pct"] = bt.groupby("date")["p"].rank(ascending=False, pct=True)
flag = bt[bt.rank_pct <= 0.10]
cancel_t = users["cancel_t"]
ch = users[users.index.isin(np.flatnonzero(test_user)) & (cancel_t >= day("2025-10-01"))].copy()
first = flag.groupby("uid")["T"].min()
lead = []
for u, ct in ch["cancel_t"].items():
    fl = flag[(flag.uid == u) & (flag["T"] < ct) & (flag["T"] >= ct - 60)]
    lead.append(ct - fl["T"].min() if len(fl) else np.nan)
ch["lead_days"] = lead
pf_users = set(df.loc[df.event == "payment_failed", "uid"])
ch["mechanism"] = np.where(ch.index.isin(list(pf_users)), "payment_failed", "voluntary")
lt = {"churners_oct_dec_test_users": int(len(ch)),
      "flagged_before_cancel_share": round(float(ch.lead_days.notna().mean()), 4),
      "median_lead_days_flagged": round(float(ch.lead_days.median()), 1),
      "share_flagged_7d_ahead": round(float((ch.lead_days >= 7).mean()), 4),
      "share_flagged_14d_ahead": round(float((ch.lead_days >= 14).mean()), 4),
      "by_mechanism": {k: {"n": int(len(g)), "flagged": round(float(g.lead_days.notna().mean()), 3),
                           "median_lead": round(float(g.lead_days.median()), 1),
                           "flagged_14d_ahead": round(float((g.lead_days >= 14).mean()), 3)}
                       for k, g in ch.groupby("mechanism")}}
# сколько «ложных тревог» в топ-10%: доля флагов на пользователях, не ушедших в 60 дней
fl2 = flag[flag.date <= D("2025-11-01")]
c2 = cancel_t.to_numpy()[fl2.uid.to_numpy()]
lt["flags_followed_by_cancel_within_60d"] = round(float(((c2 > fl2["T"]) & (c2 <= fl2["T"] + 60)).mean()), 4)
dump("lead_time.json", lt)
log("упреждение", lt)

# ---------------------------------------------------------------- проверки на утечку
# 1) перемешанные метки: модель должна стать случайной
yperm = train.y30.to_numpy()[RNG.permutation(len(train))]
mp = hgb(**BEST).fit(train[FEATURES], yperm)
perm_auc = roc_auc_score(yte, mp.predict_proba(test[FEATURES])[:, 1])
# 2) «наивная» модель: агрегаты за весь год + отток «когда-нибудь» — как обычно делают и почему так нельзя
ev = df[["uid", "event", "t", "value"]]
agg = pd.DataFrame(index=users.index)
for e in ["session_start", "feature_used", "payment", "payment_failed", "support_ticket", "plan_downgrade", "exit_survey"]:
    agg["n_" + e] = ev[ev.event == e].groupby("uid").size().reindex(users.index, fill_value=0)
agg["days_observed"] = ev.groupby("uid")["t"].max() - users["start_t"]
agg["signup_month"] = (users["start_t"] // 30.4).astype(int)
for c in CAT_COLS:
    agg[c] = pd.Categorical(users[c]).codes
yn = users["cancel_t"].notna().astype(int).to_numpy()
fold = np.array([zlib.crc32(u.encode()) % 5 for u in users["user_id"]])
pn = np.zeros(len(agg))
for k in range(5):
    m = HistGradientBoostingClassifier(max_iter=200, random_state=7).fit(agg[fold != k], yn[fold != k])
    pn[fold == k] = m.predict_proba(agg[fold == k])[:, 1]
mn = HistGradientBoostingClassifier(max_iter=200, random_state=7).fit(agg[fold != 0], yn[fold != 0])
Xn, yn0 = agg[fold == 0].reset_index(drop=True), yn[fold == 0]
naive_imp = []
for c in agg.columns:
    a, sd, r = perm_drop(mn, Xn, yn0, [c], reps=3)
    naive_imp.append({"feature": c, "perm_drop_roc_auc": round(r, 4)})
leak = {"label_permutation_test_auc": round(float(perm_auc), 4),
        "naive_full_year_model_cv_auc": round(float(roc_auc_score(yn, pn)), 4),
        "naive_top_features": sorted(naive_imp, key=lambda r: -r["perm_drop_roc_auc"])[:6]}
dump("leakage_checks.json", leak)
log("утечки", leak)

# ---------------------------------------------------------------- финальная модель для еженедельного скоринга
# Профиль (план/устройство/страна/канал) из боевой модели убран: на внутренней валидации
# (без участия теста, tmp/chk_profile.py) без него PR-AUC 0.601 -> 0.614 на 3 сидах; в причинах
# риска он давал неуправляемые «сегментные» объяснения. Отложенная выборка — только подтверждение.
PROD = [f for f in FEATURES if f not in FAMILIES["profile"]]
PROD_FAM = {k: v for k, v in FAMILIES.items() if k != "profile"}
mp_ = hgb(PROD, **BEST).fit(train[PROD], train.y30)
res_prod = metrics(yte, mp_.predict_proba(test[PROD])[:, 1], dte)
dump("holdout_metrics_production.json", res_prod)
log("боевая модель без профиля, отложенная выборка", res_prod)
full = S[S.date <= D("2025-12-01")]
final = hgb(PROD, **BEST).fit(full[PROD], full.y30)
# «типичные» значения для причин: медианы не ушедших в 60 дней
ref = full[(full.y30 == 0) & (full.y30_60 == 0)][PROD].median()
for f in ("pf_ever", "dg_ever", "n_ticket"):
    ref[f] = 0.0
for f in ("days_since_pf", "days_since_ticket", "days_since_dg"):
    ref[f] = np.nan
with open(os.path.join(HERE, "model.pkl"), "wb") as fh:
    pickle.dump({"model": final, "features": PROD, "families": PROD_FAM, "cat_levels": CAT_LEVELS,
                 "reference": ref.to_dict(), "trained_on": "все пользователи, срезы 2025-01-06..2025-12-01",
                 "params": BEST, "holdout_metrics_train_only_fit": res_prod}, fh)

# ---------------------------------------------------------------- сверка с предрегистрацией
pre = json.load(open(os.path.join(HERE, "prereg.json")))["targets"]
g = res["gbm"]
checks = {
    "roc_auc >= %.2f" % pre["roc_auc_min"]: [g["roc_auc"], g["roc_auc"] >= pre["roc_auc_min"]],
    "pr_auc >= %.2f" % pre["pr_auc_min"]: [g["pr_auc"], g["pr_auc"] >= pre["pr_auc_min"]],
    "recall_top10 >= %.2f" % pre["recall_at_top10pct_min"]: [g["recall_top10"], g["recall_top10"] >= pre["recall_at_top10pct_min"]],
    "ece <= %.2f" % pre["ece_max"]: [g["ece"], g["ece"] <= pre["ece_max"]],
    "CI(PR-AUC gbm - %s) > 0" % best_base: [ci["diff_pr_vs_" + best_base], ci["diff_pr_vs_" + best_base][0] > 0],
    "label permutation AUC in %s" % pre["label_permutation_auc_range"]:
        [leak["label_permutation_test_auc"], pre["label_permutation_auc_range"][0] <= leak["label_permutation_test_auc"] <= pre["label_permutation_auc_range"][1]],
    "early 31-60d roc_auc >= %.2f" % pre["early_signal_31_60d_roc_auc_min"]:
        [early["no_flow_signals"]["roc_auc"], early["no_flow_signals"]["roc_auc"] >= pre["early_signal_31_60d_roc_auc_min"]],
    "median lead >= %d d" % pre["lead_time_median_days_min"]:
        [lt["median_lead_days_flagged"], lt["median_lead_days_flagged"] >= pre["lead_time_median_days_min"]],
}
dump("prereg_check.json", {k: {"value": v[0], "pass": bool(v[1])} for k, v in checks.items()})
for k, v in checks.items():
    log("PASS" if v[1] else "MISS", k, v[0])
log("готово")
