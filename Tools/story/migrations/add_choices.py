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


def add_line(key, text, choices=None):
    lines[key] = {
        "key": key,
        "speaker": "player",
        "portrait": "player_neutral",
        "expression": "neutral",
        "text": text,
        "next": "",
        "choices": choices or [],
        "source": "port-scaffold",
        "canon_source": "guide",
        "confidence": "high",
        "tags": ["full_campaign", key.split(".")[0]],
    }


def insert_choice(event_id, prompt_key, prompt_text, options, skip_key=None):
    scene = scenes[f"full.{event_id}"]
    commands = scene["commands"]
    add_line(prompt_key, prompt_text, options)
    choice_command = {"type": "choice", "key": prompt_key}
    insert_at = len(commands) - 1
    for index, command in enumerate(commands):
        if command.get("type") in ("duel", "end"):
            insert_at = index
            break
    commands.insert(insert_at, choice_command)
    if skip_key:
        commands.append({
            "type": "end",
            "key": skip_key,
            "next_scene": "",
            "enter_free_roam": False,
            "complete_event": True,
        })


# E07 - Accept / Refuse the occult recommendation.
insert_choice(
    "E07", "E07.choice",
    "Torrey holds out a strange card. Do you accept the occult recommendation?",
    [
        {"id": "accept", "text": "Accept", "next_scene": "", "next_key": "",
         "outcomes": [
             {"type": "grant_card", "card_id": 602, "count": 1},
             {"type": "set_title", "title": "Occult Duelist"},
             {"type": "set_flag", "flag": "occult_duelist", "value": True},
             {"type": "set_flag", "flag": "occult_accepted", "value": True},
         ]},
        {"id": "refuse", "text": "Refuse", "next_scene": "", "next_key": "E07.refuse_end",
         "outcomes": [{"type": "set_flag", "flag": "occult_refused", "value": True}]},
    ],
    skip_key="E07.refuse_end",
)

# E12 - Accept / Refuse the elite duel.
insert_choice(
    "E12", "E12.choice",
    "The Obelisk elite demand a response. Do you accept their challenge?",
    [
        {"id": "accept", "text": "Accept", "next_scene": "", "next_key": "",
         "outcomes": [{"type": "set_flag", "flag": "elite_duel_accepted", "value": True}]},
        {"id": "refuse", "text": "Refuse", "next_scene": "", "next_key": "",
         "outcomes": [{"type": "set_flag", "flag": "elite_duel_refused", "value": True}]},
    ],
)

# E14 - Accept / Refuse helping the lackeys.
insert_choice(
    "E14", "E14.choice",
    "The Obelisk lackeys ask for your help. Do you accept?",
    [
        {"id": "accept", "text": "Accept", "next_scene": "", "next_key": "",
         "outcomes": [{"type": "set_flag", "flag": "helped_lackeys", "value": True}]},
        {"id": "refuse", "text": "Refuse", "next_scene": "", "next_key": "",
         "outcomes": [{"type": "set_flag", "flag": "refused_lackeys", "value": True}]},
    ],
)

# E24 - Insist on talking / Leave.
insert_choice(
    "E24", "E24.choice",
    "Jaden is hiding something. Do you insist on talking, or leave him alone?",
    [
        {"id": "insist", "text": "Insist", "next_scene": "", "next_key": "",
         "outcomes": [
             {"type": "grant_card", "card_id": 921, "count": 1},
             {"type": "set_flag", "flag": "blair_revealed", "value": True},
         ]},
        {"id": "leave", "text": "Leave", "next_scene": "", "next_key": "E24.leave_end",
         "outcomes": [{"type": "set_flag", "flag": "blair_left", "value": True}]},
    ],
    skip_key="E24.leave_end",
)

# E28b - Give / Do not give the reversal gift.
insert_choice(
    "E28b", "E28b.choice",
    "The Queen expects a gift in return. Do you give one?",
    [
        {"id": "give", "text": "Give gift", "next_scene": "", "next_key": "",
         "outcomes": [{"type": "set_flag", "flag": "valentine_gift_given", "value": True}]},
        {"id": "decline", "text": "Do not give gift", "next_scene": "", "next_key": "",
         "outcomes": [{"type": "set_flag", "flag": "valentine_gift_declined", "value": True}]},
    ],
)

# Remove branch rewards from event outcomes; the selected choice owns them now.
def strip_outcomes(event_id, types, flags=None):
    event = events[event_id]
    kept = []
    for outcome in event.get("outcomes", []):
        if outcome.get("type") in types:
            if flags is not None and outcome.get("flag") not in flags:
                kept.append(outcome)
            continue
        kept.append(outcome)
    event["outcomes"] = kept

strip_outcomes("E07", {"grant_card", "set_title"}, {"occult_duelist"})
strip_outcomes("E24", {"grant_card"}, {"blair_revealed"})
strip_outcomes("E28b", set(), {"valentine_gift_given"})
# The two flag strips above need an explicit keep-list pass.
for event_id, remove_flags in (("E07", {"occult_duelist"}), ("E24", {"blair_revealed"}), ("E28b", {"valentine_gift_given"})):
    events[event_id]["outcomes"] = [
        o for o in events[event_id].get("outcomes", [])
        if not (o.get("type") == "set_flag" and o.get("flag") in remove_flags)
    ]

# Record the added dialogue keys on the events.
for event_id, key in (("E07", "E07.choice"), ("E12", "E12.choice"), ("E14", "E14.choice"),
                      ("E24", "E24.choice"), ("E28b", "E28b.choice")):
    keys = events[event_id].setdefault("dialogue_keys", [])
    if key not in keys:
        keys.append(key)

events_path.write_text(json.dumps(events_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
scenes_path.write_text(json.dumps(scenes_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
dialogue_path.write_text(json.dumps(dialogue_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("added 5 story choices")
