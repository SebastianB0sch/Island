# Effects data

Owned by A05 (Cardwright). Runtime code is owned by A04; nothing here edits
`DADuelEngine.*` or `DAEffectRuntime.*`.

## Layout

```text
Content/Data/Effects/
  schema.json                  JSON Schema (Draft 2020-12) for one card file
  scripts/<card_id>.json       card effect scripts (hand-authored + generated)
  tier1_cards.json             explicit Tier 1 reservation list
  card_effect_manifest.json    generated coverage manifest (1,200 entries)
  coverage_by_deck.json        generated pending-by-reachability report
  fusion_candidates.json       generated review copy of all 76 Fusion recipes
Content/Data/fusions.json      engine-facing fusion recipes
Content/Data/rituals.json      engine-facing ritual procedures
Tools/effects/
  effect_patterns.py           whole-card recipes + pending-reason taxonomy
  generate_scripts.py          writes validated scripts from those recipes
  coverage.py                  reachability report (JSON + markdown)
  validate_effects.py          schema/manifest/fusion/ritual validator
```

Scripts are one file per card. A script file must reproduce the `cards.json`
description byte-for-byte in `source_text`; the manifest hashes it so drift is
detected. Generated scripts follow the same rule.

## Status meanings

| Status | Meaning |
| --- | --- |
| `scripted` | Data script exists, or the card is in the 137-card regression baseline and has a verified name handler in `DADuelEngine.cpp`. |
| `vanilla` | No standalone effect to script. Normal Monsters use generic rules; effect-free Fusions/Rituals use `fusions.json` / `rituals.json`; specific Ritual Spell procedures are owned by `rituals.json`; summoning-restriction-only monsters have no executable effect. |
| `pending` | Effect text exists but the whole effect is not covered. `pending_reason_code` names the missing runtime capability. |
| `unsupported` | Explicit blocker; never allowed in a deck, pack, puzzle, exam or legal list. |

`implementation` is separate from `status`:

| Implementation | Meaning |
| --- | --- |
| `data_script` | Behaviour comes from `Effects/scripts/<id>.json`. |
| `engine_cpp` | Behaviour is currently a name handler in `DADuelEngine.cpp` (Tier 0 regression contract). |
| `generic` | Normal Monster rules. |
| `generic_fusion` | Effect-free Fusion; summon procedure in `fusions.json`. |
| `generic_ritual` | Effect-free Ritual; summon procedure in `rituals.json`. |
| `none` | Pending/unsupported. |

## Tier meanings

| Tier | Definition |
| --- | --- |
| 0 | Union of the four current decks in `decks.json` (137 unique cards). Must stay green. |
| 1 | Explicit vertical-slice demonstrators in `tier1_cards.json` (10 scripts in this pass). |
| 2 | Any card referenced by `decks.json`-adjacent usage data: `Decks/`, `Shop/`, `Puzzles/`, `Opponents/`, `Exams/`, plus optional `legal_cards.json`. This currently covers the full shop pool. |
| 3 | Remaining cards not referenced by any usage dataset. |

Tier assignment is recomputed by `build_manifest.py`; do not hand-edit
`card_effect_manifest.json`.

If another lane needs an explicit legality list, add
`Content/Data/Effects/legal_cards.json` as either an array of card ids or an
object with a `cards` array. `validate_effects.py` checks that list, plus every
existing usage dataset, for `unsupported` cards.

## Commands

```powershell
python Tools/effects/generate_scripts.py --check   # show the next rule-based batch
python Tools/effects/generate_scripts.py --write   # write missing scripts only
python Tools/effects/build_manifest.py
python Tools/effects/coverage.py                    # writes coverage_by_deck.json + markdown lane report
python Tools/effects/validate_effects.py
python Tools/effects/report_coverage.py
python Tools/effects/audit.py
python Tools/effects/audit.py --release   # full 1,200-card gate
```

Run them in that order after changing a recipe: generate, rebuild the manifest,
refresh the lane report, then validate. `generate_scripts.py` refuses to
overwrite an existing file, so hand-authored work is never replaced.

## Generated scripts and pending reasons

`effect_patterns.py` contains whole-card recipes. A card is scripted only when
every printed clause is represented; partial effects stay `pending`. The
manifest records `pending_reason_code` and `pending_reason` for every pending
card, and `coverage.py` groups those rows by story event decks, opponent decks,
puzzle decks, starter decks, shop packs and the long tail.

At the Gate 3 pass there are 155 validated scripts (10 hand-authored, 145
generated), 264 `scripted` cards, 343 `vanilla`/data-covered cards and 593
`pending` cards. The lane report shows that story event opponent decks contain
92 of the pending cards; the rest are roster-only or shop-only.

`send_to_graveyard` is exposed by `schema.json` for selecting one card and
sending it to the Graveyard; the A04 runtime already implements
`send_to_graveyard`/`send_to_grave`.

`audit.py` is idempotent. Baseline mode hard-gates Tier 0/1, manifest integrity,
usage legality and fusion/ritual accounting; Tier 2/3 backlogs are reported and
become hard gates under `--release`.

## Fusion/ritual confidence

Every inferred recipe carries `confidence` and a structured `source`:

- `high` — all materials named explicitly in the result card text.
- `medium` — generic material class, or a repaired/normalized name from a
  corrupted `cards.json` description.
- `low` — reserved for indirect inference; none currently.
- `unresolved` — the current recipe model cannot express the text; the record
  has `materials: []` and a `reason` so the engine loader skips it.

No recipe is generated from a deck list or from memory. `validate_effects.py`
rejects a resolved recipe whose material names do not appear in the source card
text, unless `source.override` is explicitly set with a note.
