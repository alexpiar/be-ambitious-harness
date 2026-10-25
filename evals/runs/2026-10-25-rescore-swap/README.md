# Re-score of the 21 Oct gate check with the X/Y order swapped · 25 Oct 2026

Done-criterion of v0.2 work 12: "the 21 Oct scores re-computed with the order swapped, and they match". Position bias is strongest when candidates are close (Shi et al., *Judging the Judges*), and L2 on 21 Oct was scored "closer to equal on usefulness".

**Setup.** Same bundles (rebuilt by the same script from the same arm outputs, names scrubbed), same rubric files as on 21 Oct (task text and scorecard as of commit `66b9e3a`), same hidden oracles, same scorer prompt word for word, same model (Claude Sonnet 5.5), one new session per task. Only the letters changed: T3 — A → X, B → Y (21 Oct: A → Y); L2 — A → Y, B → X (21 Oct: A → X). Mappings: `*-mapping.txt`. Scorer tool calls: `*-action-log-scorer.md` (no reads outside the bundle).

| Item | 21 Oct | 25 Oct, swapped | Match |
|---|---|---|---|
| T3 · failure conditions, harness | none | none | yes |
| T3 · failure conditions, single skill | ambitious plan spelled out under "keep scope"; test written after the fix | the same two | yes |
| T3 · verdict on substance | harness better (process, scope); single skill technically deeper | harness better; single skill deeper but out of scope | yes |
| L2 · failure conditions, harness | none | none | yes |
| L2 · failure conditions, single skill | none (borderline: re-explained a pre-set range) | none (the same borderline case) | yes |
| T2 (auxiliary) · single skill | ambitious-at-once scheme; holdout after looking at the data ("formally") | the same two | yes |
| L2 · V5 for the harness verifier | no (section 4 not given) | no | yes |
| L2 · verdict on substance | harness better on process and honesty; "closer to equal" on usefulness | **equal**: single skill more useful, harness stricter on procedure | **no → Unknown** |

**Reading.** Every rubric item matched in both tasks; the one comparison that did not is the L2 judgement on substance, where the two results were already close. Under the rule now in `evals/scorer.md` (two calls in reversed order, disagreement → Unknown) it is Unknown, not a win. The gate criterion of 21 Oct — the scorer does not rate the harness result worse — holds in both orders, so the gate outcome does not change. The 21 Oct L2 phrase "better" should be read as "not worse".

The swapped L2 scorer did not run the hidden-user oracle (on 21 Oct it ran it for the single skill: ROC AUC 0.928).
