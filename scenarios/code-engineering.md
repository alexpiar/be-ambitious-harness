# Scenario: code and engineering

Result — working code, a fix, feature, refactoring, infrastructure. Typical statement: "fix bug X", "implement feature Y", "speed up the page".

## Analysis hints

**Point 1 — goal and bars.** One bug is a step; the goal — the bug class does not recur. One feature is a step; the goal — what the user should be able to do. Baseline bar — a fix or feature with tests within the original scope. Ambitious — usually: remove the cause of an error class (type, invariant, contract-level test); a performance threshold well above what was asked ("200 ms instead of 5 s" — as a hypothesis with a profile); automate what is now done by hand. For an unfamiliar codebase the ambitious bar is a learning goal: "find out where the time goes", and the number — a hypothesis after profiling.

**Gate check.** Reproduction: does the bug reproduce deterministically? Profile: where exactly is 80% of the time? Reconnaissance: how many code locations will the change touch (grep, dependency graph)? Criterion — observable: "reproduces in ≥9 of 10 runs", "one function takes ≥50% of profile time", "≤N files touched".

**Point 2 — improvements.** Assumption to check: that the error is where it shows (symptom in UI, cause in data); that what seems slow really is. Disciplines: testing (property-based, fuzzing for parsers and formats); observability (a metric or log showing a regression before users do); security, if input, auth, or secrets are involved; operations (rollback, migration, feature flag).

**Point 3 — grounds.** Primary: the repository and its tests, logs and traces, error reports with versions, profiles, access to a reproduction environment. The summary "users say it's slow" is not enough. Worker's tools: running tests and the app; profiler; linter and types; CI.

**Point 4 — verification.** Criteria: a test that failed before and passes after; a before/after metric on the same test bench under the same load; all existing tests green; coverage preserved. Independent verification: the verifier runs tests and benchmark itself; diff review for whether the test checks the symptom, not a tautology; reproduction on another machine or OS. Falsification test: revert the fix — the test must fail; feed edge-case input not covered by tests.

## Traps

- **Test fitted to the fix.** A test written after the fix so it passes. Needed: a test that fails on the old code — the worker logs this.
- **Benchmark on a warm cache.** "Now it's 200 ms" on the second run. The criterion must state conditions: cold start, N runs, median and p95.
- **Scope creep.** Refactoring "while we're at it". Any change outside section 2 is a separate report item with justification, or is not made.
- **Fix without a cause.** A retry, timeout, try/catch around the symptom. Cause not found — state it explicitly, mark the fix as mitigation.

## For the worker

- First artifact — a reproduction or profile, logged with command and output. Without it, the fix does not start.
- The test is written before the fix and fails; command and output — into the log. After the fix it passes; output — into the log.
- Benchmark: same test bench, ≥5 runs, median and p95, cold and warm separately. Numbers without conditions — under "unverified".
- Full test suite and linter — before hand-in; output — into the log.
- Changes outside section 2 — a list with justification for each, or revert.
- Hand over: diff or branch; commands for reproduction, tests, benchmark — so the verifier repeats them without you; the log with command outputs.

## Example of two bars

Task: "The catalog page takes 5 seconds to load, make it faster."

- Baseline: profile, remove the main bottleneck, before/after benchmark, a response-time regression test.
- Ambitious: goal — p95 ≤300 ms on a cold cache (hypothesis); check — a profile on a production copy shows ≥70% of time in one layer (DB, serialization, render) and that layer is replaceable without changing the API (limit — 2 hours, criterion — share ≥70% and replacement plan ≤2 days).
