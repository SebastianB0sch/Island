import json
import pathlib
from story_common import read_json, write_json


def main() -> int:
    ROOT = pathlib.Path(__file__).resolve().parents[2] / "DuelAcademyIsland" / "Content" / "Data" / "Story"
    scenes_path = ROOT / "scenes" / "full_campaign.json"
    dialogue_path = ROOT / "dialogue" / "full_campaign.json"
    events_path = ROOT / "events.json"

    scenes_doc = read_json(scenes_path)
    scenes = scenes_doc["scenes"]
    dialogue_doc = read_json(dialogue_path)
    lines = dialogue_doc["lines"]

    lines["E20.03"] = {
        "key": "E20.03", "speaker": "shadow_duelist", "portrait": "shadow_duelist_neutral",
        "expression": "neutral", "text": "The volcano next. The ante grows with every step.",
        "next": "", "choices": [], "source": "port-scaffold", "canon_source": "guide",
        "confidence": "medium", "tags": ["full_campaign", "E20"],
    }
    lines["E20.04"] = {
        "key": "E20.04", "speaker": "shadow_duelist", "portrait": "shadow_duelist_neutral",
        "expression": "neutral", "text": "The gym is the last table. Win, and the shadow game is over.",
        "next": "", "choices": [], "source": "port-scaffold", "canon_source": "guide",
        "confidence": "medium", "tags": ["full_campaign", "E20"],
    }


    def duel():
        return {
            "type": "duel", "opponent_id": "shadow_duelist", "opponent_name": "Titan",
            "opponent_deck_id": "shadow_duelist_fiend", "player_deck": "active", "mode": "ante",
            "on_win": "", "on_lose": "", "on_draw": "", "optional": False,
            "story_critical": True, "counts_as_win": True, "award_dp": "formula",
        }


    scenes["full.E20"]["commands"] = [
        {"type": "camera", "anchor": "beach_shore", "transition": "cut", "duration": 0.0},
        {"type": "banner", "title": "A Shadow Game", "subtitle": "Ocean", "style": "location", "duration": 2.5},
        {"type": "dialogue", "key": "E20.01"},
        {"type": "dialogue", "key": "E20.02"},
        duel(),
        {"type": "end", "next_scene": "full.E20_b", "enter_free_roam": False, "complete_event": False},
    ]
    scenes["full.E20_b"] = {
        "id": "full.E20_b", "event_id": "E20", "title": "A Shadow Game - Volcano",
        "location": "volcano", "anchor": "volcano_crater", "camera_anchor": "volcano_crater",
        "cast": ["player", "shadow_duelist"], "required_anchors": ["volcano_crater"],
        "commands": [
            {"type": "camera", "anchor": "volcano_crater", "transition": "cut", "duration": 0.0},
            {"type": "banner", "title": "A Shadow Game", "subtitle": "Volcano", "style": "location", "duration": 2.5},
            {"type": "dialogue", "key": "E20.03"},
            duel(),
            {"type": "end", "next_scene": "full.E20_c", "enter_free_roam": False, "complete_event": False},
        ],
        "source": "port-scaffold", "confidence": "medium", "notes": "Second shadow-game location.",
    }
    scenes["full.E20_c"] = {
        "id": "full.E20_c", "event_id": "E20", "title": "A Shadow Game - Gym",
        "location": "gym", "anchor": "gym_duel_field", "camera_anchor": "gym_assembly_camera",
        "cast": ["player", "shadow_duelist"], "required_anchors": ["gym_assembly_camera"],
        "commands": [
            {"type": "camera", "anchor": "gym_assembly_camera", "transition": "cut", "duration": 0.0},
            {"type": "banner", "title": "A Shadow Game", "subtitle": "Gym", "style": "location", "duration": 2.5},
            {"type": "dialogue", "key": "E20.04"},
            duel(),
            {"type": "end", "next_scene": "", "enter_free_roam": False, "complete_event": True},
        ],
        "source": "port-scaffold", "confidence": "medium", "notes": "Final shadow-game location.",
    }

    write_json(scenes_path, scenes_doc)
    write_json(dialogue_path, dialogue_doc)

    events_doc = read_json(events_path)
    event = next(e for e in events_doc["events"] if e["id"] == "E20")
    event["dialogue_keys"] = ["E20.01", "E20.02", "E20.03", "E20.04"]
    event["notes"] = "Three-location sequence restored as three chained scenes: Ocean -> Volcano -> Gym."
    write_json(events_path, events_doc)
    print("E20 three-location sequence added")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
