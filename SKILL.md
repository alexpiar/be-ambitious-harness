---
name: be-ambitious-harness
description: Harness for ambitious AI task statements. Use when the user writes /be-ambitious, "make this task deeper", "improve the task statement", "raise the bar", "strengthen the prompt" (or in Russian «сделай задачу глубже», «улучши постановку», «поставь амбициознее», «усили промпт») — or before launching any substantial task worth raising the bar on. Routes the task by scenario (design, data, code, writing, decision, generic), runs the analysis, builds a prompt with a gate check, hands it to a worker, runs an independent verifier. Not needed for five-minute tasks.
---

# Be-Ambitious Harness

Three roles and one human. **Planner** turns the task into a prompt with two bars and a gate check. **Worker** executes the prompt, starting with the check. **Verifier** grades the result seeing only the goal, requirements, criteria and facts. **Human** chooses the scheme and cost limit — this is not delegated.

Each role reads only its own files. This is deliberate: instruction following breaks down past 5–6 simultaneous constraints, so structure comes from files and templates, not from rules held in mind.

## Flow

**0. Intake.** Collect four fields: `task`, `context`, `mode` (keep scope / ambitious extension / recommend), `stop_after_analysis` (yes/no). Defaults if empty: recommend, no.

**1. Routing.** Open `scenarios/_index.md`, pick a scenario by signals. Torn between two — take the one where the result lives. None fits — `generic.md`.

**2. Analysis and prompt.** Read `agents/planner.md` and the scenario file. Run the analysis; scenario hints serve their matching points, not all at once. Output questions and the prompt per `core/prompt-template.md`. With `stop_after_analysis = yes`, stop after analysis and questions; continue only after the human answers.

**3. Pre-flight check.** Run the prompt through `checklists/pre-flight.md`. Any "no" — back to step 2.

**4. Worker.** New session or subagent. Pass: prompt, materials, the scenario's "For the worker" block, `agents/worker.md`, `core/gate.md`, `core/report-format.md`. Nothing from the analysis.

**5. Verifier.** Separate session, preferably another model. Pass: prompt sections 1, 2, 4, 6, result, materials, the worker's evidence log, `agents/verifier.md`, `core/report-format.md`, `tools/gate-check.py`. Sections 3, 5, 7, the worker's reasoning and the planner's analysis stay with you.

**6. Acceptance.** Run `checklists/post-run.md`. To the human: result, verifier's verdict, list of unverified items. The decision "accept / rework / stop" is theirs.

## Harness rules

- Mandatory requirements of the original task pass through every stage verbatim.
- Acceptance criteria and the gate criterion are fixed at step 2 and only read afterwards.
- Work specific to the ambitious branch starts after the gate outcome is logged.
- The verifier does not fix. The worker does not grade itself in place of the verifier.
- Any stage lacking materials requests them from the human and waits — this is not a gate outcome.

## Files

- `agents/` — role instructions: `planner.md`, `worker.md`, `verifier.md`
- `core/` — shared definitions: `gate.md`, `prompt-template.md`, `report-format.md`
- `scenarios/` — domain hints: `_index.md` and six scenarios
- `checklists/` — `pre-flight.md`, `post-run.md`
- `evals/` — test tasks and scorecard for the harness itself; run after any edit
