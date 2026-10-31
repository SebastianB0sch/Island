# Duel Academy port status

> **Snapshot:** 2026-10-31 (Gate 3 story integration pass).
> **Branch:** `port/baseline`; initial baseline `b4d8bb0`; Gate 2 HEAD `f6d9b12`; story integration on top of `9ae4bfb`.
> **Working tree:** local-only CardArt/Portraits remain untracked by policy; generated interior assets are committed.
> **Gatekeeper:** A10. This is the single status source.

---

## 1. Build and runtime results

| Item | Result |
| --- | --- |
| Build | **Succeeded** - Gate 3 combined build green after integration fixes |
| Packaged Win64 | **Shipping + Development** archives built; final Shipping Builds/Win64ShippingFinal2 runs; packaged 1,000-duel, puzzle/exam, campaign, portal and 141/141 effect suites pass |
| `-DAProfileSelfTest` | **182 checks, 0 failures** (save round-trip, backup recovery, corruption, migration) |
| `-DASaveFuzz=10000` | **10,000 states, 1,000 corruption cases, 200 migrations, 1,800,212 checks, 0 failures**, max save 5,634 bytes |
| `-DATwelveMonthTest` | **365 days / 12 months, 10,947 checks, 0 failures**; leap year and month rollover verified |
| `-DAEconomySelfTest` | **213 passed, 0 failed** (packs, Dorothy's Gift, bulk purchase/preview, pending grants) |
| `-DADuelRulesSelfTest` | **58 passed, 0 failed** (chains, targeting, timing, banlist, scenarios, ante) |
| `-DAEffectRuntimeSelfTest` | **141 passed, 0 failed** (current script set; source-UID trigger isolation) |
| `-DAStorySelfTest` | **14/14 PASS** (E01/E01b, 3,000 DP, Oct 7 AM, shop/save/free-roam) |
| `-DAFullStorySelfTest` | **20/20 PASS** (35 events, 44 full scenes, 176 lines, 6 emails, 84 duel refs, 35/35 reachable) |
| `-DAStoryPlaythroughTest` | **35/35 events completed, 40/40 story duels (39/39 full campaign), 28/28 checks, 0 failures** |
| `-DAPuzzleExamSelfTest` | **Puzzle 102/102 PASS, Exam 104/104 PASS, both suites PASS** |
| `-DANpcScheduleTest` | **514 passed, 0 failed** (week schedules, events, spawn/despawn, refresh) |
| `-DADuelSelfTest=1000` | **1,000 duels, 457 player wins, 543 opponent wins, 0 stalls, 0 invariant failures, deck audit 37/37, puzzle audit 100/100, 19.1s** |
| `-DAUITest` / `-DAGameplayUITest` | 8 PDA + 2 dialogue + shop/deck/exam/PDA gameplay screenshots at 1920x1080 |
| `-DATitleTest` / `-DANewGameTest` | title + new-game opening screenshots at 1920x1080 |
| `-DAPortalTest` | **188 passed, 0 failed** (all 20 portals paired; ten interior entries and classroom return teleport; screenshot captured) |
| World actors | 20 portals / 97 anchors / 38 spawn points / 1 director / 88 ambient NPCs / 47 interactables / 10 nav volumes; 1,164 level actors |
| Runtime data | 1,200 cards / 100 puzzles / 12 exam cycles / 26 duelists / 37 runtime decks / 48 packs / 37 events / 65 scenes / 176 dialogue lines / 6 emails |

The earlier profile self-test crash (backup-save assertion) is resolved; keep
the old log under `Docs/Integration/reports/logs/` as regression evidence.

Gate 3 story integration re-run (2026-10-31): real duel results now feed A02/A07
and `NotifyDuelResult`; talk-triggered events are started from world NPCs; the
opening accepts a typed name; exams apply Dropout/promotion outcomes; E20 is a
three-location chain; E29 has win/lose recovery branches; E33 is a Sheppard
promotion duel with King/Prince of Games outcomes; all 20 E33 opponents have a
world contact or ambient NPC. Validator, full story audit, campaign playthrough,
portal and NPC schedule suites are green. The remaining story debt is exact
dialogue and the four special-rule scenarios listed in section 4.

---

## 2. Canon vs runtime data

A01's immutable extracts are under `Content/Data/Canon/`; runtime data is under
the lane directories. Canon is reference; runtime is what the game loads.

| Dataset | Canon | Runtime | Status |
| --- | --- | --- | --- |
| Cards | 1,200 | 1,200 | **complete** |
| Fusions | 76 records | 76 records, 75 usable | **partial** (F.G.D. generic, UFOroid unresolved) |
| Decks | 37 (16 complete, 15 partial, 6 unknown) | 37 runtime decks (32 opponent + 5 starter), all legal | **runtime complete; canon gaps** |
| Packs | 48, pool union 1,200 | 48, pool union 1,200 | **runtime complete**; Dorothy's Gift full pool |
| Opponents | 25 | 26 (20 ranked + event/exam, incl. Sheppard) | **complete** |
| Events | 35 (E01..E33, E04b, E28b) | 37 (full 35 + opening E01b/FJ01) | **runtime complete; 35/35 playthrough PASS** |
| Scenes | n/a | 65 (21 opening + 44 full campaign, incl. E20/E29/E33 branches) | **runtime complete; playthrough PASS** |
| Dialogue | n/a | 176 lines (87 opening + 89 full campaign) | **data complete; headless playthrough PASS; exact text local-only** |
| Schedules | n/a | 7 opening NPC schedules | **opening only; director schedule test PASS** |
| Puzzles | 100 (5 levels x 20), setups/timers unknown | 100 definitions across levels 1-5 | **runtime complete; 100/100 engine replay PASS** |
| Exams | 12-cycle definition, 10 written, 7 practical, 500 pts | 12 cycles, 30 questions, 7 objectives | **runtime complete; 12/12 lifecycle PASS** |
| Emails | 6 contacts | 6 contacts / 6 messages | **unlock/read/request PASS in story playthrough** |
| Titles | 14 | 17 runtime definitions | **complete** |
| Banlist | 63 cards | 14 forbidden, 40 limited, 7 semi | **complete** |
| World | 36 mapped locations | 46 locations, 97 anchors, 10 generated interior cells, 20 portals, 38 spawns, 10 nav volumes | **generated/spawned; PIE portal 188/188 PASS** |
| Effects | manifest 1,200 entries | **362 scripted, 345 vanilla, 493 pending** | runtime implemented; 253 scripts loaded; Tier-2 gap remains |

---

## 3. System status

| System | Owner | Status | Notes |
| --- | --- | --- | --- |
| Island, sky, day/night, fast travel | A08 | **works** | Generated by `Tools/`; no manual `.umap` edits. |
| Card database (1,200) | A01/A06 | **works** | Loads in editor/headless. |
| Duel rules engine | A04 | **works** | 58/58 rules self-test; 1,000-duel gate 0 stalls, 0 invariant failures; 36/36 decks and 100/100 puzzles legal. |
| Effect layer | A04/A05 | **works / partial** | 253 data scripts load; 141/141 runtime checks; **362 scripted, 345 vanilla, 493 pending** Tier-2 cards. |
| Profile, DP, titles, counters | A02 | **works** | 182/182 profile/save checks; 10,000-state fuzz clean. |
| Calendar | A02 | **works** | 12-month simulation 10,947 checks / 0 failures; exam-Friday week rule still unproven. |
| Save/load/migration | A02 | **works** | Round-trip, backup, corruption, migration; 10,000-state fuzz + 1,000 corruption cases clean. |
| Settings | A02 | **works** | Animation speed, activation confirmation, volumes. |
| Inventory / card trunk | A06 | **works** | 1,200-card inventory, 3-copy ownership; economy 213/213. |
| Shop / packs | A06 | **works** | 48 packs cover 1,200 cards; Dorothy's Gift full pool; bulk purchase/preview tests pass. |
| Deck construction | A06 | **works** | 36 decks legal (40-60 main, <=15 Extra, <=3 copies, Year-1 banlist). |
| Opponents / AI | A07 | **works** | 26 duelists, 32 runtime opponent decks, 27 AI profiles; runtime decks all legal. |
| Exams | A07 | **works** | 12 cycles / 30 questions / 7 objectives; 104/104 engine lifecycle checks. |
| Puzzles | A07 | **works** | 100 definitions; 102/102 engine replay checks; authored fallbacks where canon setup is unknown. |
| Story / events / dialogue | A03 | **works / partial** | 35/35 events play through in-engine; 40/40 duels resolve (39/39 full campaign); name entry, talk hooks, real duel-result progression, E20/E29/E33 branches and five canon choices are wired. Exact dialogue and the E04/E09/E17/E28 special rules remain. |
| Interiors / portals / anchors | A08 | **works** | 10 cells, 20 portals, 97 anchors, 38 spawns, 1 director, 10 nav volumes; portal 188/188, NPC schedule 514/514. |
| HUD / dialogue / PDA / title / shop / deck / exam UI | A09 | **works / partial** | Title/New Game/Continue, PDA, dialogue, shop, deck editor and exam screens verified by screenshots; deeper interaction QA remains. |
| Integration/QA | A10 | **works** | Contracts, validator, puzzle validator, smoke runner, golden saves, final status. |

---

## 4. Known gaps and blockers

### P0 - remaining content blockers

1. **493 pending effects:** 362 cards are scripted, 345 vanilla, and 493 Tier-2
   cards remain `pending`; 54 story-reachable cards remain pending. No
   pending card should enter a story/puzzle deck until scripted or classified
   vanilla (A05/A04).
2. **Dialogue depth and event special rules:** the 35-event playthrough resolves
   every scene and key, but exact GBA text remains local-only; runtime uses the
   paraphrased scaffold. E04 one-turn, E09 bracket, E17 timed puzzle and E28
   bracket order are still approximations rather than authored duel scenarios.
3. **Release audits:** packaged Win64 archives now build and launch; the
   performance profile, legal/credits staging and strict validator gate remain
   (A10).

### P1 - integration debt

- 21/37 canon decks remain incomplete (15 partial, 6 unknown); runtime decks
  fill 226 slots from the generic shell/theme/legal pool and record the fills.
- All 100 canon puzzles still lack decoded setups/timers; runtime uses authored
  fallbacks. The engine replays 100/100, but the canon data gap remains.
- Canon exam week rule is unresolved (monthly Friday, exact week unknown).
- Validator warnings: 5 duplicate-material fusion recipes, F.G.D. generic
  Dragon-count, UFOroid unresolved, and 6 pre-contract shapes (roster
  `duelists[]`, banlist entry objects, `position_ue` anchors, two `scenes{}`
  bundles, `npcs{}` schedules). The validator's `flag_unwritten` /
  `counter_unwritten` warnings are data-only: `post_game`,
  `walk_home_partner_3`, `written_correct` and the `wins_*` counters are written
  by C++ (`UDAStorySubsystem`, `FDAExamUI`, `FDADuelUI`).
- PDA email backend is exercised by the campaign playthrough; the UI open/read/
  request interaction still needs a manual pass.
- Interior nav volumes exist, but the level currently rebuilds navigation at
  runtime (no saved navmesh); bake and resave before profiling/packaging.
- Shop, deck editor and exam screens are wired and screenshot-verified;
  purchase/confirm, rename/copy/erase and exam-result paths still need deeper
  interaction QA.
- No `IMPLEMENT_SIMPLE_AUTOMATION_TEST` suites; the smoke runner reports
  automation SKIP.
- A05/A07 script/exam shapes are accepted by the validator; migration to the v1
  wrappers is optional and tracked as INFO, not a blocker.

---

## 5. Gate checklist

| Gate | Criteria | Status | Evidence / blocker |
| --- | --- | --- | --- |
| **Gate 0** | Build green; Jaden duel/self-test; contracts; clean-tree merge discipline | **met** | Build green; 1,000 duels 0 stalls; 182/213/58/53/14/20 suites green; validators PASS. Gate 3 changes committed. |
| **Gate 1** | Opening -> registration -> Slifer -> Banner DP -> Syrus tutorial -> free-roam save | **partial** | Opening 14/14, 35/35 campaign playthrough, interiors/portal 188/188, gameplay UI screenshots. Exact dialogue presentation remains. |
| **Gate 2** | Systems testable; 12-month fast-forward; 1,000 AI duels; 100 puzzles; save fuzz | **met** | 1,000 duels 0 stalls/0 invariants, 100/100 puzzles, 12/12 exams, 10,000-state fuzz, 12-month 10,947 checks. |
| **Gate 3** | 33+ events, 48 packs, 100 puzzles, 12 exams, 1,200 cards, Tier-2 effects | **not met** | All content counts met; 493 effects remain pending. E02-E33 playthrough, 100 puzzles, 12 exams and 48 packs are proven. |
| **Gate 4** | RC criteria, no P0/P1, playthrough, performance | **partial** | Packaged Development/Shipping builds launch; 1,000-duel/puzzle/exam/story suites pass. Smoke performance in `Docs/PERFORMANCE.md`; full interior frame-time capture and navmesh bake remain. |
| **Gate 5** | Packaged build, legal audit, credits, tag | **partial** | Packages built; legal audit in `Docs/LEGAL_AUDIT.md`; credits/notices need staging; tag not created. |

---

## 6. Validation results

```text
python Tools/validate/validate_all.py
Result: PASS
0 errors, 15 warnings, 6 gaps, 205 info; 321 files read
```

```text
python Tools/canon/validate_canon.py
checks: 290  errors: 0  warnings: 1
```

```text
python Tools/puzzles/validate.py
PASS summary: 141 checks, 0 failures, 1 warning
duelists=25 decks=31 ai=27 puzzles=100 questions=30 cycles=12
```

```text
python Tools/economy/validate_packs.py
RESULT: PASS - 1342 checks, 0 failures
python Tools/economy/validate_decks.py
RESULT: PASS - 81 checks, 0 failures
python Tools/effects/validate_effects.py
OK: 155 effect script(s), fusion 75/76 resolved, ritual 22/22 resolved, 0 warning(s)
```

The single puzzle-validator warning is the duplicate `Luster Dragon` name (two
printings); copy limits are still enforced by id/name.

Reports:

- `Docs/Integration/reports/validate_baseline.json`
- `Docs/Integration/reports/validate_strict.json` (expected FAIL in strict mode
  until gaps are closed)
- `Docs/Integration/reports/smoke_selftests.json`
- `Docs/Integration/reports/GATE1_TEST_RESULTS.md`
- `Docs/Integration/reports/GATE3_TEST_RESULTS.md`
- `Docs/Integration/baseline.json`

Remaining validator gaps: 21 incomplete canon decks, 100 unknown canon puzzle
setups/timers, unresolved canon exam week, 493 pending effects, and the canon
pack source still expresses Dorothy's Gift as an empty `full_pool` list (the
runtime pack is complete). E02-E33/emails are data complete and proven.

