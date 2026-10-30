# Duel Academy port status

> **Snapshot:** 2026-10-30 (Gate 0 integration).
> **Branch:** `port/baseline`. Initial baseline `b4d8bb0`; Gate 0 lane commits
> are landing continuously (HEAD observed at final validation: `3c02d4c`).
> **Working tree:** active lane changes are still present and uncommitted. A10
> has not committed or pushed anything.
> **Gatekeeper:** A10. This file is the single status source; lane reports are
> linked from the handoff notes, not copied here.

---

## 1. Build and runtime baseline

| Item | Result |
| --- | --- |
| Editor target | `DuelAcademyIslandEditor Win64 Development` |
| Build command (from UBT log) | `UnrealBuildTool DuelAcademyIslandEditor Win64 Development -Project=C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject -WaitMutex -FromMsBuild` |
| Build result | **Succeeded** (initial 6 actions, 9.91 s; latest rebuild 23.29 s) |
| Build log | `C:\Users\Sebas\AppData\Local\UnrealBuildTool\Log.txt` |
| Editor DLL | `DuelAcademyIsland/Binaries/Win64/UnrealEditor-DuelAcademyIsland.dll` (rebuilt 2026-10-30 18:35:51; latest UBT result Succeeded, 23.29 s) |
| Headless duel self-test | **24 iterations, 12 player wins, 12 opponent wins, 0 stalls, average 11.7 turns** |
| Duel rules self-test | **58 passed, 0 failed (ALL PASS)** |
| Economy self-test | **119 passed, 0 failed** |
| Profile self-test | **PASS** (`DAProfileSelfTest PASSED.` on the 18:35 rebuild; an earlier run crashed at the backup-save path, now resolved) |
| Self-test command | `UnrealEditor-Cmd.exe DuelAcademyIsland.uproject -game -nullrhi -nosound -unattended -nop4 -DADuelSelfTest -log -stdout` (same pattern for `-DAProfileSelfTest`, `-DADuelRulesSelfTest`, `-DAEconomySelfTest`) |
| Runtime load evidence | 1,200 cards, 4 baseline decklists, 75 usable fusion recipes (76th unresolved), 1 player deck, 25 opponents / 31 decks, 48 packs, 30 exam questions / 12 exam sets / 7 practical objectives / 100 puzzle definitions, 16 titles |

No compiler errors were found in the baseline build output. The build was not
re-run by A10 after the later data-only changes; C++ source is owned by the
other lanes and is being rebuilt by them. The self-test above ran against the
current editor DLL and passed with zero stalls.

`Tools/integration/run_smoke.py --self-tests` reproduces the four checks and
captures logs under `Content/Data/Integration/reports/logs/`. The latest run
passed all four: duel 24/0 stalls, profile PASSED, duel rules 58/58, economy
119/119. The automation-only run is SKIP because no tests match the filter yet.

---

## 2. Canon vs runtime data

A01's immutable extracts are under `Content/Data/Canon/`; runtime data is under
the lane directories. They are intentionally different at this stage: canon is
reference, runtime is what the game actually loads.

| Dataset | Canon reference | Runtime data | Status |
| --- | --- | --- | --- |
| Cards | 1,200 / 1,200, ids 1..1200 | `cards.json` 1,200 | **complete** |
| Fusion recipes | 76 / 76 records | 76 records, 75 usable | **partial** (F.G.D. generic, UFOroid unresolved) |
| Decks | 31 (4 complete, 27 unknown/incomplete) | 36 decks, all legal | **runtime complete; canon gaps** |
| Packs | 48, pool union 1,200 | 48, pool union 1,200 | **runtime complete**; Dorothy's Gift pool empty |
| Opponents | 25 | 25 (20 ranked + event/exam) | **complete** |
| Events | 35 (E01..E33, E04b, E28b) | 3 opening events (E01, E01b, FJ01) | **runtime partial** |
| Scenes | not applicable | 21 opening scenes | **opening only** |
| Dialogue | not applicable | 86 opening lines | **opening only** |
| Schedules | not applicable | 7 opening NPC schedules | **opening only** |
| Puzzles | 100 (5 levels x 20), setups/time unknown | 100 definitions, levels 1-5 | **runtime definitions complete; engine solution validation pending** |
| Exams | 12-cycle definition, 10 written, 7 practical, 500 pts | 12 cycles, 30 questions, 7 practical objectives, 500 pts | **runtime definitions complete; lifecycle test pending** |
| Emails | 6 contacts | no runtime email table | **runtime missing** |
| Titles | 14 | 16 runtime title definitions | **complete** |
| Banlist | 63 cards | 14 forbidden, 40 limited, 7 semi | **complete** |
| World | 36 mapped locations | 41 implicit locations, 83 anchors, 10 interior cells, 20 portals, 28 spawns | **partial** (6 story anchors missing) |
| Effects | no manifest | 137 engine handlers, 10 Tier-1 scripts | **critical gap** |

