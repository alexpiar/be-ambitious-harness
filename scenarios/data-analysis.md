# Scenario: data analysis

Result — a conclusion, metric, model, data report. Typical statement: "analyze why X dropped", "compute churn by cohort", "make a sales report".

## Analysis hints

**Point 1 — goal and bars.** Behind every analysis is a decision: what will be done differently if the answer is A, not B? If nothing — no analysis is needed; say so. Baseline bar — a correct answer to the question asked, with uncertainty stated. Ambitious — usually: cause instead of description ("why", confirmed on data, not "what"); a signal earlier than the current method notices it; a reproducible pipeline instead of a one-off report. A numeric target ("predict churn 30 days ahead with precision ≥0.6") is a hypothesis checked on held-out data.

**Gate check.** The cheapest: is there enough data for the question (volume, period, key-field completeness), and is there any signal (does the simplest model or breakdown differ from the base rate?). Criterion — observable: "a baseline model on holdout gives AUC ≥0.6" or "the segment breakdown shows a difference ≥X, confidence interval not crossing zero".

**Point 2 — improvements.** Assumption to check against primary data: the very causal claim in the task ("we think churn is due to onboarding" — reproduce it from raw logs before building on it). Disciplines: statistics (not "compute the mean" but "estimate with an interval and check for multiple comparisons"); causal inference, if the question is "why"; economics (cost of type I and II errors for the decision); a forensic approach — what in the data looks too good.

**Point 3 — grounds.** Primary: raw events or rows, not aggregates; a field dictionary; how data was collected and what changed in collection during the period. Tools: database or dataframe, not a markdown table; re-runnable script; fixed random seed; separate holdout before work starts.

**Point 4 — verification.** Criteria: predictive power on data not used in development; conclusion stable when period or segment changes; result reproduced from raw data by script. Independent verification: the verifier runs the script on its own data copy; reconciliation with an external figure (finance, billing); a backtest without look-ahead. Falsification test: the same method on a period with definitely no effect — does it find one there?

## Traps

- **Description instead of cause.** "Churn rose in segment X" does not answer "why". A cause requires either an experiment or a causal design with explicit assumptions.
- **Leakage.** A feature known only after the event; a holdout chosen after looking at the data; a threshold tuned on the same data. The verifier must see when the sample was held out.
- **Multiple comparisons.** Twenty slices — one "significant" by chance. A correction or a hypothesis set in advance.
- **Gaming the metric.** A model with AUC 0.9 thanks to a feature unavailable at prediction time. The criterion must include "features available at time T".

## For the worker

- Before any analysis: set aside the holdout and log its hash or id list. Read the acceptance threshold and metric from section 6, do not tune them.
- Work in code: a script or notebook with a fixed seed; every chart and number reproducible with one command. A markdown table from memory is not a result.
- Check the data before conclusions: missing values, duplicates, collection schema changes, outliers. Record what you found and how you handled it.
- Every conclusion — with an interval or stability across subsamples. A point estimate without uncertainty goes under "unverified".
- A negative result is a result: "no signal detected at this volume", with an estimate of what volume would suffice.
- Hand over: a reproducible script; holdout data or a way to get it; a report with conclusions and their uncertainty; a list of causal-inference assumptions, if any.
- For the check without the author, hand over the saved model and next to it `score.py <events.csv> <points.csv> <out.csv>`: `events.csv` — raw events in the source format, `points.csv` — `user_id,asof` pairs (entity and prediction moment in the `ts` format; the checker picks the points), `out.csv` — `user_id,asof,score`. The script loads the model without retraining, needs no labels, and builds features only from events at or before `asof`. If the result is a conclusion, not a model — a script that recomputes the conclusion on new data.

## Example of two bars

Task: "Compute monthly churn and find which segments have it higher."

- Baseline: churn by cohort and segment with intervals, a check for changes in data collection, a reproducible script.
- Ambitious: find the earliest behavioral churn signal that predicts it on holdout better than the baseline model; check — on 20% of the data a simple logistic model on the first 7 days of activity gives AUC ≥0.65 (limit — 3 hours, material — raw events for 12 months).
