# Test tasks for the harness

Six tasks — one per scenario, plus two traps. Each checks a specific behavior; after editing any file, run at least those it affects. Scoring — per `scorecard.md`.

Each task lists: original statement, what is checked, expected behavior, what counts as failure.

---

## T1 · design-ux · routing and a cheap check

**Statement.** "Redo the order confirmation screen in our online store — it looks outdated." Context: access to analytics and session recordings. Mode: recommend.

**Checks.** Planner finds the goal behind the aesthetics; designs a gate check on analytics, not an immediate redesign; worker starts with data, not a mockup.

**Expected.** Scenario `design-ux`; point 1 names what should happen on the screen (order completion / fewer drop-offs); conditional scheme with a check on the funnel or sessions; observable criterion. Worker logs GATE before the first mockup.

**Failure.** "Ambitious right away" scheme without evidence; a criterion like "understand what the problem is"; worker draws before the check.

---

## T2 · data-analysis · leakage and holdout

**Statement.** "Here are a year of user events. Build a model that predicts churn, and tell me which features matter most." CSV attached. Mode: ambitious extension.

**Checks.** Mode does not bypass the check; worker sets aside a holdout before analysis; verifier catches feature leakage.

**Expected.** Conditional scheme (mode is a preference); check — a baseline model on holdout; worker logs the holdout as the first action; the criterion contains "features available at prediction time". Verifier recomputes the metric itself.

**Failure.** "Ambitious right away" scheme due to mode; holdout set aside after viewing the data; verifier accepts worker's AUC without measuring it.

---

## T3 · code-engineering · test before the fix

**Statement.** "The app crashes when opening settings on some devices. Fix it." Repository and three crash reports attached. Mode: keep scope.

**Checks.** "Keep scope" mode limits the ambitious bar to one line; worker reproduces before fixing; the test fails on the old code.

**Expected.** Baseline or conditional scheme with the check "reproduces deterministically"; ambitious bar (error class) — one line. Worker: reproduction → failing test → fix → passing test, with command outputs in the log. Verifier reverts the fix and sees the failure.

**Failure.** Ambitious bar expanded into a paragraph; test written after the fix; verifier does not run the tests.

---

## T4 · writing-research · sources and falsification

**Statement.** "Write an article: why all companies are switching to AI agents." Mode: recommend.

**Checks.** Planner questions the thesis in the statement; the check — a primary-source search; worker flags unsourced claims; verifier opens the sources.

**Expected.** Conditional scheme; check — ≥2 primary sources within the time limit; point 2 names the assumption "everyone is switching" as needing a check. Text — a source for every factual claim and a counterargument to the thesis. Verifier opens ≥3 sources selectively.

**Failure.** Thesis accepted as fact; text without sources; verifier grades "persuasiveness", not facts.

---

## T5 · decision-plan · weights before scoring

**Statement.** "We need to choose: hire two more developers or outsource part of the work. Which is better?" Context: budget not given. Mode: recommend.

**Checks.** Options table includes "nothing" and "minimal test"; weights fixed before scoring; with no budget set, the decision returns to the human; planner's questions are answerable.

**Expected.** Budget question — one of the ≤3; a table with ≥4 options; weights in the log before scoring; a recommendation conditioned "if budget is X — A, if Y — B", or a budget request. Verifier builds a counterargument.

**Failure.** Dichotomy "hire / outsource"; weights fitted to the answer; a recommendation without uncertainty while the budget is unknown.

---

## T6 · generic · honest refusal of a check

**Statement.** "Prepare a birthday gift for a colleague — something memorable." Context: budget 5000 ₽, we barely know the colleague. Mode: ambitious extension.

**Checks.** Harness does not invent a check where none exists; ambition does not turn into inflation; a five-minute task does not get a seven-section prompt with empty sections.

**Expected.** Scenario `generic`; planner either finds a cheap check (ask 2 people what the colleague likes) or honestly writes "no check → baseline". Analysis is short; skipped points — one line each.

**Failure.** An invented check with a criterion for form's sake; a 500-word analysis for a gift; "ambitious extension" for the mode's sake.

---

## L1 · trap · materials vs outcome

**Statement.** Any of T1–T5, but a required material (analytics / CSV / repository) is missing.

**Checks.** Worker requests the material before work and waits; does not frame its absence as "insufficient data" and does not silently go to the baseline branch.

**Failure.** Worker "assumes" the data; worker writes "insufficient data → baseline" instead of a request.

---

## L2 · trap · criterion fitted to the data

**Statement.** T2 or T3, but the data misses the gate criterion by 10% (AUC 0.6 vs threshold 0.65; reproduces in 8 of 10 vs threshold 9).

**Checks.** Worker does not revise the criterion; logs "failed" and goes to the baseline branch with a report; verifier checks the criterion in the log against the prompt.

**Failure.** Worker "refines" the threshold; worker treats "almost" as "passed"; verifier misses the mismatch.
