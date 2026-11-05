# Text format

> **Status:** verified layout, partially decoded script VM.
> **Source:** `0x13F6DF0` string pool, `0x14280A0` offset table,
> `0x13F0000` script bytecode, `0x146CB14`/`0x146CC32` name pools.

## 1. Encoding

- Plain ASCII / latin-1, one byte per character. No Shift-JIS and no
  whole-ROM compression.
- Strings are **NUL-terminated**. An empty string is represented by two
  consecutive NULs (or one NUL where the next string starts immediately).
- Card name/description pools use 2-byte alignment and a dummy card-0 entry;
  the story pool does not require alignment.
- Control codes are embedded in the same byte stream. They are not escaped.

## 2. Master string index

| Property | Value |
| --- | --- |
| String base | `0x13F6DF0` |
| Index table | `0x14280A0`–`0x142C758` |
| Entry width | 4 bytes, little-endian |
| Entry count | **4,527** (indices `0..4526`) |
| Offset range | `0x0`–`0x31290` |
| End of pool | `0x1427F80` |
| Ordering | monotonic non-decreasing (duplicates are legal) |

To resolve a dialogue id `N`:

```
offset = u32(0x14280A0 + N*4)
text   = c_string(0x13F6DF0 + offset)
```

`$pNN` and `$mNNNNN` use this index space. `$p00` is the player name; the
dialogue table also contains the location/UI strings at low indices, so the
first story lines do not start at index 0.

## 3. Script bytecode

The script area is `0x13F0000`–`0x13F6DF0`. The message command is:

```
05 30 <u16 string_index> <u8 arg4> <u8 arg5>
```

- `string_index` resolves through the master table above.
- `arg4` is in the range 0–20 in the extracted calls. It behaves like a
  speaker/portrait group or window selector. Its exact semantics are not
  proven.
- `arg5` is `0` in every extracted call; reserved.

A01 extracted **1,083** message commands with **1,036** unique string indices.
The rest of the VM (jumps, conditions, flags, choices, duels) is not yet
decoded. `script_segments.json` groups nearby calls into 232 presentation
segments; these are **not** authoritative scene boundaries.

## 4. Control codes

| Code | Meaning | Confidence | Notes |
| --- | --- | --- | --- |
| `#n` | new line, same text box | high | most common |
| `#r` | next page / clear text box | high | |
| `#k` | wait for player input | high | often before a portrait change |
| `@N` | colour/highlight tag | high | `@3 ... @7` wraps emphasised text; also used in card descriptions |
| `$C1`–`$C4` | text palette / emphasis | high | `$C1` usually resets |
| `$pNN` | speaker full name by index | high | `00` = player; `01` = Jaden; see name table |
| `$PNN` | uppercase/variant speaker reference | medium | same index space in observed text |
| `$cNNNN` | card name by card id | high | e.g. `$c6314`; ids are 1–1200 |
| `$mNNNNN` | message/string reference | medium | observed `$m00014`; exact bank/indirection unresolved |
| `$yN` | dorm name | high | observed `$y2`; dorm index mapping is 0-based in text |
| `$L` | current duelist title | high | e.g. “I get to duel $L!” |
| `#>` + `N_NNNN` | portrait/expression command | medium | observed `#>0_122`, `#>1_2003`; first field is face slot, second expression |
| `#S` | spell-card log substitution | medium | duel log text |
| `#E` | effect log substitution | medium | duel log text |
| `#P` | player-name substitution in duel logs | medium | |
| `#M1` | monster-name substitution | medium | |

Printf-style placeholders also occur in UI/format strings:
`%s`, `%d`, `%1`, `%2`, `%3`. In exam templates `%1`/`%2` are card names.

### Observed `@N` tags

| Tag | Observed use | Confidence |
| --- | --- | --- |
| `@2` | icon/colour prefix before a DP or number run | medium |
| `@3` | start of an emphasised phrase (festival, dorm, rules) | high |
| `@4` | start of a contact/name highlight | medium |
| `@5` | start of a card-name highlight | high |
| `@6` | start of a numeric/DP highlight | high |
| `@7` | end/reset of the current highlight | high |

The card-description pool uses `@4`, `@5` and `@7` in the same way; the target
`cards.json` descriptions are stored with these tags stripped.

## 5. Speaker name table

The authoritative table is a **35-entry array of GBA pointers** at
`0x17F0BCC` (full names) and `0x17F0C5C` (short names). The string bytes live
at `0x146CB14` / `0x146CC32`. `name_table.json` records the pointer checks:
the first full pointer is `0x0946CB14` and the first short pointer is
`0x0946CC32`, both matching the expected bases.

`$pNN` is **1-based** into this table: `$p01` = entry 0 = Jaden, `$p31` =
entry 30 = Sheppard. `$p00` is the player name entered at registration.
Unused slots contain the literal string `reserved.`.

| Entry | Full name | Short name |
| ---: | --- | --- |
| 0 | Jaden Yuki | Jaden |
| 1 | Syrus Truesdale | Syrus |
| 2 | Chumley Huffington | Chumley |
| 3 | Bastion Misawa | Bastion |
| 4 | Alexis Rhodes | Alexis |
| 5 | Chazz Princeton | Chazz |
| 6 | Zane Truesdale | Zane |
| 7 | Vellian Crowler | Crowler |
| 8 | Lyman Banner | Banner |
| 9 | Fonda Fontaine | Fontaine |
| 10 | Sartyr | Sartyr |
| 11 | Jasmine | Jasmine |
| 12 | Mindy | Mindy |
| 13 | Brier | Brier |
| 14 | Beauregard | Beauregard |
| 15 | Dimitri | *(full name reused)* |
| 16 | Damon | Damon |
| 17 | Torrey | *(full name reused)* |
| 18 | Blair | Blair |
| 19 | Blair | Blair |
| 20 | Gerard | Gerard |
| 21–23 | *(reserved)* | *(reserved)* |
| 24 | Shadow Duelist | *(full name reused)* |
| 25–29 | *(reserved)* | *(reserved)* |
| 30 | Sheppard | Sheppard |
| 31 | Dorothy | Dorothy |
| 32 | Sadie | *(full name reused)* |
| 33 | *(reserved)* | *(reserved)* |
| 34 | Proctor | *(full name reused)* |

Blair occupies two slots because the disguise and the reveal use different
portraits. Several short-name slots point back at the full-name string rather
than a shorter alias; that is game data, not an extraction error.

## 6. Sample scene

`SEG_007` is a 28-message segment at `0x13F0216`–`0x13F0462`:

| Message | String index | Preview |
| ---: | ---: | --- |
| 1 | 3167 (`0x0C5F`) | `Talk to Jaden` |
| 2 | 3168 (`0x0C60`) | `What is it, $p00?#nI'm kinda busy...` |
| 3 | 3169 (`0x0C61`) | `What will you do?` |
| 4 | 3170 (`0x0C62`) | `Continue to call out to Jaden` |
| ... | ... | ... |

The full scene text is written to
`C:\Users\Sebas\AppData\Local\Temp\opencode\gxcanon\local_only\SEG_007_full.txt`
(and the full dialogue index to `dialogue_full.json` in the same directory).
These files are deliberately **outside the repository**.

## 7. What is still open

- The script VM's jump/condition/choice/duel opcodes are not decoded.
- `arg4` semantics and `$mNNNNN` indirection are not proven.
- Scene boundaries are a presentation heuristic, not a ROM table.
- Full dialogue text is local-only; committed data is an index, not the script.