The validator reads both layers and reports canon findings separately
(`canon_*` checks) from runtime findings.

For context, the `b4d8bb0` baseline commit had no save/calendar/story/
inventory or interiors. The active working tree now contains A02's
save/calendar/profile, A06's inventory/shop/deck logic, A08's interior/portal/
anchor data and A03's opening story, but these are partial and not yet verified
end-to-end. The earlier profile self-test failure is resolved on the 18:35
rebuild, but save fuzz/migration and the full playthrough are still pending.

---

## 3. System status

| System | Owner | Status | Notes |
| --- | --- | --- | --- |
| Island, sky, day/night, fast travel | A08 | **works** | Baseline island generated by `Tools/`; no manual `.umap` edits. |
| Card database (1,200) | A01/A06 | **works** | Loads in editor and headless. |
| Duel rules engine | A04 | **works / partial** | 1,200-card database, 137 name-specific handlers, 0 stalls in 24-duel self-test. Chain/target/timing coverage still incomplete. |
| Effect layer | A05 | **partial** | 10 Tier-1 scripts; no 1,200-entry manifest; 137/1,200 named handlers. |
| Profile, DP, titles, counters | A02 | **works / partial** | Runtime logs show titles/DP/profile loaded; golden save validates; profile self-test passes on the 18:35 rebuild. Save fuzz/migration still pending. |
| Calendar | A02 | **works** | 12-month calendar, month index 0..11, AM/PM/Night; exam Friday rule canonical week unresolved. |
| Save/load/migration | A02 | **works / partial** | Versioned JSON, 3 slots + autosave, atomic write and backup; golden v1 save passes. Fuzz/migration suite still to be run at scale. |
| Settings | A02 | **works** | Animation speed, activation confirmation, volumes. |
| Inventory / card trunk | A06 | **works / partial** | 1,200 rarity hints, 3-copy ownership, ante pending; runtime provider save section still being wired. |
| Shop / packs | A06 | **works / partial** | 48 packs load; Dorothy's Gift pool empty; odds/prices provisional. |
| Deck construction | A06 | **works** | 36 decks validate: 40..60 main, <=20 extra, <=3 copies, banlist legal. |
| Opponents / AI profiles | A07 | **works / partial** | 25 duelists, 31 decks, 27 AI profiles; evolution/request wiring needs integration tests. |
| Exams | A07 | **works / partial** | 12 runtime cycles, 30 questions, 7 practical objectives, 500-point scoring; exam lifecycle/retry/exemption tests still pending. |
| Puzzles | A07 | **partial** | 100 runtime definitions across levels 1-5; validator checks setup/solution refs. Engine scripted-solution validation and canon setups/timers are still pending. |
| Story / events / dialogue | A03 | **partial** | Opening E01/E01b/FJ01, 21 scenes, 86 lines, 7 schedules; E02..E33 and emails missing at runtime. |
| Interiors / portals / anchors | A08 | **partial** | 46 locations, 83 anchors, 10 interior cells, 20 portals, 28 spawns; story anchor coverage is now green, interior entry/exit tests pending. |
| HUD / dialogue / PDA / shop / deck / exam UI | A09 | **partial** | Code-only Canvas screens landed in source; UI smoke/screenshot automation not yet run. |
| Integration/QA | A10 | **works** | Contracts, validator, smoke runner, golden save, baseline report. |

