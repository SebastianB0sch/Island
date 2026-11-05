# Island music

The island has an original, looping soundtrack for every outdoor zone, every
enterable building and its rooms, plus title, duel and story cues. Nothing is
ripped: the tracks are composed and rendered with the **Juicebox Studio** engine
in `C:\dev\Music`, which synthesizes every sound live with the Web Audio API.

## Soundtrack

Open `Docs/Audio/preview.html` in a browser to audition all 22 loops from the
committed source WAVs.

| Track | Used by | BPM | Key | Loop |
|---|---|---:|---|---:|
| `M_Title` | title screen, assembly cue | 96 | D major | 40.0 s |
| `M_AcademyGrounds` | academy exterior, plaza, `BGM_Academy_Arrival` | 112 | C major | 34.3 s |
| `M_AcademyHall` | academy main hall, `BGM_Registration` | 84 | F major | 22.9 s |
| `M_Classroom` | classroom, exam room, `BGM_Tutorial` | 100 | G major | 19.2 s |
| `M_AcademyStudy` | lecture halls, library | 72 | E minor | 26.7 s |
| `M_AcademyFaculty` | faculty annex, Crowler's and Sheppard's offices | 88 | B♭ major | 21.8 s |
| `M_CardShop` | card shop | 116 | A major | 16.6 s |
| `M_DuelArena` | Grand Duel Arena, all duels | 132 | D minor | 29.1 s |
| `M_SliferDorm` | Slifer Red exterior and dining hall, `BGM_Slifer_Dorm` | 92 | G major | 41.7 s |
| `M_RaDorm` | Ra Yellow exterior, hall and cafeteria | 108 | A major | 35.6 s |
| `M_ObeliskDorm` | Obelisk boys' exterior, foyer, duel salon, dining room | 88 | E minor | 43.6 s |
| `M_ObeliskGirls` | Obelisk girls' exterior, foyer and conservatory | 84 | A♭ major | 22.9 s |
| `M_DormRoom` | all player rooms, Banner's room, the bunk room | 76 | C major | 25.3 s |
| `M_Water` | lake, Volcano Falls | 76 | E♭ major | 25.3 s |
| `M_Harbor` | harbor, ferry terminal, lighthouse | 104 | D major | 36.9 s |
| `M_Beach` | South-East Beach | 112 | F major | 17.1 s |
| `M_Gym` | Duel Gym exterior and court | 128 | B minor | 30.0 s |
| `M_Forest` | Duel Academy Forest | 84 | D dorian | 22.9 s |
| `M_HotSprings` | hot springs and bathhouse | 68 | E♭ major | 28.2 s |
| `M_Volcano` | volcano and crater rim | 100 | C phrygian | 38.4 s |
| `M_Abandoned` | abandoned dorm, hall and ritual chamber | 66 | A harmonic minor | 29.1 s |
| `M_Cliffs` | West Cliffs / Sunset Point | 72 | G major | 26.7 s |

The academy suite shares a four-note motto (scale degrees 1-3-5-6) across the
grounds, hall, classrooms, study rooms and card shop. The dorm themes each keep
their own colour instead of reusing one loop.

## Runtime

`UDAMusicSubsystem` (`DAMusicSubsystem.h/.cpp`) is a world subsystem that:

* listens to `UDAIslandSubsystem::OnZoneChanged` and crossfades to the new
  zone/sublocation theme (1.75 s by default),
* receives `SetInteriorContext(InteriorId)` / `ClearInteriorContext()` from
  `ADAInteriorPortal` when a portal cell is entered or left,
* treats story `music` commands as manual cues, and returns to zone-driven music
  on `BGM_Free_Roam` (`@auto`),
* plays the title and duel themes as manual cues and restores the area music
  when they close,
* applies the existing BGM volume setting (`UDASettings::GetBgmVolume`) live.

Zone/room/cue ids and the optional per-track `volume` multipliers live in
`Content/Data/Audio/music.json`, not in C++. Edit that file to retune the map or
rebalance a track without recompiling. (The render-time loudness trims are
`TRACK_GAIN` in the Music repo's `src/songs/game/index.ts`; they are baked into
the WAVs so every loop starts at a comparable level.)

`Content/Data/Audio/music.json` is generated together with the WAVs. The
mapping has four tables:

```json
{
  "zones":         { "academy": "M_AcademyGrounds", "...": "..." },
  "sublocations":  { "academy_hall": "M_AcademyHall", "...": "..." },
  "interiors":     { "academy_classroom": "M_Classroom", "...": "..." },
  "cues":          { "BGM_Free_Roam": "@auto", "...": "..." }
}
```

## Re-rendering the soundtrack

The source project is `C:\dev\Music` (Juicebox Studio). Open it in another shell:

```powershell
cd C:\dev\Music
node node_modules\tsx\dist\cli.mjs scripts\render-game-music.ts
```

This starts Vite, renders every track through the real offline audio engine in
headless Chromium, folds the reverb tail back over the first bar (seamless loop),
normalises loudness and writes:

* `C:\dev\GX\DuelAcademyIsland\SourceAssets\Audio\M_*.wav` (22.05 kHz, stereo,
  16-bit, exactly one loop long)
* `C:\dev\GX\DuelAcademyIsland\Content\Data\Audio\music.json`
* `C:\dev\GX\DuelAcademyIsland\Content\Data\Audio\music-manifest.json`

Useful flags: `--only=M_Gym`, `--jobs=3`, `--sr=32000`, `--no-config`.

The Unreal import pass picks the WAVs up with the rest of the audio:

```powershell
cd C:\dev\GX
python Tools\build_island.py audio
UnrealEditor-Cmd DuelAcademyIsland.uproject -ExecutePythonScript="DuelAcademyIsland/Content/Python/import_audio_cli.py" -unattended -nop4 -nullrhi -nosound
```

`Content/Python/duel_academy/importer.py` marks every `M_*` sound as looping
(`A_*` ambience keeps its existing loop flags). The imported `Content/DuelAcademy`
folder stays generated/gitignored; only the source WAVs and JSON are committed.

## Checks

* `python Tools\audio\validate_music.py --strict` verifies every zone, room and
  story cue, the WAV format and the declared loop lengths.
* `python Tools\build_island.py audio` keeps the existing ambience one-shots and
  does not touch `M_*`.
* Run a headless map load and look for the music director's log line:
  `Music: 22 tracks, 17 zones, 10 rooms, 10 cues.` It also warns if a mapped
  track cannot be loaded.
* The loop files are normalised to about -19 dBFS RMS with a -1 dBFS peak
  ceiling; the BGM setting scales the result.

## Licensing

All 22 tracks are original compositions generated by the project's own
synthesizer. No samples, recordings or ripped Konami audio are used. The WAVs
and `music.json` are part of this fan project's source assets, like the
procedural ambience and UI sounds in `Tools/dai/audio.py`.
