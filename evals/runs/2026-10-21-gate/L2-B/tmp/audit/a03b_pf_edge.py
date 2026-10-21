# Аудит: доля неуспешных списаний среди всех попыток списания по неделям Oct-Dec
# Если pf — независимый процесс, доля стабильна. Если pf записан только при cancel внутри 2025,
# доля падает к 31.12 по форме P(gap <= 31.12 - t).
import sys
import numpy as np, pandas as pd
P = sys.argv[1]
df = pd.read_csv(P, dtype={"value": "string"}, usecols=["ts","user_id","event"])
df["ts"] = pd.to_datetime(df["ts"])
b = df[df.event.isin(["payment","payment_failed"])].copy()
b["wk"] = b.ts.dt.to_period("W-SUN").dt.start_time
g = b.groupby("wk").event.agg(attempts="size", pf=lambda s: (s=="payment_failed").sum())
g["pf_share"] = (g.pf/g.attempts).round(4)
ct = df[df.event=="cancel"].groupby("user_id").ts.min()
pf = df[df.event=="payment_failed"].join(ct.rename("c"), on="user_id")
gap = ((pf.c - pf.ts).dt.total_seconds()/86400).to_numpy()
base = g.loc["2025-06-01":"2025-11-15"]
base_share = base.pf.sum()/base.attempts.sum()
end = pd.Timestamp("2026-01-01")
exp = []
for wk in g.index:
    mid = wk + pd.Timedelta(days=3.5)
    left = (end - mid).total_seconds()/86400
    exp.append(round(base_share*(gap <= left).mean(), 4))
g["expected_if_recorded_only_with_cancel_in_2025"] = exp
print("base pf share Jun1-Nov15:", round(base_share,4))
print(g.loc["2025-10-01":].to_string())
