<prompt>
Scenario: data-analysis.md

## 1. Goal and outcome
Goal: build a model that predicts user churn from events and say which features matter most.
What should become possible: tell in advance who will cancel, with accuracy confirmed on held-out data.
Scheme: conditional. Bar: always the baseline (day-14 model plus feature importance with intervals); after a passed gate and with a cost limit set, the ambitious branch is added.

## 2. Mandatory requirements and boundaries
— "Build a model that predicts churn and tell me which features matter most."
Contradictions: none.

## 3. Materials and access
Required: events_2025.csv; Python 3.10 with numpy, pandas, scikit-learn.
Optional: a field dictionary.
If required ones are missing — ask me before starting work.

## 4. Gate check
Action and materials: after stage 0, on the dev part only; slice D = 7; two logistic regressions, (A) static features only, (B) static plus behavioural; 5-fold stratified CV, out-of-fold predictions; 1000 bootstrap resamples by user.
Observable result: ROC AUC(B) with its 95% CI; the difference ROC AUC(B) − ROC AUC(A) with its 95% CI; the slice population and its positive labels.
Pass criterion (fixed, not subject to revision): ROC AUC(B) ≥ 0.65 and the lower bound of the 95% CI of the difference ROC AUC(B) − ROC AUC(A) > 0. Rationale: 0.65 is the lowest ranking quality usable for retention targeting; a positive difference means first-week behaviour adds signal beyond what is known at signup. If the slice's dev population has fewer than 100 positive labels, the criterion is inapplicable.
Cost limit: 40 minutes of worker time, one script, dev part only; the holdout is not opened.
Passed → stages 2 and 3 if the ambitious-branch cost limit is set; it is not set, so stage 2 only plus a cost estimate for stage 3.
Failed → stage 2 only; the report gives the values and why the check failed.
Insufficient data (cost limit exhausted, result unobservable or criterion inapplicable) → stage 2 only; the report says what remained unknown.
The outcome is logged as a GATE block per core/gate.md before the first action of stage 3.
Ambitious-branch work starts after the outcome is logged.

## 5. Approach and stages
Stage 0 — data quality and the holdout, common to both branches.
Stage 1 — the gate check from section 4.
Stage 2 — baseline branch, D = 14.
Stage 3 — ambitious branch: slices D ∈ {3, 7, 14, 30}.

## 6. Acceptance criteria and verification
Criteria: holdout metrics with 95% CIs against three baselines.
Reference / current level: base rate; logistic regression on static features; the "fewer sessions, higher risk" rule.
Independent verification: rerun the script and compare the numbers.
Falsification test: with shuffled labels the CI of ROC AUC includes 0.5.
Gaming the metric — what counts as it: features from events after T; choices made on the holdout.

## 7. Completion and report
Done when: criteria 1–6 hold for stage 2 and the gate outcome is logged.
Report per core/report-format.md: result; scheme and gate outcome; assumptions; unverified conclusions; blockers.
</prompt>
