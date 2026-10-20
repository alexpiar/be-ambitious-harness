# Scenario routing

Choose by **where the result lives**, not by topic. The task "analyze data to decide whether to launch a feature" is `decision-plan`; data is a means. The task "make the dashboard stop lying" is `data-analysis`.

| Scenario | Result | Signals |
|---|---|---|
| `design-ux.md` | screen, flow, mockup, prototype, design system, redesign | "mockup", "screen", "prototype", "Figma", "UX", "onboarding", "flow", "make it prettier" |
| `data-analysis.md` | conclusion from data, metric, model, data report | "analyze", "why did it drop", "churn", "dataset", "table", "correlation", "A/B" |
| `code-engineering.md` | working code, fix, feature, refactoring, infrastructure | "bug", "crashes", "implement", "API", "tests", "performance", "deploy" |
| `writing-research.md` | text, article, review, documentation, talk, source research | "write", "article", "review", "research the topic", "documentation", "post", "speech" |
| `decision-plan.md` | decision, plan, strategy, prioritization, roadmap | "what to do", "is it worth", "plan", "priorities", "strategy", "choose between" |
| `generic.md` | everything else, or a mix without a clear center | — |

## Rules

- One scenario per task. A mix — the one where the result lives; a second scenario can join as one item in point 2 of the analysis, as "a method from another discipline".
- A scenario gives analysis-point hints and the "For the worker" block. The core of the analysis is in `agents/planner.md`; the scenario does not replace it.
- If a task fits no scenario and `generic.md` is clearly thinner than needed — that signals adding a new scenario, not stretching an existing one.

## Structure of each scenario

1. Signals and typical original statement
2. Hints for the analysis points (1–4)
3. Three or four typical traps
4. "For the worker" block — passed to the worker with the prompt
5. Example of two bars