---

## 7. Commands

```powershell
# Data/contract validation (baseline mode)
python Tools\validate\validate_all.py
python Tools\validate\validate_all.py --report Docs\Integration\reports\validate.json

# A01/A06/A07/A05 data validators
python Tools\canon\validate_canon.py
python Tools\puzzles\validate.py
python Tools\economy\validate_packs.py
python Tools\economy\validate_decks.py
python Tools\effects\validate_effects.py

# UE Gate 3 suites (run one switch per process)
UnrealEditor-Cmd.exe <uproject> -game -nullrhi -nosound -unattended -DADuelSelfTest=1000
UnrealEditor-Cmd.exe <uproject> -game -nullrhi -nosound -unattended -DAPuzzleExamSelfTest
UnrealEditor-Cmd.exe <uproject> -game -nullrhi -nosound -unattended -DAStoryPlaythroughTest
UnrealEditor-Cmd.exe <uproject> -game -nullrhi -nosound -unattended -DASaveFuzz=10000
UnrealEditor-Cmd.exe <uproject> -game -nullrhi -nosound -unattended -DATwelveMonthTest
UnrealEditor-Cmd.exe <uproject> -game -nullrhi -nosound -unattended -DANpcScheduleTest
UnrealEditor-Cmd.exe <uproject> -game -windowed -DAPortalTest

# Strict gate (warnings/gaps fail; currently expected red)
python Tools\validate\validate_all.py --strict
```

