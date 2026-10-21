import pandas as pd, numpy as np
df = pd.read_csv('data/events_2025.csv', parse_dates=['ts'])
u = pd.read_pickle('out/tmp/users.pkl')
df = df.merge(u[['signup','cancel']], left_on='user_id', right_index=True)
df['tenure_d'] = (df.ts-df.signup).dt.total_seconds()/86400
df['to_cancel_d'] = (df.cancel-df.ts).dt.total_seconds()/86400
act = df[df.event.isin(['session_start','feature_used'])]
# churners: sessions per user in weekly windows before cancel, only users whose tenure at cancel >= (wk+1)*7
c = u[u.cancel.notna()].copy(); c['ct'] = (c.cancel-c.signup).dt.total_seconds()/86400
ses = df[df.event=='session_start']
rows=[]
for wk in range(0,10):
    elig = c[c.ct >= (wk+1)*7].index
    x = ses[ses.user_id.isin(elig) & (ses.to_cancel_d>=wk*7) & (ses.to_cancel_d<(wk+1)*7)]
    rows.append((wk, len(elig), len(x)/len(elig)))
print('churners: sessions/user/week by weeks-before-cancel', [(a,b,round(r,2)) for a,b,r in rows])
# non-churners: sessions/user/week by tenure week (reference)
nc = u[u.cancel.isna()].index
x = ses[ses.user_id.isin(nc)]
print('nonchurners by tenure week', (x.groupby((x.tenure_d//7).astype(int)).size()/len(nc)).head(20).round(2).tolist())
# churners by tenure week, among those still active (cancel tenure > end of week)
r=[]
for wk in range(0,12):
    elig = c[c.ct >= (wk+1)*7].index
    xx = ses[ses.user_id.isin(elig) & (ses.tenure_d>=wk*7) & (ses.tenure_d<(wk+1)*7)]
    r.append(round(len(xx)/max(len(elig),1),2))
print('churners (still active) by tenure week', r)
# first-14-day activity vs churn
e14 = ses[ses.tenure_d<14].groupby('user_id').size().reindex(u.index, fill_value=0)
f14 = df[(df.event=='feature_used')&(df.tenure_d<14)].groupby('user_id').size().reindex(u.index, fill_value=0)
fd14 = df[(df.event=='feature_used')&(df.tenure_d<14)].groupby('user_id').value.nunique().reindex(u.index, fill_value=0)
u['s14']=e14; u['f14']=f14; u['fd14']=fd14
print(u.groupby(pd.cut(u.s14,[-1,0,2,4,6,8,10,15,100])).churn.agg(['mean','size']).round(3))
print(u.groupby(pd.cut(u.f14,[-1,0,1,2,3,5,100])).churn.agg(['mean','size']).round(3))
print(u.groupby('fd14').churn.agg(['mean','size']).round(3))
# first-day sessions
d1 = ses[ses.tenure_d<1].groupby('user_id').size().reindex(u.index, fill_value=0)
u['d1']=d1
print(u.groupby(pd.cut(u.d1,[-1,0,1,2,3,5,100])).churn.agg(['mean','size']).round(3))
# Overall per-user session rate (non-churners) distribution — heterogeneity
nonc = u[u.cancel.isna()]
rate = ses[ses.user_id.isin(nonc.index)].groupby('user_id').size()/((pd.Timestamp('2026-01-01')-nonc.signup).dt.days/7)
print('nonchurner sessions/week dist', rate.describe().round(2).to_dict())
# churn by signup month (censoring)
u['sm']=u.signup.dt.month
print(u.groupby('sm').churn.mean().round(3).tolist())
# churn within 90 days by signup month
u['ct']=(u.cancel-u.signup).dt.days
print('churn<=90d by signup month', u.groupby('sm').apply(lambda d:(d.ct<=90).mean()).round(3).tolist())
u.to_pickle('out/tmp/users.pkl')
