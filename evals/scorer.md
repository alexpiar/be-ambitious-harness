# Run scorer

Blind scoring of a pair of runs on one task: two arms, for example the harness and a single skill, or two versions of the harness. The first part is for the orchestrator; the second is passed to the scorer in full.

## Orchestrator: how scoring is run

1. **Bundles.** For each arm: the final artifacts, logs, reports, the verification verdict if there was one, and action logs extracted by script from the session transcripts. Arm names and mentions of the harness and the skill are scrubbed; the bundles are called X and Y.
2. **Two calls in reverse order.** Each pair is scored twice, in separate sessions with no shared context. In the first call X is the arm picked by a coin flip; in the second the letters are swapped. X is always shown first. The letter-to-arm mapping goes to `scoring/<ID>-mapping.txt` before the first call.
3. **Merging** — by arm, letters translated through the mapping. For each item and arm: if the two calls agree, that is the value; if they differ, Unknown. On substance: if both calls name the same arm better, that arm; otherwise Unknown, not a winner. The 0–1 score is recomputed from the merged items.
4. **Comparing runs.** Not only the mean score: which tasks flipped between two runs, task result pass → fail or fail → pass.
5. **The scorer does not get:** the task's reference solution (`evals/reference/`), arm names or the letter mapping, the executors' reasoning outside the artifacts, the expected outcome from the protocol, the other call's result. The scorer is a session that took no part in the run, preferably on a different model.

## Scorer: instructions

You are a scorer who took no part in the run. You score two bundles, X and Y, against a rubric. A score is evidence, not an impression. You are not told who made which bundle; do not guess.

**You get:** the task statement and its failure conditions from `evals/tasks.md`; the applicable rows of `evals/scorecard.md` and the rule for applying them to an arm without separate roles; bundles X and Y; the hidden oracle and the command to run it, if the task has one.

**Order.**
1. Read the rubric before the bundles.
2. For each rubric item and each bundle, one value with evidence: file and line, call number in the action log, command output.
   - **pass** — the failure condition did not fire; the scorecard row is "yes"; the oracle threshold is met.
   - **fail** — the condition fired; the row is "no"; the oracle threshold is not met or the oracle does not run on the result.
   - **Unknown** — not enough evidence to decide; allowed on any item. Say what is missing.
   - **n/a** — the item does not apply by the rubric's rule, not by your choice.
3. The executor's order of actions comes only from the action log, not from its own account.
4. You run the oracle yourself, on each bundle's result.
5. Compare the results on the substance of the task: X better / Y better / equal / Unknown, with the grounds. Length and polish of a bundle are not grounds.
6. In the same answer, the result. Score 0–1 = pass / (pass + fail + Unknown) over the items that are not n/a. Task result: fail if any failure condition or the oracle is fail; pass if all of them are pass; otherwise Unknown.

**Output format** — as in `evals/runs/2026-10-21-gate/scoring/T3-score.md`, with a closing block:

```
## 1. Failure conditions     table: condition | X | Y; each cell has a value and evidence
## 2. Scorecard rows         per bundle: P1 pass — evidence; …
## 3. Oracle                 per bundle: command → number → pass / fail
## 4. Substance              X better | Y better | equal | Unknown — grounds

RESULT <ID>
X: score=0.00 (pass N, fail N, Unknown N, n/a N); failures=[…]; task=pass | fail | Unknown
Y: …
substance: X better | Y better | equal | Unknown
blinding: kept | broken — by what
```
