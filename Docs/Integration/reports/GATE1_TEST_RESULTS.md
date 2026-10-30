# Gate 1 test results - 2026-10-30

Build: **green** (`DuelAcademyIslandEditor Win64 Development`, latest editor DLL
2026-10-30 18:41:17).

| Test | Result |
| --- | --- |
| `-DAProfileSelfTest` | **182 checks, 0 failures** (save round-trip, backup recovery, corruption, migration) |
| `-DAEconomySelfTest` | **119 passed, 0 failed** |
| `-DADuelRulesSelfTest` | **57 passed, 0 failed** (chains/targeting/timing/banlist/scenario/ante) |
| `-DAStorySelfTest` | **14/14 PASS** (E01/E01b, 3,000 DP, Oct 7 AM, shop/save/free-roam) |
| `-DAUITest` | **10 screenshots**: 8 PDA + 2 dialogue at 1920x1080 |
| `-DADuelSelfTest` | **24 iterations, 12 player wins, 12 opponent wins, 0 stalls, average 11.7 turns** |
| `python Tools/validate/validate_all.py` | **PASS** - 0 errors, 20 warnings, 11 gaps, 58 info, 25 checks, 176 files |
| `python Tools/puzzles/validate.py` | **PASS** - 141 checks, 0 failures, 1 warning (duplicate Luster Dragon name) |

Runtime coverage: 1,200 cards / 100 puzzles / 12 exam cycles / 25 duelists /
31 decks / 48 packs / 37 events / 56 scenes / 161 dialogue lines / 6 email
contacts.

Remaining Gate 1/3 blockers are listed in `Docs/PORT_STATUS.md`: 760 pending
effects, E02-E33 in-engine playthrough proof, full dialogue/PDA-email UI
integration, interiors generation, shop/deck/exam UI wiring, and canon gaps
(incomplete decks, unknown puzzle setups/timers, exam week).
