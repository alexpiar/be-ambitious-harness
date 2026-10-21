import pandas as pd, numpy as np
df = pd.read_csv('data/events_2025.csv', parse_dates=['ts'])
print(df.dtypes); print(df.shape)
print(df.memory_usage(deep=True).sum()/1e6, 'MB')
print(df.ts.min(), df.ts.max())
print(df.user_id.nunique())
print(df.event.value_counts())
for c in ['plan','device','country','channel']:
    print(df[c].value_counts(dropna=False).head(20))
print(df.isna().sum())
for e in df.event.unique():
    v = df.loc[df.event==e,'value']
    print('==', e, v.isna().mean(), v.dropna().head(10).tolist(), v.nunique())
