# Аудит: базовые свойства сырого лога (независимо от features.py)
import sys
import numpy as np, pandas as pd
P = sys.argv[1]
df = pd.read_csv(P, dtype={"value": "string"})
df["ts"] = pd.to_datetime(df["ts"])
print("rows", len(df), "exact dups", df.duplicated().sum(), "dups on (ts,user,event)", df.duplicated(["ts","user_id","event"]).sum())
print("ts range", df.ts.min(), df.ts.max())
print("nulls per col\n", df.isna().sum())
print("users", df.user_id.nunique())
c = df[df.event=="cancel"]
print("cancels", len(c), "users with cancel", c.user_id.nunique(), "max cancels per user", c.groupby("user_id").size().max())
s = df[df.event=="signup"]
print("signups", len(s), "users w signup", s.user_id.nunique())
# events after cancel
ct = c.groupby("user_id").ts.min()
d = df.join(ct.rename("cancel_ts"), on="user_id")
after = d[(d.ts > d.cancel_ts)]
print("events after first cancel:", len(after), after.event.value_counts().to_dict())
print("users with events after cancel:", after.user_id.nunique())
# exit survey timing
es = df[df.event=="exit_survey"].join(ct.rename("cancel_ts"), on="user_id")
gap = (es.ts - es.cancel_ts).dt.total_seconds()/60
print("exit_survey - cancel minutes: describe\n", gap.describe())
print("exit_survey without cancel:", es.cancel_ts.isna().sum())
# changing static fields
for col in ["plan","device","country","channel"]:
    nun = df.groupby("user_id")[col].nunique()
    print(col, "users with >1 value:", (nun>1).sum(), "values", df[col].value_counts(dropna=False).to_dict())