---

## 4. Known gaps and blockers

### P0 / release blockers

1. **Effect coverage:** 137/1,200 named handlers; no `Effects/manifest.json`.
   Every obtainable card must be `scripted` or explicitly `unsupported` before
   Tier 2 content can freeze (A05).
2. **Runtime event coverage:** only E01, E01b and FJ01 are wired; E02..E33 are
   canon records without runtime scenes/conditions (A03).
3. **Runtime exam lifecycle:** 12 exam cycles and 30 questions exist, but the
   written/timed/practical lifecycle, retries and title/dorm outcomes are not
   yet proven end-to-end (A07/A02).
4. **Puzzle validation:** 100 runtime definitions exist across levels 1-5, but
   the engine has not yet proven every scripted solution; canon setups/timers
   remain unknown (A07/A01).
5. **Emails:** no runtime `Story/emails.json`; PDA contacts cannot unlock (A03).
6. **Dorothy's Gift:** empty pack pool (A06).
7. **Fusion edge cases:** five duplicate-material recipes; F.G.D. needs generic
   Dragon-count support; UFOroid Fighter is unresolved (A05/A04).

### P1 / integration debt

- Nine pre-contract data shapes are normalized by the validator but still emit
  `*_schema_drift` warnings: roster `duelists[]`, single-object puzzles,
  `position_ue` anchors, opening event bundle, `nodes{}` dialogue, `scenes{}`,
  `npcs{}` schedules, and `cycles[]`/Qxxx exam data. Lanes must migrate or A10
  must formally extend the schema.
- 27/31 canon decks are marked incomplete/unknown; public guides do not give
  full lists. A01 must mark them fallback or obtain evidence.
- Canon event duels reference four decks missing from `Canon/decks.json`
  (`jinzo_spirit`, `damon_exodia`, `yugi_deck`, `bastion_seventh`) and five
  opponents missing from the canon opponent list; A01 must reconcile them.
- Canon exam week rule is unresolved (monthly Friday, exact week unknown).
- 100/100 canon puzzles lack decoded setup and timer; runtime must author them.
- No Unreal automation tests exist yet; the smoke runner skips the automation
  step. A02/A03/A04/A05/A06/A07/A08/A09 tests are still to be added.
- The 24-duel self-test is not yet the 1,000-duel gate; A04 must add
  `-DADuelSelfTest=N`.
- Pack odds/prices are provisional (A01/A06).
- No clean-checkout packaged build has been run since the lane changes.

### Explicitly not started / not verified

- Full 12-month playthrough and all 33+ events.
- Post-game/King of Games ending.
- 100/100 puzzle scripted validation.
- Save fuzz (10,000 states), migration v1->v2, corruption recovery at scale.
- Controller/accessibility/localization pass.
- Performance budget (60 fps, save <1 s, fast travel <2 s).
- Legal/asset audit for the final package.

---

## 5. Gate checklist

| Gate | Criteria | Status | Evidence / blocker |
| --- | --- | --- | --- |
| **Gate 0** | Baseline builds; Jaden duel/self-test passes; contracts reviewed; no dirty-tree conflicts | **partial** | Build succeeded; duel self-test 0 stalls; profile PASSED; duel-rules 58/58 and economy 119/119 pass. Contracts and validator published, but the tree is still large and pre-contract shapes remain. |
| **Gate 1** | Opening: name entry -> Sheppard -> registration -> Slifer -> Banner DP -> Syrus tutorial -> free-roam save | **not verified** | Opening data/scenes exist; no end-to-end playthrough run. Need A02/A03/A09 integration. |
| **Gate 2** | Every system exists/testable; 12-month fast-forward; 1,000 AI duels; 100 puzzles; save fuzz | **not met** | Systems exist in source; tests not run. 100 puzzle definitions exist but engine solution validation and save fuzz are pending. |
| **Gate 3** | 33+ events, 48 packs, 100 puzzles, 12 exams, all 1,200 cards obtainable, Tier 2 effects | **not met** | Canon events/packs/puzzles/exams mostly complete; runtime events/exams/puzzles and effects incomplete. |
| **Gate 4** | RC criteria, no P0/P1, 12-month playthrough, performance | **not started** | — |
| **Gate 5** | Packaged build, legal audit, credits, tag | **not started** | — |

