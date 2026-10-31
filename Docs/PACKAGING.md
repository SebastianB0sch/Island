# Packaging notes — Win64

## Commands

```powershell
# Shipping release package
RunUAT.bat BuildCookRun `
  -project="C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  -noP4 -platform=Win64 -clientconfig=Shipping `
  -build -cook -stage -pak -archive `
  -archivedirectory="C:\dev\GX\Builds\Win64Shipping" `
  -map="/Game/DuelAcademy/Maps/DuelAcademyIsland" `
  -unattended -utf8output

# Development package for packaged self-tests/logs
# same command with -clientconfig=Development and Builds\Win64Dev
```

The archive is a bootstrap `DuelAcademyIsland.exe` at the archive root plus
`DuelAcademyIsland/Binaries/Win64/` and `DuelAcademyIsland/Content/Paks/`.
`Builds/` is ignored by Git.

## Verified packages

| Package | Result |
| --- | --- |
| Shipping | Cooked 1,590 packages, 0 cook errors; title screen launches at the title screen (`NEW GAME`, `CONTINUE`, `NO SAVE DATA`) |
| Development | `-DADuelSelfTest=1000`: 457/543 wins, 0 stalls, 0 invariant failures, deck audit 36/36, puzzle audit 100/100, exit 0 |
| Development | `-DAPuzzleExamSelfTest`: Puzzle 102/102, Exam 104/104, `BOTH SUITES PASS`, exit 0 |
| Development | `-DAStoryPlaythroughTest`: story JSON loads from the pak after the content-path fix; 35/35 campaign events |

## Static-initialization rule

Packaged builds initialize globals **before** `FCommandLine`, the ticker and the
content paths are ready. A global constructor calling `FParse::Param`,
`FCommandLine::Get()` or `FTSTicker::GetCoreTicker()` crashes with exit code
**777006 (`CrashDuringStaticInit`)** and writes no log.

The A02 and profile self-tests originally used global bootstrap objects. They
are now `UGameInstanceSubsystem`s:

- `UDAA02GateTestSubsystem` (`DASaveFuzz` / `DATwelveMonthTest`)
- `UDAProfileSelfTestSubsystem` (`DAProfileSelfTest`)

Any future command-line self-test must use the subsystem/ticker pattern, not a
global constructor.

## Content packaging

The runtime reads raw JSON from `Content/Data` via `FPaths::ProjectContentDir()`.
Cook includes those files (verified with `UnrealPak -List`). Story paths must be
kept relative to `Content/Data`; combining a relative packaged
`ProjectContentDir()` twice produces `.../Content/.../Content/...` and the story
fails to load. `LoadContentJsonObject` now resolves the content dir once.

## Remaining packaging work

- Bake and save navmesh data; the level currently rebuilds navigation at runtime
  on first load.
- Include `CREDITS.md` in the distribution archive; `NOTICES.txt` is staged but
  credits are not copied automatically.
- Run the performance profile and legal/credits review before tagging.
