# Аудит: помесячные/понедельные ряды событий, привязка pf/dg к cancel, расписание платежей
import sys
import numpy as np, pandas as pd
P = sys.argv[1]
df = pd.read_csv(P, dtype={"value": "string"})
df["ts"] = pd.to_datetime(df["ts"])
df["m"] = df.ts.dt.month
st = df[df.event=="signup"].groupby("user_id").ts.min()
ct = df[df.event=="cancel"].groupby("user_id").ts.min()
print("signups by month:", df[df.event=="signup"].m.value_counts().sort_index().to_dict())
print("cancels by month:", df[df.event=="cancel"].m.value_counts().sort_index().to_dict())
print("pf by month:", df[df.event=="payment_failed"].m.value_counts().sort_index().to_dict())
print("dg by month:", df[df.event=="plan_downgrade"].m.value_counts().sort_index().to_dict())
print("ticket by month:", df[df.event=="support_ticket"].m.value_counts().sort_index().to_dict())
print("payment by month:", df[df.event=="payment"].m.value_counts().sort_index().to_dict())
# активные на середину месяца
for mth in range(1,13):
    T = pd.Timestamp(2025, mth, 15)
    act = ((st < T) & ~(ct.reindex(st.index) <= T)).sum()
    pf = ((df.event=="payment_failed") & (df.m==mth)).sum()
    tk = ((df.event=="support_ticket") & (df.m==mth)).sum()
    ca = ((df.event=="cancel") & (df.m==mth)).sum()
    print(f"month {mth:2d} active~{act:5d} cancel/1000={1000*ca/act:6.1f} pf/1000={1000*pf/act:5.1f} ticket/1000={1000*tk/act:5.1f}")
# pf и dg: разрыв до cancel
for e in ["payment_failed","plan_downgrade","support_ticket"]:
    x = df[df.event==e].join(ct.rename("c"), on="user_id")
    gap = (x.c - x.ts).dt.total_seconds()/86400
    print(e, "n", len(x), "with cancel", x.c.notna().sum(), "gap days q:", gap.quantile([0,.1,.5,.9,1]).round(2).to_dict())
    # тикеты без cancel: когда
    if e=="support_ticket":
        nt = x[x.c.isna()]
        print("  tickets of never-cancel users by month:", nt.m.value_counts().sort_index().to_dict())
        yt = x[x.c.notna()]
        print("  tickets of churners by month:", yt.m.value_counts().sort_index().to_dict())
# последний pf / dg
print("last pf ts", df[df.event=="payment_failed"].ts.max(), "last dg ts", df[df.event=="plan_downgrade"].ts.max(), "last cancel", ct.max())
# платёжный цикл: дни от signup до платежей
pay = df[df.event.isin(["payment","payment_failed"])].join(st.rename("s"), on="user_id")
d = (pay.ts - pay.s).dt.total_seconds()/86400
r = np.mod(d, 30)
print("payment day-since-signup mod 30 quantiles:", pd.Series(r).quantile([0,.01,.5,.99,1]).round(3).to_dict())
print("first payment day after signup quantiles:", d[pay.event=="payment"].groupby(pay.user_id[pay.event=="payment"]).min().quantile([0,.5,1]).round(2).to_dict())
print("pf day-since-signup / 30 (cycle no.) q:", (d[pay.event=="payment_failed"]/30).quantile([0,.1,.5,.9]).round(3).to_dict())
