import sys; sys.path.insert(0,'.')
import numpy as np, pandas as pd
from features import *
df, users, _ = load_events('../data/events_2025.csv')
rows=[]
for T in ['2025-09-01','2025-10-01','2025-11-01','2025-12-01','2025-12-15','2025-12-29','2026-01-01']:
    F = build_snapshot(df, users, day(T))
    rows.append({'T':T,'active':len(F),
      'pf_last30_share':round(float((F.days_since_pf<=30).mean()),4),
      'dg_last30_share':round(float((F.days_since_dg<=30).mean()),4),
      'ticket_last30_share':round(float((F.days_since_ticket<=30).mean()),4),
      'decay_below_0.5_share':round(float((F.decay_28<0.5).mean()),4),
      'no_session_14d_share':round(float((F.days_since_session>=14).mean()),4),
      'mean_tenure':round(float(F.tenure.mean()),1)})
r = pd.DataFrame(rows); print(r.to_string()); r.to_csv('results/year_end_truncation_check.csv', index=False)
