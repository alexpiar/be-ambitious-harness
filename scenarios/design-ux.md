# Scenario: design and UX

Result — a screen, flow, mockup, prototype, component, redesign. Typical original statement: "make screen X", "improve onboarding", "draw a mockup from the brief".

## Analysis hints

**Point 1 — goal and bars.** The screen is a means. What should the person on the other side of the screen do, and what stops them now? Baseline bar — a mockup per the brief. Ambitious — usually one of three: remove a step instead of improving it; find the cause of drop-off at this step from data, not a hypothesis; build a solution reused in neighboring flows. Here the ambitious bar is almost always a learning goal: "find out where and why people leave" — not "raise conversion by N%".

**Gate check** for design is cheap and often available: step funnel from analytics; 3–5 session recordings; interviews or a hallway test on the current version; heuristic audit against a list. Pass criterion — observable: "in ≥3 of 5 sessions the person stops at field X".

**Point 2 — improvements.** Assumption worth checking against primary data: that the problem really is the interface, not the offer, price, trust, or incoming traffic. Disciplines via "action and result": an onboarding screen is "get a stranger to trust you with data and reach value" → behavioral economics (friction, default effect), copywriting (microcopy carries half of conversion), product analytics, accessibility.

**Point 3 — grounds.** Primary: step analytics, session recordings, current mockups and design system, support tickets for this flow, platform constraints. The summary "users complain it's complicated" is not enough — specific complaints needed. Worker's tools: design system access (tokens, components), a clickable-prototype environment, analytics.

**Point 4 — verification.** Criteria measure the goal: step completion, time to value, support requests — not "beautiful" and not "follows guidelines" (that is a requirement, not a criterion). Independent verification: a test with 5 audience members on a task script; heuristic audit by another agent against a checklist; comparison with the current version on the same task. Falsification test: a target-audience member, given the task and no hints — do they finish?

## Traps

- **Aesthetics replacing the goal.** "More modern" and "cleaner" are not criteria. If there is no goal behind the screen, point 1 must find it or honestly say the task is decorative.
- **Role instead of method.** "Think like a UX researcher" gives nothing. A method is "run 5 hallway tests with a protocol", "check against WCAG 2.2 AA with a checklist".
- **Redesigning everything.** Ambition ≠ volume. One removed step is worth more than three redrawn ones.
- **Testing on yourself.** The mockup's author is the worst test subject. The verifier should get the task script and the prototype, not the designer's explanation.

## For the worker

- Start with the gate check, if any: funnel data or sessions — before the first pixel.
- Every decision in the mockup — which problem from the check it addresses. A decision without a problem is a candidate for removal.
- Design system: use existing components; a new component — justified by why existing ones fall short.
- States: empty, loading, error, edge values, long strings, small screen. A mockup without states is not done.
- Accessibility: contrast, focus, tab order, target sizes — check with a tool, not by eye.
- Hand over: the mockup or prototype; a "problem → solution" map; a test script for the verifier to check without you.

## Example of two bars

Task: "Redo the company-details screen in B2B onboarding."

- Baseline: a screen in the current design system, all states, accessibility, a test script.
- Ambitious: find out which fields can be auto-filled from the tax ID or domain, and remove them from the screen; check — what share of fields in current applications matches public registry data (material: last 50 applications, limit — 2 hours, criterion — ≥40% of fields auto-fillable).
