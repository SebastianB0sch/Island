# Agent Briefs

One brief per subagent. Read `Docs/PORT_MASTERPLAN.md` first; then use the matching brief verbatim when dispatching.

| Order | File | Agent | Lane |
| --- | --- | --- | --- |
| 1 | [`01-canon-extraction.md`](01-canon-extraction.md) | A01 Source Scribe | Canon extraction, ROM archaeology, traceability |
| 2 | [`02-registrar.md`](02-registrar.md) | A02 Registrar | Profile, calendar, save, titles, DP |
| 3 | [`03-director.md`](03-director.md) | A03 Director | Story events, dialogue, schedules, emails |
| 4 | [`04-rules-architect.md`](04-rules-architect.md) | A04 Rules Architect | Chains, targeting, timing, modes, tests |
| 5 | [`05-cardwright.md`](05-cardwright.md) | A05 Cardwright | 1,200-card effects, fusion/ritual |
| 6 | [`06-quartermaster.md`](06-quartermaster.md) | A06 Quartermaster | Shop, packs, inventory, deck builder |
| 7 | [`07-challenger.md`](07-challenger.md) | A07 Challenger | Opponents, AI, exams, 100 puzzles |
| 8 | [`08-architect.md`](08-architect.md) | A08 Architect | Interiors, portals, anchors, NPC placement |
| 9 | [`09-interface.md`](09-interface.md) | A09 Interface | HUD, dialogue, PDA, shop/deck/exam UI |
| 10 | [`10-integration-qa.md`](10-integration-qa.md) | A10 Gatekeeper | Contracts, merges, tests, release |

## Dispatch rule

Do not start all ten at once. Start **A01 + A10**, pass Gate 0, then **A02 + A04 + A09**, then **A03 + A06 + A08**, then **A05 + A07**. A10 runs continuously and owns every merge gate.

## Common prompt suffix

> Read `Docs/PORT_MASTERPLAN.md` first. Work only in your owned files. Baseline is `port/baseline`; your branch is in the brief. Do not touch another lane's files. Report files changed, tests run, API changes and blockers.
