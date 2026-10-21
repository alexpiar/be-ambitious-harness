# -*- coding: utf-8 -*-
"""
Прогноз оттока (cancel) по событиям пользователей за 2025 год.

Одна команда воспроизводит все числа отчёта из сырого CSV (seed 42):

    OMP_NUM_THREADS=2 python churn.py all --csv ../data/events_2025.csv --out results

Режимы:
    split     — отложить holdout (20 % пользователей, страта = месяц регистрации, seed 42)
    quality   — проверка качества данных (этап 0.1)
    gate      — входная проверка D=7 (раздел 4), только dev
    stage2    — базовая ветка D=14 (этап 2): CV-выбор модели на dev, одна оценка на holdout
    refute    — тест на опровержение: перемешанные метки на dev, одиночные AUC признаков
    export    — выгрузка таблицы признаков на T в CSV (для независимой проверки (б))
    all       — split + quality + gate + stage2 + refute
"""
import argparse
import hashlib
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "2")

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

SEED = 42
N_BOOT = 1000
HORIZON_DAYS = 60
DATA_END = pd.Timestamp("2025-12-31 23:59:59")

STATIC_VARS = ["plan_T", "device", "country", "channel"]
# события, которые никогда не являются признаками
NEVER_FEATURE_EVENTS = {"exit_survey", "cancel"}
FEATURE_KINDS = ["export", "tags", "search", "share"]


# ----------------------------------------------------------------------------
# Загрузка
# ----------------------------------------------------------------------------
def load_events(csv_path):
    df = pd.read_csv(
        csv_path,
        dtype={"user_id": str, "event": str, "value": str, "plan": str,
               "device": str, "country": str, "channel": str},
        keep_default_na=False, na_values=[""],
    )
    df["ts"] = pd.to_datetime(df["ts"], format="%Y-%m-%dT%H:%M:%S")
    return df


def signup_table(df):
    s = df[df["event"] == "signup"].groupby("user_id")["ts"].min().rename("signup_ts")
    return s.to_frame()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# ----------------------------------------------------------------------------
# 0.2 Holdout
# ----------------------------------------------------------------------------
def make_holdout(df, out_dir):
    from sklearn.model_selection import train_test_split
    su = signup_table(df).sort_index()
    users = su.index.to_numpy()
    month = su["signup_ts"].dt.month.to_numpy()
    _, ho = train_test_split(users, test_size=0.2, stratify=month, random_state=SEED)
    ho = np.sort(ho)
    path = os.path.join(out_dir, "holdout_ids.txt")
    content = "\n".join(ho) + "\n"
    if os.path.exists(path):
        with open(path, "r") as f:
            old = f.read()
        if old != content:
            raise SystemExit("holdout_ids.txt не совпадает с воспроизведённым сплитом")
    else:
        with open(path, "w") as f:
            f.write(content)
    digest = sha256_file(path)
    by_month = pd.DataFrame({"month": month, "holdout": np.isin(users, ho)}).groupby("month")["holdout"].agg(["sum", "count"])
    return set(ho), digest, by_month


def load_holdout(out_dir):
    with open(os.path.join(out_dir, "holdout_ids.txt")) as f:
        return set(x.strip() for x in f if x.strip())


