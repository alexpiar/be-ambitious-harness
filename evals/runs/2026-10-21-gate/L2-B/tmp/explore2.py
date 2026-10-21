import pandas as pd, numpy as np
df = pd.read_csv('data/events_2025.csv', parse_dates=['ts'])
df = df.sort_values(['user_id','ts'])
g = df.groupby('user_id')
u = pd.DataFrame({
 'signup': df[df.event=='signup'].groupby('user_id').ts.min(),
 'n_signup': df[df.event=='signup'].groupby('user_id').size(),
 'first': g.ts.min(), 'last': g.ts.max(), 'n': g.size(),
 'cancel': df[df.event=='cancel'].groupby('user_id').ts.min(),
 'n_cancel': df[df.event=='cancel'].groupby('user_id').size(),
 'survey': df[df.event=='exit_survey'].groupby('user_id').ts.min(),
 'n_plans': g.plan.nunique(), 'n_dev': g.device.nunique(), 'n_cty': g.country.nunique(), 'n_ch': g.channel.nunique(),
})
print(u.describe(include='all').T)
print('signup==first', (u.signup==u['first']).mean())
print('users with cancel', u.cancel.notna().sum(), 'multi', (u.n_cancel>1).sum())
print('survey w/o cancel', (u.survey.notna() & u.cancel.isna()).sum(), 'survey w cancel', (u.survey.notna()&u.cancel.notna()).sum())
d = (u.survey - u.cancel).dt.total_seconds()/3600
print('survey - cancel hours', d.describe())
# events after cancel
m = df.merge(u[['cancel']], left_on='user_id', right_index=True)
after = m[m.ts > m.cancel]
print('events after cancel', len(after), after.event.value_counts())
print('users w events after cancel', after.user_id.nunique())
# last event relative to cancel
c = u[u.cancel.notna()]
print('last - cancel days', ((c['last']-c.cancel).dt.total_seconds()/86400).describe())
print('cancel - signup days', ((c.cancel-c.signup).dt.total_seconds()/86400).describe())
print('signups by month', u.signup.dt.month.value_counts().sort_index().tolist())
print('cancels by month', c.cancel.dt.month.value_counts().sort_index().tolist())
# inactivity: last event month for non-cancel users
nc = u[u.cancel.isna()]
print('noncancel last event month', nc['last'].dt.month.value_counts().sort_index().tolist())
print('noncancel days since last at year end', ((pd.Timestamp('2026-01-01')-nc['last']).dt.days).describe())
u.to_pickle('out/tmp/users.pkl')
