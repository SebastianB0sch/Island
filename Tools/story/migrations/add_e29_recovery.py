import json
import pathlib

ROOT = pathlib.Path(r"C:\dev\GX\DuelAcademyIsland\Content\Data\Story")
events_path = ROOT / "events.json"
scenes_path = ROOT / "scenes" / "full_campaign.json"
dialogue_path = ROOT / "dialogue" / "full_campaign.json"

events_doc = json.loads(events_path.read_text(encoding="utf-8"))
event = next(e for e in events_doc["events"] if e["id"] == "E29")
for outcome in event.get("outcomes", []):
    if outcome.get("type") == "grant_dp":
        outcome["type"] = "grant_dp_from_last_lp"
        outcome.pop("amount", None)
event["outcomes"] = [o for o in event["outcomes"] if o.get("type") != "grant_dp_from_last_lp" or True]
# Ensure the DP outcome exists exactly once.
if not any(o.get("type") == "grant_dp_from_last_lp" for o in event["outcomes"]):
    event["outcomes"].insert(0, {"type": "grant_dp_from_last_lp"})
event["notes"] = "Recovery duel: win -> Apprentice Duelist and DP equal to remaining LP; loss leaves Dropout Boy and can be retried."
for duel in event.get("duels", []):
    duel["on_win"] = "full.E29_win"
    duel["on_lose"] = "full.E29_lose"
    duel["on_draw"] = "full.E29_lose"
event["dialogue_keys"] = ["E29.01", "E29.02", "E29.03", "E29.04"]

scenes_doc = json.loads(scenes_path.read_text(encoding="utf-8"))
scenes = scenes_doc["scenes"]
scene = scenes["full.E29"]
for command in scene["commands"]:
    if command.get("type") == "duel":
        command["on_win"] = "full.E29_win"
        command["on_lose"] = "full.E29_lose"
        command["on_draw"] = "full.E29_lose"
scenes["full.E29_win"] = {
    "id": "full.E29_win", "event_id": "E29", "title": "Helping the Dropout - Recovery",
    "location": "gym", "anchor": "gym_practice_field_a", "camera_anchor": "gym_assembly_camera",
    "cast": ["player", "fontaine"], "required_anchors": ["gym_assembly_camera"],
    "commands": [
        {"type": "camera", "anchor": "gym_assembly_camera", "transition": "cut", "duration": 0.0},
        {"type": "banner", "title": "RECOVERY", "subtitle": "Apprentice Duelist", "style": "chapter", "duration": 3.0},
        {"type": "dialogue", "key": "E29.03"},
        {"type": "end", "next_scene": "", "enter_free_roam": True, "complete_event": True},
    ],
    "source": "port-scaffold", "confidence": "high",
    "notes": "Win branch: resumes the Apprentice title and awards remaining-LP DP through outcomes.",
}
scenes["full.E29_lose"] = {
    "id": "full.E29_lose", "event_id": "E29", "title": "Helping the Dropout - Retry",
    "location": "gym", "anchor": "gym_practice_field_a", "camera_anchor": "gym_assembly_camera",
    "cast": ["player", "fontaine"], "required_anchors": ["gym_assembly_camera"],
    "commands": [
        {"type": "camera", "anchor": "gym_assembly_camera", "transition": "cut", "duration": 0.0},
        {"type": "banner", "title": "TRY AGAIN", "subtitle": "Dropout Boy", "style": "chapter", "duration": 3.0},
        {"type": "dialogue", "key": "E29.04"},
        {"type": "end", "next_scene": "", "enter_free_roam": True, "complete_event": False},
    ],
    "source": "port-scaffold", "confidence": "high",
    "notes": "Loss branch: event stays available so the player can retry the recovery duel.",
}

dialogue_doc = json.loads(dialogue_path.read_text(encoding="utf-8"))
lines = dialogue_doc["lines"]
lines["E29.03"] = {
    "key": "E29.03", "speaker": "fontaine", "portrait": "fontaine_happy", "expression": "happy",
    "text": "You did it. Welcome back, Apprentice Duelist. Take the DP you earned and keep moving forward.",
    "next": "", "choices": [], "source": "port-scaffold", "canon_source": "guide",
    "confidence": "high", "tags": ["full_campaign", "E29", "win"],
}
lines["E29.04"] = {
    "key": "E29.04", "speaker": "fontaine", "portrait": "fontaine_neutral", "expression": "neutral",
    "text": "Not yet. Go rest, rebuild your deck, and come back when you are ready to try again.",
    "next": "", "choices": [], "source": "port-scaffold", "canon_source": "guide",
    "confidence": "high", "tags": ["full_campaign", "E29", "lose"],
}

events_path.write_text(json.dumps(events_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
scenes_path.write_text(json.dumps(scenes_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
dialogue_path.write_text(json.dumps(dialogue_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("E29 recovery branches added")
