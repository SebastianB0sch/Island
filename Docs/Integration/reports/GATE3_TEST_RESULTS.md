# Gate 3 test results — full runtime evidence

**Date:** 2026-10-31  
**Branch:** `port/baseline`  
**Build:** `DuelAcademyIslandEditor Win64 Development` — **Succeeded**  
**Runtime:** `UnrealEditor-Cmd -game -nullrhi -nosound -unattended` (portal/UI runs use windowed 1920×1080).

## 1. Data and contract validation

| Command | Result | Tail |
| --- | --- | --- |
| `python Tools/canon/validate_canon.py` | **PASS** | `checks: 290  errors: 0  warnings: 1` |
| `python Tools/validate/validate_all.py` | **PASS** | `0 error(s), 15 warning(s), 6 gap(s), 205 info; 321 file(s) read` |
| `python Tools/validate/validate_all.py --strict` | **FAIL (expected)** | 15 warnings + 6 gaps |
| `python Tools/puzzles/validate.py` | **PASS** | `141 checks, 0 failures, 1 warning` |
| `python Tools/economy/validate_packs.py` | **PASS** | `48 packs, 1200 cards, pool union 1200; 1342 checks, 0 failures` |
| `python Tools/economy/validate_decks.py` | **PASS** | `5 decks; 81 checks, 0 failures` |
| `python Tools/effects/validate_effects.py` | **PASS** | `155 scripts, fusion 75/76, ritual 22/22, 0 warnings` |
| `python Tools/world/validate_layout.py --strict` | **PASS** | `36 locations, 10 interiors, 20 portals, 89 anchors, 28 spawns` |
| `python Tools/world/test_interiors.py` | **PASS** | 10 portal routes |

## 2. Runtime suites

| Switch | Result | Evidence |
| --- | --- | --- |
| `-DAProfileSelfTest` | **PASS** | `182 checks, 0 failure(s)` |
| `-DAEconomySelfTest` | **PASS** | `213 passed, 0 failed` |
| `-DADuelRulesSelfTest` | **PASS** | `58 passed, 0 failed` |
| `-DADuelSelfTest=1000` | **PASS** | `1000 iterations, 457 player wins, 543 opponent wins, 0 stalls, 0 invariant failures, deck audit 36/36, puzzle audit 100/100` |
| `-DAEffectRuntimeSelfTest` | **PASS** | `53 passed, 0 failed` (155 scripts loaded) |
| `-DAStorySelfTest` | **PASS** | 14/14 (opening E01/E01b) |
| `-DAFullStorySelfTest` | **PASS** | 20/20 (35 events, 6 emails, 82 duel refs, 35/35 reachable) |
| `-DAStoryPlaythroughTest` | **PASS** | 35/35 events, 39/39 story duels, 0 missing scenes/dialogue/outcomes |
| `-DAPuzzleExamSelfTest` | **PASS** | `PuzzleSelfTest: 102 passed, 0 failed`; `ExamSelfTest: 104 passed, 0 failed`; `BOTH SUITES PASS` |
| `-DANpcScheduleTest` | **PASS** | `414 passed, 0 failed` |
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
