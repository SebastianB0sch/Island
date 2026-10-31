# Gate 3 test results — full runtime evidence

**Date:** 2026-10-31  
**Branch:** `port/baseline`  
**Build:** `DuelAcademyIslandEditor Win64 Development` — **Succeeded**  
**Runtime:** `UnrealEditor-Cmd -game -nullrhi -nosound -unattended` (portal/UI runs use windowed 1920×1080).

## 1. Data and contract validation

| Command | Result | Tail |
| --- | --- | --- |
| `python Tools/canon/validate_canon.py` | **PASS** | `checks: 290  errors: 0  warnings: 1` |
| `python Tools/validate/validate_all.py` | **PASS** | `0 error(s), 15 warning(s), 6 gap(s), 304 info; 420 file(s) read` |
| `python Tools/validate/validate_all.py --strict` | **FAIL (expected)** | 15 warnings + 6 gaps |
| `python Tools/puzzles/validate.py` | **PASS** | `145 checks, 0 failures, 1 warning` |
| `python Tools/economy/validate_packs.py` | **PASS** | `48 packs, 1200 cards, pool union 1200; 1342 checks, 0 failures` |
| `python Tools/economy/validate_decks.py` | **PASS** | `5 decks; 81 checks, 0 failures` |
| `python Tools/effects/validate_effects.py` | **PASS** | `253 scripts, fusion 75/76, ritual 22/22, 0 warnings` |
| `python Tools/world/validate_layout.py --strict` | **PASS** | `36 locations, 10 interiors, 20 portals, 97 anchors, 38 spawns` |
| `python Tools/world/test_interiors.py` | **PASS** | 10 portal routes |

## 2. Runtime suites

| Switch | Result | Evidence |
| --- | --- | --- |
| `-DAProfileSelfTest` | **PASS** | `182 checks, 0 failure(s)` |
| `-DAEconomySelfTest` | **PASS** | `213 passed, 0 failed` |
| `-DADuelRulesSelfTest` | **PASS** | `58 passed, 0 failed` |
| `-DADuelSelfTest=1000` | **PASS** | `1000 iterations, 457 player wins, 543 opponent wins, 0 stalls, 0 invariant failures, deck audit 37/37, puzzle audit 100/100` |
| `-DAEffectRuntimeSelfTest` | **PASS** | `147 passed, 0 failed` (current script set; re-run after the equip target-loss fixes) |
| `-DAStorySelfTest` | **PASS** | 14/14 (opening E01/E01b) |
| `-DAFullStorySelfTest` | **PASS** | 20/20 (35 events, 44 full scenes, 176 lines, 84 duel refs, 35/35 reachable) |
| `-DAStoryPlaythroughTest` | **PASS** | 35/35 events, 40/40 story duels (39/39 full campaign), 28/28 checks, 0 missing scenes/dialogue/outcomes |
| `-DAPuzzleExamSelfTest` | **PASS** | `PuzzleSelfTest: 102 passed, 0 failed`; `ExamSelfTest: 104 passed, 0 failed`; `BOTH SUITES PASS` |
| `-DANpcScheduleTest` | **PASS** | `514 passed, 0 failed` |
| `-DASaveFuzz=10000` | **PASS** | `10,000 states, 1,000 corruption cases, 200 migrations, 1,800,212 checks, 0 failures` |
| `-DATwelveMonthTest` | **PASS** | `365 days, 12 months, 45 saves/loads, 10,947 checks, 0 failures` |
| `-DAPortalTest` | **PASS** | `188 passed, 0 failed`; ten interior entries + classroom return |
| `-DAGameplayUITest` | **PASS** | shop/deck/exam/PDA screenshots at 1920×1080 |
| Packaged Shipping title | **PASS** | `Builds/Win64Shipping` archive launches to the title screen |
| Packaged `-DADuelSelfTest=1000` | **PASS** | `457/543 wins, 0 stalls, 0 invariant failures, deck audit 36/36, puzzle audit 100/100`, exit 0 |
| Packaged `-DAPuzzleExamSelfTest` | **PASS** | Puzzle 102/102, Exam 104/104, exit 0 |
| Packaged story load | **PASS** | `35/35` events, `39/39` duels from the pak after the content-path fix |
| Packaged `-DAPortalTest` | **PASS** | `188 passed, 0 failed` in the Development archive |

## 2b. Packaging and static initialization

- Shipping archive: 1,590 cooked packages, 578.96 MiB IoStore container, 0 cook errors.
- Development archive: same content, logs enabled, used for packaged self-tests.
- Two global bootstrap objects (`FDAA02GateBootstrap`, `FProfileSelfTestBootstrap`)
  were calling `FCommandLine`/tickers during static initialization and crashed
  before logging with `777006 (CrashDuringStaticInit)`. Both are now
  `UGameInstanceSubsystem`s.
- Raw `Content/Data/*.json` files are present in the pak; packaged story paths
  are resolved once against `ProjectContentDir()`.
- Details: `Docs/PACKAGING.md`.

## 3. Content dimensions

| Dataset | Result |
| --- | --- |
| Cards | 1,200 exact |
| Effect scripts | 253 (362 scripted, 345 vanilla, 493 pending) |
| Packs | 48, pool union 1,200; Dorothy's Gift full 1,200-card pool |
| Runtime opponent decks | 31, all legal under Year 1 banlist |
| Constructed decks | 36/36 legal; 3 copies / 40–60 main / ≤15 Extra |
| Events | 35 canonical, all completed in-engine |
| Puzzles | 100 definitions; 102/102 engine checks |
| Exams | 12 cycles; 104/104 lifecycle checks |
| Interiors | 10 generated cells; 20 portals; 10 nav volumes |
| NPC actors | 88 placed + 28 schedule spawn points + 1 director |

