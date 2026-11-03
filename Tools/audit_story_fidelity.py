#!/usr/bin/env python3
"""Ad-hoc fidelity audit for the story data.

Run from any directory:
    python Tools/audit_story_fidelity.py
    python Tools/audit_story_fidelity.py --local path/to/dialogue_full.json

The optional --local dossier is the extracted ROM dialogue kept outside the
repository; without it the audit still reports runtime coverage.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "DuelAcademyIsland" / "Content" / "Data"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit runtime story coverage against canon.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Content/Data directory")
    parser.add_argument("--local", type=Path, default=None, help="optional local dialogue_full.json dossier")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    canon = load(root / "Canon" / "events.json")["events"]
    runtime = {e["id"]: e for e in load(root / "Story" / "events.json")["events"]}
    scenes = load(root / "Story" / "scenes" / "full_campaign.json")["scenes"]
    dialogue = load(root / "Story" / "dialogue" / "full_campaign.json")["lines"]

    print("=== RUNTIME EVENT FIDELITY ===")
    total_canon_duels = 0
    total_runtime_duels = 0
    missing_scene = []
    for canon_event in canon:
        event_id = canon_event["id"]
        runtime_event = runtime.get(event_id)
        if not runtime_event:
            print(event_id, "MISSING FROM RUNTIME")
            continue
        # canonical duel total: count field or tournament rounds
        canon_duels = 0
        for duel in canon_event.get("duels", []):
            if "tournament" in duel:
                canon_duels += int(
                    duel["tournament"].get("rounds")
                    or len(duel["tournament"].get("participants") or [])
                    or 1
                )
            else:
                canon_duels += int(duel.get("count") or 1)
        runtime_duels = len(runtime_event.get("duels", []))
        total_canon_duels += canon_duels
        total_runtime_duels += runtime_duels
        scene = scenes.get(runtime_event.get("scene"), {})
        commands = scene.get("commands", [])
        dialogue_lines = sum(1 for key in dialogue if key.startswith(event_id + "."))
        choice_commands = sum(1 for command in commands if command.get("type") == "choice")
        embedded_choices = sum(
            1
            for key, value in dialogue.items()
            if key.startswith(event_id + ".") and value.get("choices")
        )
        canon_choices = len(canon_event.get("choices", []))
        flags = []
        if canon_duels != runtime_duels:
            flags.append(f"DUELS canon={canon_duels} runtime={runtime_duels}")
        if canon_choices != choice_commands + embedded_choices:
            flags.append(
                f"CHOICES canon={canon_choices} scene={choice_commands} dialogue={embedded_choices}"
            )
        if not scene:
            missing_scene.append(event_id)
            flags.append("NO SCENE")
        if dialogue_lines == 0:
            flags.append("NO DIALOGUE")
        if flags:
            print(f"{event_id}: " + "; ".join(flags))
    print(f"canon duel total={total_canon_duels} runtime duel total={total_runtime_duels}")
    print("events without scenes:", missing_scene)

    print("\n=== DIALOGUE COVERAGE ===")
    print("runtime full-campaign lines:", len(dialogue))
    opening = load(root / "Story" / "dialogue" / "opening.json")["lines"]
    print("runtime opening lines:", len(opening))
    print("runtime total story lines:", len(dialogue) + len(opening))
    lengths = [len(value.get("text", "")) for value in dialogue.values()]
    print(
        "runtime full-campaign total chars:",
        sum(lengths),
        "avg:",
        round(sum(lengths) / max(1, len(lengths)), 1),
    )
    lengths_o = [len(value.get("text", "")) for value in opening.values()]
    print("runtime opening total chars:", sum(lengths_o))

    local_norm: set[str] = set()
    if args.local is not None:
        if not args.local.is_file():
            print(f"local-only dossier not found, skipping comparison: {args.local}")
        else:
            local = load(args.local)
            print(
                "local-only dossier type:",
                type(local),
                "keys:",
                list(local.keys())[:8] if isinstance(local, dict) else len(local),
            )
            strings = (
                local.get("strings") or local.get("lines") or local.get("entries") or local
                if isinstance(local, dict)
                else local
            )
            if isinstance(strings, dict):
                strings = list(strings.values())
            print("local string count:", len(strings))
            sample = strings[:2]
            print("local sample:", json.dumps(sample)[:500])
            raw = []
            for entry in strings:
                if isinstance(entry, str):
                    raw.append(entry)
                elif isinstance(entry, dict):
                    raw.append(entry.get("text") or entry.get("value") or "")
            print(
                "local total chars:",
                sum(len(text) for text in raw),
                "nonempty:",
                sum(1 for text in raw if text.strip()),
            )
            local_norm = {norm(text) for text in raw if len(norm(text)) > 8}

    runtime_all = {**opening, **dialogue}
    verbatim = 0
    near = 0
    checked = 0
    for value in runtime_all.values():
        text = norm(value.get("text", ""))
        if len(text) <= 8:
            continue
        checked += 1
        if text in local_norm:
            verbatim += 1
        elif any(text in candidate for candidate in local_norm):
            near += 1
    print(f"runtime lines checked={checked} exact matches={verbatim} contained-in-local={near}")
    print("runtime source:", load(root / "Story" / "dialogue" / "full_campaign.json")["source"])
    print(
        "opening source:",
        load(root / "Story" / "dialogue" / "opening.json").get("source"),
    )

    print("\n=== CANON DIALOGUE INDEX ===")
    index = load(root / "Canon" / "text" / "dialogue_index.json")
    print("dialogue index keys:", list(index.keys())[:10] if isinstance(index, dict) else len(index))
    if isinstance(index, dict):
        entries = index.get("entries") or index.get("strings") or index.get("lines") or []
        print("index entries:", len(entries))
        print("sample keys:", list(entries[0].keys()) if entries else None)

    print("\n=== SCENE COMMAND STATS ===")
    command_types = collections.Counter()
    for scene in scenes.values():
        for command in scene.get("commands", []):
            command_types[command.get("type")] += 1
    print(command_types)
    print("scene count:", len(scenes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
