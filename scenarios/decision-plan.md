# Scenario: decision and plan

Result — a decision, plan, strategy, prioritization, choice between options. Typical statement: "is X worth doing", "draw up a quarterly plan", "choose between A and B".

## Analysis hints

**Point 1 — goal and bars.** A decision is a means; what should become possible after it, and what happens if it is not made? Baseline bar — a justified recommendation with explicit criteria, options, and risks. Ambitious — usually: turn the decision into a testable bet (what we learn in N weeks, what confirms or refutes it); find an option not among those proposed; design a reversible decision instead of an irreversible one. Numeric plan targets ("+20% to the metric") are hypotheses, stating when and how it becomes clear they are failing.

**Gate check.** The most valuable: checking the main assumption the decision rests on: "we believe clients want X" → 5 conversations or last month's data; "option A is cheaper" → an estimate with grounds. Criterion — observable: "≥3 of 5 clients confirm the problem", "estimate for A is below B with ±30% uncertainty accounted for".

**Point 2 — improvements.** Assumption to check: that the options are exhausted ("A or B" — why not C, and not "nothing"); that the selection criteria are the ones named, not the ones the decision will really be judged by. Disciplines: decision theory (cost of error per option, reversibility); finance (cash flow, not "benefit"); risk analysis (premortem: the decision failed — why); the argument against (who will oppose and why, and are they right).

**Point 3 — grounds.** Primary: data the assumptions rest on; past decisions of the same type and their outcome; constraints not named in the task (budget, people, deadlines, politics). Worker's tools: an options table with criteria and weights, if more than three criteria; calculation in code, if there are numbers; access to people, if assumptions are about people.

**Point 4 — verification.** Criteria: every assumption marked checked or not; every option scored on the same criteria; the recommendation changes if the key assumption fails — and this is shown. Independent verification: the verifier builds a counterargument to the recommendation from the same data; a premortem by another agent; recalculating the numbers. Falsification test: what observation in the next N weeks will show the decision is wrong — and it is assigned for tracking.

## Traps

- **False dichotomy.** Two options from the task are not the full list. The "don't do it" and "run a small test" options are always in the table.
- **Criteria fitted to the answer.** Weights picked so a preselected option wins. Weights are fixed before scoring options, in the log.
- **Plan without a signal.** A quarterly plan with no points where it becomes clear it isn't working. Every stage — with a continuation condition.
- **Confidence without uncertainty.** "Option A will bring in 2 million" — without interval or grounds. A number without an interval goes under "unverified".

## For the worker

- Start with the gate check, if any: check the main assumption and log it before the options table.
- Criteria and weights — into the log before scoring options. Changing weights afterwards — a separate line with justification.
- The options table includes "do nothing" and "minimal test". If absent — explain why they were excluded.
- Every number — with grounds and an interval. Premortem — one paragraph on the recommended option.
- For a plan: every stage — a continuation condition and a stop signal with a check date.
- Hand over: the recommendation with grounds; the options table; a list of assumptions marked "checked / not"; signals and dates by which it becomes clear the decision is wrong.

## Example of two bars

Task: "Should we build a mobile app, or is a responsive website enough?"

- Baseline: an options table (app / website / PWA / nothing) on fixed criteria, a recommendation with a premortem and revision signals.
- Ambitious: check the main assumption — that users need specifically a mobile use case; check — share of mobile sessions and their completion rate from analytics over 3 months plus 5 conversations (limit — 1 day; criterion — ≥40% of sessions mobile and ≥3 of 5 name a concrete mobile use case; otherwise — baseline with the recommendation "website").
