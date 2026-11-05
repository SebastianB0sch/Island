# Gate 3 reconciliation — A01 canon

**Date:** 2026-10-31  
**Scope:** opponent decks, missing event opponents, event deck references, exam-week rule.  
**Data/docs/tools only.** No UE build, no C++ or A06 shop-pack edits.

## 1. Before / after at a glance

| Measure | Before Gate 3 | After Gate 3 | Change |
| --- | ---: | ---: | --- |
| Canon decks | 31 | 37 | +6 event/variant records |
| Complete decks | 4 | **16** | +12 |
| Incomplete decks | 27 | **21** | -6 |
| — partial records with explicit status | 0 (implicit empty skeletons) | **15** (14 with unknown slots, 1 unverified list) | +15 |
| — fully unknown | 27 | **6** | -21 |
| Known main-deck cards | 173 | **1,278** | +1,105 |
| Explicit unknown main-deck slots | 0 (not encoded) | **380** | +380 |
| Canon opponents | 25 named | **28** (25 named + 3 event) | +3 |
| Event deck refs absent from `Canon/decks.json` | 4 | **0** | fixed |
| Event opponents absent from `Canon/opponents.json` | 5 | **0** (2 added: `jinzo`, `goblin_king`; 2 mapped brackets; 1 partner pool; `sheppard` added separately for E33) | fixed |
| Exam-week rule | unresolved, no evidence trail | **explicit canon question with evidence** | documented |
| Dorothy's Gift empty pack pool | open (A06) | open (A06) | unchanged, noted |
| `validate_canon.py` | 0 errors, 1 warning (old 54 checks) | **290 checks, 0 errors, 1 warning** | stronger coverage |
| `validate_all.py` | 0 errors, 20 warnings, 11 gaps, 58 info | **0 errors, 15 warnings, 6 gaps, 205 info** | fewer canon gaps |
| `validate_all.py --strict` | expected red | **expected red** (6 gaps / 15 warnings) | still gated |

The total file/check counts in `validate_all` include concurrent non-canon lanes
(A05 effects and runtime data); the canon-specific deltas are the deck, opponent
and exam rows above.

## 2. Deck audit

Every deck id, opponent, evidenced card list, count, unknown-slot count and
source is in [`DECK_TRACEABILITY.md`](DECK_TRACEABILITY.md). The compact summary:

| Deck id | Opponent | Main | Extra | Status | Unknown slots | Evidence |
| --- | --- | ---: | ---: | --- | ---: | --- |
| `fire` | starter | 40 | 1 | complete | 0 | Yugipedia Starter Decks + donor |
| `water` | starter | 40 | 0 | complete | 0 | Yugipedia Starter Decks + donor |
| `wind` | starter | 40 | 0 | complete | 0 | Yugipedia Starter Decks + donor |
| `alexis_year1` | alexis | 49 | 1 | partial | 4 | FAQ v1.4 §a |
| `banner_year1` | banner | 40 | 2 | partial | 2 | FAQ v1.4 §b |
| `bastion_year1` | bastion | 43 | 0 | partial | 3 | FAQ v1.4 §c |
| `beauregard_year1` | beauregard | 52 | 0 | complete | 0 | FAQ v1.4 §d |
| `blair_year1` | blair | 43 | 0 | partial | 1 | FAQ v1.4 §e |
| `brier_year1` | brier | 47 | 0 | complete | 0 | FAQ v1.4 §f |
| `chazz_year1` | chazz | 45 | 0 | complete | 0 | FAQ v1.4 §g |
| `chumley_year1` | chumley | 50 | 1 | complete | 0 | FAQ v1.4 §h |
| `crowler_year1` | crowler | 45 | 0 | partial | 4 | FAQ v1.4 §i |
| `damon_year1` | damon | 50 | 1 | complete | 0 | FAQ v1.4 §j |
| `dimitri_year1` | dimitri | 51 | 4 | complete | 0 | FAQ v1.4 §k |
| `fontaine_year1` | fontaine | 45 | 0 | partial | 2 | FAQ v1.4 §l |
| `gerard_year1` | gerard | 44 | 2 | partial | 1 | FAQ v1.4 §m |
| `jasmine_year1` | jasmine | 60 | 0 | complete | 0 | FAQ v1.4 §o |
| `mindy_year1` | mindy | 28 | 0 | partial | 12 | FAQ v1.4 §p + random pool |
| `pharaoh_year1` | pharaoh | 39 | 0 | partial | 1 | FAQ v1.4 §q + 16th-shell gap |
| `sartyr_year1` | sartyr | 43 | 0 | complete | 0 | FAQ v1.4 §r |
| `syrus_year1` | syrus | 45 | 1 | complete | 0 | FAQ v1.4 §s |
| `torrey_year1` | torrey | 48 | 0 | complete | 0 | FAQ v1.4 §t |
| `zane_year1` | zane | 50 | 2 | complete | 0 | FAQ v1.4 §v |
| `shadow_duelist_year1` | shadow_duelist | 16 | 0 | partial | 24 | FAQ v1.4 §w (one card only) |
| `mimicry_year1` | mimicry | 46 | 0 | partial | 0 | FAQ v1.4 §x, author unverified |
| `topher_year1` | topher | 17 | 0 | partial | 23 | Yugipedia signature cards only |
| `conklin_year1` | conklin | 17 | 0 | partial | 23 | Yugipedia signature cards only |
| `sheppard_year1` | sheppard | 48 | 3 | complete | 0 | FAQ v1.4 §y |
| `jaden_year1` | jaden | 53 | 4 | complete | 0 | Donor implementation + FAQ §n cross-check |
| `jinzo_spirit` | jinzo | 0 | 0 | unknown | 40 | E08; no published list |
| `damon_exodia` | damon | 5 | 0 | partial | 35 | E22; only Exodia pieces evidenced |
| `yugi_deck` | dimitri | 39 | 2 | partial | 5 | FAQ v1.4 §u |
| `bastion_seventh` | bastion | 0 | 0 | unknown | 40 | E26; no published list |
| `torrey_special` | torrey | 0 | 0 | unknown | 40 | E07 player override; no list |
| `chazz_ojama` | chazz | 0 | 0 | unknown | 40 | E15 variant; no list |
| `jaden_improved` | jaden | 0 | 0 | unknown | 40 | E03 variant; no list |
| `bastion_magnet` | bastion | 0 | 0 | unknown | 40 | Bastion variant; no list |

### Evidence method

- Character-specific lists and counts: GameFAQs **Character Deck List FAQ v1.4**
  (Tracy_Smith, 2006-03-11), section VII.
- Shared generic shell: FAQ section V, resolved to the 15-card **Year 1** legal
  selection from `banned_list.json`.
- Jaden: donor `game3d/src/duel/decklists.js` (local-only, not committed) plus
  FAQ §n cross-check.
- Card identity: every name resolved against `cards.json`; aliases are limited to
  proven guide/ROM name differences (e.g. Sapphire Dragon = 780, Emerald Dragon
  = 663, Wasteland Amazon = 1199). Unresolved names were not substituted.
- ROM deck table: **not located**. A raw little-endian `u16` scan for the known
  starter/Jaden sequences and a scan of every valid GBA BIOS LZ77/RLE block both
  found no contiguous 40-card table. The decks are therefore guide-derived, not
  ROM-exact. This is recorded as negative evidence in `SOURCE_MAP.md` and
  `DECK_TRACEABILITY.md`.

### Explicit unknown slots

No unknown slot is silently dropped. Each partial deck carries
`unresolved_slots` and `unresolved_reason`; fully unknown decks carry
`status: "unknown"` and 40 explicit slots. The 380 explicit unknown slots break
down as 140 partial + 240 fully unknown.

## 3. Event deck references

| Event | Opponent | Deck | Before | After |
| --- | --- | --- | --- | --- |
| E08 | jinzo | `jinzo_spirit` | missing deck + missing opponent | deck record added as **unknown** (40 slots); opponent added |
| E22 | damon | `damon_exodia` | missing deck | partial deck added: five Exodia pieces evidenced, 35 unknown |
| E23 | dimitri | `yugi_deck` | missing deck | partial deck added: 39 evidenced, 5 unknown |
| E26 | bastion | `bastion_seventh` | missing deck | deck record added as **unknown** (40 slots) |
| E07 | torrey | `torrey_special` (player override) | unvalidated hidden gap | explicit unknown player-override deck added |