---

## 8. Owner matrix

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
| Contracts, validators, smoke harness, CI, build/release, status | A10 |

Shared files (`DAGameMode.*`, `DATypes.h`, `DAIslandSubsystem.*`,
`DAStudentCharacter.*`, `Build.cs`, `Config/*.ini`, `.uproject`, target files)
change only through A10.

---

## 9. Next actions

1. A05: reduce the 493 pending effects; script or classify every card used by
   story/puzzle/shop content first (92 story-event cards are highest impact).
2. A03/A09: replace the paraphrased dialogue scaffold with the local exact text
   and finish choice/history/portrait presentation; manually exercise PDA email
   open/read and pending duels.
3. A08/A10: bake and save the interior navmesh, then profile interior traversal
   and remove the runtime nav rebuild warning.
4. A09/A06/A07: deeper interaction QA for shop purchase, deck rename/copy/erase
   and exam lifecycle/result/DP feedback.
5. A01: fill the remaining 21 incomplete canon decks and resolve the exam-week
   rule; keep runtime deck fills traceable.
6. A10: packaged build, performance and legal/credits audit, strict validator
   gate, then freeze Gate 4/5 evidence.
7. A02/A04/A07: optionally add `IMPLEMENT_SIMPLE_AUTOMATION_TEST` wrappers around
   the existing switch-driven suites for CI.

