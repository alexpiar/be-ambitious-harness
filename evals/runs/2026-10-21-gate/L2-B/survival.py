"""Анализ выживаемости и механизмов ухода (метод биостатистики: время до события
с цензурированием), деньги под риском, проверка анкеты ухода.

Запуск: python -I survival.py  → results/survival.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from scipy.stats import CensoredData, chi2_contingency, kruskal, logrank

from features import day, load_events

HERE = os.path.dirname(os.path.abspath(__file__))
df, users, _ = load_events(os.path.join(HERE, "..", "data", "events_2025.csv"))
END = day("2026-01-01")
u = users.copy()
u["event"] = u.cancel_t.notna()
u["dur"] = np.where(u.event, u.cancel_t, END) - u.start_t
ev = df[["uid", "event", "t", "value"]].copy()
ev["ten"] = ev.t - u.start_t.to_numpy()[ev.uid.to_numpy()]
u["s14"] = ev[(ev.event == "session_start") & (ev.ten < 14)].groupby("uid").size().reindex(u.index, fill_value=0)
u["pf"] = u.index.isin(ev.loc[ev.event == "payment_failed", "uid"])
u["ticket"] = u.index.isin(ev.loc[ev.event == "support_ticket", "uid"])
u["dg"] = u.index.isin(ev.loc[ev.event == "plan_downgrade", "uid"])
u["reason"] = ev[ev.event == "exit_survey"].set_index("uid")["value"].reindex(u.index)
u["signup_month"] = pd.to_datetime(u.start_t, unit="D", origin="2025-01-01").dt.month


def km(d, e):
    """Каплан–Мейер: S(t) в точках 30/60/90/180 и медиана."""
    order = np.argsort(d)
    d, e = d[order], e[order]
    times = np.unique(d[e])
    n_at = len(d) - np.searchsorted(d, times, side="left")
    deaths = np.array([np.sum((d == t) & e) for t in times])
    S = np.cumprod(1 - deaths / n_at)
    f = lambda t: float(S[times <= t][-1]) if np.any(times <= t) else 1.0
    med = times[np.argmax(S <= 0.5)] if np.any(S <= 0.5) else None
    return {"n": int(len(d)), "S30": round(f(30), 3), "S60": round(f(60), 3), "S90": round(f(90), 3),
            "S180": round(f(180), 3), "median_days": None if med is None else round(float(med), 1)}


def by(col, groups=None):
    out = {}
    g = u.groupby(col)
    for k, x in g:
        out[str(k)] = km(x.dur.to_numpy(), x.event.to_numpy())
    keys = list(g.groups)
    if len(keys) == 2 or groups:
        a, b = (g.get_group(k) for k in (groups or keys)[:2])
        r = logrank(CensoredData(uncensored=a.dur[a.event], right=a.dur[~a.event]),
                    CensoredData(uncensored=b.dur[b.event], right=b.dur[~b.event]))
        out["logrank_p_first_vs_last"] = float(r.pvalue)
    return out


R = {"overall": km(u.dur.to_numpy(), u.event.to_numpy())}
u["onboarding_tercile"] = pd.qcut(u.s14, 3, labels=["low_s14", "mid_s14", "high_s14"])
u["onboarding_tercile"] = u["onboarding_tercile"].astype(str)
R["by_onboarding_first14d"] = by("onboarding_tercile", ["low_s14", "high_s14"])
R["onboarding_tercile_edges_sessions"] = [float(x) for x in u.s14.quantile([1 / 3, 2 / 3])]
for c in ("plan", "channel", "device", "country"):
    R["by_" + c] = by(c, sorted(u[c].unique())[:1] + sorted(u[c].unique())[-1:])
# ловушка цензурирования: «доля ушедших» по месяцу регистрации против KM S(90)
R["censoring_trap"] = {int(m): {"raw_churn_share": round(float(x.event.mean()), 3),
                                "km_churn_by_90d": round(1 - km(x.dur.to_numpy(), x.event.to_numpy())["S90"], 3)}
                       for m, x in u.groupby("signup_month")}

# механизмы ухода
c = u[u.event]
mech = np.where(c.pf, "involuntary_payment_failed",
                np.where(c.dg | c.ticket, "voluntary_with_signal(downgrade/ticket)", "voluntary_silent"))
c = c.assign(mechanism=mech)
R["mechanisms"] = {k: {"churners": int(len(x)), "share": round(len(x) / len(c), 3),
                       "lost_mrr": round(float(x.price.sum()), 2)} for k, x in c.groupby("mechanism")}
R["lost_mrr_total"] = round(float(c.price.sum()), 2)
R["active_mrr_end_of_year"] = round(float(u.loc[~u.event, "price"].sum()), 2)
R["payment_failed_users_who_cancelled"] = f"{int((u.pf & u.event).sum())} из {int(u.pf.sum())}"
pf_gap = (u.cancel_t - ev[ev.event == "payment_failed"].groupby("uid").t.min().reindex(u.index)).dropna()
R["days_from_payment_failed_to_cancel"] = {q: round(float(pf_gap.quantile(p)), 1)
                                          for q, p in (("p10", .1), ("median", .5), ("p90", .9))}
R["ticket_users_who_cancelled"] = f"{int((u.ticket & u.event).sum())} из {int(u.ticket.sum())}"
R["downgrade_users_who_cancelled"] = f"{int((u.dg & u.event).sum())} из {int(u.dg.sum())}"
R["churners_never_paid"] = int((c.index.isin(np.setdiff1d(u.index, ev.loc[ev.event == 'payment', 'uid']))).sum())

# когда уходят добровольно: позиция в 30-дневном цикле списания
vol = c[~c.pf]
pos = 30 - np.mod(vol.cancel_t - vol.start_t, 30)   # дней до следующего списания в момент ухода
hist = np.histogram(pos, bins=[0, 6, 12, 18, 24, 30])[0]
R["voluntary_cancel_by_days_to_next_bill"] = {"bins": ["0-6", "6-12", "12-18", "18-24", "24-30"],
                                              "cancels": hist.tolist()}
R["voluntary_hazard_ratio_last12d_before_bill"] = round(float((pos < 12).mean() / (12 / 30)), 2)

# активность ушедших в последние недели (сессий в неделю), против не ушедших
ses = ev[ev.event == "session_start"]
ses_c = ses.merge(c[["cancel_t"]], left_on="uid", right_index=True)
ses_c["wk_before"] = ((ses_c.cancel_t - ses_c.t) // 7).astype(int)
cten = c.cancel_t - c.start_t
rate = {}
for wk in range(0, 9):
    elig = cten[cten >= (wk + 1) * 7].index
    rate[wk] = round(float(((ses_c.uid.isin(elig)) & (ses_c.wk_before == wk)).sum() / len(elig)), 2)
nc = u[~u.event]
R["sessions_per_week_churners_by_weeks_before_cancel"] = rate
R["sessions_per_week_retained"] = round(float(ses[ses.uid.isin(nc.index)].groupby("uid").size().sum()
                                              / ((END - nc.start_t) / 7).sum()), 2)

# анкета ухода: связана ли названная причина с поведением
s = u[u.reason.notna()]
R["exit_survey"] = {"response_rate_among_churners": round(len(s) / len(c), 3),
                    "reasons": s.reason.value_counts().to_dict(),
                    "chi2_p_reason_vs_payment_failed": round(float(chi2_contingency(pd.crosstab(s.reason, s.pf))[1]), 3),
                    "chi2_p_reason_vs_downgrade": round(float(chi2_contingency(pd.crosstab(s.reason, s.dg))[1]), 3),
                    "chi2_p_reason_vs_ticket": round(float(chi2_contingency(pd.crosstab(s.reason, s.ticket))[1]), 3),
                    "chi2_p_reason_vs_plan": round(float(chi2_contingency(pd.crosstab(s.reason, s.plan))[1]), 3),
                    "kruskal_p_reason_vs_first14d_sessions": round(float(kruskal(*[x.s14 for _, x in s.groupby("reason")])[1]), 3),
                    "share_saying_price_among_payment_failed": round(float((s[s.pf].reason == "price").mean()), 3),
                    "share_saying_price_among_downgraders": round(float((s[s.dg].reason == "price").mean()), 3),
                    "share_saying_price_overall": round(float((s.reason == "price").mean()), 3)}
json.dump(R, open(os.path.join(HERE, "results", "survival.json"), "w"), ensure_ascii=False, indent=2)
print(json.dumps(R, ensure_ascii=False, indent=1))
