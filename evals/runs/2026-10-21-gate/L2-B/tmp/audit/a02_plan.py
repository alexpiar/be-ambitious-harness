# Аудит: plan — начальное или итоговое значение? payment value vs plan
import sys
import numpy as np, pandas as pd
P = sys.argv[1]
df = pd.read_csv(P, dtype={"value": "string"})
df["ts"] = pd.to_datetime(df["ts"])
print(df[df.duplicated(["ts","user_id","event"], keep=False)])
u = df.groupby("user_id").agg(plan=("plan","first"))
dg = df[df.event=="plan_downgrade"]
print("plan_downgrade values:", dg.value.value_counts(dropna=False).to_dict())
print("downgraders:", dg.user_id.nunique(), "plan of downgraders:", u.loc[dg.user_id.unique()].plan.value_counts().to_dict())
print("overall plan share:", u.plan.value_counts(normalize=True).round(3).to_dict())
# payment amounts by plan, before/after downgrade
pay = df[df.event=="payment"].copy()
pay["v"] = pd.to_numeric(pay.value, errors="coerce")
print("payment value by plan:\n", pay.groupby("plan").v.describe())
dgt = dg.groupby("user_id").ts.min()
pay = pay.join(dgt.rename("dg_ts"), on="user_id")
pd_ = pay[pay.dg_ts.notna()]
pd_["phase"] = np.where(pd_.ts < pd_.dg_ts, "before_dg", "after_dg")
print("downgraders payment value by phase & plan field:\n", pd_.groupby(["phase","plan"]).v.describe())
for e in ["payment_failed","support_ticket","session_start","feature_used","signup","cancel","exit_survey"]:
    print(e, "value sample:", df[df.event==e].value.value_counts(dropna=False).head(8).to_dict())
