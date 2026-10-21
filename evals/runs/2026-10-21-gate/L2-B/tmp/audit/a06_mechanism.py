# Аудит: (1) бывают ли pf/dg/ticket у неушедших; (2) обусловлены ли предвестники будущим cancel (край года);
# (3) календарный спад ухода в декабре при той же длительности жизни; (4) анкета ухода против поведения
import sys, os
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency, kruskal
OUT = sys.argv[1]; sys.path.insert(0, OUT)
from features import load_events, build_snapshot, day
df, users, _ = load_events(os.path.join(OUT, "..", "data", "events_2025.csv"))
ct = users.cancel_t.to_numpy(); never = np.isnan(ct)
ev = df.event.astype(str).to_numpy(); uid = df.uid.to_numpy()
for e in ["payment", "payment_failed", "plan_downgrade", "support_ticket"]:
    m = ev == e
    print(f"{e:15s} events by never-cancel users: {int(never[uid[m]].sum()):6d} | by churners: {int((~never[uid[m]]).sum()):6d}")
# доля неуспешных списаний: неушедшие против ушедших (до их последнего месяца)
b = df[np.isin(ev, ["payment", "payment_failed"])]
bn = b[never[b.uid.to_numpy()]]
print("never-cancel users: billing attempts", len(bn), "failed", int((bn.event == "payment_failed").sum()))
# полнота биллинга: у активных на 31.12 каждая дата списания имеет payment или pf?
st = users.start_t.to_numpy()
miss = 0; tot = 0
pay_t = {}
for u_, t_ in zip(b.uid.to_numpy(), b.t.to_numpy()):
    pay_t.setdefault(u_, []).append(t_)
END = day("2026-01-01")
for u_ in np.flatnonzero(never):
    k = np.arange(30, END - st[u_], 30)
    bills = st[u_] + k
    have = np.array(sorted(pay_t.get(u_, [])))
    for x in bills:
        tot += 1
        if not len(have) or np.min(np.abs(have - x)) > 0.01:
            miss += 1
print("never-cancel users: scheduled billing dates", tot, "with neither payment nor pf", miss)
# (2) спад вовлечённости у неушедших по датам среза: если предвестники идут вперёд во времени,
# среди never-cancel к концу года должны появляться будущие (январские) уходящие со спадом
rows = []
for Ts in ["2025-06-02", "2025-08-04", "2025-09-01", "2025-10-06", "2025-11-03", "2025-12-01", "2025-12-15", "2025-12-29"]:
    F = build_snapshot(df, users, day(Ts))
    nv = never[F.uid.to_numpy()]
    c = ct[F.uid.to_numpy()] - F["T"].to_numpy()
    soon = (c > 0) & (c <= 30)
    rows.append({"T": Ts, "never_n": int(nv.sum()),
                 "never_decay<0.5": round(float((F.decay_28[nv] < 0.5).mean()), 4),
                 "never_no_session_14d": round(float((F.days_since_session[nv] >= 14).mean()), 4),
                 "never_sess28_mean": round(float(F.sess_28[nv].mean()), 3),
                 "churn<=30d_decay<0.5": round(float((F.decay_28[soon] < 0.5).mean()), 4) if soon.any() else np.nan,
                 "churn<=30d_n": int(soon.sum())})
