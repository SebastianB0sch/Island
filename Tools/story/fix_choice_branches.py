import json
import pathlib

ROOT = pathlib.Path(r"C:\dev\GX\DuelAcademyIsland\Content\Data\Story")
scenes_path = ROOT / "scenes" / "full_campaign.json"
dialogue_path = ROOT / "dialogue" / "full_campaign.json"

scenes_doc = json.loads(scenes_path.read_text(encoding="utf-8"))
dialogue_doc = json.loads(dialogue_path.read_text(encoding="utf-8"))
scenes = scenes_doc["scenes"]

# Refusing these offers must actually skip the duel they would otherwise force.
# The last End gets a stable key; the refuse option jumps to it.
branches = {
    "full.E12": ("E12.choice", "refuse", "E12.refuse_end"),
    "full.E14": ("E14.choice", "refuse", "E14.refuse_end"),
}
for scene_id, (line_key, choice_id, end_key) in branches.items():
    commands = scenes[scene_id]["commands"]
    ends = [i for i, c in enumerate(commands) if c.get("type") == "end"]
    if not ends:
        raise SystemExit(f"{scene_id} has no End")
    # Keep exactly one End, last.
    keep = ends[-1]
    commands[:] = [c for i, c in enumerate(commands) if c.get("type") != "end" or i == keep]
    commands[-1]["key"] = end_key
    line = dialogue_doc["lines"][line_key]
    for choice in line.get("choices", []):
        if choice.get("id") == choice_id:
            choice["next_scene"] = ""
            choice["next_key"] = end_key
    print(scene_id, "refuse ->", end_key, "commands", len(commands))

scenes_path.write_text(json.dumps(scenes_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
dialogue_path.write_text(json.dumps(dialogue_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("E12/E14 refusal branches now skip their duels")
