# A01 handoff — canon baseline

**Status:** first high-value canon dataset complete and validated.
**Branch:** `port/baseline` working tree (not committed).
**Date:** 2026-10-30.

## 1. What is verified

| Area | Result |
| --- | --- |
| Card database | **1,200 / 1,200** records match the ROM on id, name, card type, monster type, subtype, attribute, level, ATK, DEF and cleaned description. 0 differences. |
| Card canon hash | `1ebf1f7217522b6c3bc38ae5f4f8f34fba1507ecfa2e179f20b9e8eda755751a` |
| Card type counts | Effect 410, Spell 280, Normal 252, Trap 160, Fusion 76, Ritual 22 |
| Booster packs | **48 / 48**, all prices and pools extracted; **all 1,200 cards obtainable** across the pools |
| Events | **35 records**: E01–E33 + E04b + E28b, with conditions, locations, choices, rewards and dialogue candidates |
| Opponents | **25** named duelists, archetypes, signature cards and gifts |
| Decks | **31**: 3 complete 40-card starters, donor Jaden, 27 opponent/variant skeletons |
| Puzzles | **100 / 100** solutions; setups still unknown |
| Banned/Limited | **63** cards across three school years |
| Titles | 12 permanent + Dropout penalty + Occult temporary |
| Calendar | 12 months (Oct 2006–Sep 2007), Sunday–Saturday, AM/PM/Night |
| Exam bank | 89 question templates, 161 answer options, 7 practical objectives, Gerard quiz |
| Text system | 4,527-string master index, 1,083 script message calls, 35-slot speaker table, control-code inventory |
| Validation | 54 checks, **0 errors**, 1 expected warning (pack odds unpublished) |

## 2. Top 10 facts downstream agents need now

1. **Cards are frozen and exact.** Use `Content/Data/Canon/cards_manifest.json`;
   ids are 1–1200 and match `cards.json` byte-for-byte. Do not re-extract with
   a different decoder.
2. **Pack names/prices/pools are real.** `packs.json` has all 48 packs and every
   card in at least one pool. Prices range 100–1000 DP; pack size is usually
   5, but several packs use 3 or 7. Odds are **not** published.
3. **The story text is plain ASCII and located.** String base `0x13F6DF0`,
   index table `0x14280A0` (4,527 offsets), script at `0x13F0000`. Full text is
   local-only; the committed index has keys, hashes and previews.
4. **Speaker tokens are 1-based.** `$p01` = Jaden, `$p09` = Banner,
   `$p10` = Fontaine, `$p11` = Sartyr, `$p31` = Sheppard, `$p00` = player.
   The speaker table is 35 pointer slots, not 26.
5. **Pack 1-A is the canonical opening purchase.** It costs 100 DP, has 5
   cards, and is unlocked by default. Basic 1-B, 2-A and 2-B are also default;
   later packs unlock by date, tutorial, event, collection rate or title.
6. **The first playable day is Saturday, October 7, 2006.** Opening ceremony is
   Sunday, October 1. The school year runs October–September. Exam day is
   Friday, but the exact week-of-month is unresolved (last-Friday working
   default).
7. **Events E01–E33 plus E04b/E28b are encoded.** E01 gives 3,000 DP and
   Jaden/Syrus/Chumley email. E09 gives 15,000 DP. E28 gives 10,000 DP. E33 is
   the King of Games gate (200 wins, 10 wins vs each of 20 duelists, 60%
   written).
8. **Titles are not all settled.** Average=10 wins, Fiery=30, Superior=50
   wins+50 timed, Shrewd=100, King=the E33 gate. Novice/Celebrity/Calm/Honored/
   Elite/Prince need in-game verification; see `GAPS.md`.
9. **100 puzzle solutions are available, but setups are not.** Each record has
   level, one-turn objective and solution steps/cards. Do not ship a puzzle
   until A07 supplies the fixed hand/field/graveyard.
10. **The banned list is three-year.** `banned_list.json` stores Year 1/2/3
    status per card. Deck validation must select the current school year, not a
    single flat list.

## 3. Blockers for other lanes

| Lane | Blocker |
| --- | --- |
| A02 | Exam Friday week; exact DP turn multiplier; save field layout. |
| A03 | Script VM opcodes and scene boundaries; full dialogue is local-only. |
| A06 | Pack rarity/odds/slot model; exact "last week" calendar rule. |
| A07 | Full opponent deck lists; 100 puzzle setups/time limits/rewards; exam answer key and pass mark. |
| A08 | `Abandoned Dorm` string not found in the plain-text pool; confirm anchor. |
| A10 | Freeze `Canon/` after reviewing `GAPS.md`; validator is the gate. |

## 4. Commands

```powershell
python Tools/canon/build_all.py
python Tools/canon/validate_canon.py
python Tools/canon/extract_text.py   # also writes local-only full dialogue
```

## 5. Files

- Tools: `Tools/canon/*.py`, `Tools/canon/card_aliases.json`,
  `Tools/canon/cache/*.json`.
- Data: `DuelAcademyIsland/Content/Data/Canon/*.json`,
  `.../Canon/text/*.json`.
- Docs: `Docs/Canon/SOURCE_MAP.md`, `TEXT_FORMAT.md`, `TRACEABILITY.md`,
  `GAPS.md`, `LOCATION_MAP.md` (A08, preserved), `LOCATION_MAP_A01.md`,
  `LOCAL_ONLY.md`, `VALIDATION.md`, `README.md`, `HANDOFF.md`.

## 6. Legal

No ROM, save, emulator, ripped art/audio or full dialogue was copied into
`C:\dev\GX`. The full dialogue dump lives outside the repo; see
`LOCAL_ONLY.md`.
