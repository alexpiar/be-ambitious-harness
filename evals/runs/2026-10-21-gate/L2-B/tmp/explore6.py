import pandas as pd, numpy as np
u = pd.read_pickle('out/tmp/users.pkl')
c = u[u.cancel.notna()].copy()
ct = (c.cancel-c.signup).dt.total_seconds()/86400
print('cancel tenure mod 30 (3-day bins)', np.histogram(ct%30, bins=range(0,31,3))[0].tolist())
# split by pf / non-pf
for flag in [True, False]:
    x = ct[c.pf==flag]
    print('pf' if flag else 'voluntary', len(x), 'mod30 bins', np.histogram(x%30, bins=range(0,31,3))[0].tolist())
# voluntary churner composition
vol = c[~c.pf]
print('voluntary', len(vol), 'with ticket', vol.st.mean().round(3), 'with dg', vol.dg.mean().round(3))
print('pf churners with ticket', c[c.pf].st.mean().round(3), 'dg', c[c.pf].dg.mean().round(3))
# pf predictability by static attrs
for col in ['plan','device','country','channel']:
    print(u.groupby(col).pf.mean().round(3).to_dict())
# pf rate per billing attempt
df = pd.read_csv('data/events_2025.csv', usecols=['user_id','event'])
n_pay = (df.event=='payment').sum(); n_pf=(df.event=='payment_failed').sum()
print('pf per billing attempt', n_pf/(n_pay+n_pf))
# s14 among pf vs not
print('s14 by pf', u.groupby('pf').s14.mean().round(2).to_dict())
# survey reason vs behavior: s14 by reason; activity
print(u.groupby('reason')[['s14','fd14']].mean().round(2))
from scipy.stats import chi2_contingency
t = pd.crosstab(u.reason, u.pf); print('chi2 reason x pf p=', chi2_contingency(t)[1])
t = pd.crosstab(u.reason, u.st); print('chi2 reason x ticket p=', chi2_contingency(t)[1])
t = pd.crosstab(u.reason, u.plan); print('chi2 reason x plan p=', chi2_contingency(t)[1])
t = pd.crosstab(u.reason, u.dg); print('chi2 reason x dg p=', chi2_contingency(t)[1]); print(t)
