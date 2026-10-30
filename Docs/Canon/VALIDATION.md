# Canon validation report

Generated: 2026-10-30T17:24:04+00:00

- Errors: **0**
- Warnings: **1**

| Check | Result | Detail |
| --- | --- | --- |
| `cards.count` | PASS | 1200 records, ids 1..1200 |
| `cards.verified` | PASS | 0 differences |
| `cards.hash` | PASS | 1ebf1f7217522b6c... |
| `packs.count` | PASS | 48 |
| `packs.ids_unique` | PASS |  |
| `packs.cards_valid` | PASS | 0 invalid ids |
| `packs.all_cards_obtainable` | PASS | 0 cards missing |
| `packs.prices` | PASS | [] |
| `packs.pack_sizes` | PASS | [] |
| `packs.odds` | WARN | pack rarity odds are not published; A06 must define a seeded model |
| `packs.unresolved_names` | PASS | 0 packs have unresolved guide names |
| `events.count` | PASS | 35 |
| `events.ids_unique` | PASS |  |
| `events.numbered` | PASS |  |
| `events.reward_cards_resolved` | PASS | [] |
| `opponents.count` | PASS | 25 |
| `opponents.ids_unique` | PASS |  |
| `decks.count` | PASS | 31 |
| `decks.ids_unique` | PASS |  |
| `decks.fire.size` | PASS | main 40 |
| `decks.fire.extra` | PASS | extra 1 |
| `decks.fire.copies` | PASS | copy limit check is against the 3-copy rule, not the year list |
| `decks.water.size` | PASS | main 40 |
| `decks.water.extra` | PASS | extra 0 |
| `decks.water.copies` | PASS | copy limit check is against the 3-copy rule, not the year list |
| `decks.wind.size` | PASS | main 40 |
| `decks.wind.extra` | PASS | extra 0 |
| `decks.wind.copies` | PASS | copy limit check is against the 3-copy rule, not the year list |
| `decks.jaden_year1.size` | PASS | main 56 |
| `decks.jaden_year1.extra` | PASS | extra 4 |
| `decks.jaden_year1.copies` | PASS | copy limit check is against the 3-copy rule, not the year list |
| `puzzles.count` | PASS | 100 |
| `puzzles.levels` | PASS |  |
| `puzzles.solutions` | PASS | 0 missing |
| `puzzles.card_ids` | PASS |  |
| `titles.count` | PASS | 12 permanent titles |
| `titles.dropout` | PASS | Dropout Boy state |
| `titles.temporary` | PASS | Occult Duelist |
| `calendar.months` | PASS | 12 |
| `calendar.periods` | PASS | ['AM', 'PM', 'Night'] |
| `calendar.first_playable` | PASS |  |
| `banned.count` | PASS | 63 |
| `banned.ids` | PASS |  |
| `banned.statuses` | PASS |  |
| `exams.templates` | PASS | 89 |
| `exams.practical` | PASS |  |
| `text.index` | PASS | 4527 |
| `text.name_table` | PASS | 35 |
| `text.full_names` | PASS | 26 |
| `text.short_names` | PASS | 26 |
| `text.name_pointer_pools` | PASS | {'full_base_expected': '0x146CB14', 'full_first_pointer': '0x0946CB14', 'full_first_pointer_matches': True, 'short_base_expected': '0x146CC32', 'short_first_pointer': '0x0946CC32', 'short_first_pointer_matches': True} |
| `legal.no_rom_or_save` | PASS | [] |
| `legal.no_full_dialogue` | PASS | [] |
| `manifest.hashes` | PASS |  |

## Warnings

- packs.odds: pack rarity odds are not published; A06 must define a seeded model
