# Evidence log — churn (synthetic fixture for tools/gate-check.py, modelled on run L2-A of 2026-10-21)

## 01:28 — stage 0.2, holdout
- 1200 user_id set aside before any features or models; SHA-256 of the id list recorded.

## 01:32–01:33 — stage 1, gate check (dev only)
- dev population 4800, positives 1176 (0.245).

```
GATE
action:                 D=7, T = ts(signup)+7 days; LR (A) static and (B) static+behaviour; 5-fold stratified CV, OOF;
                        bootstrap 1000 by user for AUC(B) and AUC(B)−AUC(A)
materials:              dev part (4800 users) of events_2025.csv; Python from section 3
observable result:      population 4800, positives 1176; AUC(B) = 0.5483 [0.5287; 0.5684];
                        AUC(B)−AUC(A) = 0.0177 [0.0057; 0.0298]
criterion (as written): ROC AUC(B) ≥ 0.65 and the lower bound of the 95% CI of the difference ROC AUC(B) − ROC AUC(A) > 0;
                        inapplicable if < 100 positive labels in the slice's dev population
cost limit:             40 minutes of worker time, one script, dev part only; the holdout is not opened
actual cost:            ≈ 3 min of worker time; one script; dev only
outcome:                failed
consequence:            baseline branch — stage 2 only (D=14). The criterion applies (1176 ≥ 100); AUC(B) = 0.548 < 0.65.
                        Stage 3 is not run.
```

## 01:34–01:54 — stage 2, baseline branch D=14
- Holdout ROC AUC 0.7395 [0.7078; 0.7697]; static baseline 0.5373 [0.5012; 0.5748].
- Stage 3 was not run (gate outcome: failed).
