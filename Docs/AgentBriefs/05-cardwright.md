# A05 — Cardwright

> **Read first:** `Docs/PORT_MASTERPLAN.md` (data contracts, tiering).
> **Role:** card effects, fusion/ritual data, coverage.
> **Baseline branch:** `port/baseline` → work branch `port/a05-effects`.

## Mission

Make every one of the 1,200 cards behave correctly through a data-driven effect layer. This is the largest content lane; tier it and keep the coverage manifest honest.

## Inputs

- `Content/Data/cards.json` (1,200 records; 252 Normal, 410 Effect, 280 Spell, 160 Trap, 76 Fusion, 22 Ritual).
- `Content/Data/fusions.json` (currently 5 recipes; expand).
- A04: effect runtime primitives + script schema + test harness.
- A01: card text/errata, banned/limited list, puzzle/opponent deck usage.
- Donor: `$GX_ROM\ue5\Source\DuelAcademy\DuelEngine.cpp` (137 card handlers), `game3d/src/duel/engine.js`.

## Owned files

- `DuelAcademyIsland/Content/Data/Effects/**`
- `.../Content/Data/fusions.json`, `rituals.json`, `card_effect_manifest.json`
- `Tools/effects/**` (schema validator, converter, coverage report)
- Tests: `.../DAEffectTests.cpp`, `Tools/effects/test_*.py`

Do not edit `DADuelEngine.*`/`DAEffectRuntime.*` (A04 owns). For a missing primitive, file an interface request with a minimal repro and expected behavior.

## Deliverables

1. **Effect script schema**
   - `trigger`, `condition`, `cost`, `target`, `operations`, `duration`, `optional`, `spell_speed`, `once_per_turn`, `source_text`.
   - Deterministic, serializable, no C++ pointers in data.
   - Validator with clear errors (unknown op, bad target, missing cost, etc.).

2. **Runtime primitives (joint with A04)**
   - Draw/discard/search/mill/banish/return, destroy, summon (normal/special/fusion/ritual), set, position, ATK/DEF change, damage/heal, negate, counters, equip, control, copy, shuffle, reveal, etc.
   - Event hooks for summon/activation/battle/destroy/end/standby/draw.
   - Prompt data for target/cost/optional choices (A09 renders).

3. **Card coverage**
   - Tier 0: current 137 cards (must stay green).
   - Tier 1: vertical-slice cards (starters, Jaden, first opponents/packs/puzzles).
   - Tier 2: every card in any story/opponent/puzzle/pack/exam deck.
   - Tier 3: all 1,200.
   - Manifest per card: `scripted` / `vanilla` / `unsupported` (+reason), `tier`, `tests`.
   - No `unsupported` card in a legal deck, pack, puzzle or story duel.

4. **Fusion/ritual**
   - All 76 Fusion results: materials, fusion spell names, variants (Polymerization, Miracle Fusion, Dragon's Mirror, Power Bond, Fusion Gate, etc.).
   - All 22 Ritual monsters: ritual spells, material requirements, level sums.
   - Validation: every recipe uses existing cards; every Fusion/Ritual card has a recipe or explicit no-recipe.
   - Tests for each recipe and for invalid-material rejection.

5. **Coverage/audit tooling**
   - `python Tools/effects/audit.py` writes `card_effect_manifest.json` and fails on missing/unsupported cards.
   - Per-card test runner with seed/replay.
   - Batch conversion reports: cards added, tests added, failures.

## Work plan

1. Agree the script schema/primitive list with A04; write the validator.
2. Port the existing 137 handlers into scripts or keep them as Tier 0 C++ handlers (documented).
3. Add Tier 1 cards for the opening/vertical slice.
4. Batch the remaining Effect Monsters, Spells, Traps; then Fusions/Rituals.
5. Expand `fusions.json`/`rituals.json` from A01 canon.
6. Run coverage vs. all decks/packs/puzzles; fix gaps.
7. Freeze Tier 2 before content lock; finish Tier 3 for release.

## Acceptance criteria

- [ ] Every card has a manifest entry; 1,200/1,200.
- [ ] Tier 1+2 cards are 100% scripted; no unsupported card in any legal deck/pack/puzzle.
- [ ] All 76 Fusions + 22 Rituals have recipes/handling; invalid materials rejected.
- [ ] Per-card tests or shared tests cover every script.
- [ ] `audit.py` passes; coverage report is reproducible.
- [ ] Existing 137-card behavior unchanged.
- [ ] A04's runtime contract is respected; no direct engine edits.

## Non-goals

- Opponent AI/decks (A07), pack odds/shop (A06), UI (A09), story (A03), rules engine design (A04).

## Handoff report

Report: coverage counts by tier/type, unsupported list, fusion/ritual counts, tests added, runtime primitive requests, blockers.
