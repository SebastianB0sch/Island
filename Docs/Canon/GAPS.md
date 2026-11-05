# Canon gaps and fallback decisions

> **Gate 3 update (2026-10-31):** opponent decks are now transcribed from the
> GameFAQs Character Deck List FAQ v1.4 and the Year 1 generic shell. 16/37 decks
> are complete; 15 are partial (14 with explicit `unresolved_slots`, 1
> unverified list); 6 are fully unknown. Event deck references and the five missing event opponents are
> reconciled. The exam week remains an explicit question with recorded evidence.
> See `GATE3_RECONCILIATION.md` and `DECK_TRACEABILITY.md`.
>
> **Rule:** no datum is silently invented. Every unresolved item below has an
> owner and a downstream impact. Items marked **blocking** must be resolved
> before the content freeze.

Legend: **confidence** = exact / high / medium / low / unknown.

---

## 1. Text and story

| Gap | Status | Fallback / decision | Owner | Impact |
| --- | --- | --- | --- | --- |
| Full story dialogue in the repo | **resolved as local-only** | `extract_text.py` writes full text to a directory outside the repo; committed index has hashes and 80-char previews. | A01/A03 | A03 must run the extractor locally or write transformative dialogue. |
| Script VM opcodes (jumps, conditions, choices, duels) | **open** | Documented `05 30` message command only; scene segments are a presentation heuristic. | A01/A03 | Cannot auto-generate scene graphs; event conditions come from the guide. |
| `$mNNNNN` indirection | **open** | Treated as a message reference; exact bank not proven. | A01/A03 | Risk of wrong string links if used mechanically. |
| `arg4` in the message command | **open** | Looks like a speaker/portrait group (0–20); not used as a hard key. | A01/A03 | Speaker display should use `$pNN` and portrait commands. |
| `#>N_NNNN` portrait/expression semantics | **medium** | Format documented as face slot + expression; exact expression table not decoded. | A01/A09 | Portrait fallbacks required. |
| Full dialogue text licensing | **local-only** | Public build must use paraphrased/transformative text unless the owner accepts the risk. | A01/A10 | See `LOCAL_ONLY.md`. |

## 2. Cards

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| Card 212 name | **known quirk** | ROM bytes `F2 A4` render as Greek alpha; target DB has U+FFFD. Display override `Kuwagata α` supplied. | A01/A06 |
| Duplicate `Luster Dragon` names | **known quirk** | Cards 663 (2400/1400 L6) and 780 (1900/1600 L4) share the extracted name. Treat 663 as `Luster Dragon #2` by stats. | A01/A06 |
| OCG names | **known quirk** | `Cemetary Bomb` (1030) and `Wasteland Amazon` (1199) are the ROM names for guide `Cemetery Bomb` / `Warrior Lady of the Wasteland`. | A01/A06 |
| Effect coverage | **out of A01 scope** | Every card needs an A05 manifest entry; A01 only verifies data. | A05 |
| Banned/limited legality | **high** | Three-year list extracted; deck validator must apply the correct year. | A04/A06 |

## 3. Packs

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| Rarity odds / slots | **blocking for A06** | Guide publishes card rarities but not per-slot odds. `odds_status: unresolved` on all 48 packs. | A06 |
| Stock / restock | **partial** | Infobox packs have stock counts; summary-format packs only have frequency text, stock often null. | A06 |
| Unlock dates | **medium** | Dates/week labels extracted; exact "last week" day is a calendar rule. | A02/A06 |
| Card-pool completeness | **high** | All 1,200 cards appear in at least one pack; 2 guide names required alias resolution. | A01/A06 |
| Pack pool duplicates | **info** | `pool_cards_listed` can exceed unique ids because guide lists variants/duplicates. | A06 |
| Dorothy's Gift empty pool | **known gap (A06)** | `packs.json` still has an empty `dorothys_gift` pool. A06 owns the shop-pack fix; A01 only records it. | A06 |

## 4. Opponents and decks

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| Full opponent deck lists | **partial (Gate 3)** | **16/37 complete**, **15 partial** (14 with explicit `unresolved_slots`; 1 unverified list), **6 fully unknown**. Source: GameFAQs Character Deck List FAQ v1.4 (Tracy_Smith, 2006-03-11) + Year 1 generic shell. No ROM deck table was located. See `DECK_TRACEABILITY.md`. | A07 |
| Deck evolution | **partial** | Jaden improved, Chazz Ojama and Bastion's Magnet/Seventh decks are named; `jaden_improved`, `chazz_ojama`, `bastion_magnet`, `bastion_seventh` remain fully unknown. | A07 |
| AI profiles | **out of A01 scope** | A07 defines behavior from archetype/signature cards. | A07 |
| Ante/gift cards | **medium** | Gift cards extracted where the guide lists them; ante rules unresolved. | A07 |
| Roster count | **high (Gate 3)** | **28** canon entries: 25 named duelists + 3 event duelists (`jinzo`, `goblin_king`, `sheppard`). The three bracket/partner constructs are not roster duelists; see `decks.json` `event_constructs`. | A07 |
| Torrey special player deck | **unknown** | E07 forces a special deck made by Torrey; no list is published. Explicit `torrey_special` deck record with 40 unresolved slots. | A07 |

