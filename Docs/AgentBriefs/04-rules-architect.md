# A04 — Rules Architect

> **Read first:** `Docs/PORT_MASTERPLAN.md` (duel request/result contract §4.4).
> **Role:** duel rules core, chain/targeting/timing, modes and deterministic tests.
> **Baseline branch:** `port/baseline` → work branch `port/a04-rules`.

## Mission

Turn the current 137-card friendly engine into a complete, tested 2006-era rules engine that can support all 1,200 cards, the 100 puzzles, exams, ante duels and the story.

## Inputs

- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DADuelEngine.h`
- `.../Private/DADuelEngine.cpp` (current monolith)
- `C:\dev\argh\game3d\src\duel\engine.js` (reference rules + 22 tests)
- `C:\dev\argh\ue5\Source\DuelAcademy\DuelEngine.*` (native donor, 137 cards)
- A01: `banned_list.json`, `dp_rules.json`, puzzle/exam rules.
- A05: effect runtime/scripts (joint contract).

## Owned files

- `.../DADuelEngine.*` and split units (`DADuelRules.*`, `DADuelChain.*`, `DADuelTargeting.*`, `DAEffectRuntime.*`, `DADuelAiBase.*`)
- `.../DADuelTests.cpp`, `DADuelSelfTest.cpp`
- `Content/Data/Rules/**` (banned list defaults, rule constants)
- Contract header: `Docs/Contracts/DuelEngine.md`

Do not edit card effect JSON (A05), opponent AI profiles (A07), UI (A09) or save (A02).

## Deliverables

1. **Rules core**
   - Turn/phase flow: Draw, Standby, Main 1, Battle, Main 2, End; first turn draw rules; coin toss/go first-second.
   - Summon/set/flip/special/fusion/ritual; tribute requirements; position changes; battle step/damage step/replay.
   - Chain building: spell speeds, priority, optional/trigger effects, counter traps, negate, resolution order.
   - Targeting: per-effect target prompts/selections, cost payment, legality re-check on resolution.
   - Continuous/lingering effects, equip handling, control changes, banished/graveyard/return-to-deck.
   - Damage step timing, trap timing, end-phase effects, hand-limit discard, deck-out.
   - Banned/limited list, 3-copy limit, 40–60 main, 20 extra (verify side deck with A01).

2. **Modes**
   - Normal/story/free duel, exam timed, exam practical, puzzle, ante.
   - Puzzle mode loads fixed hands/fields/graveyards, turn/time limits, objective checks.
   - Ante: select card, transfer on result, return on draw.
   - Surrender/quit, result statistics: turns, LP, battle damage dealt, monsters destroyed by battle, special/fusion/ritual counts, spells/traps used.

3. **Determinism and AI interface**
   - Seeded `FRandomStream`; replay/record of inputs + seed; no wall-clock/UI dependency.
   - `IAiPolicy`/`FDAiProfile` interface for A07; base AI stays as fallback.
   - `RunSelfTest` supports 1,000 seeded AI-vs-AI; logs stalls/illegal actions.

4. **Effect runtime contract**
   - Work with A05 to define primitives: draw/discard/search/mill/banish/return, destroy, summon, position, ATK/DEF, damage/heal, negate, counters, equip, control, copies, etc.
   - Script schema validation; effect event hooks (`on_summon`, `on_activate`, `on_battle`, `on_destroy`, `on_end`, ...).
   - A05 writes scripts; you own the interpreter and primitives.

5. **Tests**
   - Regression: all existing 137-card tests pass unchanged.
   - New: chain, targeting, damage step, priority, timing, banned list, ante, deck validation, puzzle setup, replay.
   - 1,000 seeded duels; no stalls, no illegal state transitions, no crashes.

## Work plan

1. Baseline the current engine behavior with a golden test suite.
2. Split the monolith into rules/chain/targeting/effect/AI units without behavior changes.
3. Add chain/targeting/timing + activation settings; keep old behavior behind flags until tests pass.
4. Add deck validation, banned list, modes (puzzle/exam/ante), result stats.
5. Freeze `FDuelRequest`/`FDuelResult` contract with A05/A07/A09.
6. Integrate A05 scripts incrementally; run Tier 0/1/2 tests.
7. Publish `Docs/Contracts/DuelEngine.md`; support A07's puzzle/AI work.

## Acceptance criteria

- [ ] Existing 137-card regression suite passes.
- [ ] Chain, targeting, damage step, priority, timing, banned list, ante and deck validation tests pass.
- [ ] 1,000 seeded AI-vs-AI duels complete with no stalls/crashes.
- [ ] Puzzle/exam modes load and report results correctly.
- [ ] Effect runtime primitives documented and stable for A05.
- [ ] AI interface stable for A07.
- [ ] No UI/save/world dependencies in the rules engine.

## Non-goals

- Writing card scripts (A05), opponent decks/AI profiles (A07), UI (A09), story (A03).
- Rebalancing the game; preserve canon rules.

## Handoff report

Report: split files, rule coverage, test counts, known simplifications, contract changes, blockers.
