# Duel data

Runtime data for the native duel system. Loaded by `UCardDatabaseSubsystem`,
`UCardArtSubsystem` and `UCharacterPortraitSubsystem` from `Content/Data`; the
same files are staged into packaged builds through
`DirectoriesToAlwaysStageAsUFS=(Path="Data")` in `Config/DefaultGame.ini`.

| Path | Contents |
| --- | --- |
| `cards.json` | 1,200-card database (`id`, `name`, `card_type`, `monster_type`, `subtype`, `attribute`, `level`, `atk`, `def`, `description`). |
| `decks.json` | Starter deck lists (Fire, Water, Wind, Jaden) with main and Extra Deck ids. |
| `fusions.json` | Fusion recipes (result, materials, fusion spell names). |
| `CardArt/` | Card scans used by the board, hand, detail panel and pile browser. |
| `Portraits/` | Character busts and expression frames for the duel scoreboards, cut-ins and results. See `Portraits/README.md`. |

The card names, rules text and scans are Yu-Gi-Oh! TCG material (Konami /
Shueisha) and are included for this non-commercial fan project only. The
portrait renders are Konami *Duel Links* reference art and are **not**
redistributable. See the project [CREDITS.md](../../../CREDITS.md).
