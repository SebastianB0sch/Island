# Port data validator

`validate_all.py` checks the live data tree against `Docs/Contracts/schemas`.
It uses only the Python standard library and never needs Unreal.

```powershell
python Tools\validate\validate_all.py
python Tools\validate\validate_all.py --strict
python Tools\validate\validate_all.py --json --report Content\Data\Integration\reports\validate.json
```

Exit codes: `0` pass, `1` errors (or warnings/gaps under `--strict`), `2`
bad arguments.

## Modes

- **Baseline** (default): structural errors fail; missing lane data and
  incomplete content are `GAP` findings, so early lanes can run it.
- **Strict**: warnings and gaps also fail. Use at a content gate.
- `--fail-on-gaps`: only gaps fail; warnings remain warnings.
- `--verbose`: show info and passing checks.

## Checks

| Check | What it validates |
| --- | --- |
| `cards` | 1,200 unique ids 1..1200, required fields, card type/subtype/attribute consistency, monster levels, spell/trap rules. |
| `canon_*` | A01 extracts: 35 events, 100 puzzles (20/level), 48 packs, 31 decks, 25 opponents, 12-cycle exams, 14 titles, 63 banlist cards, calendar. Complete canon records must be structurally valid; unknown canon is a gap. |
| `fusions` | Result is a fusion monster, materials/ids valid, `fusionTypes`, duplicate/generic/unresolved recipes, coverage vs 76 fusion monsters. |
| `decks` | 40..60 main, <=20 extra, <=15 side, valid ids, <=3 copies, forbidden/limited/semi limits, fusion monsters in extra. |
| `limitations` | Banlist ids valid, buckets disjoint. |
| `packs` | 48 packs, price/size/pool, valid card ids, slot totals, rarity weights, unlock refs, pool coverage. |
| `opponents` | Unique roster ids, decks/evolution refs, AI profile, difficulty, dorm, schedule, email hook. |
| `puzzles` | P001..P100, levels, setup card ids, turn/time limits, solution actions/cards, opponent/deck refs. |
| `exams` | 12 cycles, 10 written questions, puzzle refs, 7 practical objectives, 500-point scoring, pass mark. |
| `anchors` | Unique locations/anchors/portals/spawns, position refs, portal endpoints, story/schedule anchor coverage. |
| `events` | Event ids, dates, conditions, rewards, choices, duel refs, scene refs, `requires_events` reachability/cycles. |
| `dialogue` | Key/speaker/text/portrait shape; scene text keys resolve. |
| `scenes` | FStoryCommand queue, command-specific args, anchors/duel/reward refs, terminal End. |
| `emails` | Contact/from/subject/body/unlock/duel-request refs. |
| `schedules` | NPC, weekday/period, location/anchor refs, overlap detection, event overrides, opponent schedule refs. |
| `effects` | 1,200 manifest entries, status enum, script existence, non-empty operations, orphan scripts. |
| `saves` | Golden save payloads against `save.v1`, deck/card/inventory/calendar semantics. |

## Compatibility

The validator accepts the pre-contract shapes that landed during Gate 0
(`duelists[]`, single-object puzzles, `position_ue` anchors, `scenes{}`,
`nodes{}`, `npcs{}`, event bundles) and emits `*_schema_drift` warnings. It does
not silently rewrite the files. The canonical shapes are in
`Docs/Contracts/schemas`; see `Docs/Contracts/README.md` section 12.
