# Integration fixtures, reports and evidence

Owner: **A10 Gatekeeper**.

This directory is the shared evidence locker for the ten lanes. It contains
only small JSON fixtures and generated reports; no binary assets, saves, ROMs or
ripped content.

```text
Docs/Integration/
  README.md                 this file
  baseline.json             current baseline snapshot and counts
  fixtures/                 small hand-authored test inputs
  reports/                  generated validator/smoke reports and logs
```

Golden save payloads stay next to the runtime data they test:

```text
DuelAcademyIsland/Content/Data/Integration/saves/
  golden_new_game.json      v1 save that must always round-trip
  golden_runtime_v1.json    A02 runtime payload shape
```

## Golden save

`saves/golden_new_game.json` and `saves/golden_runtime_v1.json` must:

- validate against `Docs/Contracts/schemas/save.v1.schema.json`;
- load into a new game with the Fire starter deck (`player_1`, 40 main + 1
  extra);
- survive a round-trip through A02's save subsystem without byte changes;
- keep working through every save migration.

Run the check:

```powershell
python Tools/validate/validate_all.py --report Docs/Integration/reports/validate.json
```

## Reports

`reports/` is generated output. Do not treat a report as canonical data, and do
not hand-edit it. A report records the tool version, timestamp, counts, checks
and findings so a gate review can diff two runs.

Recommended gate commands:

```powershell
python Tools/validate/validate_all.py --report Docs/Integration/reports/validate.json
python Tools/integration/run_smoke.py --validate --report Docs/Integration/reports/smoke.json
python Tools/integration/run_smoke.py --self-tests --report Docs/Integration/reports/smoke_selftests.json
```

## Adding a fixture

1. Keep it small and deterministic (no timestamps that change per run).
2. Name it by scenario: `golden_new_game.json`, `save_pre_exam.json`,
   `duel_result_win.json`, `pack_opening_seed_42.json`.
3. Add or update a validator/smoke assertion in `Tools/validate` or
   `Tools/integration`.
4. Record the fixture in `baseline.json` if it becomes a release gate.

## Current known state (2026-10-30)

The validator passes baseline mode with zero structural errors. The remaining
findings are content gaps and pre-contract data shapes; see `baseline.json`,
`Docs/PORT_STATUS.md` and the latest report. The UE self-test suite is green:
duel 24/0 stalls, profile 182 checks/0 failures, duel rules 57/57, economy
119/119, story 14/14, and UI generated 10 screenshots. The earlier profile
crash log is kept as regression evidence.
