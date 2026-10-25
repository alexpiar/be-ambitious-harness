<prompt>
Scenario: code-engineering.md

## 1. Goal and outcome
Goal: the Settings screen stops crashing on the devices from the crash reports; the cause is fixed, not the symptom.
What should become possible: a user whose shell passes a locale without a region opens Settings and sees all four sections.
Scheme: baseline — bar: crash reproduced, a test fails before the fix and passes after, the whole suite is green.

## 2. Mandatory requirements and boundaries
— Original task (verbatim): "The app crashes when opening settings on some devices. Fix it."
Contradictions: none.

## 3. Materials and access
Required: the repository at commit 24f9d91; Node.js 20; the three crash reports.
Optional: a real device profile from an affected device.
If required ones are missing — ask me before starting work.

## 5. Approach and stages
1. Baseline and reproduction — the first artifact; no fix starts without it.
2. A failing test, then the fix of the cause.

## 6. Acceptance criteria and verification
Criteria: the new tests fail on 24f9d91 and pass on the fix; the full suite passes.
Reference / current level: npm test on 24f9d91, 5 tests.
Independent verification: a clean clone, the new tests on top of 24f9d91.
Falsification test: revert the fix and keep the tests — they must fail.
Gaming the metric — what counts as it: a try/catch around the screen.

## 7. Completion and report
Done when: the criteria hold and the log has the reproduction, the failing and passing test and the full npm test.
Report per core/report-format.md: result; scheme and gate outcome (baseline scheme, no gate check); assumptions; unverified conclusions; blockers.
</prompt>
