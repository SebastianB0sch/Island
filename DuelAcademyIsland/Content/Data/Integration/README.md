# Runtime test saves

Golden save payloads live here because `UDASaveSubsystem` and the save tests
load them as runtime data:

```text
saves/golden_new_game.json
saves/golden_runtime_v1.json
```

They must validate against `Docs/Contracts/schemas/save.v1.schema.json` and
survive A02's round-trip/fuzz/migration checks.

Validation reports, logs, fixtures and the baseline snapshot live in
`Docs/Integration/`, not under `Content/`.
