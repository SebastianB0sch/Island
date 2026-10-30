# Canon source map

> **Status:** first-pass extraction, verified against the US GBA ROM.
> **ROM:** `Yu-Gi-Oh! - GX Duel Academy (U).gba` — 32 MiB, SHA-256
> `0c2f606986c84d584510d0b80e7cb8e2970f9c15c71d29f9bb9d5f67ceef2afe`.
> **Header:** title `YUGIOHGXDA`, game code `BYGE`, maker `A4`.
> **Target:** `DuelAcademyIsland/Content/Data/cards.json` (1,200 records).

The ROM stays at `C:\dev\argh\...` and is read in place. No ROM, save file,
emulator binary or extracted art is copied or committed by this toolkit.

---

## 1. ROM map (verified offsets)

| File offset | Size / count | Contents | Status |
| --- | --- | --- | --- |
| `0x000000` | 0xC0 | GBA header, title/maker/complement check | verified |
| `0x0000C0`–`0x100000` | ~1 MiB | ARM/Thumb engine, BIOS SWI callers, sound driver | not disassembled |
| `0x60BA48` | 372 pointers | character portrait pointer table | verified by existing toolkit |
| `0x798018` | 36 pointers | portrait palette pointer table | verified by existing toolkit |
| `0xF243CC` | 1,201 × 4 | card stats dword table (card 0 dummy + 1,200) | **verified** |
| `0xF25690` | 20,476 B | card name pool, NUL-terminated, 2-byte aligned | **verified** |
| `0xF2A68C` | 1,201 × 4 | card name offset table | **verified** |
| `0xF2B950` | 182,596 B | card description pool, NUL-terminated, `@N` tags | **verified** |
| `0xF58294` | 1,201 × 4 | card description offset table | **verified** |
| `0x13F0000`–`0x13F6DF0` | 28,144 B | story-script bytecode; 1,083 `05 30` message commands | partially decoded |
| `0x13F6DF0`–`0x1427F80` | 0x31290 B | master NUL-terminated string pool (story/UI/locations) | **verified** |
| `0x14280A0`–`0x142C758` | 4,527 × 4 | master string offset table (monotonic) | **verified** |
| `0x1430BE0`–`0x1430E00` | 136 × 4 | written-exam card-id / parameter array | partially decoded |
| `0x1430E00`–`0x1430F00` | 64 × 4 | written-exam record offset table | partially decoded |
| `0x1430F10`–`0x1434522` | ~13.6 KiB | written-exam text bank: 89 templates + 161 options | **verified text** |
| `0x1433D4E`–`0x1433F00` | 64 × 28 | written-exam binary records | low confidence |
| `0x146C000`–`0x146D600` | 355 strings | UI, format, title, calendar and dorm strings | **verified** |
| `0x146CB14` | 26 named strings | full speaker-name bytes (35-entry pointer table at `0x17F0BCC`) | **verified** |
| `0x146CC32` | 26 named strings | short speaker-name bytes (35-entry pointer table at `0x17F0C5C`) | **verified** |
| `0x146C858`–`0x146C92A` | 16 strings | title strings (13 permanent states + temporary + labels) | **verified** |
| `0x146CCD8`–`0x146CE12` | — | weekdays, months, AM/PM/Night, dorms | **verified** |
| `0x1470000`–`0x147F9BD` | — | duel quips + tutorial prose | text verified, table layout open |
| `0x14EDD78`–`0x14EFxxx` | 48 packs | pack names/descriptions (shop text) | **verified text** |

### Save file

`patched.sav` is 32 KiB (the flash save is 64 KiB in the toolkit). The checksum
format is documented by `romhack/save_crypto.py`, but the **field layout**
(flags, counters, calendar, DP, inventory) has not been decoded. A01 did not
write to the save. Treat save-derived event conditions as unresolved.

---

## 2. Card tables

Each card is one little-endian `uint32` at `0xF243CC + id*4`:

```
bits  0.. 8  DEF / 10          (0..511 -> 0..5110)
bits  9..17  ATK / 10          (0..511 -> 0..5110)
bits 16..19  Spell/Trap icon   (0 Normal, 2 Counter, 4 Field, 6 Equip,
                                8 Continuous, 10 Quick-Play)
bits 18..19  Monster subtype   (0 Normal, 1 Effect, 2 Fusion, 3 Ritual)
bits 20..24  Type id           (1 Dragon ... 20 Reptile, 21 Trap, 22 Spell)
bits 25..28  Level             (1..12)
bits 29..31  Attribute         (1 LIGHT, 2 DARK, 3 WATER, 4 FIRE,
                                5 EARTH, 6 WIND, 7 DIVINE, 0 NONE)
```

The name offset is relative to `0xF25690`; the description offset is relative
to `0xF2B950`. Card 0 is an empty dummy entry. Descriptions are cleaned by
removing `@N` tags; names/descriptions are decoded latin-1.

