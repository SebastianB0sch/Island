# Effects data

Owned by A05 (Cardwright). Runtime code is owned by A04; nothing here edits
`DADuelEngine.*` or `DAEffectRuntime.*`.

## Layout

```text
Content/Data/Effects/
  schema.json                  JSON Schema (Draft 2020-12) for one card file
  scripts/<card_id>.json       hand-authored effect scripts
  tier1_cards.json             explicit Tier 1 reservation list
  card_effect_manifest.json    generated coverage manifest (1,200 entries)
  fusion_candidates.json       generated review copy of all 76 Fusion recipes
Content/Data/fusions.json      engine-facing fusion recipes
Content/Data/rituals.json      engine-facing ritual procedures
```

Scripts are one file per card. A script file must reproduce the `cards.json`
description byte-for-byte in `source_text`; the manifest hashes it so drift is
detected.

## Status meanings

| Status | Meaning |
| --- | --- |
| `scripted` | Data script exists, or the card is in the 137-card regression baseline and has a verified name handler in `DADuelEngine.cpp`. |
| `vanilla` | No effect text. Generic rules or `fusions.json` / `rituals.json` cover it. |
| `pending` | Effect text exists but no script/handler yet. |
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
python Tools/effects/build_manifest.py
python Tools/effects/extract_fusion_recipes.py   # writes fusions.json, rituals.json and fusion_candidates.json
python Tools/effects/validate_effects.py
python Tools/effects/report_coverage.py
python Tools/effects/audit.py
python Tools/effects/audit.py --release   # full 1,200-card gate
```

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
