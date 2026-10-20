# Prompt pre-flight check

Run by the planner before output and by the orchestrator before hand-off to the worker. Any "no" — prompt goes back for rework.

## Structure

- [ ] First line — scenario name from `scenarios/`.
- [ ] Sections 1, 2, 3, 5, 6, 7 present in this order.
- [ ] Section 4 present if and only if the scheme is conditional.
- [ ] Prompt has only template sections; analysis, rejected options, and choice history are absent.

## Content

- [ ] Section 1 names what should become possible or happen — not only the artifact.
- [ ] Section 1 names the scheme and bar in one line.
- [ ] Section 2 — mandatory requirements carried over verbatim (compare with the original task line by line).
- [ ] Section 3 — required and optional materials separated; has the line on requesting before work.
- [ ] Section 6 — criteria measure the goal; has a reference or current level; a falsification test; an independent verification method runnable without the worker.
- [ ] Numeric targets marked: mandatory — in the criteria, experimental — as hypotheses.
- [ ] `[...]` fields stand only where the human can fill them in; for each it is clear what to enter.

## Gate check (for the conditional scheme)

- [ ] All five attributes from `core/gate.md`: action, observable result, criterion, cost limit, three outcomes.
- [ ] Criterion is observable (number, fact, artifact), not an opinion.
- [ ] Cost limit substantially smaller than the work the check unlocks.
- [ ] For the "passed" outcome it states: a cost limit for the ambitious branch is set — or baseline plus report.
- [ ] There is an ordering line: ambitious work — after the logged outcome.

## Self-sufficiency

- [ ] The prompt is clear without this conversation: no references to "as discussed", "see above", names from the analysis.
- [ ] All context the worker needs is inside the prompt or in the listed materials.

## Questions

- [ ] No more than three; each changes the scheme, a criterion, or the cost limit; the human can answer each.