## 4. Defects fixed during Gate 3

- Effect loader rejected `send_to_graveyard`; aborted all 155 scripts. Fixed.
- Generated scripts fired cross-copy by card name; added source-UID trigger
  isolation and two-copy regression tests.
- Interior arrivals were reset by the fall-out-of-world rescue at Z −29,900;
  added interior state to suppress rescue/swimming and restore it on exit.
- Save migration truncated fractional playtime and mishandled JSON version 0;
  fixed and fuzzed.
- 12-month test double-counted its start day; corrected the test.
- NPC director ownership was not applied to spawned characters; fixed and
  verified with 414 checks.
- P010 puzzle used a Defense Position battle that cannot deal damage; replaced
  with a legal Spear Dragon piercing line.
- A04 puzzle audit rejected revive lines; replaced by A07's authored solution
  replay.
- Deck legality: runtime opponent decks regenerated from canon; 30/36 failures
  → 36/36 pass.

## 5. Remaining Gate 3 gaps

- 493 pending Tier-2 effects (54 story-reachable).
- Exact GBA dialogue text remains local-only; runtime uses the paraphrased
  scaffold.
- 21/37 canon decks incomplete (15 partial, 6 unknown); runtime fills 226 slots.
- 100 canon puzzle setups/timers still undecoded; authored fallbacks.
- Exam-week rule unresolved.
- Navmesh is rebuilt at runtime; bake/save before packaging.
- Packaged build, performance, legal/credits audit and strict validator gate
  remain.

## 6. Evidence locations

- `Docs/Port_STATUS.md`
- `Docs/Canon/GATE3_RECONCILIATION.md`
- `Docs/Canon/DECK_TRACEABILITY.md`
- `Docs/Effects/COVERAGE_BY_DECK.md`
- `Docs/Opponents_Deck_Report.md`
- `Docs/Story/CAMPAIGN_PLAYTHROUGH.md`
- `Docs/Puzzles/PUZZLE_ENGINE_TESTS.md`
- `Docs/World/NPC_SCHEDULES.md`
- `Docs/renders/port/interior_classroom.png`

## 7. Story integration re-run (2026-10-31)

Commands were run headless with
`UnrealEditor-Cmd.exe <uproject> /Game/DuelAcademy/Maps/DuelAcademyIsland -game -nullrhi`.

| Suite | Result |
| --- | --- |
| `Tools/validate/validate_all.py` | **PASS**, 0 errors; 15 warnings, 6 known gaps |
| `Tools/puzzles/validate.py` | **PASS**, 145 checks, 1 duplicate-name warning |
| `Tools/economy/validate_packs.py` | **PASS**, 1,342 checks |
| `Tools/economy/validate_decks.py` | **PASS**, 81 checks |
| `Tools/effects/validate_effects.py` | **PASS**, 253 scripts, 75/76 fusions, 22/22 rituals |
| `-DAStorySelfTest` | **14/14 PASS** |
| `-DAFullStorySelfTest` | **20/20 PASS** (35 events, 44 full scenes, 176 lines, 84 duel refs, 35/35 reachable) |
| `-DAStoryPlaythroughTest` | **PASS**, 35/35 events, 40/40 story duels (39/39 full campaign), 28/28 checks |
| `-DAPuzzleExamSelfTest` | **PASS**, puzzle 102/102, exam 104/104 |
| `-DAProfileSelfTest` | **PASS**, 182 checks |
| `-DAEconomySelfTest` | **PASS**, 213 checks |
| `-DAEffectRuntimeSelfTest` | **PASS**, 147/147 |
| `-DADuelSelfTest=1000` | **PASS**, 457/543 wins, 0 stalls, 0 invariants, deck audit 37/37, puzzle audit 100/100 |
| `-DAPortalTest` | **PASS**, 188/188 |
| `-DANpcScheduleTest` | **PASS**, 514/514 |

Story fixes verified by these runs:

- `FDADuelUI` records profile/opponent results, DP, `wins_<opponent>` and
  `last_duel_player_lp`, then notifies the story after the result screen closes.
- Tutorial and exam duels can suppress DP; headless story duels record synthetic
  counters so story gates do not depend on the UI.
- `ADAStudentNPC::Interact` starts talk-triggered events before generic dialogue;
  Banner, Brier, Sartyr, Fontaine, Blair, Topher, Conklin, Damon, Dimitri and
  Gerard have world contacts, and Sheppard/chancellor, Chumley and Shadow Duelist
  are spawned.
- Opening name entry is a real 1-8 character text field backed by
  `SetPlayerName`; starter deck choice is a scene choice.
- Exams apply Dropout/promotion outcomes and written counters.
- E20 is Ocean -> Volcano -> Gym; E29 has win/lose recovery scenes and LP-based
  DP; E33 is a Sheppard promotion duel with King/Prince of Games branches.
- E32 uses a stable per-day 2/5 roll; E33 enforces 200 wins, 10 wins against
  each of 20 duelists and 60% written answers.

Remaining story gaps: exact GBA dialogue is local-only, the runtime remains a
paraphrase, and E04/E09/E17/E28 still need authored special-rule scenarios.
