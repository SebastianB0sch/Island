import json
import pathlib
from story_common import read_json, write_json


def main() -> int:
    ROOT = pathlib.Path(__file__).resolve().parents[2] / "DuelAcademyIsland" / "Content" / "Data"
    SCENES = ROOT / "Story" / "scenes" / "full_campaign.json"
    DIALOGUE = ROOT / "Story" / "dialogue" / "full_campaign.json"

    doc = read_json(SCENES)
    dialogue = read_json(DIALOGUE)
    scenes = doc["scenes"]

    # A choice with next_key must jump to a single, final End. The first pass
    # appended a second End, which fails the story contract validator.
    fixes = {
        "full.E07": "E07.refuse_end",
        "full.E24": "E24.leave_end",
    }
    for scene_id, target_key in fixes.items():
        commands = scenes[scene_id]["commands"]
        ends = [i for i, c in enumerate(commands) if c.get("type") == "end"]
        keep = ends[-1]
        commands[:] = [c for i, c in enumerate(commands) if c.get("type") != "end" or i == keep]
        commands[-1]["key"] = target_key

        line_key = scene_id.split(".")[-1] + ".choice"
        line = dialogue["lines"].get(line_key)
        if line:
            for choice in line.get("choices", []):
                if choice.get("next_key") == target_key:
                    choice["next_scene"] = ""
        print(scene_id, "ends:", [i for i, c in enumerate(commands) if c.get("type") == "end"])

    write_json(SCENES, doc)
    write_json(DIALOGUE, dialogue)
    print("story ends normalized")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
