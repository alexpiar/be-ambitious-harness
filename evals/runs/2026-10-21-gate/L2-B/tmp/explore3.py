import pandas as pd, numpy as np
df = pd.read_csv('data/events_2025.csv', parse_dates=['ts'])
u = pd.read_pickle('out/tmp/users.pkl')
print('dup rows', df.duplicated().sum(), 'dup ts+user+event', df.duplicated(['ts','user_id','event']).sum())
bad = u[u.signup!=u['first']].index
print('pre-signup users', len(bad))
x = df[df.user_id.isin(bad)].sort_values(['user_id','ts']).groupby('user_id').head(3)
print(x.head(15))
# plan vs payment amounts
pay = df[df.event=='payment'].copy(); pay['amt']=pay.value.astype(float)
print(pd.crosstab(pay.plan, pay.amt))
dg = df[df.event=='plan_downgrade']
print('downgrade users', dg.user_id.nunique(), dg.plan.value_counts())
# payments around downgrade
dgu = dg.groupby('user_id').ts.min()
p2 = pay.merge(dgu.rename('dg'), left_on='user_id', right_index=True)
p2['after'] = p2.ts > p2.dg
print(pd.crosstab([p2.plan,p2.after], p2.amt))
# churn rate by plan, among downgraders
u['plan'] = df.groupby('user_id').plan.first()
for c in ['device','country','channel']:
    u[c] = df.groupby('user_id')[c].first()
u['churn'] = u.cancel.notna()
u['dg'] = u.index.isin(dgu.index)
for c in ['plan','device','country','channel','dg']:
    print(u.groupby(c).churn.agg(['mean','size']))
# downgrade timing relative to cancel
dd = (u.cancel - dgu.reindex(u.index)).dt.days
print('cancel - downgrade days', dd.describe())
# payment intervals
pay = pay.sort_values(['user_id','ts'])
iv = pay.groupby('user_id').ts.diff().dt.total_seconds()/86400
print('payment interval days', iv.describe(), iv.round().value_counts().head(10))
# first payment relative to signup
fp = pay.groupby('user_id').ts.min()
print('first pay - signup days', ((fp-u.signup).dt.total_seconds()/86400).describe())
print('users with no payment', (~u.index.isin(fp.index)).sum())
# payment_failed
pf = df[df.event=='payment_failed']
print('pf users', pf.user_id.nunique())
u['pf'] = u.index.isin(pf.user_id)
print(u.groupby('pf').churn.agg(['mean','size']))
st = df[df.event=='support_ticket']; u['st']=u.index.isin(st.user_id)
print(u.groupby('st').churn.agg(['mean','size']))
sv = df[df.event=='exit_survey'].set_index('user_id').value
print(sv.value_counts())
u.to_pickle('out/tmp/users.pkl')
