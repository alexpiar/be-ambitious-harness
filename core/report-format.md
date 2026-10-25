# Report formats

The worker and the verifier share the same fields — so the reports can be laid side by side.

## Worker report

```
RESULT
delivered: [files, links, artifacts]
check without the author: [commands, one line each — per the scenario's "For the worker" block]

SCHEME
chosen: baseline | ambitious right away | conditional
GATE: [block from core/gate.md, if any]

BARS (baseline miss — defect; ambitious miss — expected result)
baseline: met | not met (why)
ambitious: reached | not reached | not run (why) — what we learned

EVIDENCE
claim → supported by (file / test / number / source)
…
unverified: [claims without support]

CRITERIA (self-check — does not replace the verifier)
criterion → measured as → value → met / not met / cannot measure

ASSUMPTIONS
…

BLOCKERS
…

FOR THE VERIFIER
what to check differently from how I checked: …
```

## Verifier verdict

```
VERDICT: accept | accept with notes | reject (stage 1 | 2)

REQUIREMENTS (section 2, verbatim)
requirement → met / violated / cannot verify → evidence

CRITERIA (section 6)
criterion → my measurement method → my value → worker's value → match / mismatch

FALSIFICATION
test: … → result: …

GAMING
checked: [methods from section 6 + one of my own] → found / not found

GATE
gate-check --strict: result, FAIL lines
criterion matches section 4: yes / no
outcome logged before ambitious work: yes / no
outcome matches the criterion: yes / no

GOAL CONFORMANCE (section 1)
what should become possible → achieved / not achieved / cannot verify → evidence

UNVERIFIED
what and why; what is needed to verify it

DEFECTS
one defect — one line — one fix suggestion
```

## Report for the human (assembled by the orchestrator)

Five lines: what was done; which scheme and gate outcome; verifier's verdict; what is unverified; what decision is required from the human.
