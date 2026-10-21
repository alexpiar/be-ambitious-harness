import pandas as pd, numpy as np
df = pd.read_csv('data/events_2025.csv', parse_dates=['ts'])
u = pd.read_pickle('out/tmp/users.pkl')
df = df.merge(u[['signup','cancel']], left_on='user_id', right_index=True)
df['tenure_d'] = (df.ts-df.signup).dt.total_seconds()/86400
df['to_cancel_d'] = (df.cancel-df.ts).dt.total_seconds()/86400
for e in ['payment_failed','support_ticket','plan_downgrade']:
    x = df[df.event==e]
    print(e, 'to_cancel days', x.to_cancel_d.describe().round(1).to_dict())
    print('  per user count', x.groupby('user_id').size().value_counts().to_dict())
# payment failed: are payments continuing after fail?
pf = df[df.event=='payment_failed'].groupby('user_id').ts.min()
pay = df[df.event=='payment']
pp = pay.merge(pf.rename('pf'), left_on='user_id', right_index=True)
print('payments after first pf', (pp.ts>pp.pf).sum())
# failed payment tenure: is it on the 30-day cycle?
x = df[df.event=='payment_failed']
print('pf tenure mod 30', (x.tenure_d % 30).round().value_counts().head().to_dict())
# no-payment users
fp = pay.groupby('user_id').ts.min()
nop = u[~u.index.isin(fp.index)]
print('nopay churn', nop.cancel.notna().mean(), len(nop), 'cancel tenure', ((nop.cancel-nop.signup).dt.days).describe().to_dict())
# cancel tenure distribution
ct = ((u.cancel-u.signup).dt.total_seconds()/86400).dropna()
print('cancel tenure hist (10d bins)', np.histogram(ct, bins=range(0,340,10))[0].tolist())
# sessions value
s = df[df.event=='session_start'].copy(); s['v']=s.value.astype(int)
s['churner'] = s.cancel.notna()
print(s.groupby('churner').v.describe())
# churners: session value & weekly rate by weeks before cancel
c = s[s.churner].copy(); c['wk'] = (c.to_cancel_d//7).astype(int)
agg = c.groupby('wk').agg(n=('v','size'), v=('v','mean'))
nusers = u.cancel.notna().sum()
print(agg.head(16))
# weekly sessions per churner by weeks before cancel (only users with tenure covering)
# non-churners weekly session rate by tenure week
s['twk'] = (s.tenure_d//7).astype(int)
r = s.groupby(['churner','twk']).agg(n=('v','size'), v=('v','mean')).reset_index()
print(r[r.twk<16].pivot(index='twk', columns='churner', values=['n','v']))
# features used
f = df[df.event=='feature_used']
f['churner']=f.cancel.notna()
print(pd.crosstab(f.value, f.churner, normalize='columns'))
# feature adoption in first 14 days vs churn
early = f[f.tenure_d<14]
for val in ['export','share','tags','search']:
    us = set(early[early.value==val].user_id)
    u[f'early_{val}'] = u.index.isin(us)
    print(val, u.groupby(f'early_{val}').churn.agg(['mean','size']).round(3).to_dict())
# survey reasons cross pre-cancel signals
sv = df[df.event=='exit_survey'].set_index('user_id').value
u['reason'] = sv
print(pd.crosstab(u.reason, [u.pf], normalize='index'))
print(pd.crosstab(u.reason, [u.st], normalize='index'))
print(pd.crosstab(u.reason, u.plan, normalize='index'))
print(u.groupby('reason').apply(lambda d: ((d.cancel-d.signup).dt.days).median()))
u.to_pickle('out/tmp/users.pkl')
