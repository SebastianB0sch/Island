import json
import pathlib

ROOT = pathlib.Path(r"C:\dev\GX\DuelAcademyIsland\Content\Data")
CANON = ROOT / "Canon"
STORY = ROOT / "Story"

# ---------------------------------------------------------------- Sheppard deck
canon = json.loads((CANON / "decks.json").read_text(encoding="utf-8"))
sheppard = next((d for d in canon["decks"] if d["id"] == "sheppard_year1"), None)
if not sheppard:
    raise SystemExit("sheppard_year1 missing from canon decks")
runtime_deck = {
    "schema_version": 1,
    "id": "sheppard_year1",
    "opponent": "sheppard",
    "name": "Chancellor Sheppard - Year 1",
    "variant": "base",
    "confidence": "high",
    "source": "Content/Data/Canon/decks.json (GameFAQs Character Deck List FAQ v1.4, section y)",
    "notes": "E33 promotion duel. Exact canon list; generic shell included.",
    "cards": sheppard["main"],
    "extra": sheppard["extra"],
    "side": [],
}
(STORY.parent / "Opponents" / "decks" / "sheppard_year1.json").write_text(
    json.dumps(runtime_deck, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
)
print("wrote sheppard_year1.json", len(sheppard["main"]), "main", len(sheppard["extra"]), "extra")

# ---------------------------------------------------------------- E33 event
events_path = STORY / "events.json"
events_doc = json.loads(events_path.read_text(encoding="utf-8"))
e33 = next(e for e in events_doc["events"] if e["id"] == "E33")
e33["trigger"] = {"type": "weekday", "value": "Saturday"}
e33["requirements"] = [
    {"type": "counter", "counter": "wins_total", "op": ">=", "value": 200},
    {"type": "wins_against_each", "count": 10, "duelists": 20},
    {"type": "written_correct_percent", "percent": 60},
    {"type": "flag", "flag": "post_game", "value": True},
]
e33["duels"] = [{
    "type": "duel",
    "opponent_id": "sheppard",
    "opponent_name": "Chancellor Sheppard",
    "opponent_deck_id": "sheppard_year1",
    "player_deck": "active",
    "mode": "story",
    "on_win": "full.E33_win",
    "on_lose": "full.E33_lose",
    "on_draw": "full.E33_lose",
    "optional": False,
    "story_critical": True,
    "counts_as_win": True,
    "award_dp": "formula",
}]
e33["outcomes"] = [
    {"type": "set_flag", "flag": "event_33_cleared", "value": True},
]
e33["dialogue_keys"] = ["E33.01", "E33.02", "E33.03", "E33.04", "E33.05"]
e33["notes"] = (
    "Promotion duel vs Chancellor Sheppard restored. Win -> King of Games; "
    "loss -> Prince of Games. Per-duelist 10-win and 60% written gates are "
    "evaluated by the event graph; post_game opens at the end of the school year."
)
events_path.write_text(json.dumps(events_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("updated E33 event")

# ---------------------------------------------------------------- scenes
scenes_path = STORY / "scenes" / "full_campaign.json"
scenes_doc = json.loads(scenes_path.read_text(encoding="utf-8"))
scenes = scenes_doc["scenes"]
e33_scene = scenes["full.E33"]
e33_scene["commands"] = [
    {"type": "camera", "anchor": "chancellor_office_camera", "transition": "cut", "duration": 0.0},
    {"type": "banner", "title": "The Duel King", "subtitle": "E33", "style": "location", "duration": 2.5},
    {"type": "dialogue", "key": "E33.01"},
    {"type": "dialogue", "key": "E33.02"},
    {"type": "dialogue", "key": "E33.03"},
    {"type": "duel", "opponent_id": "sheppard", "opponent_name": "Chancellor Sheppard",
     "opponent_deck_id": "sheppard_year1", "player_deck": "active", "mode": "story",
     "on_win": "full.E33_win", "on_lose": "full.E33_lose", "on_draw": "full.E33_lose",
     "optional": False, "story_critical": True, "counts_as_win": True, "award_dp": "formula"},
    {"type": "end", "next_scene": "", "enter_free_roam": False, "complete_event": True},
]
scenes["full.E33_win"] = {
    "id": "full.E33_win",
    "event_id": "E33",
    "title": "King of Games",
    "location": "academy",
    "anchor": "chancellor_office_desk",
    "camera_anchor": "chancellor_office_camera",
    "cast": ["player", "sheppard"],
    "required_anchors": ["chancellor_office_camera", "chancellor_office_desk"],
    "commands": [
        {"type": "camera", "anchor": "chancellor_office_camera", "transition": "cut", "duration": 0.0},
        {"type": "banner", "title": "KING OF GAMES", "subtitle": "The island is yours", "style": "chapter", "duration": 4.0},
        {"type": "dialogue", "key": "E33.04"},
        {"type": "reward", "reward_id": "e33_king_of_games"},
        {"type": "set_flag", "flag": "king_of_games", "value": True},
        {"type": "set_flag", "flag": "name_change_unlocked", "value": True},
        {"type": "end", "next_scene": "", "enter_free_roam": True, "complete_event": True},
    ],
    "source": "port-scaffold",
    "confidence": "high",
    "notes": "King of Games branch; name change is unlocked for post-game.",
}
scenes["full.E33_lose"] = {
    "id": "full.E33_lose",
    "event_id": "E33",
    "title": "Prince of Games",
    "location": "academy",
    "anchor": "chancellor_office_desk",
    "camera_anchor": "chancellor_office_camera",
    "cast": ["player", "sheppard"],
    "required_anchors": ["chancellor_office_camera", "chancellor_office_desk"],
    "commands": [
        {"type": "camera", "anchor": "chancellor_office_camera", "transition": "cut", "duration": 0.0},
        {"type": "banner", "title": "PRINCE OF GAMES", "subtitle": "A rival is waiting next year", "style": "chapter", "duration": 4.0},
        {"type": "dialogue", "key": "E33.05"},
        {"type": "reward", "reward_id": "e33_prince_of_games"},
        {"type": "set_flag", "flag": "prince_of_games", "value": True},
        {"type": "end", "next_scene": "", "enter_free_roam": True, "complete_event": True},
    ],
    "source": "port-scaffold",
    "confidence": "high",
    "notes": "Prince of Games branch for losing the promotion duel.",
}
scenes_path.write_text(json.dumps(scenes_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("updated E33 scenes")

# ---------------------------------------------------------------- dialogue
dialogue_path = STORY / "dialogue" / "full_campaign.json"
dialogue_doc = json.loads(dialogue_path.read_text(encoding="utf-8"))
lines = dialogue_doc["lines"]
lines["E33.04"] = {
    "key": "E33.04",
    "speaker": "sheppard",
    "portrait": "sheppard_happy",
    "expression": "happy",
    "text": "Then it is official. You are the King of Games. The island is yours to enjoy, and your name is yours to change.",
    "next": "",
    "choices": [],
    "source": "port-scaffold",
    "canon_source": "guide",
    "confidence": "high",
    "tags": ["full_campaign", "E33", "win"],
}
lines["E33.05"] = {
    "key": "E33.05",
    "speaker": "sheppard",
    "portrait": "sheppard_neutral",
    "expression": "neutral",
    "text": "Not this time. You are the Prince of Games, and the throne will wait for your next challenge.",
    "next": "",
    "choices": [],
    "source": "port-scaffold",
    "canon_source": "guide",
    "confidence": "high",
    "tags": ["full_campaign", "E33", "lose"],
}
dialogue_path.write_text(json.dumps(dialogue_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("added E33 ending lines")

# ---------------------------------------------------------------- rewards
opening_path = STORY / "opening.json"
opening_doc = json.loads(opening_path.read_text(encoding="utf-8"))
opening_doc["rewards"]["e33_king_of_games"] = {
    "id": "e33_king_of_games",
    "type": "title",
    "title": "King of Games",
    "once": True,
    "source": "canon",
    "confidence": "high",
    "note": "Win the E33 promotion duel against Chancellor Sheppard.",
}
opening_doc["rewards"]["e33_prince_of_games"] = {
    "id": "e33_prince_of_games",
    "type": "title",
    "title": "Prince of Games",
    "once": True,
    "source": "canon",
    "confidence": "high",
    "note": "Alternative E33 outcome when the promotion duel is lost.",
}
opening_path.write_text(json.dumps(opening_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("added E33 title rewards")