---

## 6. Validation and smoke commands

```powershell
# Data/contract validation (baseline mode: gaps pass, structural errors fail)
python Tools\validate\validate_all.py

# Strict gate (warnings and gaps fail)
python Tools\validate\validate_all.py --strict

# Full smoke: validator + headless duel self-test (+ automation when tests exist)
python Tools\integration\run_smoke.py --validate
python Tools\integration\run_smoke.py --duel-selftest
python Tools\integration\run_smoke.py --self-tests
python Tools\integration\run_smoke.py --all --automation-filter DuelAcademy
```

`--self-tests` passes all four on the 18:35 rebuild: duel, profile, duel rules
and economy. `--all` still reports automation SKIP until test suites exist.

Current baseline report (2026-10-30, 161 files read):

```text
Result: PASS
0 errors, 21 warnings, 13 gaps, 40 info, 25 checks
```

Report: `Content/Data/Integration/reports/validate_baseline.json`.
The warnings are fusion edge cases, five canon event/deck references and
schema-drift notices; the gaps are
canon/runtime coverage (27 incomplete canon decks, canon puzzle setups/timers,
canon exam week, runtime events/emails/effects, Dorothy's Gift).

---

## 7. Owner matrix

| Path / system | Owner |
| --- | --- |
| `Tools/canon/**`, `Docs/Canon/**`, `Content/Data/Canon/**` | A01 |
| Save, profile, calendar, titles, settings, DP, counters | A02 |
| Story events, scenes, dialogue, schedules, emails | A03 |
| Duel rules, chain, targeting, timing, self-tests | A04 |
| Effects, fusion/ritual data, coverage manifest | A05 |
| Inventory, shop, packs, deck logic, card trunk | A06 |
| Opponents, AI, puzzles, exams | A07 |
| World, interiors, portals, anchors, spawns, NPC placement | A08 |
| HUD, dialogue UI, PDA, shop/deck/exam UI, cutscenes | A09 |
| Contracts, validator, smoke harness, CI, build/release, status | A10 |

Shared files (`DAGameMode.*`, `DATypes.h`, `DAIslandSubsystem.*`,
`DAStudentCharacter.*`, `Build.cs`, `Config/*.ini`, `.uproject`, target files)
change only through A10.

---

## 8. Immediate next actions

1. A03: wire the remaining E02..E33 scenes/rewards and publish emails; migrate
   the opening bundle to the v1 event/scene/dialogue/schedule wrappers.
2. A05: publish `Effects/manifest.json` for 1,200 cards and resolve the three
   fusion edge cases.
3. A07: prove the 12-exam lifecycle (written/timed/practical, retries,
   exemptions, title/dorm outcomes) and run the engine scripted-solution proof
   over all 100 puzzle definitions.
4. A08: publish the 6 missing story anchors; merge `location_map.json` into the
   anchors contract or expose it to the validator.
5. A06: fill Dorothy's Gift and confirm the runtime inventory/deck save
   provider section names.
6. A04: add `-DADuelSelfTest=N` and run the 1,000-duel gate.
7. A02: run save fuzz/migration and point the runtime save payload at the
   validated `save.v1` fixture.
8. A09: add UI automation/screenshot tests and a PDA/dialogue smoke.
9. A10: clean the baseline branch, run strict validation, and start the Gate 1
   opening-hour playthrough.

---

## 9. Change log

| Date | Change | Owner |
| --- | --- | --- |
| 2026-10-30 | Gate 0 contracts v1 (`Docs/Contracts`), validator, smoke runner, golden save, baseline report, status. | A10 |
| 2026-10-30 | Build verified; 24-duel self-test 0 stalls; profile/duel-rules/economy self-tests all green on the 18:35 rebuild. | A10 |
| 2026-10-30 | Canon 35 events / 100 puzzles / 48 packs / 25 opponents / 12-cycle exams validated; runtime puzzle definitions reached 100 across levels 1-5 and runtime exams reached 12 cycles / 30 questions. | A10 |