**Result:** all 1,200 target records match the ROM on id, name, card type,
monster type, subtype, attribute, level, ATK, DEF and cleaned description.
`cards_manifest.json` records the per-card hashes and the aggregate hash.

Known byte-level quirks:

- Card 212 (`Kuwagata` + bytes `F2 A4`) has a non-ASCII name. The game renders
  it as a Greek alpha; the target DB stores U+FFFD. See `card_name_overrides.json`.
- Cards 663 and 780 both extract as `Luster Dragon`. Card 663 is the 2400/1400
  Level 6 card (TCG `Luster Dragon #2`); card 780 is the 1900/1600 Level 4 card.
- Cards 1030 and 1199 use the OCG names `Cemetary Bomb` and `Wasteland Amazon`
  where the guide says `Cemetery Bomb` and `Warrior Lady of the Wasteland`.

---

## 3. Story text system

The text system is **uncompressed ASCII**, not a compressed script archive.

1. `0x13F6DF0` is the string base. Strings are NUL-terminated; empty strings
   appear as consecutive NULs.
2. `0x14280A0` is a table of 4,527 little-endian `uint32` offsets relative to
   `0x13F6DF0`. The table is monotonic and ends at `0x142C758`; the largest
   offset is `0x31290`, which lands at `0x1427F80`, just before the table.
3. Script bytecode at `0x13F0000` calls strings with the 6-byte command
   `05 30 <u16 string-index> <u8 arg4> <u8 arg5>`. A01 found 1,083 calls and
   1,036 unique string indices.
4. `0x146CB14` / `0x146CC32` hold the speaker names used by `$pNN` tokens.
   `$p00` is the player; `$p01` maps to `Jaden Yuki`, and so on.

`extract_text.py` writes the full text to a **local-only** directory outside the
repository, and a committed index containing hashes, lengths, control tokens
and 80-character previews.

---

## 4. Written-exam bank

`0x1430F2C`–`0x1434522` contains 89 question templates ending in `?` plus 161
answer/option strings. The templates use `%1`, `%2`, `%3` placeholders that are
filled from the card data. The `0x1430BE0` array contains a mix of card ids and
parameters; 27 entries are valid card ids. The 64 × 28-byte records at
`0x1433D4E` are preserved raw in `exams.json` because their 16-bit fields have
not been proven to be answer keys.

What is **not** yet decoded: the exact per-question correct-answer mapping and
the pass mark (sources disagree between 250 and 300 out of 500).

---

## 5. Pack text

`0x14EDD78` begins the shop pack text (`Basic 1-A`, description, `Basic 1-B`,
...). The 48 pack names/prices/pools in `packs.json` come from the public set
pages; the ROM text confirms the pack-name pool and gives a cross-check for the
shop strings. Rarity odds and the exact rarity-slot model are not published and
remain a gap.

---

## 6. Extraction commands

```powershell
python Tools/canon/extract_cards.py
python Tools/canon/extract_text.py
python Tools/canon/extract_exam.py
python Tools/canon/build_packs.py
python Tools/canon/build_banned.py
python Tools/canon/build_decks.py
python Tools/canon/build_puzzles.py
python Tools/canon/build_events.py
python Tools/canon/build_curated.py
python Tools/canon/build_manifest.py
python Tools/canon/build_traceability.py
python Tools/canon/validate_canon.py
```

`build_packs.py`, `build_banned.py`, `build_decks.py`, `build_puzzles.py` and
`build_events.py` read either the checked-in facts cache or a local fetched
wikitext snapshot. The normal validation path requires no network.

---

## 7. Extracted vs inferred vs unknown

**Extracted from the ROM**

- All 1,200 card records (stats/names/descriptions).
- The 4,527-entry story/UI string index and the 1,083 script message calls.
- Speaker name table, titles, weekdays, months, periods, dorms.
- 89 written-exam question templates and 161 answer options.
- Pack names/descriptions in the shop text pool.

**Reconstructed from public guides (marked medium/high)**

- Pack prices, pools, rarities and unlock conditions.
- Event conditions, locations, choices and rewards.
- Starter deck lists; opponent archetypes and signature cards.
- Puzzle solution steps; title thresholds; banned/limited list.

**Still unknown (see `GAPS.md`)**

- Full 40-card opponent deck lists and deck evolution.
- 100 puzzle setups, time limits and clear rewards.
- Per-question written-exam answer key and the 250/300 pass mark.
- Script VM jump/condition/choice/duel opcodes.
- Save-file field layout (flags, counters, DP, inventory).
- Exact DP turn multiplier and special-victory bonuses.
- Exact exam Friday week-of-month and Year 2/3 weekday offsets.

## 8. Confidence legend

- **exact** — byte-for-byte ROM comparison.
- **high** — direct ROM text or an unambiguous guide fact.
- **medium** — guide fact plus a reasonable inference; may need in-game check.
- **low** — placeholder or unresolved; do not freeze without verification.
- **unknown** — no data; listed in `GAPS.md`.
