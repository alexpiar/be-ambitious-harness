# Be-Ambitious Harness — a planner / worker / verifier workflow for ambitious AI tasks

> Make AI agents aim higher without losing control: two bars for every task, a cheap gate check before expensive work, and an independent verifier that never sees the worker's reasoning.

**English** · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · [Español](README.es.md)

![Scenarios](https://img.shields.io/badge/scenarios-6-blue) ![Roles](https://img.shields.io/badge/roles-planner%20%7C%20worker%20%7C%20verifier-informational) ![Eval runs](https://img.shields.io/badge/eval%20runs-2%20of%208%20tasks-yellow) ![Languages](https://img.shields.io/badge/files-EN%20%7C%20RU-informational) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## What it is: a prompt engineering framework, a Claude Code skill, a multi-agent workflow

Most AI prompts ask for a step: *fix this bug, make this screen, analyze this CSV.* The outcome you wanted — *the app stops crashing, users finish checkout, you know why churn rose* — stays implicit, so the model delivers the step and stops.

Be-Ambitious Harness is a **prompt engineering framework and multi-agent workflow** that turns any task into a prompt with:

- **Two bars** — the baseline result and a more ambitious one, with the extra work and the main uncertainty named.
- **A gate check** — a cheap, observable test that decides whether the ambitious path is worth starting, with a pass criterion fixed *before* the test runs and three outcomes: passed, failed, insufficient data.
- **Role isolation** — a planner writes the prompt, a worker executes it, a verifier grades the result seeing only the requirements, the acceptance criteria and the evidence log. Nobody grades their own work.
- **Six scenario playbooks** — design/UX, data analysis, code, writing/research, decisions/plans, generic — each with domain-specific checks and traps.
- **An eval suite** — 8 test tasks and a 30-criteria scorecard, so you can tell when the harness itself breaks. Two of the tasks have been run so far — see [Status](#status-what-has-been-tested).

It ships as a **Claude Code skill** (`/be-ambitious-harness`) in **English and Russian**, and works with any agent that can read a folder of markdown files.

---

## Why this exists

On 13 October 2026 Felix Rieseberg, an engineering manager at Anthropic who has led engineering for Claude.ai, Cowork and Claude Code Desktop, published [*How to be more ambitious: A tutorial for humans with models*](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/). The core ideas: consider the outcome rather than the individual task; insist on the instruments the best in the industry use; bring in additional fields; and do not ask the model to judge itself — insist on outside validation. He shared a short prompt: *"I want a deeper version of this task, not a bigger one…"*

Community skills followed within days: [DannyMac180's `be-ambitious`](https://github.com/DannyMac180/skills) wraps that prompt, and [robonuggets/be-ambitious](https://github.com/robonuggets/be-ambitious) turns altitude, depth and range into steps and then does the work.

The prompt is excellent and it has a limit: it is one prompt. As soon as you add the rules that make ambition safe — fixed criteria, budget limits, mandatory verification — you run into three failure modes reported in recent LLM research:

| Failure mode | What the research says | What the harness does about it |
|---|---|---|
| **Constraint saturation** | Reliable instruction following breaks down beyond 5–6 simultaneous constraints in a single generation; across 15 models at k=8, individual constraints still pass ~41% of the time, but all eight hold together only 5.7% of the time ([Vasileva, arXiv:2608.12426](https://arxiv.org/abs/2608.12426); poster at an ICML 2026 workshop) | Each role gets only the files for its step (250–630 words each); structure comes from templates, not from rules held in context |
| **Negative instructions backfire** | Naming a forbidden word primes the model to produce it; in failures the suppression signal is 4.4× weaker ([Rana, 2026 preprint](https://arxiv.org/abs/2601.08070); one model, Qwen2.5-7B-Instruct) | Instructions are positive: "include only the template sections" instead of "do not include the analysis" |
| **Self-preference bias** | LLM judges rate low-perplexity text higher than human evaluators do, regardless of who wrote it ([Wataoka et al., NeurIPS 2024 Safe Generative AI Workshop](https://arxiv.org/abs/2410.21819)) | The verifier sees only requirements, criteria, result and evidence — and preferably runs on a different model, which is what actually changes the judge's perplexity |

Each of these rests on one recent study, and applying them to agent instructions is the harness's own extrapolation. The harness is an attempt to keep "be more ambitious" working within these limits — and its eval suite is there to show where it does not.

---

## The principles

### 1. Outcome over step (altitude)

Every analysis starts with *what should become possible after this result?* A bug fix is a step; "this class of crash does not recur" is an outcome. A slide deck is a step; "leadership catches problems a quarter earlier" is an outcome. The planner names both and builds the prompt around the outcome.

### 2. Two bars, always

The **baseline bar** is quality execution within the original scope. The **ambitious bar** is one of three moves: a higher quality threshold, removing the cause instead of the symptom, or a more useful way to reach the goal. For every ambitious bar the planner states the expected gain, the extra work, and the main uncertainty. If no useful ambitious bar exists, the planner says so — ambition is not inflation.

### 3. Learning goals for new tasks

Goal-setting research shows that specific, difficult goals beat "do your best" ([Locke & Latham, 2002](https://med.stanford.edu/content/dam/sm/s-spire/documents/PD.locke-and-latham-retrospective_Paper.pdf)). But where a task first requires acquiring new knowledge or strategies, a specific difficult *performance* goal can do worse than "do your best", while a specific difficult *learning* goal does better (Seijts & Latham, 2001; 2005). Critics add that stretch goals narrow focus and invite shortcuts (Ordóñez et al., 2009). So for unfamiliar tasks the ambitious bar is phrased as a **learning goal** ("find out where the time goes"), with any number attached as a **hypothesis** ("p95 ≤ 300 ms"), not a promise. Rieseberg's "need 5 s instead of 10 s? Ask for 200 ms" trick lives here — as an experimental target with a feasibility check, so it stops being filtered out as "unfounded".

### 4. The gate: cheap evidence before expensive work

Before the ambitious branch starts, a **gate check** answers two questions: is the extra result actually valuable, and is it reachable with the available means? A gate is fully specified only when it has five attributes:

1. a concrete action and the materials it needs,
2. an observable result (a number, a fact, an artifact — not an opinion),
3. a pass criterion fixed *before* the check runs,
4. a cost limit, **substantially smaller than the work it unlocks** (a 20-minute test that saves a week is fine, even if the baseline task takes 5 minutes),
5. actions for all three outcomes: **passed, failed, insufficient data.**

Ambiguity is the third outcome, never the first. The criterion is read, not revised: if it turns out inapplicable, that is "insufficient data", not a reason to move the goalposts. And missing materials are a request to the human *before* work starts — not a gate outcome.

### 5. The human owns scope and budget

A gate can show that 200 ms is reachable and that users would notice. Whether that is worth a week depends on budget and priorities — the harness never decides that. If the gate passes and no budget for the ambitious branch was set, the worker delivers the baseline **plus** the gate results and a cost estimate, and the decision returns to the human. An "ambitious extension" mode is a *preference*, not a substitute for evidence.

### 6. Three roles, strictly separated

| Role | Reads | Produces |
|---|---|---|
| **Planner** | task, context, mode, one scenario file | a seven-section prompt with the gate inside |
| **Worker** | the prompt, materials, the scenario's "for the worker" block, its instruction files | the result and an evidence log |
| **Verifier** | sections 2 and 6 of the prompt, the result, materials, the evidence log | a verdict: accept / accept with notes / reject |

The verifier does not fix. The worker does not grade itself in place of the verifier. The verifier preferably runs on a **different model** — same-model verification is partial by construction.

### 7. Templates over rules

The worker's prompt has **seven fixed sections** (goal and outcome; mandatory requirements copied verbatim; materials; gate; approach; acceptance criteria and verification; completion and report). Structure is enforced by a skeleton, not by a list of "make sure to…" rules the model must hold in attention. A pre-flight checklist runs before hand-off; a post-run checklist runs before the human sees anything.

### 8. Verification is independent or it is not verification

Acceptance criteria measure the goal, not a convenient proxy. Every prompt includes a falsification test ("what observation would prove this wrong?") and names what counts as gaming the metric. Independence, in order of preference: a tool or test the worker can run; an external benchmark; held-out data; a different measurement method; reproduction. Another agent is useful **if it performs such a check** — agreement with the answer is not a check.

### 9. Scenarios carry the domain knowledge

Six playbooks route by *where the result lives*, not by topic. Each gives hints for the four analysis points, typical traps, a "for the worker" block, and a worked example of two bars. The design/UX playbook starts from funnel data before the first pixel; the data playbook holds out a test set as the worker's first logged action; the code playbook writes the failing test before the fix.

### 10. The harness tests itself

`evals/` holds six tasks (one per scenario) and two traps — missing materials, and a gate that misses its threshold narrowly (AUC 0.60 vs 0.65; 8 vs 9 of 10 runs). The tasks check what reading cannot: did the worker start with the gate? Was the test written before the fix (T3)? Did anyone quietly lower the criterion (L2)?

---

## How a task flows

```
 human ──▶ task + context + mode
              │
              ▼
        ┌──────────┐   scenarios/_index.md
        │ PLANNER  │──▶ picks a scenario
        └──────────┘
              │  analysis (≤500 words) → questions (≤3) → prompt (7 sections)
              ▼
        checklists/pre-flight.md       ◀── any "no" → back to planner
              │
              ▼
        ┌──────────┐   new session: prompt, materials, its instruction files — never the analysis
        │  WORKER  │──▶ gate first → outcome logged → branch → work → report
        └──────────┘
              │
              ▼
        ┌──────────┐   new session, other model if possible
        │ VERIFIER │──▶ measures criteria itself → falsification test → verdict
        └──────────┘
              │
              ▼
        checklists/post-run.md ──▶ five lines to the human ──▶ accept / rework / stop
```

---

## Scenarios

| Scenario | Result lives in | Gate example |
|---|---|---|
| `design-ux` | a screen, flow, prototype, design system | funnel by step from analytics; 3–5 session recordings |
| `data-analysis` | a finding, metric, model, data report | a baseline on a 20% holdout reaches AUC ≥ 0.6 |
| `code-engineering` | working code, a fix, a feature, infra | bug reproduces in ≥9/10 runs; one function owns ≥50% of profile time |
| `writing-research` | an article, review, docs, a talk | ≥2 primary sources found within the time limit |
| `decision-plan` | a decision, plan, roadmap, prioritization | the key assumption checked with 5 conversations or last month's data |
| `generic` | anything else | the cheapest action after which it is clear whether the expensive path is worth it — or "no gate, baseline" |

---

## Status: what has been tested

<!-- GATE-RESULTS -->

**Known gaps** (from the original notes):
- No scenario for multimodal tasks (video, audio, 3D).
- No mechanism for multi-day tasks with several gates in a row.
- The verifier on another model is a recommendation; how to pick the model depends on your environment.

---

## Install

**Claude Code, English files** — clone straight into your skills directory:

```bash
git clone https://github.com/alexpiar/be-ambitious-harness.git ~/.claude/skills/be-ambitious-harness
```

**Claude Code, Russian files** — the originals live in `ru/`:

```bash
git clone https://github.com/alexpiar/be-ambitious-harness.git /tmp/be-ambitious-harness
cp -r /tmp/be-ambitious-harness/ru ~/.claude/skills/be-ambitious-harness
```

For a single project, use `.claude/skills/be-ambitious-harness/` inside the project instead. Then in any session: `/be-ambitious-harness`, or just say *"make this task deeper"*. If you also have one of the community `be-ambitious` skills installed, call this one by its full name — `/be-ambitious` will go to theirs.

**Any other agent** — point it at `SKILL.md` as the entry point. Everything is plain markdown; there is no code to run.

---

## Quick start

1. Give the planner four things: the **task**, the **context** (who the result is for, materials, deadline, mandatory requirements), the **mode** (`keep scope` / `ambitious extension` / `recommend` — default `recommend`), and **stop after analysis** (`yes` / `no` — default `no`).
2. Read the analysis and the ≤3 questions. Answer, or accept the assumptions marked `[...]`.
3. Hand the prompt to a worker in a fresh session, with the materials.
4. Hand sections 2 and 6, the result, and the evidence log to a verifier in another fresh session.
5. Run `checklists/post-run.md`. Decide.

**What the first call looks like** (Claude Code):

```
/be-ambitious-harness

Task: The catalog page takes 5 seconds to load. Make it faster.
Context: Node/Postgres monolith, repo attached, I can give you a prod DB copy. Deadline: this sprint.
Mode: recommend
Stop after analysis: yes
```

The planner replies with a ≤500-word analysis (type of task, two bars, gate design, chosen scheme), up to three questions, and a prompt block with seven numbered sections. With `Stop after analysis: yes` it waits for your answer before finalizing the prompt.

Not every task needs this: for a five-minute task, skip the harness. It earns its cost when the ambitious branch would cost a day or more.

---

## Example: one task, two bars

**Task:** "The catalog page takes 5 seconds to load. Make it faster."

**Baseline bar:** profile, remove the main bottleneck, benchmark before/after on the same test bench (≥5 runs, median and p95, cold and warm separately), add a regression test on response time.

**Ambitious bar (as a learning goal):** find where the time goes well enough to reach p95 ≤ 300 ms cold — the number is a hypothesis.

**Gate:** profile a production copy; **pass criterion:** one layer (DB, serialization, render) owns ≥70% of the time *and* can be replaced without changing the API in ≤2 days; **cost limit:** 2 hours.
- Passed and budget set → ambitious branch.
- Passed and no budget set → baseline + profile + cost estimate; the human decides.
- Failed or insufficient data → baseline; report what was learned.

**Verification:** the verifier re-runs the benchmark, reverts the fix to confirm the regression test fails, and checks that the "warm" number was not reported as the "cold" one.

---

## Repository layout

```
be-ambitious-harness/
├── SKILL.md                 router: intake + six steps (0–6), rules, file map
├── agents/
│   ├── planner.md           four-point analysis → prompt
│   ├── worker.md            execution order, evidence log
│   └── verifier.md          verification order, verdict
├── core/
│   ├── gate.md              the gate: 5 attributes, 3 outcomes, ordering
│   ├── prompt-template.md   7 sections + skeleton
│   └── report-format.md     worker report, verifier verdict, 5-line human summary
├── scenarios/               _index.md + six playbooks
├── checklists/              pre-flight.md, post-run.md
├── evals/                   tasks.md (6 + 2 traps), scorecard.md (30 criteria)
│   └── runs/                recorded runs: protocol, fixtures, logs, scores
├── ru/                      the Russian originals — same layout
├── README.md · README.ru.md · README.zh-CN.md · README.es.md
└── LICENSE · CITATION.cff
```

---

## FAQ

**How do I make an AI agent more ambitious without it going off the rails?**
Name two bars, put a cheap gate with a fixed criterion between them, and keep the budget decision with the human. That is the whole harness in one sentence.

**Why shouldn't an LLM grade its own work?**
Because in Wataoka et al.'s study LLM judges rated low-perplexity — familiar-to-the-judge — text higher than human evaluators did, whether or not they wrote it; GPT-4 showed the strongest self-preference ([Wataoka et al.](https://arxiv.org/abs/2410.21819)). The verifier here never sees the worker's reasoning, and ideally runs on a different model.

**Isn't a seven-section prompt too long?**
It is long for the human, short for the model: each role reads a few short files (250–630 words each) plus its inputs. The alternative — one prompt carrying all the rules — crosses the 5–6 constraint threshold where instruction following breaks down.

**What is a "harness" for AI agents?**
A set of files and checklists that fix *who reads what, in which order, and what counts as done* — so the quality of the result depends on the process, not on the model remembering everything at once.

**Does it work with GPT / Gemini / local models?**
The files are plain markdown with no vendor-specific syntax. The `/skill` entry point is a Claude Code convention; any agent that can read a folder can follow `SKILL.md`. The recorded runs so far used Claude models only.

**What's the difference from the community `/be-ambitious` skills?**
Rieseberg published a prompt, not a skill. DannyMac180's `be-ambitious` (15 Oct 2026) wraps that prompt: it answers four questions for the task's field and rewrites your prompt. robonuggets/be-ambitious (17 Oct 2026) turns altitude, depth and range into steps and then does the work. This harness adds the gate with its three outcomes, role isolation with a separate verifier, scenario playbooks, checklists, and an eval suite with recorded runs.

**Which language should I use?**
Both versions have the same structure. The Russian files in `ru/` are the originals, and the first recorded runs used them; the English files are a translation checked for structural parity. Tasks and output can be in any language either way.

---

## Research behind the design

- F. Rieseberg — [How to be more ambitious: A tutorial for humans with models](https://felixrieseberg.com/how-to-be-more-ambitious-a-tutorial-for-humans-with-models/) (13 Oct 2026). Altitude / depth / range; outside judge; the original prompt.
- M. I. Vasileva — [Large Language Models Can Follow Instructions, But Not Many at Once: Phase Transitions in Compositional Constraint Satisfaction](https://arxiv.org/abs/2608.12426) (arXiv, 2026; poster at the 2nd Workshop on Compositional Learning, ICML 2026). Reliability breaks down beyond 5–6 simultaneous constraints.
- S. Rana — [Semantic Gravity Wells: Why Negative Constraints Backfire](https://arxiv.org/abs/2601.08070) (arXiv preprint, 2026). Naming a forbidden word primes it.
- K. Wataoka, T. Takahashi, R. Ri — [Self-Preference Bias in LLM-as-a-Judge](https://arxiv.org/abs/2410.21819) (NeurIPS 2024 Safe Generative AI Workshop). Judges favor low-perplexity text.
- E. Locke, G. Latham — *Building a practically useful theory of goal setting and task motivation: A 35-year odyssey* (American Psychologist, 2002).
- G. Seijts, G. Latham — *The effect of distal learning, outcome, and proximal goals on a moderately complex task* (Journal of Organizational Behavior, 2001); *Learning versus performance goals: When should each be used?* (Academy of Management Executive, 2005).
- L. Ordóñez, M. Schweitzer, A. Galinsky, M. Bazerman — *Goals Gone Wild: The Systematic Side Effects of Overprescribing Goal Setting* (Academy of Management Perspectives, 2009); disputed by Locke & Latham in the same issue.
- N. Edwards, S. Schuster — [Ask or Assume? Uncertainty-Aware Clarification-Seeking in Coding Agents](https://arxiv.org/abs/2603.26233) (arXiv, 2026). On an underspecified SWE-bench Verified, splitting underspecification detection from code execution raised an uncertainty-aware agent's resolve rate from 61.2% to 69.4% (OpenHands + Claude Sonnet 4.5); a simpler prompted interactive baseline reached 70.4%.

---

## Contributing

Issues and pull requests are welcome. The most useful contributions, in order:

1. **Eval runs.** Run any task from `evals/tasks.md`, fill the scorecard, open an issue titled `eval: T3 — <what broke>`. Real failures beat opinions. `evals/runs/` shows how a run is recorded.
2. **New scenarios.** If `generic.md` is clearly too thin for your domain, that is the signal for a new playbook — follow the structure in `scenarios/_index.md`.
3. **Translations.** New languages are welcome; `ru/` stays the source of truth until a translation has passed the evals.
4. **Research.** A paper that changes a principle above belongs in an issue with a one-line summary of what it changes.

Please keep files short: the harness relies on giving each role few instructions at a time.

---

## Roadmap

- [x] English translation of all harness files
- [ ] Recorded eval runs for all eight tasks — T3 and L2 done, see [Status](#status-what-has-been-tested)
- [ ] Scenario for multimodal tasks (video, audio, 3D)
- [ ] Multi-gate support for tasks spanning several days
- [ ] Verifier-on-another-model recipe for Claude Code subagents

---

## Author

Created by **Chernov Alexandr** (@alexpr). If you build on the harness, GitHub's "Cite this repository" button gives a ready citation from `CITATION.cff`.

If the harness saves you a wasted day of AI work, a ⭐ helps others find it: many of GitHub's rankings and Explore depend on stars.

---

## License

MIT — see [`LICENSE`](LICENSE).

Not affiliated with or endorsed by Anthropic. Claude and Claude Code are trademarks of Anthropic, PBC.