`damon_exodia` deliberately does **not** reuse the complete FAQ Damon deck: the
FAQ deck has no Exodia pieces, while E22 says both sides use a draw/Exodia deck.
The conflict is recorded rather than resolved by invention.

## 4. Missing event opponents

| Reference | Resolution | Evidence |
| --- | --- | --- |
| `jinzo` (E08) | Added as event opponent with `jinzo_spirit` unknown deck | E08 guide: "spirit of Jinzo"; FAQ/Event FAQ |
| `goblin_king` (E17) | Added as event opponent; duel is `deck_kind: "timed_puzzle"`, not a 40-card deck | E17 guide: timed duel, Change of Heart on Toon Goblin Attack Force |
| `festival_bracket` (E09) | Mapped to an E09 `tournament` object over the ranked roster; no roster id | E09 guide: Interdorm Duel; no bracket published |
| `chocolate_bracket` (E28) | Mapped to a 4-round `tournament` over `fontaine/alexis/jasmine/mindy/blair` | E28 guide: four rounds, all female characters |
| `walk_home_partner` (E31) | Mapped to a `partner_pool` over `jaden/syrus/chumley/bastion/alexis/chazz/zane` | E31 reward table names exactly this pool |
| `sheppard` (E33) | Added as event opponent with complete `sheppard_year1` deck and E33 promotion duel | FAQ v1.4 §y; E33 guide promotion duel |

The three bracket/partner constructs are not roster duelists. They live in
`decks.json` → `event_constructs` and in the E09/E28/E31 duel objects, so the
roster stays semantically clean: **25 named + 3 event duelists = 28**.

## 5. Exam-week rule

**Status: still unresolved, now an explicit canon question.**

Confirmed:

- The exam is monthly and falls on a **Friday** (Yugipedia Events; GameFAQs
  Written Examination Guide).
- There are **12 exams in the 12-month school year** (E33: 60% = 120 questions =
  12 exams = 12 months).
- ROM text indices **74** (`0x13F7548`, "Next Friday is the Dorm Switch Exam.")
  and **93** (`0x13F7FE2`, "Next Friday will be the Dorm Switch Exam.") prove a
  **one-week warning**, not the week-of-month.

Conflicting / insufficient:

- No public guide states first/second/third/fourth/last Friday.
- E09's "third Friday of November" is an **event-specific Duel Festival rule**;
  it is not evidence that monthly exams use the third Friday.
- A raw byte/u16 search for the 2006-2007 first/second/third/fourth/last-Friday
  day sequences found **no 12-entry exam-date table** in the ROM.
- The ROM calendar/exam routine and save-file date layout are not decoded, so
  the current **last-Friday fallback is unproven**.

The fallback remains in `calendar.json` (`exam_rule.fallback`) and
`exams.json` (`cycle.exam_week_fallback`) but is explicitly marked unproven.
The exact question is stored as `exam_week_question`; confirmed and conflicting
evidence are stored in `exam_week_evidence`. The validator reports this as a
canon gap, not as silent data.

## 6. Remaining unknowns

| Area | Remaining unknown | Why it stays open | Owner |
| --- | --- | --- | --- |
| Partial opponent decks | 15 decks / 140 slots | FAQ marks missing cards or optional/dorm-dependent slots | A07 |
| Fully unknown decks | 6 decks / 240 slots | No published list: `jinzo_spirit`, `bastion_seventh`, `torrey_special`, `chazz_ojama`, `jaden_improved`, `bastion_magnet` | A07 |
| Generic shell 16th slot | 1 shared slot | FAQ says 15 or 16; only the 15-card Year 1 selection is proven | A01/A07 |
| ROM deck table | not located | Raw `u16` and LZ77/RLE scans found no contiguous deck table | A01 |
| Exam week | exact Friday | ROM calendar routine/save layout not decoded; fallback unproven | A02 |
| Dorothy's Gift | empty pack pool | A06 owns the shop-pack fix; A01 only records it | A06 |
| Puzzle setups/timers | 100/100 | ROM puzzle table not decoded | A07 |
| Exam answer key / pass mark | 89 templates, 250 vs 300 | Not part of Gate 3 deck scope | A07 |

