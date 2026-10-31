# A02 — Registrar

> **Read first:** `Docs/PORT_MASTERPLAN.md` (contracts §4.4–4.8, gates).
> **Role:** profile, calendar, save, progression.
> **Baseline branch:** `port/baseline` → work branch `port/a02-registrar`.

## Mission

Make the player, the school year and the save data real. Every other lane depends on your APIs; keep them small, stable and data-driven.

## Inputs

- `Docs/Canon/calendar.json`, `titles.json`, `dp_rules.json` (from A01; use stubs until frozen).
- Target: `DAStudentCharacter.*`, `DAIslandManager.*`, `DAHUD.*`, `DAGameMode.*`.
- Donor: `$GX_ROM\ue5\Source\DuelAcademy\DuelAcademyGameMode.*` (quest state patterns), save crypto `romhack/save_crypto.py` (reference only).

## Owned files

- `DuelAcademyIsland/Source/DuelAcademyIsland/Public|Private/DASaveGame.*`
- `.../DAProfileSubsystem.*`
- `.../DACalendarSubsystem.*`
- `.../DATitleSystem.*`
- `.../DASettings.*`
- `.../Content/Data/Profile/**`
- Tests: `.../DASaveTests.cpp`, `DACalendarTests.cpp`, `DAProfileTests.cpp`

Shared files (`DAGameMode.*`, `DATypes.h`, `DAIslandSubsystem.*`, `DAStudentCharacter.*`) only via A10.

## Deliverables

1. **`UDAProfileSubsystem`**
   - Identity: name, dorm, title, DP, gender/pronouns if needed.
   - Counters: `wins_total`, `wins_<duelist>`, `timed_clears`, `written_correct`, `written_total`, `cards_owned`, `duels_total`, `story_events_cleared`.
   - Flags: string→bool, with typed helpers and validation against A01's flag list.
   - Deck/inventory/email handles (owned by A06/A03) behind interfaces, not direct storage.
   - Delegates: `OnDPChanged`, `OnTitleChanged`, `OnDormChanged`, `OnFlagChanged`, `OnDayChanged`.
   - Debug API: `SetDate`, `AwardDP`, `SetFlag`, `ForceTitle`, `SetDorm`, `SaveNow`.

2. **`UDACalendarSubsystem`**
   - Fields: `Year` (1..), `MonthIndex` (0..11, Oct..Sep), `Day` (1..31), `Weekday` (Sun..Sat), `Period` (AM/PM/Night), `Hour`.
   - `AdvancePeriod`, `AdvanceDay`, `Sleep`, `SkipToDate`, `GetExamDay`, `IsExamDay`, `GetDateText`.
   - Exam days: monthly Friday (verify exact rule with A01); events query date/weekday/period.
   - Bridge to `ADAIslandManager`: set visual hour from calendar; do not let the manager own the date.

3. **`UDATitleSystem`**
   - 12 permanent titles, ordered; temporary titles (e.g., Occult Duelist, Novice Duelist).
   - Canonical conditions from A01; evaluate after duel/exam/collection changes.
   - Dorm promotion/demotion rules and event exemptions; `Dropout Boy` fail state.
   - `GetTitle`, `EvaluateTitle`, `CanPromoteDorm`, `ApplyExamOutcome`.

4. **`UDASaveSubsystem`**
   - 3 slots + autosave; save metadata (name, date, DP, title, dorm, playtime, screenshot optional).
   - Payload: versioned JSON in a `USaveGame`; atomic write; backup; corruption detection/recovery.
   - Versioning: `CurrentVersion`, `Migrate(json, fromVersion)`; no silent field drops.
   - Autosave triggers: day change, exam result, event complete, pack purchase, duel result, manual save.
   - `Save`, `Load`, `Delete`, `EnumerateSlots`, `GetLastError`.

5. **`UDASettings`**
   - Animation speed, confirm activation, text speed, BGM/SFX volume, controls, language key, subtitles.
   - Saved in profile/settings; defaults in `Content/Data/Profile/settings.json`.

6. **Tests**
   - Calendar: 12 months, leap/year rollover, weekdays, periods, exam days, first playable day.
   - DP: base + LP + battle damage + 50/monster + Exodia/deck-out/Final Countdown/Destiny Board; turn multipliers; halving/doubling; no negative.
   - Titles: every threshold; exam/dorm outcomes; Dropout Boy recovery.
   - Save: round-trip, fuzz 10,000 states, migration v1→v2, corruption recovery, autosave.

## Work plan

1. Define the save schema (`Docs/Contracts/DAProfileSave.schema.json`) and review with A10.
2. Implement `UDAProfileSubsystem` + counters/flags/delegates.
3. Implement `UDACalendarSubsystem` and the `ADAIslandManager` bridge.
4. Implement `UDATitleSystem` and dorm logic with stub canon data.
5. Implement save/autosave/migration/settings.
6. Add tests; wire debug commands for other agents.
7. Replace stubs with A01 canon; freeze the API at Gate 1.

## Acceptance criteria

- [ ] New game creates a valid profile with 3,000 DP, Slifer, Apprentice Duelist, date Sat Oct 7, AM.
- [ ] 12-month calendar correct; exam Fridays identified; day/period rollover correct.
- [ ] DP formula matches canon; tests for every branch/multiplier; no negative DP.
- [ ] All 12 titles + temporary titles evaluate correctly; dorm promotion/demotion works.
- [ ] Save/load round-trip; 3 slots + autosave; fuzz/migration/corruption tests pass.
- [ ] Settings persist; typewriter/animation/activation settings exposed.
- [ ] No direct disk writes outside `UDASaveSubsystem`.
- [ ] Other agents can compile against the API without touching your files.

## Non-goals

- Story content (A03), inventory/shop (A06), exam logic (A07), UI drawing (A09).
- Editing `DAGameMode`/`DATypes` without A10.

## Handoff report

Report: schema version, API signatures, tests run, canon assumptions, migration notes, blockers.
