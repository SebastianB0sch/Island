# A03 — Director

> **Read first:** `Docs/PORT_MASTERPLAN.md` (story command contract §4.3, events).
> **Role:** story campaign, event graph and NPC schedules.
> **Baseline branch:** `port/baseline` → work branch `port/a03-director`.

## Mission

Deliver the complete GBA story as a data-driven, testable event graph: every scene, choice, schedule, requirement, reward, email and branch — from Sheppard's speech to the King of Games ending.

## Inputs

- `Content/Data/Canon/events.json`, `dialogue_keys.json`, `emails.json`, `packs.json`, `opponents.json` (A01; stubs until frozen).
- A02 APIs: profile, calendar, titles, flags, counters, save.
- A08 anchors/portals/spawn points; A09 dialogue/cutscene UI.
- Donor: `$GX_ROM\ue5\Source\DuelAcademy\DialogueNpc.*`, `DuelAcademyGameMode.cpp` (quest/state patterns).
- Public event guide (Appendix D).

## Owned files

- `.../DAStorySubsystem.*`, `DAEventGraph.*`
- `.../Content/Data/Story/**` (`events.json`, `dialogue.json`, `schedules.json`, `emails.json`, `scenes/*.json`)
- `Docs/Story/**`
- Tests: `DAStoryTests.cpp`, `DAEventGraphTests.cpp`

Do not edit UI drawing, world layout, duel rules, inventory or save schema.

## Deliverables

1. **`UDAStorySubsystem` / `FDAEventGraph`**
   - Event definitions: `id`, title, priority, once/repeatable, trigger, requirements, scene, outcomes.
   - Trigger types: date, weekday, period, location, talk-to-NPC, duel result, exam result, flag, counter, card ownership, dorm/title, random chance.
   - Requirements: all/any, nested, counters (`wins_jaden >= 3`), titles, cards, flags, completed events.
   - Scene queue: emits `FStoryCommand` (§4.3) to A09/A08; serializable for save/load mid-scene.
   - Choices: options with requirements, outcomes, flags, rewards; deterministic.
   - Outcomes: flags, counters, DP, cards, packs, title, dorm, email unlock, next event.
   - Failure/retry: duel losses, exam fails, event retries; never softlock.

2. **All 33+ events**
   - Opening: Sheppard speech, registration, Slifer dorm, Banner 3,000 DP, Syrus tutorial.
   - Slifer arc: Pharaoh, Jaden's new hero, Old Memories, Dark Fiend, Occult, Jinzo, Blair/Missing Hero, Chumley room.
   - Ra arc: Brier/Beauregard, Goblin King, Sartyr, Dimitri/Yugi's deck, 7th Deck.
   - Obelisk arc: Pride of the Elite, Chazz battles, Obelisk revenge, Chazz Reborn, Alexis suspicion, Shadow Game, Damon/draw, Valentine.
   - Holidays/festivals: Duel Festival, Christmas, New Year, Valentine + reversal, Dorothy truck, walk-home.
   - Endgame: King of Games trigger, credits, post-game/name change.
   - Exact conditions/rewards from A01; ambiguous conditions flagged.

3. **Dialogue and scenes**
   - Data-driven dialogue nodes with speaker, portrait/expression, text key, next, choices, conditions, commands.
   - Use A01 keys; if exact dialogue is unavailable, write a faithful paraphrase and mark `source: "port"` in traceability.
   - Camera anchors, NPC moves, fades, banners, music/SFX through the command queue.
   - Email content: contact unlock, messages, duel requests, event triggers.

4. **Schedules**
   - `schedules.json`: NPC → weekday/date/period → location/anchor → activity/conditions/priority.
   - Event overrides (e.g., a character waits at the arena only for an event).
   - Dorm restrictions (who is where, who can be challenged).
   - Hand off spawn/anchor requirements to A08; do not move actors directly.

5. **Tests**
   - Event graph reachability from new game; no dead ends/cycles without exit.
   - Condition unit tests for every event; reward-once tests; choice branch tests.
   - 12-month simulation: all events reachable under canonical conditions.
   - Save/load mid-scene restores queue; no duplicate rewards; no softlocks.

## Work plan

1. Implement the event graph + command queue against stubs; write the opening vertical slice first.
2. Hand off opening anchors/dialogue needs to A08/A09; test the opening.
3. Add Slifer arc; then Ra; then Obelisk; then holidays/endgame.
4. Add schedules/emails; integrate A08's director.
5. Run the 12-month simulation; fix unreachable/dead events with A01.
6. Freeze event IDs and dialogue keys; publish `Docs/Story/EVENT_INDEX.md`.

## Acceptance criteria

- [ ] 33+ events implemented; every event has a trace ID and canon source/confidence.
- [ ] Event graph validator passes; all events reachable; no softlocks.
- [ ] Opening hour matches the original beats and is save/load safe.
- [ ] Rewards granted exactly once; choices deterministic; failures retryable.
- [ ] Schedules cover every day/period for every NPC; event overrides work.
- [ ] Emails unlock/trigger correctly; walk-home/random events work.
- [ ] 12-month simulation passes; ending/post-game reachable.
- [ ] No hardcoded dialogue in C++; all text keys validated.

## Non-goals

- UI drawing (A09), world geometry (A08), duel rules (A04), pack odds (A06), exam scoring (A07).
- Changing the save schema; request fields from A02.

## Handoff report

Report: event count, conditions implemented, scene command coverage, schedule coverage, simulation results, canon gaps, blockers.
