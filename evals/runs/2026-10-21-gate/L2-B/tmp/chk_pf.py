import sys; sys.path.insert(0,'.')
import numpy as np, pandas as pd
from features import *
df, users, _ = load_events('../data/events_2025.csv')
for e in ['payment_failed','plan_downgrade','support_ticket']:
    x = df[df.event==e]
    late = x[x.t >= day('2025-12-01')]
    c = users.cancel_t.to_numpy()[late.uid.to_numpy()]
    print(e, 'events in Dec', len(late), 'of them cancelled by Dec31', int(np.isfinite(c).sum()), 'gap days', np.round(np.nanpercentile(c-late.t.to_numpy(),[0,50,100]),1) if len(late) else None)
# expected under 0-30d uniform gap: share of Dec-pf whose cancel would fall in 2026
x = df[df.event=='payment_failed']; gap = users.cancel_t.to_numpy()[x.uid.to_numpy()] - x.t.to_numpy()
late = x.t.to_numpy() >= day('2025-12-01')
print('pf gaps early-year', np.round(np.percentile(gap[~late],[0,25,50,75,100]),1), 'Dec', np.round(np.percentile(gap[late],[0,25,50,75,100]),1) if late.any() else '')
# last pf date overall, last downgrade
print('last pf', pd.Timestamp('2025-01-01')+pd.Timedelta(days=x.t.max()))
