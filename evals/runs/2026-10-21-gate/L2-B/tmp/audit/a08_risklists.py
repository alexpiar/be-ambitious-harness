# Аудит: сводка по спискам риска автора (чтение CSV, без переобучения)
import sys, pandas as pd
for f in sys.argv[1:]:
    r = pd.read_csv(f)
    print(f.split("/")[-1], "rows", len(r), "sum risk", round(r.risk_30d.sum(), 1), "mean", round(r.risk_30d.mean(), 3),
          "min", r.risk_30d.min(), "| reason_1 starts:", r.reason_1.str.split(" ").str[0].value_counts().head(5).to_dict())
