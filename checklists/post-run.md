# Post-run acceptance

Run by the orchestrator once the worker report and verifier verdict exist. Result — a five-line report for the human per `core/report-format.md`.

## Process integrity

- [ ] Worker did not get the planner's analysis; verifier did not get the worker's reasoning or sections 1, 3, 4, 5, 7.
- [ ] Verifier is a separate session; if the same model, this is noted in the report to the human.
- [ ] If there was a gate check: GATE block is in the log, precedes the first ambitious-branch action, its criterion matches section 4 verbatim.
- [ ] If the worker requested materials — the request came before work, not framed as an "insufficient data" outcome.

## Report reconciliation

- [ ] Every section 2 requirement has a line in the verifier's verdict.
- [ ] Every section 6 criterion is measured by the verifier its own way or marked "cannot verify" with a reason.
- [ ] Worker and verifier values per criterion are compared; mismatches listed.
- [ ] Falsification test run; result recorded.
- [ ] Worker's and verifier's "unverified" lists merged; duplicates consolidated.

## Boundaries

- [ ] Changes outside section 2 (if any) are listed by the worker with justification.
- [ ] Signs of gaming the metric were checked by the verifier; result recorded.

## For the human

- [ ] Five lines: what was done; scheme and gate outcome; verdict; what is unverified; what decision is required.
- [ ] If gate outcome is "passed" with no cost limit set — a cost estimate for the ambitious branch attached, decision goes to the human.
- [ ] If verdict is "reject" — defects listed with suggestions; the next step (rework / stop) is the human's choice, not the orchestrator's.

## Feedback to the harness

- [ ] What in the scenario did not work or was not needed — one line in `evals/scorecard.md` for this run.
