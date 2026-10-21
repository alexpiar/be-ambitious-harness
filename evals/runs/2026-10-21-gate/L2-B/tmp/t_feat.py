import time, sys
sys.path.insert(0, '.')
from features import *
t0=time.time()
df, users, q = load_events('../data/events_2025.csv')
print(q, time.time()-t0, df.memory_usage(deep=True).sum()/1e6)
t0=time.time()
F = build_snapshot(df, users, day('2025-06-01'))
F['y'] = add_labels(F, users)
print(time.time()-t0, F.shape, F.y.mean())
print(F.describe().T.round(2))
