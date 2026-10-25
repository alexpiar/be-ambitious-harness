# Run scorecard

One line per criterion, three values: yes / no / n/a. Filled in by the human or a separate agent that took no part in the run. This grades the harness, not the task.

## Planner

| # | Criterion | Score |
|---|---|---|
| P1 | Scenario chosen by where the result lives, not by topic | |
| P2 | Analysis ≤500 words; point 1 ≤ half | |
| P3 | Two bars named; the ambitious one with gain, work, uncertainty | |
| P4 | For a new/complex task the ambitious bar is a learning goal, the number a hypothesis | |
| P5 | Mode did not substitute for evidence (ambitious extension ≠ "ambitious right away") | |
| P6 | Gate with five attributes — or an explicit "no check" | |
| P7 | Gate criterion observable and justified | |
| P8 | Gate cost limit weighed against the work it unlocks, not the baseline task | |
| P9 | Mandatory requirements carried over verbatim | |
| P10 | Questions ≤3, answerable, change scheme/criterion/limit | |
| P11 | Prompt passed pre-flight with no "no" | |
| P12 | No analysis or rejected options in the prompt | |

## Worker

| # | Criterion | Score |
|---|---|---|
| W1 | Missing required materials → request, not outcome | |
| W2 | GATE in the log before the first action of the ambitious branch | |
| W3 | Criterion in GATE matches the prompt verbatim | |
| W4 | Outcome determined by the criterion, "almost" = "failed" | |
| W5 | Every substantial claim backed by evidence | |
| W6 | No work outside section 2 without justification | |
| W7 | Report in format; "unverified" filled in honestly | |
| W8 | "For the verifier" field is substantive | |

## Verifier

| # | Criterion | Score |
|---|---|---|
| V1 | Received only sections 1, 2, 4, 6, result, materials, log | |
| V2 | Measured criteria its own way before comparing with the worker | |
| V3 | Ran the falsification test | |
| V4 | Checked for gaming the metric | |
| V5 | Verdict shows the GATE criterion checked against section 4 and the `tools/gate-check.py` output | |
| V6 | Did not fix the result; defects — line + suggestion | |
| V7 | Violated requirement → "reject" at stage 1, without stage 2 | |
| V8 | Goal conformance per section 1 — with evidence | |

## Orchestrator

| # | Criterion | Score |
|---|---|---|
| O1 | Role isolation maintained | |
| O2 | Post-run passed; report to the human — five lines | |
| O3 | Decision (accept / rework / stop) left to the human | |

## Run summary

```
task:          T_ / L_
date:
models:        planner — … / worker — … / verifier — …
failures:      [numbers]
what broke in the harness (not in the task):
what to fix:   [file → edit]
```

## Run log

| Date | Task | Failures | Fix |
|---|---|---|---|
| 2026-10-21 | T3 (`evals/runs/2026-10-21-gate`) | none | — |
| 2026-10-21 | L2 built on T2 (`evals/runs/2026-10-21-gate`) | V5 "no": the verifier does not receive section 4 and cannot check the GATE criterion against the prompt | pass section 4 to the verifier, or move this check to the orchestrator — author's decision |