---

## 10. Change log

| Date | Change | Owner |
| --- | --- | --- |
| 2026-10-30 | Gate 0 contracts v1, validator, puzzle validator, smoke runner, golden saves, status. | A10 |
| 2026-10-30 | Build green; profile 182/0, economy 119/119, rules 57/57, story 14/14, UI 10 screenshots, duel 24/0 stalls. | A10 |
| 2026-10-30 | Accepted A05 `card_effect_manifest.json` (760 pending as a GAP), A07 100-puzzle/12-exam shapes, and A03 full events/scenes/dialogue/emails shapes; moved reports to `Docs/Integration/`. | A10 |
| 2026-10-31 | Gate 2: data-driven effect runtime 44/44; shop/deck/exam/PDA screens; 10 interior cells + 20 portals / 89 anchors / 28 spawns / 1 director / 88 NPCs / 45 interactables; gameplay UI screenshots; duel 24/0 stalls. | A10 |
| 2026-10-31 | Fixed unity-build JSON helper collisions, effect-trigger enum mismatch, Python native class names and bool property names; rebuilt the level (1,134 actors). | A10 |
| 2026-10-31 | Added `-DAPortalTest`; fixed the fall-out-of-world rescue swallowing interior arrivals; 188/188 portal checks pass and the classroom screenshot is captured. | A10 |
| 2026-10-31 | Gate 3: canon decks 37/16 complete, 155 effect scripts, runtime decks 36/36 legal, 1,000 duels 0 stalls, 35/35 campaign events, 100/100 puzzles, 12/12 exams, NPC 414/414, 10k save fuzz and 12-month sim clean. | A10 |
| 2026-10-31 | Packaged Shipping/Development Win64; fixed unity-build collisions, static-init crashes and packaged story path; packaged 1,000-duel and puzzle/exam suites pass. | A10 |
| 2026-10-31 | Packaged campaign 35/35, packaged portal 188/188; legal audit and performance snapshot added; archive docs staged. | A10 |
| 2026-10-31 | Story integration: real duel results feed A02/A07 and NotifyDuelResult; talk NPCs start events; typed name entry; exam outcomes; E20 Ocean-Volcano-Gym; E29 win/lose recovery; E33 Sheppard promotion duel with King/Prince branches; five canon choices; all 20 E33 opponents have world contacts. Story 14/14, full audit 20/20, playthrough 35/35 + 40/40 duels, NPC 514/514, portal 188/188. | A03/A10 |