## 5. Puzzles

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| Initial hands/fields/graveyards | **blocking for A07** | 100 solutions extracted, but no setups; ROM puzzle table not decoded. | A07 |
| Time limits | **unknown** | Not in guide pages; likely level-based. | A07 |
| Rewards | **unknown** | DP/clear rewards not published on puzzle pages. | A07 |
| One-turn rule | **high** | Rules text says the duel starts on your turn and must be won during your turn. | A07 |

## 6. Exams

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| Per-question answer key | **blocking for A07** | 89 templates and 161 options extracted; mapping to 4 answers per question is not proven. | A07 |
| Pass mark | **blocking** | Sources disagree: 250 vs 300 out of 500. | A02/A07 |
| Written/timed/practical weights | **open** | 10 questions per exam; 500 total; component weights unresolved. | A07 |
| Practical scoring | **open** | Seven objectives extracted; thresholds/points unresolved. | A07 |
| Exam week | **open (explicit question)** | Monthly Friday is confirmed (guide + 12-exam year). Exact week is not proven: no guide states first/second/third/fourth/last; E09's "third Friday of November" is an event-specific rule. ROM strings 74/93 (`Next Friday is/will be the Dorm Switch Exam`) only prove a one-week warning; a raw search found no 12-entry exam-date table. Last-Friday fallback retained and marked unproven in `calendar.json` / `exams.json`. | A02 |

## 7. Titles and progression

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| Novice Duelist threshold | **low** | Working assumption 5 wins; not in public guide. | A02 |
| Celebrity Duelist threshold | **low** | Working assumption 150 wins; no public source. | A02 |
| Calm / Honored / Elite | **medium** | GameFAQs board list vs official event guide disagree on 100-win gates. | A02 |
| Prince of Games | **medium** | All 1,200 cards + 40% written; event text also calls 200 wins "Duel Prince". | A02 |
| Dropout recovery | **high** | E29: win vs Fontaine, DP = remaining LP, title -> Apprentice. | A02/A03 |
| Temporary titles | **medium** | Occult Duelist from E07, reverts after E08; other event titles may exist. | A02/A03 |

## 8. Calendar, DP and save data

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| Exam Friday week | **open** | Calendar lists all Fridays and a low-confidence last-Friday default. | A02 |
| Year 2/3 dates | **medium** | `calendar.json` models Year 1 (2006-10..2007-09); packs/banned list reference Year 2/3. Recompute dates per year, including leap-year shifts. | A02/A06 |
| DP turn multiplier | **open** | Masterplan says it exists; exact table not extracted. | A02 |
| Special-victory DP bonuses | **open** | Exodia/deck-out/Final Countdown/Destiny Board amounts unknown. | A02 |
| "LP lost" branch | **ambiguous** | Formula wording does not say player or opponent LP. | A02 |
| Save layout / flags | **blocking for event verification** | `save_crypto.py` covers checksums, not field layout. | A01/A02 |
| Side Deck | **open** | Guide says side deck up to 15; masterplan says 20-card Fusion Deck. Confirm both. | A04/A06 |

## 9. Events

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| E19/E20/E25/E28/E30 timing | **medium** | Guide wording is vague ("3 months", "weekend", "after event"). | A03 |
| Event numbering | **info** | Yugipedia and GameFAQs order events differently; Yugipedia numbering used. | A03 |
| Event-only opponents | **reconciled (Gate 3)** | `jinzo`, `goblin_king` and `sheppard` added to the canon roster with traceability. E09/E28/E31 brackets/partner pools now map to existing roster ids. Topher/Conklin/Mimicry/Shadow Duelist remain partial with explicit unknown slots; full lists still missing. | A07 |
| Event dialogue text | **local-only** | Keyword candidates attached; exact scene scripts not extracted. | A03 |
| Mandatory vs optional | **open** | Guide implies all 33 are reachable; exact ending gate is E33. | A03 |

## 10. Locations

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| GBA location → UE zone | **initial** | `locations.json` + `LOCATION_MAP_A01.md` map 26 names; A08's audited `LOCATION_MAP.md` remains authoritative. | A08 |
| Interior room variants | **open** | "Your Room", "Lobby", "Cafeteria" are context-dependent; mapping needs dorm context. | A08 |

## 11. Legal / assets

| Gap | Status | Detail | Owner |
| --- | --- | --- | --- |
| ROM/save/emulator | **resolved** | Not copied; validator scans the repo for `.gba`/`.sav`. | A01/A10 |
| Ripped art/audio | **out of scope** | No art/audio extracted or committed. | A10 |
| Full dialogue | **local-only** | Outside repo; see `LOCAL_ONLY.md`. | A01/A03 |
