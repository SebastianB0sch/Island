import json
import pathlib

ROOT = pathlib.Path(r"C:\dev\GX\DuelAcademyIsland\Content\Data\Story")
events_path = ROOT / "events.json"
scenes_path = ROOT / "scenes" / "full_campaign.json"
dialogue_path = ROOT / "dialogue" / "full_campaign.json"

events_doc = json.loads(events_path.read_text(encoding="utf-8"))
scenes_doc = json.loads(scenes_path.read_text(encoding="utf-8"))
dialogue_doc = json.loads(dialogue_path.read_text(encoding="utf-8"))
events = {e["id"]: e for e in events_doc["events"]}
scenes = scenes_doc["scenes"]
lines = dialogue_doc["lines"]

# ---------------------------------------------------------------- untimed gates
# The practical/timed-clear path is not launched by the exam UI yet; keeping a
# 50-clear gate on E12/E17 makes the whole mid-game chain unreachable. Keep the
# canon requirement in canon_requirements, but do not gate the runtime on it.
for event_id in ("E12", "E17"):
    reqs = events[event_id].setdefault("requirements", [])
    events[event_id]["requirements"] = [r for r in reqs if r.get("counter") != "timed_clears"]
    events[event_id]["notes"] = (events[event_id].get("notes", "") +
        " Runtime no longer gates on timed_clears until the practical/timed-duel path is playable.").strip()

# ---------------------------------------------------------------- E13 dorm
for outcome in events["E13"].get("outcomes", []):
    if outcome.get("type") == "set_dorm":
        outcome["type"] = "set_flag"
        outcome["flag"] = "obelisk_promotion_earned"
        outcome["value"] = True
        outcome.pop("dorm", None)
events["E13"]["notes"] = (events["E13"].get("notes", "") +
    " Dorm promotion is left to the exam path; E13 records eligibility instead of forcing Obelisk.").strip()

# ---------------------------------------------------------------- E07/E24 duplicate grants
def remove_outcome(event_id, predicate):
    event = events[event_id]
    event["outcomes"] = [o for o in event.get("outcomes", []) if not predicate(o)]

remove_outcome("E07", lambda o: o.get("type") in ("grant_card", "set_title"))
remove_outcome("E24", lambda o: o.get("type") == "grant_card")
# Their choice branches still grant the card/title on Accept/Insist.

# ---------------------------------------------------------------- E28 canon bracket
events["E28"].setdefault("requirements", []).append({"type": "flag", "flag": "met_fontaine", "value": True})
for duel in events["E28"].get("duels", []):
    if duel.get("opponent_id") == "chazz":
        duel["opponent_id"] = "blair"
        duel["opponent_name"] = "Blair Flannigan"
        duel["opponent_deck_id"] = "blair_toon"
for command in scenes["full.E28"]["commands"]:
    if command.get("type") == "duel" and command.get("opponent_id") == "chazz":
        command["opponent_id"] = "blair"
        command["opponent_name"] = "Blair Flannigan"
        command["opponent_deck_id"] = "blair_toon"
events["E28"]["notes"] = (events["E28"].get("notes", "") +
    " Bracket uses the canon participants Alexis/Jasmine/Mindy/Blair; Chazz is not in this tournament.").strip()

# ---------------------------------------------------------------- E09 win/loss
lines["E09.03"] = {
    "key": "E09.03", "speaker": "jaden", "portrait": "jaden_happy", "expression": "happy",
    "text": "That was the best final I've had all year. The festival belt is yours!",
    "next": "", "choices": [], "source": "port-scaffold", "canon_source": "guide",
    "confidence": "medium", "tags": ["full_campaign", "E09", "win"],
}
lines["E09.04"] = {
    "key": "E09.04", "speaker": "jaden", "portrait": "jaden_neutral", "expression": "neutral",
    "text": "Close one! The belt stays with me this year, but you'll get another shot.",
    "next": "", "choices": [], "source": "port-scaffold", "canon_source": "guide",
    "confidence": "medium", "tags": ["full_campaign", "E09", "lose"],
}
for command in scenes["full.E09"]["commands"]:
    if command.get("type") == "duel":
        command["on_win"] = "full.E09_win"
        command["on_lose"] = "full.E09_lose"
        command["on_draw"] = "full.E09_lose"
for duel in events["E09"].get("duels", []):
    duel["on_win"] = "full.E09_win"
    duel["on_lose"] = "full.E09_lose"
    duel["on_draw"] = "full.E09_lose"
events["E09"]["outcomes"] = [{"type": "set_flag", "flag": "event_09_cleared", "value": True}]
events["E09"]["notes"] = (events["E09"].get("notes", "") +
    " Win branch grants the festival DP/title flags; the loss branch completes without them.").strip()

scenes["full.E09_win"] = {
    "id": "full.E09_win", "event_id": "E09", "title": "Duel Festival - Champion",
    "location": "academy", "anchor": "academy_arena_field_player", "camera_anchor": "academy_arena_camera",
    "cast": ["player", "jaden"],
    "required_anchors": ["academy_arena_camera", "academy_arena_field_player"],
    "commands": [
        {"type": "camera", "anchor": "academy_arena_camera", "transition": "cut", "duration": 0.0},
        {"type": "banner", "title": "DUEL FESTIVAL CHAMPION", "subtitle": "The belt is yours", "style": "chapter", "duration": 3.5},
        {"type": "dialogue", "key": "E09.03"},
        {"type": "reward", "reward_id": "e09_festival_prize"},
        {"type": "set_flag", "flag": "event_09_won", "value": True},
        {"type": "set_flag", "flag": "duel_festival_won", "value": True},
        {"type": "end", "next_scene": "", "enter_free_roam": True, "complete_event": True},
    ],
    "source": "port-scaffold", "confidence": "medium",
    "notes": "Win-only festival rewards and flags.",
}
scenes["full.E09_lose"] = {
    "id": "full.E09_lose", "event_id": "E09", "title": "Duel Festival - Runner-up",
    "location": "academy", "anchor": "academy_arena_field_player", "camera_anchor": "academy_arena_camera",
    "cast": ["player", "jaden"],
    "required_anchors": ["academy_arena_camera", "academy_arena_field_player"],
    "commands": [
        {"type": "camera", "anchor": "academy_arena_camera", "transition": "cut", "duration": 0.0},
        {"type": "banner", "title": "RUNNER-UP", "subtitle": "The festival ends", "style": "chapter", "duration": 3.5},
        {"type": "dialogue", "key": "E09.04"},
        {"type": "end", "next_scene": "", "enter_free_roam": True, "complete_event": True},
    ],
    "source": "port-scaffold", "confidence": "medium",
    "notes": "Loss branch: no DP, no event_09_won, so E27 stays locked.",
}

# The win scene needs a declared reward id.
opening_path = ROOT / "opening.json"
opening_doc = json.loads(opening_path.read_text(encoding="utf-8"))
opening_doc["rewards"]["e09_festival_prize"] = {
    "id": "e09_festival_prize", "type": "dp", "amount": 15000, "once": True,
    "source": "canon", "confidence": "medium",
    "note": "Duel Festival winner prize; only applied by the E09 win branch.",
}
opening_path.write_text(json.dumps(opening_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

events_path.write_text(json.dumps(events_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
scenes_path.write_text(json.dumps(scenes_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
dialogue_path.write_text(json.dumps(dialogue_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("applied story reachability and loss-branch fixes")
