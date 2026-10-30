# A07 — Challenger

> **Read first:** `Docs/PORT_MASTERPLAN.md` (duelists, exams, puzzles).
> **Role:** duelist roster, AI profiles, 100 timed puzzles, exam lifecycle.
> **Baseline branch:** `port/baseline` → work branch `port/a07-challenger`.

## Mission

Populate the school with the full GBA roster, make each duelist play like their deck, and implement the 100 timed puzzles and the monthly exam cycle.

## Inputs

- A01: `opponents.json`, `decks.json`, `puzzles.json`, `exams.json`, `banned_list.json`.
- A02: profile/calendar/title/dorm/DP APIs.
- A04: rules engine, modes, AI interface, result stats.
- A05: effect support manifest (no unsupported cards in decks/puzzles).
- A06: deck validation/inventory.
- Donor: `game3d/src/duel/engine.js` AI, `ue5/DuelEngine.*` AI.

## Owned files

- `.../DAOpponentSubsystem.*`, `DADuelistAI.*`, `DAExamSubsystem.*`
- `Content/Data/Opponents/**`, `Puzzles/**`, `Exams/**`
- `Tools/puzzles/**`
- Tests: `DAOpponentTests.cpp`, `DAPuzzleTests.cpp`, `DAExamTests.cpp`

Do not edit duel rules (A04), effect scripts (A05), UI (A09), story (A03) or world (A08).

## Deliverables

1. **Roster**
   - 20+ ranked duelists + event-only opponents: Banner, Pharaoh, Jaden, Syrus, Chumley, Blair, Gerard; Sartyr, Bastion, Dimitri, Brier, Beauregard; Crowler, Fontaine, Zane, Chazz, Topher, Conklin, Alexis, Mindy, Jasmine, Torrey, Damon; Mimicry, Shadow Duelist/Titan.
   - Canonical decks, variants/evolution (Jinzo additions, Chazz Ojama, etc.), dorm/location/schedule gates, gifts/ante.
   - Email/duel requests, walk-home, rematch, deck evolution counters.
   - `Content/Data/Opponents/roster.json`, `decks/*.json`, `ai/*.json`.

2. **AI profiles**
   - Per-deck strategy: beatdown, burn, stall, fusion, ritual, control, draw/Exodia, goblin, etc.
   - Difficulty tiers; deterministic seeds; no illegal actions; no infinite loops.
   - Puzzle solver/validator (scripted solution + engine replay).
   - AI self-test: 1,000 seeded duels, no stalls; profile behavior tests.

3. **100 timed puzzles**
   - 5 levels × 20; fixed hands/fields/graveyards/LP; turn/time limits; objective; retries.
   - `Content/Data/Puzzles/P001..P100.json` with setup, solution, reward, source trace.
   - Validator: every puzzle solvable via solution; no ambiguous/illegal states; time limit fair.
   - UI payload for A09 (board preview, objective, timer, result).

4. **Exams**
   - Monthly lifecycle: written (10 questions), timed puzzle, practical (7 objectives: Battle, Spells, Traps, Damage, Fusion, Ritual, Special Summon).
   - Mimicry stall deck; 500-point scoring; pass/fail; retries; exemptions; Dropout Boy/Fonda recovery.
   - `Content/Data/Exams/questions.json`, `practicals.json`, `scoring.json`.
   - Result payload for A02 (title/dorm/DP) and A09 (breakdown).
   - Exam-day scheduling with A02/A03.

5. **Tests**
   - Every deck legal/use supported cards.
   - 100/100 puzzles validated; turn/time limits; retries.
   - Exam scoring/pass/fail; practical objectives count correctly; exemption logic.
   - AI no stalls; evolution triggers; email/duel requests.

## Work plan

1. Define roster/deck/AI/puzzle/exam schemas; review with A04/A09.
2. Implement roster + deck loading + basic AI profiles; test vs. Tier 1 cards.
3. Implement 20 puzzles (level 1) + validator; then all 100.
4. Implement exam lifecycle + scoring + Mimicry; wire A02/A09.
5. Add evolution/emails/walk-home/ante with A03/A06.
6. Run 1,000 AI duels; tune difficulty; freeze IDs.
7. Support story-required opponents/modes.

## Acceptance criteria

- [ ] 20+ opponents with legal canonical decks and variants.
- [ ] Every deck uses only supported cards (A05 manifest).
- [ ] 100/100 puzzles have setups, limits, solutions and rewards; validator passes.
- [ ] Exam scoring reproducible; pass/fail/title/dorm outcomes match canon; Dropout Boy recovery.
- [ ] AI profiles distinct and stable; 1,000 seeded duels no stalls.
- [ ] Email/duel requests/evolution/walk-home/ante logic works.
- [ ] No UI/rules/story/world edits; APIs stable.

## Non-goals

- Implementing card effects (A05), rules engine (A04), UI (A09), story scripts (A03), interiors (A08).

## Handoff report

Report: roster/deck/puzzle/exam counts, validation results, AI stall report, canon gaps, blockers.