## 7. Files changed

Data:

- `DuelAcademyIsland/Content/Data/Canon/decks.json` — 37 deck records with
  `status`, `fixed_cards`, `unresolved_slots`, `unresolved_reason`, generic
  shell and event constructs.
- `DuelAcademyIsland/Content/Data/Canon/opponents.json` — 28 entries (25 named +
  3 event), deck refs/defaults.
- `DuelAcademyIsland/Content/Data/Canon/events.json` — E09/E28/E31 construct
  mappings, E17 timed-puzzle shape, E33 Sheppard duel, E12 deck refs.
- `DuelAcademyIsland/Content/Data/Canon/exams.json` — exam-week question and
  evidence.
- `DuelAcademyIsland/Content/Data/Canon/calendar.json` — exam-rule question and
  evidence; last-Friday fallback explicitly unproven.
- `DuelAcademyIsland/Content/Data/Canon/manifest.json` — regenerated hashes and
  coverage/confidence.

Tools:

- `Tools/canon/deck_lists_faq.json` — new curated transcription with resolved
  card ids, counts, status and unresolved slots.
- `Tools/canon/build_decks.py` — rebuilds decks/opponents from the curated file.
- `Tools/canon/build_events.py` — event construct/Sheppard/E12 updates.
- `Tools/canon/extract_exam.py` — exam-week evidence block.
- `Tools/canon/build_curated.py` — calendar exam-rule evidence.
- `Tools/canon/build_manifest.py` — deck confidence text.
- `Tools/canon/build_traceability.py` — deck status/unresolved columns.
- `Tools/canon/build_deck_report.py` — new `DECK_TRACEABILITY.md` generator.
- `Tools/canon/validate_canon.py` — deck/opponent/event/exam checks.
- `Tools/validate/validate_all.py` — explicit partial/unknown deck handling,
  event construct/timed-puzzle handling, exam-week evidence check, and exclusion
  of A05 coverage reports from the effect-script schema check.
- `Tools/canon/build_all.py` — includes the deck report step.

Docs:

- `Docs/Canon/GATE3_RECONCILIATION.md` — this report.
- `Docs/Canon/DECK_TRACEABILITY.md` — generated per-deck audit.
- `Docs/Canon/HANDOFF.md`, `GAPS.md`, `README.md`, `SOURCE_MAP.md`,
  `TRACEABILITY.md`, `VALIDATION.md`.
- `Docs/Integration/reports/validate_baseline.json`,
  `validate_strict.json`, `GATE3_TEST_RESULTS.md`.

## 8. Validator output (exact)

`python Tools/canon/validate_canon.py`:

```text
checks: 290  errors: 0  warnings: 1
```

`python Tools/validate/validate_all.py`:

```text
Summary: 0 error(s), 15 warning(s), 6 gap(s), 205 info; 321 file(s) read
Result: PASS
```

`python Tools/validate/validate_all.py --strict`:

```text
Summary: 0 error(s), 15 warning(s), 6 gap(s), 205 info; 321 file(s) read
Result: FAIL
  (strict mode: warnings and gaps fail the run)
```

`python Tools/puzzles/validate.py`:

```text
PASS summary: 141 checks, 0 failures, 1 warnings
duelists=25 decks=31 ai=27 puzzles=100 questions=30 cycles=12
```

The remaining `validate_all` gaps are:

1. `canon_deck_incomplete` — 21/37 decks (15 partial + 6 unknown).
2. `canon_pack_empty` — Dorothy's Gift, A06-owned.
3. `canon_puzzle_setup` — 100/100 setups unknown, A07-owned.
4. `canon_puzzle_timer` — 100/100 timers unknown, A07-owned.
5. `canon_exam_week` — exact Friday unresolved, A02-owned.
6. `effects_pending` — 596 effects pending, A05-owned (outside Gate 3).

Strict mode is therefore still expected to fail; the canon deck/event/opponent
gaps that Gate 3 targeted are closed or explicitly bounded.

`validate_all` also excludes A05 coverage summaries (`coverage_by_deck.json`,
`coverage.json`, `effect_coverage.json`) from the effect-script schema check;
they are data reports, not executable card scripts. This removed five false
`effect-script` errors without changing A05 data.
