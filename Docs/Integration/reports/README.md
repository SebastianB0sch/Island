# Generated reports

Do not hand-edit. The validator and smoke runner write JSON reports here:

```powershell
python Tools/validate/validate_all.py --report Docs/Integration/reports/validate.json
python Tools/integration/run_smoke.py --validate --report Docs/Integration/reports/smoke.json
```

Reports are build evidence, not content. They may be deleted and regenerated.
The current baseline snapshot is `../baseline.json`.
