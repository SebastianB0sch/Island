# Local-only reference data

The full GBA story script is **not** committed to this repository.

`Tools/canon/extract_text.py` writes:

- `%TEMP%\opencode\gxcanon\local_only\dialogue_full.json` — all 4,527 strings
  with their ROM offsets and exact text.
- `%TEMP%\opencode\gxcanon\local_only\SEG_007_full.txt` — one complete
  28-message sample scene with script offsets and resolved text.
- `%TEMP%\opencode\gxcanon\local_only\SEG_227_full.txt` — a second sample.

The default directory is:

```
C:\Users\Sebas\AppData\Local\Temp\opencode\gxcanon\local_only
```

Override it with the `GX_CANON_LOCAL_DIR` environment variable.

## What is committed instead

- `Content/Data/Canon/text/dialogue_index.json`: index, ROM offset, length,
  SHA-256, 80-character preview, control tokens and cross-references.
- `Content/Data/Canon/text/script_segments.json`: presentation segments with
  message ids and hashes; the sample scene is redacted.
- `Content/Data/Canon/text/name_table.json`: speaker names and table slots.
- `Content/Data/Canon/text/ui_strings.json`: functional UI strings.

## Rules

1. **Do not commit** `dialogue_full.json`, `SEG_*_full.txt`, the ROM, a save
   file, an emulator binary, or extracted art/audio.
2. A03 may use the local dump as reference, but player-facing dialogue must be
   a transformative port or an original paraphrase unless the project owner
   explicitly accepts the fan-project risk. See masterplan §7.5.
3. A09 must consume dialogue **keys**, never the raw local dump.
4. The validator checks that `Tools/canon/` contains no `dialogue_full.json`
   and that canon-owned paths contain no `.gba`/`.sav` files.
5. Regenerate the local dump from a legally obtained ROM with:
   `python Tools/canon/extract_text.py`.

## Why this split

The masterplan requires traceability and a reproducible text map, but the
public build must not ship a verbatim copy of the commercial script. The index
gives downstream agents stable keys, offsets, hashes and control-code metadata;
the text itself stays on the extraction machine.