# ----------------------------------------------------------------------------
# 0.1 Качество данных
# ----------------------------------------------------------------------------
def quality(df, holdout, out_dir):
    """Целостность — по всему файлу; проверки, от которых зависит выбор, — только dev."""
    q = {}
    pr = lambda *a: print(*a)  # noqa: E731
    pr("== Целостность (весь файл) ==")
    q["n_rows"] = int(len(df))
    q["columns"] = list(df.columns)
    q["missing_by_col"] = {c: int(df[c].isna().sum()) for c in df.columns}
    q["missing_value_by_event"] = df.groupby("event")["value"].apply(lambda s: int(s.isna().sum())).to_dict()
    q["nonmissing_value_by_event"] = df.groupby("event")["value"].apply(lambda s: int(s.notna().sum())).to_dict()
    q["full_duplicates"] = int(df.duplicated().sum())
    q["dup_ts_user_event"] = int(df.duplicated(["ts", "user_id", "event"]).sum())
    q["sorted_by_ts"] = bool(df["ts"].is_monotonic_increasing)
    q["ts_min"], q["ts_max"] = str(df["ts"].min()), str(df["ts"].max())
    q["n_users"] = int(df["user_id"].nunique())
    sig = df[df["event"] == "signup"].groupby("user_id").size()
    q["signups_per_user"] = sig.value_counts().to_dict()
    q["users_without_signup"] = int(len(set(df["user_id"]) - set(sig.index)))
    su = signup_table(df)
    q["signup_by_month"] = su["signup_ts"].dt.month.value_counts().sort_index().to_dict()
    q["event_counts"] = df["event"].value_counts().to_dict()
    q["values_by_event"] = {e: g["value"].value_counts().to_dict() for e, g in df.groupby("event") if g["value"].notna().any()}
    for c in ["plan", "device", "country", "channel"]:
        q[f"nunique_{c}_per_user_max"] = int(df.groupby("user_id")[c].nunique().max())
        q[f"{c}_values"] = df.groupby("user_id")[c].first().value_counts().to_dict()
    for k in ["n_rows", "full_duplicates", "dup_ts_user_event", "sorted_by_ts", "ts_min", "ts_max", "n_users",
              "signups_per_user", "users_without_signup", "missing_by_col", "missing_value_by_event",
              "nonmissing_value_by_event", "signup_by_month", "event_counts"]:
        pr(f"{k}: {q[k]}")
    for c in ["plan", "device", "country", "channel"]:
        pr(f"{c}: max nunique per user = {q[f'nunique_{c}_per_user_max']}; {q[f'{c}_values']}")
    for e, v in q["values_by_event"].items():
        pr(f"values[{e}]: {dict(list(v.items())[:15])}")
    cancels_per_user = df[df["event"] == "cancel"].groupby("user_id").size()
    q["cancels_per_user"] = cancels_per_user.value_counts().to_dict()
    pr("cancels_per_user:", q["cancels_per_user"])

    pr("\n== Проверки для решений (только dev) ==")
    d = df[~df["user_id"].isin(holdout)].copy()
    d = d.merge(su, left_on="user_id", right_index=True, how="left")
    d["dt_days"] = (d["ts"] - d["signup_ts"]).dt.total_seconds() / 86400
    q["dev_users"] = int(d["user_id"].nunique())
    q["dev_events_before_signup"] = int((d["dt_days"] < 0).sum())
    q["dev_events_before_signup_by_event"] = d.loc[d["dt_days"] < 0, "event"].value_counts().to_dict()
    pr("dev users:", q["dev_users"], "| events before signup:", q["dev_events_before_signup"],
       q["dev_events_before_signup_by_event"])

    # частоты по месяцам: события на активного пользователя
    d["month"] = d["ts"].dt.month
    cnt = d.pivot_table(index="month", columns="event", values="user_id", aggfunc="size", fill_value=0)
    active = d.groupby("month")["user_id"].nunique().rename("active_users")
    per_user = cnt.div(active, axis=0).round(3)
    pr("\nСобытия по месяцам (dev, штук):\n" + cnt.to_string())
    pr("\nСобытия на активного пользователя по месяцам (dev):\n" + pd.concat([active, per_user], axis=1).to_string())
    cnt.to_csv(os.path.join(out_dir, "quality_events_by_month.csv"))
    ss = d[d["event"] == "session_start"].copy()
    ss["v"] = ss["value"].astype(float)
    sv = ss.groupby("month")["v"].describe()[["count", "mean", "std", "min", "50%", "max"]].round(3)
    pr("\nsession_start.value по месяцам (dev):\n" + sv.to_string())
    fu = d[d["event"] == "feature_used"]
    fuk = pd.crosstab(fu["month"], fu["value"], normalize="index").round(3)
    pr("\nДоли видов feature_used по месяцам (dev):\n" + fuk.to_string())
    pay = d[d["event"].isin(["payment", "payment_failed"])]
    pv = pd.crosstab([pay["event"], pay["month"]], pay["value"])
    pr("\nСуммы payment/payment_failed по месяцам (dev):\n" + pv.to_string())
    # распределение по дням жизни: сессии по неделям жизни
    ss["life_week"] = (ss["dt_days"] // 7).astype(int)
    q["session_value_dist_dev"] = ss["v"].value_counts().sort_index().to_dict()
    pr("\nsession_start.value распределение (dev):", q["session_value_dist_dev"])
    # value как порядковый номер сессии? корреляция с номером сессии у пользователя
    ss = ss.sort_values(["user_id", "ts"])
    ss["sess_idx"] = ss.groupby("user_id").cumcount() + 1
    rho = spearmanr(ss["v"], ss["sess_idx"]).correlation
    rho_dt = spearmanr(ss["v"], ss["dt_days"]).correlation
    rho_hour = spearmanr(ss["v"], ss["ts"].dt.hour).correlation
    q["session_value_spearman"] = {"vs_session_index": float(rho), "vs_days_since_signup": float(rho_dt), "vs_hour": float(rho_hour)}
    pr("session_start.value Spearman: с номером сессии %.3f; с днями от signup %.3f; с часом %.3f" % (rho, rho_dt, rho_hour))
    # выбросы: события на пользователя, сессии в сутки
    epu = d.groupby("user_id").size()
    q["events_per_user_dev"] = epu.describe().round(2).to_dict()
    spd = ss.groupby([ss["user_id"], ss["ts"].dt.date]).size()
    q["sessions_per_user_day_dev"] = spd.describe().round(2).to_dict()
    pr("событий на пользователя (dev):", q["events_per_user_dev"])
    pr("session_start на пользователя в сутки (dev):", q["sessions_per_user_day_dev"])
    top = epu.sort_values(ascending=False).head(5)
    pr("топ-5 по числу событий:", top.to_dict())

    # события после cancel
    can = d[d["event"] == "cancel"].groupby("user_id")["ts"].min().rename("cancel_ts")
    dc = d.merge(can, left_on="user_id", right_index=True, how="inner")
    after = dc[dc["ts"] > dc["cancel_ts"]]
    q["dev_cancel_users"] = int(len(can))
    q["dev_users_with_events_after_cancel"] = int(after["user_id"].nunique())
    q["dev_events_after_cancel_by_event"] = after["event"].value_counts().to_dict()
    pr("\ncancel (dev): пользователей", q["dev_cancel_users"], "| с событиями после cancel:",
       q["dev_users_with_events_after_cancel"], q["dev_events_after_cancel_by_event"])
    if len(after):
        lag = (after["ts"] - after["cancel_ts"]).dt.total_seconds() / 86400
        pr("  дней после cancel у таких событий:", lag.describe().round(3).to_dict())
        q["dev_after_cancel_lag_days"] = lag.describe().round(3).to_dict()
    # cancel: дней от signup
    cl = (can - su.loc[can.index, "signup_ts"]).dt.total_seconds() / 86400
    q["dev_cancel_days_since_signup"] = cl.describe().round(2).to_dict()
    pr("cancel: дней от signup:", q["dev_cancel_days_since_signup"])
    pr("cancel: гистограмма по 7 дням (первые 20 недель):",
       (cl // 7).astype(int).value_counts().sort_index().head(20).to_dict())

    # exit_survey vs cancel
    ex = d[d["event"] == "exit_survey"][["user_id", "ts", "value"]].rename(columns={"ts": "ex_ts"})
    exc = ex.merge(can, left_on="user_id", right_index=True, how="left")
    q["dev_exit_survey"] = int(len(ex))
    q["dev_exit_survey_without_cancel"] = int(exc["cancel_ts"].isna().sum())
    lag = (exc["ex_ts"] - exc["cancel_ts"]).dt.total_seconds() / 3600
    q["dev_exit_minus_cancel_hours"] = lag.describe().round(3).to_dict()
    q["dev_exit_before_cancel"] = int((lag < 0).sum())
    pr("\nexit_survey (dev):", q["dev_exit_survey"], "| без cancel:", q["dev_exit_survey_without_cancel"],
       "| раньше cancel:", q["dev_exit_before_cancel"])
    pr("  часов exit_survey − cancel:", q["dev_exit_minus_cancel_hours"])
    pr("  доля отменивших с exit_survey:", round(exc["user_id"].nunique() / max(len(can), 1), 3))

    # plan vs payment / downgrade
    up = d.groupby("user_id")["plan"].first()
    dg = d[d["event"] == "plan_downgrade"]
    q["dev_downgrade_events"] = int(len(dg))
    q["dev_downgrade_users"] = int(dg["user_id"].nunique())
    q["dev_plan_of_downgrade_users"] = up.loc[dg["user_id"].unique()].value_counts().to_dict()
    pr("\nplan_downgrade (dev): событий", q["dev_downgrade_events"], "пользователей", q["dev_downgrade_users"],
       "| их plan в колонке:", q["dev_plan_of_downgrade_users"])
    pays = d[d["event"] == "payment"].copy()
    pays["amt"] = pays["value"].astype(float)
    dg_first = dg.groupby("user_id")["ts"].min().rename("dg_ts")
    pays = pays.merge(dg_first, left_on="user_id", right_index=True, how="left")
    pays["has_dg"] = pays["dg_ts"].notna()
    pays["phase"] = np.where(~pays["has_dg"], "no_downgrade",
                             np.where(pays["ts"] < pays["dg_ts"], "before_downgrade", "after_downgrade"))
    tab = pd.crosstab([pays["plan"], pays["phase"]], pays["amt"])
    q["dev_payment_amount_by_plan_phase"] = {f"{k[0]}|{k[1]}": {str(a): int(v) for a, v in r.items()} for k, r in tab.iterrows()}
    pr("payment.value по plan и фазе относительно downgrade (dev):\n" + tab.to_string())
    pf = d[d["event"] == "payment_failed"].copy()
    pf = pf.merge(dg_first, left_on="user_id", right_index=True, how="left")
    pf["phase"] = np.where(pf["dg_ts"].isna(), "no_downgrade", np.where(pf["ts"] < pf["dg_ts"], "before_downgrade", "after_downgrade"))
    tabf = pd.crosstab([pf["plan"], pf["phase"]], pf["value"])
    pr("payment_failed.value по plan и фазе (dev):\n" + tabf.to_string())
    # время первого payment от signup
    fp = pays.groupby("user_id")["ts"].min()
    fpl = (fp - su.loc[fp.index, "signup_ts"]).dt.total_seconds() / 86400
    q["dev_first_payment_days"] = fpl.describe().round(3).to_dict()
    q["dev_users_without_payment"] = int(q["dev_users"] - len(fp))
    pr("первый payment: дней от signup:", q["dev_first_payment_days"], "| без payment:", q["dev_users_without_payment"])
    # интервалы между платежами
    pays = pays.sort_values(["user_id", "ts"])
    gap = pays.groupby("user_id")["ts"].diff().dt.total_seconds() / 86400
    pr("интервал между payment, дней:", gap.describe().round(2).to_dict())
    # downgrade: дней от signup
    dgl = (dg_first - su.loc[dg_first.index, "signup_ts"]).dt.total_seconds() / 86400
    pr("plan_downgrade: дней от signup:", dgl.describe().round(2).to_dict())

    # окно метки и доля отменивших до T
    last_signup = su["signup_ts"].max()
    q["last_signup"] = str(last_signup)
    rows = {}
    for D in [3, 7, 14, 30]:
        T = su["signup_ts"] + pd.Timedelta(days=D)
        end = T + pd.Timedelta(days=HORIZON_DAYS)
        dev_su = su.loc[~su.index.isin(holdout)]
        Td = dev_su["signup_ts"] + pd.Timedelta(days=D)
        cdev = can.reindex(dev_su.index)
        before = (cdev <= Td).sum()
        pos = ((cdev > Td) & (cdev <= Td + pd.Timedelta(days=HORIZON_DAYS))).sum()
        n_pop = len(dev_su) - before
        rows[D] = {"max_T_plus_60": str(end.max()), "window_inside_data": bool(end.max() <= DATA_END),
                   "dev_cancel_before_T": int(before), "dev_share_cancel_before_T": round(before / len(dev_su), 4),
                   "dev_population": int(n_pop), "dev_positives": int(pos), "dev_pos_rate": round(pos / n_pop, 4)}
    q["slices"] = rows
    pr("\nСрезы (dev):\n" + pd.DataFrame(rows).T.to_string())

    with open(os.path.join(out_dir, "quality.json"), "w") as f:
        json.dump(q, f, ensure_ascii=False, indent=1, default=str)
    return q


def quality_extra(df, holdout, out_dir):
    """Дополнение к 0.1: дубли по (ts,user,event), события до signup, биллинг, когорты (смена сбора)."""
    from scipy.stats import chi2_contingency
    q = {}
    pr = print
    dup = df[df.duplicated(["ts", "user_id", "event"], keep=False)]
    q["dup_ts_user_event_rows"] = dup.astype(str).to_dict("records")
    pr("Строки-дубли по (ts,user_id,event):\n" + dup.to_string())
    su = signup_table(df)
    d = df[~df["user_id"].isin(holdout)].merge(su, left_on="user_id", right_index=True)
    d["dt"] = (d["ts"] - d["signup_ts"]).dt.total_seconds() / 86400
    pre = d[d["dt"] < 0]
    q["dev_pre_signup_rows"] = pre[["ts", "user_id", "event", "signup_ts", "dt"]].astype(str).to_dict("records")
    pr("События раньше signup (dev):\n" + pre[["ts", "user_id", "event", "signup_ts", "dt"]].to_string())
    bill = d[d["event"].isin(["payment", "payment_failed"])]
    q["dev_billing_dt_mod30_max"] = float((bill["dt"] % 30).max())
    q["dev_billing_dt_min"] = float(bill["dt"].min())
    pr("payment/payment_failed: min дней от signup = %.6f; max (дней mod 30) = %.6f"
       % (q["dev_billing_dt_min"], q["dev_billing_dt_mod30_max"]))
    u = su.loc[~su.index.isin(holdout)].copy()
    u["cm"] = u["signup_ts"].dt.month
    can = d[d["event"] == "cancel"].groupby("user_id")["ts"].min().reindex(u.index)
    npay = d[d["event"] == "payment"].groupby("user_id").size().reindex(u.index).fillna(0)
    npf = d[d["event"] == "payment_failed"].groupby("user_id").size().reindex(u.index).fillna(0)
    cdt = (can - u["signup_ts"]).dt.total_seconds() / 86400
    nop = npay == 0
    q["dev_no_payment"] = {"users": int(nop.sum()), "cancel_before_30d": int((nop & (cdt < 30)).sum()),
                           "with_payment_failed": int((nop & (npf > 0)).sum()), "no_cancel": int((nop & cdt.isna()).sum())}
    pr("Пользователи без payment (dev):", q["dev_no_payment"])
    w = d[(d["dt"] >= 0) & (d["dt"] <= 14)]
    for e in ["session_start", "feature_used", "support_ticket", "plan_downgrade"]:
        u[e] = w[w["event"] == e].groupby("user_id").size().reindex(u.index).fillna(0)
    T = u["signup_ts"] + pd.Timedelta(days=14)
    u["y14"] = ((can > T) & (can <= T + pd.Timedelta(days=HORIZON_DAYS))).astype(int)
    coh = u.groupby("cm")[["session_start", "feature_used", "support_ticket", "plan_downgrade", "y14"]].mean().round(3)
    coh["n"] = u.groupby("cm").size()
    pr("Когорты по месяцу регистрации (dev), среднее за [signup, signup+14d] и метка D=14:\n" + coh.to_string())
    coh.to_csv(os.path.join(out_dir, "quality_cohorts_dev.csv"))
    ct = pd.crosstab(u["cm"], u["y14"])
    chi2, p, dof, _ = chi2_contingency(ct)
    q["dev_y14_by_cohort_chi2"] = {"chi2": float(chi2), "dof": int(dof), "p": float(p)}
    pr("Метка D=14 по месяцу регистрации: chi2=%.2f, dof=%d, p=%.4f" % (chi2, dof, p))
    # активность отменивших перед cancel (описательно, dev)
    x = d[~d["event"].isin(["exit_survey", "cancel", "signup"])].merge(
        d[d["event"] == "cancel"].groupby("user_id")["ts"].min().rename("c"), left_on="user_id", right_index=True)
    x["before"] = ((x["c"] - x["ts"]).dt.total_seconds() // 86400).astype(int)
    ncan = int(d.loc[d["event"] == "cancel", "user_id"].nunique())
    prof = (x[x["before"].between(0, 40)].groupby("before").size() / ncan).round(3)
    q["dev_events_per_canceller_by_day_before_cancel"] = prof.to_dict()
    gap = (x.groupby("user_id")["c"].first() - x.groupby("user_id")["ts"].max()).dt.total_seconds() / 86400
    q["dev_days_last_event_to_cancel"] = gap.describe().round(2).to_dict()
    pr("Отменившие (dev): событий на пользователя в день k до cancel, k=0..40:", q["dev_events_per_canceller_by_day_before_cancel"])
    pr("Дней от последнего события до cancel (dev):", q["dev_days_last_event_to_cancel"])
    # события-предвестники: доля с последующим cancel и лаг до cancel (dev)
    canu = d[d["event"] == "cancel"].groupby("user_id")["ts"].min()
    q["dev_precursor_lag_to_cancel_days"] = {}
    for e in ["plan_downgrade", "support_ticket", "payment_failed"]:
        xe = d[d["event"] == e][["user_id", "ts"]].copy()
        lag = (xe["user_id"].map(canu) - xe["ts"]).dt.total_seconds() / 86400
        q["dev_precursor_lag_to_cancel_days"][e] = {"events": int(len(xe)), "share_followed_by_cancel": round(float((lag > 0).mean()), 4),
                                                    "without_cancel": int(lag.isna().sum()), "lag": lag[lag > 0].describe().round(2).to_dict()}
        pr(f"{e} (dev): событий {len(xe)}, доля с последующим cancel {(lag > 0).mean():.3f}, без cancel {int(lag.isna().sum())}, "
           f"дней до cancel: {lag[lag > 0].describe().round(2).to_dict()}")
    with open(os.path.join(out_dir, "quality_extra.json"), "w") as f:
        json.dump(q, f, ensure_ascii=False, indent=1, default=str)
    return q


# ----------------------------------------------------------------------------
# Признаки на T и метка
# ----------------------------------------------------------------------------
BEHAV = ["n_sessions", "sess_value_sum", "sess_value_mean", "sess_value_max", "active_days",
         "n_feature_used", "n_fu_export", "n_fu_tags", "n_fu_search", "n_fu_share",
         "n_payment", "n_payment_failed", "n_support_ticket", "had_downgrade",
         "days_since_last_event", "days_to_first_session"]


def build_features(df, D):
    """Признаки на T = ts(signup) + D суток. Используются только события с ts(signup) <= ts <= T,
    кроме exit_survey и cancel. Популяция: нет cancel с ts <= T. Возвращает DataFrame по user_id."""
    su = signup_table(df)
    T = su["signup_ts"] + pd.Timedelta(days=D)
    attrs = df.groupby("user_id")[["plan", "device", "country", "channel"]].first()
    x = df.merge(T.rename("T"), left_on="user_id", right_index=True)
    x = x.merge(su, left_on="user_id", right_index=True)
    # популяция — только по событиям с ts <= T
    canc_before = x.loc[(x["event"] == "cancel") & (x["ts"] <= x["T"]), "user_id"].unique()
    w = x[(x["ts"] >= x["signup_ts"]) & (x["ts"] <= x["T"]) & (~x["event"].isin(NEVER_FEATURE_EVENTS))].copy()

    out = pd.DataFrame(index=su.index)
    out["plan_T"] = attrs["plan"]
    out["device"] = attrs["device"]
    out["country"] = attrs["country"]
    out["channel"] = attrs["channel"]
    ss = w[w["event"] == "session_start"].copy()
    ss["v"] = ss["value"].astype(float)
    g = ss.groupby("user_id")["v"]
    out["n_sessions"] = g.size()
    out["sess_value_sum"] = g.sum()
    out["sess_value_mean"] = g.mean()
    out["sess_value_max"] = g.max()
    w["date"] = w["ts"].dt.normalize()
    out["active_days"] = w.groupby("user_id")["date"].nunique()
    fu = w[w["event"] == "feature_used"]
    out["n_feature_used"] = fu.groupby("user_id").size()
    for k in FEATURE_KINDS:
        out[f"n_fu_{k}"] = fu[fu["value"] == k].groupby("user_id").size()
    out["n_payment"] = w[w["event"] == "payment"].groupby("user_id").size()
    out["n_payment_failed"] = w[w["event"] == "payment_failed"].groupby("user_id").size()
    out["n_support_ticket"] = w[w["event"] == "support_ticket"].groupby("user_id").size()
    out["had_downgrade"] = (w[w["event"] == "plan_downgrade"].groupby("user_id").size() > 0).astype(float)
    last = w.groupby("user_id")["ts"].max()
    out["days_since_last_event"] = (T - last).dt.total_seconds() / 86400
    first_s = ss.groupby("user_id")["ts"].min()
    out["days_to_first_session"] = (first_s - su["signup_ts"]).dt.total_seconds() / 86400
    # заполнение: счётчики 0; mean/max value 0 при отсутствии сессий; первая сессия не до T -> цензура D
    fill0 = [c for c in BEHAV if c not in ("days_since_last_event", "days_to_first_session")]
    out[fill0] = out[fill0].fillna(0.0)
    out["days_to_first_session"] = out["days_to_first_session"].fillna(float(D))
    out[BEHAV] = out[BEHAV].astype(float)
    out["signup_ts"] = su["signup_ts"]
    out = out[~out.index.isin(canc_before)]
    return out.sort_index()


def build_label(df, feats, D):
    """Метка: cancel в (T, T+60 суток]. Использует события после T — только для y, не для признаков."""
    T = feats["signup_ts"] + pd.Timedelta(days=D)
    can = df[df["event"] == "cancel"].groupby("user_id")["ts"].min().reindex(feats.index)
    y = ((can > T) & (can <= T + pd.Timedelta(days=HORIZON_DAYS))).astype(int)
    return y


# ----------------------------------------------------------------------------
# Модели и метрики
# ----------------------------------------------------------------------------
CAT_STATIC = ["plan_T", "device", "country", "channel"]


def make_lr(cols_num, cols_cat, C=1.0, log1p=False):
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
    num_steps = []
    if log1p:
        num_steps.append(("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")))
    num_steps.append(("sc", StandardScaler()))
    tr = []
    if cols_num:
        tr.append(("num", Pipeline(num_steps), cols_num))
    if cols_cat:
        tr.append(("cat", Pipeline([("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                                    ("sc", StandardScaler())]), cols_cat))
    return Pipeline([("pre", ColumnTransformer(tr)),
                     ("clf", LogisticRegression(C=C, max_iter=5000, random_state=SEED))])


def make_hgb(cols_num, cols_cat, learning_rate=0.1, max_leaf_nodes=15, min_samples_leaf=20, max_iter=200):
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    tr = [("num", "passthrough", cols_num),
          ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cols_cat)]
    return Pipeline([("pre", ColumnTransformer(tr)),
                     ("clf", HistGradientBoostingClassifier(learning_rate=learning_rate, max_leaf_nodes=max_leaf_nodes,
                                                            min_samples_leaf=min_samples_leaf, max_iter=max_iter,
                                                            early_stopping=False, random_state=SEED))])


def oof_predict(make_model, X, y, seed=SEED, return_folds=False):
    from sklearn.model_selection import StratifiedKFold
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    oof = np.zeros(len(y))
    folds = np.zeros(len(y), dtype=int)
    models = []
    for k, (tr, va) in enumerate(skf.split(X, y)):
        m = make_model()
        m.fit(X.iloc[tr], y[tr])
        oof[va] = m.predict_proba(X.iloc[va])[:, 1]
        folds[va] = k
        models.append(m)
    if return_folds:
        return oof, folds, models
    return oof


def auc_fast(y, s):
    """ROC AUC через ранги (средние ранги при равенствах). Поддерживает 2D s (строки = варианты)."""
    y = np.asarray(y)
    n1 = y.sum()
    n0 = len(y) - n1
    r = rankdata(s, axis=-1)
    return (r[..., y == 1].sum(axis=-1) - n1 * (n1 + 1) / 2) / (n1 * n0)


def ap_score(y, s):
    from sklearn.metrics import average_precision_score
    return average_precision_score(y, s)


def top_share(y, s, frac=0.2):
    """Доля уходящих среди frac пользователей с наибольшим риском; равенства на границе —
    математическое ожидание при случайном разбиении (детерминированно)."""
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    n = len(y)
    k = int(np.ceil(frac * n))
    order = np.sort(s)[::-1]
    cut = order[k - 1]
    above = s > cut
    at = s == cut
    n_above = above.sum()
    pos = y[above].sum() + (k - n_above) * (y[at].mean() if at.any() else 0.0)
    return pos / k


def boot_idx(n, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    return rng.integers(0, n, size=(n_boot, n))


def ci(a):
    a = np.asarray(a, dtype=float)
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


# ----------------------------------------------------------------------------
# Этап 1 — входная проверка D=7 (только dev)
# ----------------------------------------------------------------------------
def gate(df, holdout, out_dir):
    t0 = time.time()
    D = 7
    F = build_features(df, D)
    y_all = build_label(df, F, D)
    dev = ~F.index.isin(holdout)
    X = F.loc[dev]
    y = y_all.loc[dev].to_numpy()
    n_pop, n_pos = int(len(y)), int(y.sum())
    print(f"GATE D=7: dev-популяция {n_pop}, положительных {n_pos} (доля {n_pos / n_pop:.4f})")
    res = {"D": D, "n_population_dev": n_pop, "n_positive_dev": n_pos, "pos_rate": n_pos / n_pop}
    if n_pos < 100:
        res["outcome"] = "данных недостаточно (меньше 100 положительных)"
        print(res["outcome"])
    oof_a = oof_predict(lambda: make_lr([], CAT_STATIC, C=1.0), X, y)
    oof_b = oof_predict(lambda: make_lr(BEHAV, CAT_STATIC, C=1.0), X, y)
    auc_a, auc_b = float(auc_fast(y, oof_a)), float(auc_fast(y, oof_b))
    idx = boot_idx(len(y))
    ba, bb = [], []
    for ii in idx:
        ba.append(auc_fast(y[ii], oof_a[ii]))
        bb.append(auc_fast(y[ii], oof_b[ii]))
    ba, bb = np.array(ba), np.array(bb)
    res.update({"auc_A_static": auc_a, "auc_A_ci": ci(ba), "auc_B": auc_b, "auc_B_ci": ci(bb),
                "diff_B_minus_A": auc_b - auc_a, "diff_ci": ci(bb - ba)})
    passed = (auc_b >= 0.65) and (res["diff_ci"][0] > 0) and n_pos >= 100
    res["criterion"] = "ROC AUC(Б) >= 0.65 и нижняя граница 95% ДИ разности Б−А > 0; при <100 положительных — неприменим"
    res.setdefault("outcome", "пройдена" if passed else "не пройдена")
    res["elapsed_sec"] = time.time() - t0
    print("AUC(А, статика) = %.4f [%.4f; %.4f]" % (auc_a, *res["auc_A_ci"]))
    print("AUC(Б, статика+поведение) = %.4f [%.4f; %.4f]" % (auc_b, *res["auc_B_ci"]))
    print("AUC(Б) − AUC(А) = %.4f [%.4f; %.4f]" % (res["diff_B_minus_A"], *res["diff_ci"]))
    print("исход:", res["outcome"], "| секунд:", round(res["elapsed_sec"], 1))
    with open(os.path.join(out_dir, "gate.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return res


# ----------------------------------------------------------------------------
# Этап 2 — базовая ветка D=14
# ----------------------------------------------------------------------------
LR_GRID = [{"kind": "lr", "C": C, "log1p": lg} for C in (0.01, 0.1, 1.0, 10.0) for lg in (False, True)]
HGB_GRID = [{"kind": "hgb", "learning_rate": lr, "max_leaf_nodes": mln, "min_samples_leaf": msl, "max_iter": 150}
            for lr in (0.03, 0.1) for mln in (7, 31) for msl in (20, 100)]
STATIC_GRID = [{"kind": "lr_static", "C": C} for C in (0.01, 0.1, 1.0, 10.0)]
CORR_THRESHOLD = 0.8  # |Spearman| на dev, задан до расчёта
N_PERM_HOLDOUT = 30
N_PERM_DEV = 10


def model_from_cfg(cfg):
    if cfg["kind"] == "lr":
        return lambda: make_lr(BEHAV, CAT_STATIC, C=cfg["C"], log1p=cfg["log1p"])
    if cfg["kind"] == "hgb":
        return lambda: make_hgb(BEHAV, CAT_STATIC, learning_rate=cfg["learning_rate"], max_leaf_nodes=cfg["max_leaf_nodes"],
                                min_samples_leaf=cfg["min_samples_leaf"], max_iter=cfg["max_iter"])
    if cfg["kind"] == "lr_static":
        return lambda: make_lr([], CAT_STATIC, C=cfg["C"])
    raise ValueError(cfg)


def cfg_name(cfg):
    return ",".join(f"{k}={v}" for k, v in cfg.items())


def cv_grid(grid, X, y):
    rows = []
    for cfg in grid:
        oof, folds, _ = oof_predict(model_from_cfg(cfg), X, y, return_folds=True)
        fa = [float(auc_fast(y[folds == k], oof[folds == k])) for k in range(5)]
        rows.append({"cfg": cfg_name(cfg), "oof_auc": float(auc_fast(y, oof)), "fold_mean": float(np.mean(fa)),
                     "fold_sd": float(np.std(fa, ddof=1)), "_cfg": cfg, "_oof": oof})
    return rows


def metric_boot(y, scores, idx):
    """scores: dict name -> вектор. Возвращает точечные значения, ДИ и бутстрэп-массивы."""
    out = {}
    br = {}
    for name, s in scores.items():
        auc_b, ap_b, top_b, lift_b = [], [], [], []
        for ii in idx:
            yy, ss = y[ii], s[ii]
            auc_b.append(auc_fast(yy, ss))
            ap_b.append(ap_score(yy, ss))
            t = top_share(yy, ss)
            top_b.append(t)
            lift_b.append(t / yy.mean())
        t0 = top_share(y, s)
        out[name] = {"roc_auc": float(auc_fast(y, s)), "roc_auc_ci": ci(auc_b),
                     "pr_auc": float(ap_score(y, s)), "pr_auc_ci": ci(ap_b),
                     "top20_share": float(t0), "top20_share_ci": ci(top_b),
                     "lift_top20": float(t0 / y.mean()), "lift_top20_ci": ci(lift_b)}
        br[name] = {"roc_auc": np.array(auc_b), "pr_auc": np.array(ap_b), "lift_top20": np.array(lift_b),
                    "top20_share": np.array(top_b)}
    return out, br


def corr_groups(X, cols, thr=CORR_THRESHOLD):
    v = X[cols]
    var = v.std() > 0
    cols_v = [c for c in cols if var[c]]
    rho = v[cols_v].corr(method="spearman").abs()
    # компоненты связности графа |rho| >= thr
    parent = {c: c for c in cols_v}

    def find(a):
        while parent[a] != a:
            a = parent[a]
        return a
    for i, a in enumerate(cols_v):
        for b in cols_v[i + 1:]:
            if rho.loc[a, b] >= thr:
                parent[find(a)] = find(b)
    comp = {}
    for c in cols_v:
        comp.setdefault(find(c), []).append(c)
    groups = [sorted(g, key=cols.index) for g in comp.values() if len(g) > 1]
    return groups, rho


def perm_preds(model, X, units, n_perm, rng, rows=None):
    """Для каждой единицы — матрица (n_perm, n) предсказаний при перестановке её колонок
    (одна перестановка строк на всю группу колонок). rows — маска строк, внутри которых переставлять."""
    n = len(X)
    if rows is None:
        rows = np.ones(n, dtype=bool)
    pos = np.where(rows)[0]
    Xs = X.iloc[pos]
    res = {}
    for name, cols in units:
        P = np.empty((n_perm, len(pos)))
        for j in range(n_perm):
            perm = rng.permutation(len(pos))
            Xp = Xs.copy()
            for c in cols:
                Xp[c] = Xs[c].to_numpy()[perm]
            P[j] = model.predict_proba(Xp)[:, 1]
        res[name] = P
    return res


def stage2(df, holdout, out_dir):
    t0 = time.time()
    D = 14
    F = build_features(df, D)
    yall = build_label(df, F, D)
    is_ho = F.index.isin(holdout)
    Xd, Xh = F.loc[~is_ho], F.loc[is_ho]
    yd, yh = yall.loc[~is_ho].to_numpy(), yall.loc[is_ho].to_numpy()
    R = {"D": D, "n_dev": int(len(yd)), "pos_dev": int(yd.sum()), "n_holdout": int(len(yh)), "pos_holdout": int(yh.sum()),
         "base_rate_dev": float(yd.mean()), "base_rate_holdout": float(yh.mean())}
    R["holdout_ids_in_dev"] = int(np.isin(Xd.index, list(holdout)).sum())
    print(f"D=14: dev {len(yd)} / положительных {yd.sum()} ({yd.mean():.4f}); holdout {len(yh)} / {yh.sum()} ({yh.mean():.4f});"
          f" id holdout в dev: {R['holdout_ids_in_dev']}")

    # проверка одиночных AUC до включения в модель (dev)
    single = {c: float(auc_fast(yd, Xd[c].to_numpy())) for c in BEHAV}
    R["single_feature_auc_dev"] = single
    R["single_feature_auc_gt_0_90"] = [c for c, a in single.items() if max(a, 1 - a) > 0.90]
    R["constant_features_dev"] = [c for c in BEHAV if Xd[c].std() == 0]
    print("одиночные AUC (dev):", {c: round(a, 3) for c, a in single.items()})
    print("признаки с max(AUC,1-AUC) > 0.90:", R["single_feature_auc_gt_0_90"], "| константы на dev:", R["constant_features_dev"])

    # корреляционные группы (dev)
    groups, rho = corr_groups(Xd, BEHAV)
    R["corr_groups"] = groups
    rho.round(3).to_csv(os.path.join(out_dir, "stage2_spearman_dev.csv"))
    print("группы |Spearman| >= %.1f (dev):" % CORR_THRESHOLD, groups)

    # CV-сетка на dev
    rows = cv_grid(LR_GRID + HGB_GRID, Xd, yd)
    srows = cv_grid(STATIC_GRID, Xd, yd)
    cvtab = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows + srows])
    cvtab.to_csv(os.path.join(out_dir, "stage2_cv_grid.csv"), index=False)
    print("CV-сетка (dev):\n" + cvtab.round(4).to_string(index=False))
    best = max(rows, key=lambda r: r["oof_auc"])
    best_lr = max([r for r in rows if r["_cfg"]["kind"] == "lr"], key=lambda r: r["oof_auc"])
    best_st = max(srows, key=lambda r: r["oof_auc"])
    R["n_configs_tried"] = {"model": len(rows), "static": len(srows)}
    R["selected_model"] = best["cfg"]
    R["selected_static"] = best_st["cfg"]
    R["best_lr"] = best_lr["cfg"]
    print("выбрана модель:", best["cfg"], "| статический бейзлайн:", best_st["cfg"])

    # OOF на dev для сравнения (справочно)
    idx_d = boot_idx(len(yd))
    rule_d = -Xd["n_sessions"].to_numpy()
    cvm, cvb = metric_boot(yd, {"model": best["_oof"], "static_lr": best_st["_oof"], "rule_sessions": rule_d}, idx_d)
    d_ms = cvb["model"]["roc_auc"] - cvb["static_lr"]["roc_auc"]
    R["dev_oof"] = cvm
    R["dev_oof_diff_model_static"] = {"value": cvm["model"]["roc_auc"] - cvm["static_lr"]["roc_auc"], "ci": ci(d_ms),
                                       "sd": float(np.std(d_ms, ddof=1))}
    print("dev OOF: AUC модель %.4f, статика %.4f, разность %.4f [%.4f; %.4f]" % (
        cvm["model"]["roc_auc"], cvm["static_lr"]["roc_auc"], R["dev_oof_diff_model_static"]["value"], *R["dev_oof_diff_model_static"]["ci"]))

    # диагностика (dev OOF): качество по сроку от T до cancel у положительных
    Td = Xd["signup_ts"] + pd.Timedelta(days=D)
    cd = df[df["event"] == "cancel"].groupby("user_id")["ts"].min().reindex(Xd.index)
    lead = ((cd - Td).dt.total_seconds() / 86400).to_numpy()
    lead_tab = {}
    for lo_, hi_ in [(0, 14), (14, 30), (30, 60)]:
        msk = (yd == 0) | ((yd == 1) & (lead > lo_) & (lead <= hi_))
        yy, ss = yd[msk], best["_oof"][msk]
        bb = [auc_fast(yy[ii], ss[ii]) for ii in boot_idx(len(yy))]
        lead_tab[f"({lo_},{hi_}]"] = {"n_pos": int(yy.sum()), "auc": float(auc_fast(yy, ss)), "ci": ci(bb)}
        print("dev OOF: положительные с cancel через (%d; %d] сут после T: n=%d, AUC против всех отрицательных %.4f [%.4f; %.4f]" % (
            lo_, hi_, yy.sum(), lead_tab[f"({lo_},{hi_}]"]["auc"], *lead_tab[f"({lo_},{hi_}]"]["ci"]))
    R["dev_oof_auc_by_lead_time"] = lead_tab

    # финальные модели на всём dev, одна оценка на holdout
    m = model_from_cfg(best["_cfg"])()
    m.fit(Xd, yd)
    ms = model_from_cfg(best_st["_cfg"])()
    ms.fit(Xd, yd)
    p_model = m.predict_proba(Xh)[:, 1]
    p_static = ms.predict_proba(Xh)[:, 1]
    p_rule = -Xh["n_sessions"].to_numpy()
    p_base = np.full(len(yh), yd.mean())
    idx_h = boot_idx(len(yh))
    hm, hb = metric_boot(yh, {"model": p_model, "static_lr": p_static, "rule_sessions": p_rule, "base_rate": p_base}, idx_h)
    R["holdout"] = hm
    diffs = {}
    for other in ["static_lr", "rule_sessions", "base_rate"]:
        for met in ["roc_auc", "pr_auc", "lift_top20"]:
            dd = hb["model"][met] - hb[other][met]
            diffs[f"model-{other}:{met}"] = {"value": hm["model"][met] - hm[other][met], "ci": ci(dd), "sd": float(np.std(dd, ddof=1))}
    R["holdout_diffs"] = diffs
    tab = pd.DataFrame(hm).T
    tab.to_csv(os.path.join(out_dir, "stage2_holdout_metrics.csv"))
    print("HOLDOUT (одна оценка):")
    for name, v in hm.items():
        print("  %-14s ROC AUC %.4f [%.4f; %.4f] | PR AUC %.4f [%.4f; %.4f] | доля уходящих в топ-20%% %.4f [%.4f; %.4f] | лифт %.3f [%.3f; %.3f]" % (
            name, v["roc_auc"], *v["roc_auc_ci"], v["pr_auc"], *v["pr_auc_ci"], v["top20_share"], *v["top20_share_ci"],
            v["lift_top20"], *v["lift_top20_ci"]))
    for k, v in diffs.items():
        print("  %-32s %.4f [%.4f; %.4f]" % (k, v["value"], *v["ci"]))

    # 2.5: отрицательный результат и объём
    dms = diffs["model-static_lr:roc_auc"]
    R["negative_result"] = bool(dms["ci"][0] <= 0)
    za, zb = 1.959964, 0.841621  # 95 % двусторонний, мощность 80 %
    vol = {}
    for src, d_val, sd, n in [("holdout", dms["value"], dms["sd"], len(yh)),
                              ("dev_oof", R["dev_oof_diff_model_static"]["value"], R["dev_oof_diff_model_static"]["sd"], len(yd))]:
        if d_val > 0:
            vol[src] = {"diff": d_val, "sd": sd, "n": n,
                        "n_for_ci_lower_gt0": float(n * (za * sd / d_val) ** 2),
                        "n_for_80pct_power": float(n * ((za + zb) * sd / d_val) ** 2)}
        else:
            vol[src] = {"diff": d_val, "sd": sd, "n": n, "note": "разность ≤ 0, объём не оценивается"}
    R["volume_estimate"] = vol
    print("отрицательный результат (нижняя граница ДИ разности ≤ 0):", R["negative_result"], "| объём:", vol)

    # 2.4 перестановочная важность на holdout
    static_units = [(c, [c]) for c in CAT_STATIC]
    beh_units = [(c, [c]) for c in BEHAV]
    group_units = [("grp:" + "+".join(g), g) for g in groups]
    units = beh_units + static_units + group_units
    rng = np.random.default_rng(SEED)
    P = perm_preds(m, Xh, units, N_PERM_HOLDOUT, rng)
    auc0 = auc_fast(yh, p_model)
    imp = {}
    base_b = np.array([auc_fast(yh[ii], p_model[ii]) for ii in idx_h])
    for name, _ in units:
        point = float(auc0 - auc_fast(yh, P[name]).mean())
        bdrop = np.array([base_b[b] - auc_fast(yh[ii], P[name][:, ii]).mean() for b, ii in enumerate(idx_h)])
        c = ci(bdrop)
        sd_b = float(np.std(bdrop, ddof=1))
        cols_u = dict(units)[name]
        const = bool(all(Xh[c].nunique() == 1 for c in cols_u))
        # объём holdout, при котором нижняя граница ДИ была бы > 0 при той же точечной оценке (SE ~ 1/sqrt(n))
        n_need = float(len(yh) * (1.959964 * sd_b / point) ** 2) if (point > 0 and c[0] <= 0) else None
        imp[name] = {"drop_auc": point, "ci": c, "indistinguishable_from_0": bool(c[0] <= 0 <= c[1]),
                     "boot_sd": sd_b, "constant_on_holdout": const, "n_holdout_needed_for_ci_lo_gt_0": n_need,
                     "perm_sd": float(auc_fast(yh, P[name]).std(ddof=1))}
    indiv = [u for u, _ in beh_units + static_units]
    ranked = sorted(indiv, key=lambda u: -imp[u]["drop_auc"])
    for r_, u in enumerate(ranked, 1):
        imp[u]["rank"] = r_
    R["perm_importance_holdout"] = imp
    R["ranking_holdout"] = ranked

    # направление: знак ЛР (лучшая ЛР по CV, обучена на dev), частичная зависимость выбранной модели, Spearman на dev
    mlr = model_from_cfg(best_lr["_cfg"])()
    mlr.fit(Xd, yd)
    coef = pd.Series(mlr.named_steps["clf"].coef_[0], index=mlr.named_steps["pre"].get_feature_names_out())
    coef.to_csv(os.path.join(out_dir, "stage2_lr_coef.csv"), header=["coef_std"])
    direction = {}
    for u in ranked[:10]:
        if u in CAT_STATIC:
            cats = sorted(Xd[u].unique())
            pdv = {}
            for cval in cats:
                Xt = Xd.copy()
                Xt[u] = cval
                pdv[cval] = float(m.predict_proba(Xt)[:, 1].mean())
            lrc = {k.split("__", 1)[1]: float(v) for k, v in coef.items() if k.startswith(f"cat__{u}_")}
            rate = Xd.assign(y=yd).groupby(u)["y"].mean().round(4).to_dict()
            direction[u] = {"type": "category", "pd_selected_model": pdv, "lr_coef_std": lrc, "label_rate_dev": rate}
        else:
            lo, hi = np.percentile(Xd[u], [10, 90])
            if lo == hi:
                lo, hi = float(Xd[u].min()), float(Xd[u].max())
            Xt = Xd.copy()
            Xt[u] = lo
            p_lo = float(m.predict_proba(Xt)[:, 1].mean())
            Xt[u] = hi
            p_hi = float(m.predict_proba(Xt)[:, 1].mean())
            lrc = float(coef.get(f"num__{u}", np.nan))
            rs = float(spearmanr(Xd[u], yd).correlation) if Xd[u].std() > 0 else float("nan")
            xb = Xd[u]
            if xb.nunique() <= 3:
                bins = xb.astype(str)
            else:
                bins = pd.qcut(xb, 4, duplicates="drop").astype(str)
            emp = pd.DataFrame({"b": bins, "y": yd}).groupby("b", sort=False)["y"].agg(["mean", "size"])
            emp = emp.loc[sorted(emp.index, key=lambda t: float(t.strip("([").split(",")[0]))]
            emp_d = {k: [round(float(r["mean"]), 4), int(r["size"])] for k, r in emp.iterrows()}
            direction[u] = {"type": "numeric", "pd_lo_hi": [float(lo), float(hi)], "pd_selected_model": [p_lo, p_hi],
                            "label_rate_by_bin_dev": emp_d,
                            "pd_sign": int(np.sign(p_hi - p_lo)), "lr_coef_std": lrc, "lr_sign": int(np.sign(lrc)) if lrc == lrc else 0,
                            "spearman_dev": rs}
    R["direction_top10"] = direction

    # устойчивость: фолды dev и сегменты (plan, квартал регистрации) на OOF
    oof, folds, fmodels = oof_predict(model_from_cfg(best["_cfg"]), Xd, yd, return_folds=True)
    rng2 = np.random.default_rng(SEED + 1)
    indiv_units = beh_units + static_units
    quarter = ((Xd["signup_ts"].dt.month - 1) // 3 + 1).to_numpy()
    plan = Xd["plan_T"].to_numpy()
    segments = {f"fold{k}": folds == k for k in range(5)}
    segments.update({"plan=basic": plan == "basic", "plan=pro": plan == "pro",
                     "Q1": quarter == 1, "Q2": quarter == 2, "Q3": quarter == 3})
    stab = {}
    for sname, mask in segments.items():
        drops = {u: [] for u, _ in indiv_units}
        base_pred = oof[mask]
        ys = yd[mask]
        auc_base = auc_fast(ys, base_pred)
        # перестановка внутри (сегмент ∩ фолд k), предсказание моделью фолда k
        perm_pred = {u: np.empty((N_PERM_DEV, mask.sum())) for u, _ in indiv_units}
        pos_in_mask = np.cumsum(mask) - 1
        for k in range(5):
            rows_k = mask & (folds == k)
            if rows_k.sum() == 0:
                continue
            Pk = perm_preds(fmodels[k], Xd, indiv_units, N_PERM_DEV, rng2, rows=rows_k)
            where = pos_in_mask[rows_k]
            for u, _ in indiv_units:
                perm_pred[u][:, where] = Pk[u]
        for u, _ in indiv_units:
            drops[u] = float(auc_base - auc_fast(ys, perm_pred[u]).mean())
        stab[sname] = {"n": int(mask.sum()), "pos": int(ys.sum()), "auc_oof": float(auc_base), "drop": drops}
    ho_vec = np.array([imp[u]["drop_auc"] for u, _ in indiv_units])
    top5_ho = set(ranked[:5])
    stab_rows = []
    for sname, s in stab.items():
        vec = np.array([s["drop"][u] for u, _ in indiv_units])
        order = [u for u, _ in sorted(zip([u for u, _ in indiv_units], vec), key=lambda t: -t[1])]
        s["ranking"] = order
        s["top5"] = order[:5]
        s["top5_overlap_with_holdout"] = len(set(order[:5]) & top5_ho)
        s["spearman_with_holdout"] = float(spearmanr(vec, ho_vec).correlation)
        stab_rows.append({"segment": sname, "n": s["n"], "pos": s["pos"], "auc_oof": round(s["auc_oof"], 4),
                          "top5": ", ".join(order[:5]), "top5_overlap": s["top5_overlap_with_holdout"],
                          "spearman_vs_holdout": round(s["spearman_with_holdout"], 3)})
    R["stability"] = stab
    # ранги каждой единицы по сегментам
    rank_tab = pd.DataFrame({sname: {u: s["ranking"].index(u) + 1 for u, _ in indiv_units} for sname, s in stab.items()})
    rank_tab.insert(0, "holdout", [imp[u]["rank"] for u in rank_tab.index])
    rank_tab = rank_tab.sort_values("holdout")
    rank_tab.to_csv(os.path.join(out_dir, "stage2_rank_stability.csv"))
    pd.DataFrame(stab_rows).to_csv(os.path.join(out_dir, "stage2_stability_summary.csv"), index=False)

    # таблица важности
    imp_rows = []
    for u, _ in units:
        row = {"unit": u, "rank_holdout": imp[u].get("rank", ""), "drop_auc": imp[u]["drop_auc"], "ci_lo": imp[u]["ci"][0],
               "ci_hi": imp[u]["ci"][1], "indistinguishable_from_0": imp[u]["indistinguishable_from_0"],
               "constant_on_holdout": imp[u]["constant_on_holdout"],
               "n_holdout_needed": (round(imp[u]["n_holdout_needed_for_ci_lo_gt_0"]) if imp[u]["n_holdout_needed_for_ci_lo_gt_0"] else "")}
        if u in direction:
            dct = direction[u]
            if dct["type"] == "numeric":
                row["direction"] = (f"PD {dct['pd_selected_model'][0]:.4f}->{dct['pd_selected_model'][1]:.4f} при {dct['pd_lo_hi'][0]:g}->{dct['pd_lo_hi'][1]:g}; "
                                    f"ЛР {dct['lr_coef_std']:+.4f}; Spearman {dct['spearman_dev']:+.4f}; доля метки по бинам dev "
                                    + " | ".join(f"{k}: {v[0]:.3f} (n={v[1]})" for k, v in dct["label_rate_by_bin_dev"].items()))
            else:
                row["direction"] = "PD " + "; ".join(f"{k}={v:.4f}" for k, v in dct["pd_selected_model"].items())
        if u in rank_tab.index:
            rr = rank_tab.loc[u].drop("holdout")
            row["rank_min_max_dev"] = f"{int(rr.min())}-{int(rr.max())}"
        imp_rows.append(row)
    imp_tab = pd.DataFrame(imp_rows)
    imp_tab["_o"] = [int(v) if v != "" else 999 for v in imp_tab["rank_holdout"]]
    imp_tab = imp_tab.sort_values(["_o", "drop_auc"], ascending=[True, False]).drop(columns="_o")
    imp_tab.to_csv(os.path.join(out_dir, "stage2_importance.csv"), index=False)
    print("Перестановочная важность (holdout, %d перестановок, бутстрэп %d):" % (N_PERM_HOLDOUT, N_BOOT))
    print(imp_tab.to_string(index=False))
    print("Ранги по фолдам и сегментам dev:\n" + rank_tab.to_string())
    print("Сводка устойчивости:\n" + pd.DataFrame(stab_rows).to_string(index=False))
    R["elapsed_sec"] = time.time() - t0
    print("секунд:", round(R["elapsed_sec"], 1))
    with open(os.path.join(out_dir, "stage2.json"), "w") as f:
        json.dump(R, f, ensure_ascii=False, indent=1, default=float)
    # предсказания holdout — для независимой сверки
    pd.DataFrame({"user_id": Xh.index, "y": yh, "p_model": p_model, "p_static": p_static, "rule_neg_sessions": p_rule}).to_csv(
        os.path.join(out_dir, "stage2_holdout_predictions.csv"), index=False)
    return R, best["_cfg"]


# ----------------------------------------------------------------------------
# Тест на опровержение: перемешанные метки на dev
# ----------------------------------------------------------------------------
def refute(df, holdout, out_dir, selected_cfg):
    t0 = time.time()
    D = 14
    F = build_features(df, D)
    y = build_label(df, F, D)
    dev = ~F.index.isin(holdout)
    Xd, yd = F.loc[dev], y.loc[dev].to_numpy()
    rng = np.random.default_rng(SEED)
    ysh = rng.permutation(yd)
    R = {"D": D, "n": int(len(ysh)), "pos": int(ysh.sum())}
    rows = cv_grid(LR_GRID + HGB_GRID, Xd, ysh)
    best = max(rows, key=lambda r: r["oof_auc"])
    idx = boot_idx(len(ysh))
    b = np.array([auc_fast(ysh[ii], best["_oof"][ii]) for ii in idx])
    R["full_pipeline"] = {"selected_on_shuffled": best["cfg"], "oof_auc": best["oof_auc"], "ci": ci(b),
                          "ci_contains_0.5": bool(ci(b)[0] <= 0.5 <= ci(b)[1]),
                          "all_configs_oof_auc": {r["cfg"]: r["oof_auc"] for r in rows}}
    fixed = [r for r in rows if r["_cfg"] == selected_cfg][0]
    b2 = np.array([auc_fast(ysh[ii], fixed["_oof"][ii]) for ii in idx])
    R["fixed_selected_cfg"] = {"cfg": fixed["cfg"], "oof_auc": fixed["oof_auc"], "ci": ci(b2),
                               "ci_contains_0.5": bool(ci(b2)[0] <= 0.5 <= ci(b2)[1])}
    # gate-пайплайн (D=7, ЛР Б) на перемешанных метках
    F7 = build_features(df, 7)
    y7 = build_label(df, F7, 7)
    dev7 = ~F7.index.isin(holdout)
    y7sh = np.random.default_rng(SEED).permutation(y7.loc[dev7].to_numpy())
    oof7 = oof_predict(lambda: make_lr(BEHAV, CAT_STATIC, C=1.0), F7.loc[dev7], y7sh)
    b3 = np.array([auc_fast(y7sh[ii], oof7[ii]) for ii in boot_idx(len(y7sh))])
    R["gate_pipeline_D7"] = {"oof_auc": float(auc_fast(y7sh, oof7)), "ci": ci(b3), "ci_contains_0.5": bool(ci(b3)[0] <= 0.5 <= ci(b3)[1])}
    R["elapsed_sec"] = time.time() - t0
    print("ОПРОВЕРЖЕНИЕ (перемешанные метки, dev, seed 42):")
    print("  полный пайплайн (сетка %d конфигураций, выбор по CV): %s, OOF AUC %.4f [%.4f; %.4f], 0.5 внутри: %s" % (
        len(rows), best["cfg"], best["oof_auc"], *R["full_pipeline"]["ci"], R["full_pipeline"]["ci_contains_0.5"]))
    print("  выбранная на реальных метках конфигурация: OOF AUC %.4f [%.4f; %.4f], 0.5 внутри: %s" % (
        fixed["oof_auc"], *R["fixed_selected_cfg"]["ci"], R["fixed_selected_cfg"]["ci_contains_0.5"]))
    print("  пайплайн проверки D=7 (ЛР Б): OOF AUC %.4f [%.4f; %.4f], 0.5 внутри: %s" % (
        R["gate_pipeline_D7"]["oof_auc"], *R["gate_pipeline_D7"]["ci"], R["gate_pipeline_D7"]["ci_contains_0.5"]))
    with open(os.path.join(out_dir, "refute.json"), "w") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    return R


# ----------------------------------------------------------------------------
# Выгрузка таблицы признаков на T (проверка (б))
# ----------------------------------------------------------------------------
def export_features(df, D, path, holdout=None):
    F = build_features(df, D)
    out = F.copy()
    out.insert(0, "T", (F["signup_ts"] + pd.Timedelta(days=D)).dt.strftime("%Y-%m-%dT%H:%M:%S"))
    out["signup_ts"] = F["signup_ts"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    if holdout is not None:
        out.insert(0, "split", np.where(F.index.isin(holdout), "holdout", "dev"))
    out.index.name = "user_id"
    out.to_csv(path)  # float пишутся repr (кратчайшее точное представление)
    return out


def compare_feature_tables(a_path, b_path, tol=1e-9):
    a = pd.read_csv(a_path, index_col="user_id").sort_index()
    b = pd.read_csv(b_path, index_col="user_id").sort_index()
    if list(a.index) != list(b.index) or list(a.columns) != list(b.columns):
        return {"same_shape": False, "rows": [len(a), len(b)]}
    num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c])]
    oth = [c for c in a.columns if c not in num]
    return {"same_shape": True, "rows": len(a), "max_abs_diff": float((a[num] - b[num]).abs().to_numpy().max()),
            "non_numeric_equal": bool((a[oth] == b[oth]).all().all()), "tol": tol,
            "ok": bool((a[num] - b[num]).abs().to_numpy().max() <= tol and (a[oth] == b[oth]).all().all())}


def truncate_after_T(df, D):
    su = signup_table(df)
    T = (su["signup_ts"] + pd.Timedelta(days=D)).rename("T")
    x = df.merge(T, left_on="user_id", right_index=True)
    return x[x["ts"] <= x["T"]].drop(columns="T")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["split", "quality", "gate", "stage2", "refute", "export", "all"])
    ap.add_argument("--csv", required=True, help="сырой events_2025.csv")
    ap.add_argument("--out", default="results", help="каталог результатов")
    ap.add_argument("--holdout-file-dir", default=os.path.dirname(os.path.abspath(__file__)),
                    help="каталог holdout_ids.txt (по умолчанию рядом со скриптом)")
    ap.add_argument("--D", type=int, default=14, help="срез для export")
    ap.add_argument("--features-out", default=None, help="путь CSV для export")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    df = load_events(a.csv)
    print("CSV:", a.csv, "| SHA-256:", sha256_file(a.csv), "| строк:", len(df))
    if a.mode in ("split", "all"):
        ho, digest, bm = make_holdout(df, a.holdout_file_dir)
        print("holdout: %d id, SHA-256 holdout_ids.txt = %s" % (len(ho), digest))
    ho = load_holdout(a.holdout_file_dir)
    if a.mode == "export":
        path = a.features_out or os.path.join(a.out, f"features_D{a.D}.csv")
        out = export_features(df, a.D, path, ho)
        print("таблица признаков:", path, out.shape)
        return
    summary = {}
    if a.mode in ("quality", "all"):
        quality(df, ho, a.out)
        quality_extra(df, ho, a.out)
    if a.mode in ("gate", "all"):
        g = gate(df, ho, a.out)
        summary["gate"] = {k: g[k] for k in ["auc_B", "auc_B_ci", "diff_B_minus_A", "diff_ci", "n_population_dev", "n_positive_dev", "outcome"]}
    sel = None
    if a.mode in ("stage2", "all"):
        r2, sel = stage2(df, ho, a.out)
        summary["stage2_holdout"] = r2["holdout"]
        summary["stage2_diffs"] = {k: v for k, v in r2["holdout_diffs"].items()}
        summary["importance"] = {u: r2["perm_importance_holdout"][u]["drop_auc"] for u in r2["perm_importance_holdout"]}
        path = os.path.join(a.out, "features_D14.csv")
        export_features(df, 14, path, ho)
        F = build_features(df, 14)
        build_label(df, F, 14).rename("y").to_csv(os.path.join(a.out, "labels_D14.csv"), index_label="user_id")
        # самопроверка (б): обрезка событий после T и пересчёт
        tpath = os.path.join(a.out, "features_D14_truncated.csv")
        export_features(truncate_after_T(df, 14), 14, tpath, ho)
        cmp = compare_feature_tables(path, tpath)
        summary["truncation_check_D14"] = cmp
        print("проверка (б) — признаки по данным, обрезанным после T:", cmp)
    if a.mode in ("refute", "all"):
        if sel is None:
            with open(os.path.join(a.out, "stage2.json")) as f:
                s2 = json.load(f)
            sel = [c for c in LR_GRID + HGB_GRID if cfg_name(c) == s2["selected_model"]][0]
        rr = refute(df, ho, a.out, sel)
        summary["refute"] = {k: rr[k] for k in ["full_pipeline", "fixed_selected_cfg", "gate_pipeline_D7"]}
    if summary:
        with open(os.path.join(a.out, f"summary_{a.mode}.json"), "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main()
