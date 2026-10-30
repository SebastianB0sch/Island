# Opponents / Exams / Puzzles — Validation Report

- Generated: 2026-10-30
- Root: `C:\dev\GX`
- Result: **PASS**
- Checks: 137 · Failures: 0 · Warnings: 1

## Counts

- Cards: 1200
- Duelists: 25 (20 ranked)
- Opponent decks: 31
- AI profiles: 27
- Puzzles: 20 (level 1, P001-P020)
- Canon puzzle references attached: 20/20
- Engine-ready fallback lines: 20/20
- Written questions: 30; exam sets: 12
- Practical objectives: 7
- Scoring: 500 points, pass mark 300

## Card support

- Referenced card ids: 375 unique; unknown ids: 0
- Extra Deck cards without a `fusions.json` recipe: 0

## Deck results

| Deck | Opponent | Main | Extra | Confidence | Result |
| --- | --- | ---: | ---: | --- | --- |
| `alexis_cyber` | alexis | 40 | 2 | low | PASS |
| `alexis_cyber_plus` | alexis | 40 | 2 | low | PASS |
| `banner_alchemy` | banner | 40 | 0 | low | PASS |
| `bastion_chem` | bastion | 40 | 0 | medium | PASS |
| `bastion_chem_plus` | bastion | 40 | 0 | low | PASS |
| `beauregard_rock` | beauregard | 40 | 0 | low | PASS |
| `blair_toon` | blair | 40 | 0 | low | PASS |
| `brier_quiz` | brier | 40 | 0 | low | PASS |
| `chazz_ojama` | chazz | 40 | 3 | medium | PASS |
| `chazz_ojama_plus` | chazz | 40 | 3 | low | PASS |
| `chumley_koala` | chumley | 40 | 1 | medium | PASS |
| `conklin_dino` | conklin | 40 | 2 | low | PASS |
| `crowler_ancient_gear` | crowler | 40 | 0 | medium | PASS |
| `crowler_ancient_gear_plus` | crowler | 40 | 0 | low | PASS |
| `damon_exodia` | damon | 40 | 0 | low | PASS |
| `dimitri_copycat` | dimitri | 40 | 0 | low | PASS |
| `fontaine_nurse` | fontaine | 40 | 0 | low | PASS |
| `gerard_quiz` | gerard | 40 | 0 | low | PASS |
| `jaden_year1` | jaden | 53 | 4 | high | PASS |
| `jasmine_amazoness` | jasmine | 40 | 0 | medium | PASS |
| `mimicry_stall` | mimicry | 40 | 0 | medium | PASS |
| `mindy_fairy` | mindy | 40 | 0 | low | PASS |
| `pharaoh_guardian` | pharaoh | 40 | 0 | low | PASS |
| `sartyr_curry` | sartyr | 40 | 0 | low | PASS |
| `shadow_duelist_fiend` | shadow_duelist | 40 | 0 | low | PASS |
| `syrus_roids` | syrus | 42 | 4 | medium | PASS |
| `syrus_roids_plus` | syrus | 40 | 4 | low | PASS |
| `topher_goblin` | topher | 40 | 0 | low | PASS |
| `torrey_insect` | torrey | 40 | 1 | low | PASS |
| `zane_cyber` | zane | 40 | 4 | high | PASS |
| `zane_cyber_end` | zane | 40 | 4 | medium | PASS |

## Puzzle results

| Puzzle | Time | Reward DP | Result |
| --- | ---: | ---: | --- |
| `P001` | 30s | 100 | PASS |
| `P002` | 45s | 100 | PASS |
| `P003` | 45s | 100 | PASS |
| `P004` | 60s | 120 | PASS |
| `P005` | 45s | 120 | PASS |
| `P006` | 60s | 120 | PASS |
| `P007` | 60s | 120 | PASS |
| `P008` | 75s | 140 | PASS |
| `P009` | 60s | 140 | PASS |
| `P010` | 60s | 140 | PASS |
| `P011` | 60s | 140 | PASS |
| `P012` | 45s | 120 | PASS |
| `P013` | 45s | 120 | PASS |
| `P014` | 60s | 140 | PASS |
| `P015` | 60s | 140 | PASS |
| `P016` | 30s | 100 | PASS |
| `P017` | 75s | 160 | PASS |
| `P018` | 75s | 180 | PASS |
| `P019` | 75s | 180 | PASS |
| `P020` | 60s | 160 | PASS |

## Failures

None.

## Warnings

- cards.json: 1 duplicate card names (copy-limit by name still enforced)

## Canon confidence

Decks, puzzles and exam weights carry `confidence` and `source`. High-confidence entries: existing
Jaden deck, Cyber Dragon/Ancient Gear/Amazoness card availability, core written rules. Low-confidence
entries are reconstructions where the GBA list could not be extracted; A01 should replace them with
traceable canon data. See `Docs/Opponents_Exams_Notes.md`.
