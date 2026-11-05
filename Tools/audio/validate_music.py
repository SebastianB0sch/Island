#!/usr/bin/env python3
"""Validate the Duel Academy Island music map and the rendered loop files.

    python Tools/audio/validate_music.py
    python Tools/audio/validate_music.py --strict

Checks:
  * Content/Data/Audio/music.json parses and every track has a source WAV.
  * Every LOCATIONS zone and every interiors.json cell maps to a known track.
  * Every story `music` cue (BGM_*) is in the cue table.
  * Each M_*.wav has a track entry, is stereo 16-bit PCM, and its duration
    matches the declared loop length.
  * The default, title and duel tracks are valid.

Exit codes: 0 pass, 1 problems (or warnings under --strict), 2 setup error.
"""

from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "Tools"))

import dai.config as C  # noqa: E402

MUSIC_JSON = ROOT / "DuelAcademyIsland" / "Content" / "Data" / "Audio" / "music.json"
AUDIO_DIR = ROOT / "DuelAcademyIsland" / "SourceAssets" / "Audio"
INTERIORS = ROOT / "DuelAcademyIsland" / "Content" / "Data" / "World" / "interiors.json"
STORY_DIR = ROOT / "DuelAcademyIsland" / "Content" / "Data" / "Story"


def wav_info(path: Path) -> tuple[int, int, int, float]:
    with wave.open(str(path), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes() / w.getframerate()


def story_cues() -> set[str]:
    cues: set[str] = set()
    for path in STORY_DIR.rglob("*.json"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if '"music"' not in text:
            continue

        def walk(node):
            if isinstance(node, dict):
                if node.get("type") == "music" and node.get("track"):
                    cues.add(str(node["track"]))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        try:
            walk(json.loads(text))
        except json.JSONDecodeError:
            continue
    return cues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    if not MUSIC_JSON.exists():
        print(f"missing {MUSIC_JSON}")
        return 2
    doc = json.loads(MUSIC_JSON.read_text(encoding="utf-8"))
    tracks = doc.get("tracks") or {}
    zones = doc.get("zones") or {}
    sublocations = doc.get("sublocations") or {}
    interiors = doc.get("interiors") or {}
    cues = doc.get("cues") or {}

    errors: list[str] = []
    warnings: list[str] = []

    def check_track(label: str, track: str):
        if not track or track == "@auto":
            return
        if track not in tracks:
            errors.append(f"{label}: unknown track {track!r}")
            return
        path = AUDIO_DIR / f"{track}.wav"
        if not path.exists():
            errors.append(f"{label}: missing {path.name}")
            return
        sr, channels, width, duration = wav_info(path)
        if sr < 22050 or channels != 2 or width != 2:
            errors.append(f"{label}: {path.name} is {sr} Hz / {channels} ch / {width * 8} bit")
        declared = float(tracks[track].get("loop_seconds") or 0)
        if declared and abs(duration - declared) > 0.02:
            errors.append(f"{label}: {track} duration {duration:.3f}s != declared {declared:.3f}s")

    for key in ("default_track", "title_track", "duel_track"):
        check_track(key, doc.get(key, ""))

    for key in C.LOCATIONS:
        check_track(f"zone {key}", zones.get(key, ""))
        if key not in zones:
            errors.append(f"zone {key}: no music mapping")

    interior_doc = json.loads(INTERIORS.read_text(encoding="utf-8")) if INTERIORS.exists() else {}
    for cell in interior_doc.get("cells", []):
        cid = cell.get("id", "")
        if cid not in interiors:
            errors.append(f"interior {cid}: no music mapping")
        check_track(f"interior {cid}", interiors.get(cid, ""))

    for cue, track in cues.items():
        check_track(f"cue {cue}", track)

    for cue in sorted(story_cues()):
        if cue not in cues:
            errors.append(f"story cue {cue}: missing from music.json")

    mapped = {t for t in list(zones.values()) + list(sublocations.values()) + list(interiors.values()) + list(cues.values()) if t != "@auto"}
    for track in tracks:
        if track not in mapped:
            warnings.append(f"track {track}: rendered but not mapped to a zone/room/cue")
        path = AUDIO_DIR / f"{track}.wav"
        if not path.exists():
            errors.append(f"track {track}: no source WAV")
    for path in sorted(AUDIO_DIR.glob("M_*.wav")):
        if path.stem not in tracks:
            errors.append(f"{path.name}: WAV has no entry in music.json")

    print(f"tracks {len(tracks)} | zones {len(zones)} | sublocations {len(sublocations)} | rooms {len(interiors)} | cues {len(cues)}")
    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")

    if errors or (args.strict and warnings):
        return 1
    print("music map OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
