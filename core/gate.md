# Gate check

The single definition. Planner designs it, worker runs it, verifier cross-checks it.

## What it is

An action that shows whether the ambitious branch is worth starting, before resources are spent on it. Checks one or both:

- **value** — the extra result actually advances the goal;
- **feasibility** — obtainable with available means within the constraints.

## Five attributes

A check is fully written when all five are present:

1. **Action** — what exactly is done and which materials are needed.
2. **Observable result** — a number, fact, artifact; an opinion does not qualify.
3. **Pass criterion** — a threshold set before running; justified by the goal, constraints, or data. Unknown threshold — a `[...]` field the human fills in.
4. **Cost limit** — time, calls, money; substantially smaller than the extra work the check unlocks. The baseline task is not the yardstick: a twenty-minute check is justified if it saves a week.
5. **Actions for three outcomes** — see below.

If a check with these attributes cannot be built — this is recorded; the scheme becomes baseline.

## Three outcomes

| Outcome | Condition | Action |
|---|---|---|
| **Passed** | criterion met within the cost limit | ambitious branch — if its cost limit is set; otherwise baseline + report with a cost estimate for the human's decision |
| **Failed** | criterion not met | baseline branch; the report gives the check result and why |
| **Insufficient data** | cost limit exhausted, result unobservable, criterion turned out inapplicable | baseline branch; the report gives what remained unknown and what is needed to find out |

Ambiguity is the third outcome, not the first.

## Order of work

- The check runs first. Before its outcome, only the check itself and work common to both branches are allowed.
- The criterion stays as written. Revising it based on observed data is unavailable to the worker; if the criterion is inapplicable — the outcome is "insufficient data", and the report says so.
- Missing materials listed as required for the check — a request to the human before work starts, not an outcome.
- The outcome is logged before the first action of the ambitious branch.

## Log entry format

```
GATE
action:                 …
materials:              …
observable result:      …
criterion (as written): …
cost limit:             …
actual cost:            …
outcome:                passed | failed | insufficient data
consequence:            which branch and why
```
