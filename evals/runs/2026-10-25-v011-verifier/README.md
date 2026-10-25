# Verifier checks for v0.1.1 · 25 Oct 2026

Behavioral checks of the "done when" criteria of v0.2 works 2 and 14 (verifier gets sections 1, 2, 4, 6; two stages). Not a comparison run: one verifier session per check, on artifacts recorded on 21 Oct (`../2026-10-21-gate/`). Verifier model: Claude Sonnet 5.5, Russian files (`ru/`) from branch `v011/verifier`. Each verifier saw only a fresh folder `$V` with the files listed in its brief; `action-log.md` is extracted by script from the session transcript (no reads outside `$V` in any of the three).

| Check | Input | Expected | Result |
|---|---|---|---|
| `T3-B-run1/` | T3 sections 1, 2, 6 (from T3-A's prompt), single-skill result from 21.10 | "reject (stage 1)", stage 2 not run | "reject (stage 1)", **but stage 2 checks were run anyway** → rule clarified in `agents/verifier.md` (record stage 1 before any stage 2 step; stage 2 fields "not run") |
| `T3-B-run2/` | same, after the clarification | same | "reject (stage 1)": currency shows "USD" where section 2 requires "—"; scope beyond "keep scope" without justification. Stage 2 "not run" |
| `L2-A/` | L2 sections 1, 2, 4, 6, worker result and journal from 21.10, regenerated data (sha256 `2284d9bc…`) | V5 can be scored from the verdict alone | "accept with notes". GATE block: `gate-check --strict` = 1 (the 21.10 journal paraphrased the applicability clause and dropped the rationale), default mode = 0; own check: threshold clause matches section 4, outcome "not passed" matches the criterion (own AUC(B) 0.550). A separate scorer session given only `verdict.md` and rows V1–V8 scored V5 "yes", V8 "yes", V7 "n/a" |

Criterion of work 14 (T3-B → "reject" at stage 1): met in run 2. Criterion of work 2 (V5 scorable on L2 without the orchestrator): met.