print(pd.DataFrame(rows).to_string())
# (3) интенсивность ухода по возрасту (месяц жизни) и календарному месяцу
c = users[users.cancel_t.notna()]
ten_m = ((c.cancel_t - c.start_t) // 30).astype(int)
cal_m = pd.to_datetime(c.cancel_t, unit="D", origin="2025-01-01").dt.month
# риск-набор: пользователь-месяцы жизни, разложенные по календарному месяцу (грубо: по дате начала месяца жизни)
expo = []
for u_, s in users.start_t.items():
    end = users.cancel_t[u_] if not np.isnan(users.cancel_t[u_]) else END
    for k in range(0, 12):
        a = s + 30 * k
        if a >= end: break
        expo.append((k, pd.Timestamp("2025-01-01") + pd.Timedelta(days=a), min(30, end - a)))
E = pd.DataFrame(expo, columns=["k", "start", "days"]); E["cal"] = E.start.dt.month
ev_ = pd.DataFrame({"k": ten_m.values, "cal": pd.to_datetime(c.cancel_t - (c.cancel_t - c.start_t) % 30, unit="D", origin="2025-01-01").dt.month.values})
H = ev_.groupby(["k", "cal"]).size().rename("n").to_frame().join(E.groupby(["k", "cal"]).days.sum())
H["haz_per_30d"] = (H.n / H.days * 30).round(3)
piv = H.haz_per_30d.unstack("cal")
print("cancel hazard per 30 days, rows = month of life, cols = calendar month when that month of life starts")
print(piv.loc[2:8].to_string())
# (4) анкета ухода против поведения: несколько поведенческих переменных, поправка Бонферрони
es = df[df.event == "exit_survey"][["uid", "value"]].set_index("uid").value.astype(str)
cc = users.loc[es.index].copy(); cc["reason"] = es
ses = df[df.event == "session_start"]; fu = df[df.event == "feature_used"]
cc["tenure_at_cancel"] = cc.cancel_t - cc.start_t
def cnt(x, lo, hi):
    t = x.t.to_numpy(); u_ = x.uid.to_numpy(); c_ = users.cancel_t.to_numpy()[u_]
    m = (t >= c_ - hi) & (t < c_ - lo)
    return pd.Series(u_[m]).value_counts().reindex(cc.index, fill_value=0)
cc["sess_last28"] = cnt(ses, 0, 28).values
cc["sess_28_56"] = cnt(ses, 28, 56).values
cc["sess_all"] = ses.groupby("uid").size().reindex(cc.index, fill_value=0).values
cc["feat_distinct_all"] = fu.groupby("uid").value.nunique().reindex(cc.index, fill_value=0).values
cc["n_pay"] = df[df.event == "payment"].groupby("uid").size().reindex(cc.index, fill_value=0).values
for e, nm in (("payment_failed", "pf"), ("plan_downgrade", "dg"), ("support_ticket", "ticket")):
    cc[nm] = cc.index.isin(df.loc[df.event == e, "uid"])
cc["pro"] = cc.plan == "pro"
tests = {}
for v in ["pf", "dg", "ticket", "pro"]:
    tests[v] = chi2_contingency(pd.crosstab(cc.reason, cc[v]))[1]
for v in ["tenure_at_cancel", "sess_last28", "sess_28_56", "sess_all", "feat_distinct_all", "n_pay"]:
    tests[v] = kruskal(*[x[v] for _, x in cc.groupby("reason")])[1]
for c_ in ["device", "country", "channel"]:
    tests[c_] = chi2_contingency(pd.crosstab(cc.reason, cc[c_]))[1]
print("exit survey n", len(cc), "p-values:", {k: round(float(v), 4) for k, v in tests.items()})
print("min p", round(min(tests.values()), 4), "Bonferroni threshold", round(0.05 / len(tests), 4))
print(cc.groupby("reason")[["tenure_at_cancel", "sess_last28", "sess_28_56", "sess_all", "feat_distinct_all", "n_pay"]].median().round(1).to_string())
print(cc.groupby("reason")[["pf", "dg", "ticket", "pro"]].mean().round(3).to_string())
# мощность: при каком эффекте chi2 по pf с этим n был бы значим — эффект Крамера V
from scipy.stats import chi2
n = len(cc); crit = chi2.ppf(0.95, 3)
print("detectable Cramer V at 80% power approx (df=3):", round(float(np.sqrt(11.0 / n)), 3), "(noncentrality 11 ~ 80% power at df=3)")
tab = pd.crosstab(cc.reason, cc.pf); chi = chi2_contingency(tab)[0]
print("observed Cramer V reason x pf", round(float(np.sqrt(chi / n)), 3))
# кто отвечает на анкету
resp = users.cancel_t.notna() & users.index.isin(es.index)
chs = users[users.cancel_t.notna()].copy(); chs["resp"] = chs.index.isin(es.index)
chs["pf"] = chs.index.isin(df.loc[df.event == "payment_failed", "uid"])
print("response rate by pf:", chs.groupby("pf").resp.mean().round(3).to_dict())
