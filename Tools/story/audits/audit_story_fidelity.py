#!/usr/bin/env python3
"""Report-only audit: runtime story fidelity (duels, choices, scenes, dialogue coverage).

    python Tools/story/audits/audit_story_fidelity.py

The verbatim/paraphrase comparison needs the local-only dialogue dossier, which is
never committed. Point GX_DIALOGUE_FULL at it (default:
<GX_CANON_LOCAL_DIR or Tools/canon/.local_only>/dialogue_full.json); without it
that section is skipped.
"""
import collections
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # Tools/, for the shared common package
from common.jsonio import read_json  # noqa: E402
from common.paths import DATA_DIR as ROOT, TOOLS_DIR  # noqa: E402

LOCAL_ONLY_DIR = Path(os.environ.get("GX_CANON_LOCAL_DIR", str(TOOLS_DIR / "canon" / ".local_only")))
DIALOGUE_FULL = Path(os.environ.get("GX_DIALOGUE_FULL", str(LOCAL_ONLY_DIR / "dialogue_full.json")))

canon = read_json(ROOT / "Canon" / "events.json")["events"]
runtime = {e["id"]: e for e in read_json(ROOT / "Story" / "events.json")["events"]}
scenes = read_json(ROOT / "Story" / "scenes" / "full_campaign.json")["scenes"]
dialogue = read_json(ROOT / "Story" / "dialogue" / "full_campaign.json")["lines"]

print("=== RUNTIME EVENT FIDELITY ===")
total_canon_duels = 0
total_runtime_duels = 0
missing_scene = []
for ce in canon:
    i = ce["id"]
    re_ = runtime.get(i)
    if not re_:
        print(i, "MISSING FROM RUNTIME")
        continue
    # canonical duel total: count field or tournament rounds
    cd = 0
    for d in ce.get("duels", []):
        if "tournament" in d:
            cd += int(d["tournament"].get("rounds") or len(d["tournament"].get("participants") or []) or 1)
        else:
            cd += int(d.get("count") or 1)
    rd = len(re_.get("duels", []))
    total_canon_duels += cd
    total_runtime_duels += rd
    scene = scenes.get(re_.get("scene"), {})
    cmds = scene.get("commands", [])
    dl = sum(1 for k in dialogue if k.startswith(i + "."))
    choice_cmds = sum(1 for c in cmds if c.get("type") == "choice")
    embedded_choices = sum(1 for k, v in dialogue.items() if k.startswith(i + ".") and v.get("choices"))
    canon_choices = len(ce.get("choices", []))
    flags = []
    if cd != rd:
        flags.append(f"DUELS canon={cd} runtime={rd}")
    if canon_choices != choice_cmds + embedded_choices:
        flags.append(f"CHOICES canon={canon_choices} scene={choice_cmds} dialogue={embedded_choices}")
    if not scene:
        missing_scene.append(i)
        flags.append("NO SCENE")
    if dl == 0:
        flags.append("NO DIALOGUE")
    if flags:
        print(f"{i}: " + "; ".join(flags))
print(f"canon duel total={total_canon_duels} runtime duel total={total_runtime_duels}")
print("events without scenes:", missing_scene)

print("\n=== DIALOGUE COVERAGE ===")
print("runtime full-campaign lines:", len(dialogue))
opening = read_json(ROOT / "Story" / "dialogue" / "opening.json")["lines"]
print("runtime opening lines:", len(opening))
print("runtime total story lines:", len(dialogue) + len(opening))
lengths = [len(v.get("text", "")) for v in dialogue.values()]
print("runtime full-campaign total chars:", sum(lengths), "avg:", round(sum(lengths)/max(1,len(lengths)),1))
lengths_o = [len(v.get("text", "")) for v in opening.values()]
print("runtime opening total chars:", sum(lengths_o))

def norm(t):
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


if not DIALOGUE_FULL.exists():
    print(f"local-only dossier not found ({DIALOGUE_FULL}); skipping verbatim comparison")
else:
    local = read_json(DIALOGUE_FULL)
    print("local-only dossier type:", type(local), "keys:", list(local.keys())[:8] if isinstance(local, dict) else len(local))
    strings = local.get("strings") or local.get("lines") or local.get("entries") or local if isinstance(local, dict) else local
    if isinstance(strings, dict):
        strings = list(strings.values())
    print("local string count:", len(strings))
    sample = strings[:2]
    print("local sample:", json.dumps(sample)[:500])
    # extract raw text
    raw = []
    for s in strings:
        if isinstance(s, str):
            raw.append(s)
        elif isinstance(s, dict):
            raw.append(s.get("text") or s.get("value") or "")
    print("local total chars:", sum(len(x) for x in raw), "nonempty:", sum(1 for x in raw if x.strip()))

    local_norm = {norm(x) for x in raw if len(norm(x)) > 8}
    runtime_all = {**opening, **dialogue}
    verbatim = 0
    near = 0
    checked = 0
    for k, v in runtime_all.items():
        t = norm(v.get("text", ""))
        if len(t) <= 8:
            continue
        checked += 1
        if t in local_norm:
            verbatim += 1
        else:
            # check whether runtime line is contained in any local string (paraphrase detection)
            if any(t in l for l in local_norm):
                near += 1
    print(f"runtime lines checked={checked} exact matches={verbatim} contained-in-local={near}")
print("runtime source:", read_json(ROOT / "Story" / "dialogue" / "full_campaign.json")["source"])
print("opening source:", read_json(ROOT / "Story" / "dialogue" / "opening.json").get("source"))

print("\n=== CANON DIALOGUE INDEX ===")
idx = read_json(ROOT / "Canon" / "text" / "dialogue_index.json")
print("dialogue index keys:", list(idx.keys())[:10] if isinstance(idx, dict) else len(idx))
if isinstance(idx, dict):
    entries = idx.get("entries") or idx.get("strings") or idx.get("lines") or []
    print("index entries:", len(entries))
    print("sample keys:", list(entries[0].keys()) if entries else None)

print("\n=== SCENE COMMAND STATS ===")
cmd_types = collections.Counter()
for s in scenes.values():
    for c in s.get("commands", []):
        cmd_types[c.get("type")] += 1
print(cmd_types)
print("scene count:", len(scenes))
