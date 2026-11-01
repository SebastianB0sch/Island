import json
import pathlib
from story_common import read_json, write_json


def main() -> int:
    path = pathlib.Path(__file__).resolve().parents[2] / "DuelAcademyIsland" / "Content" / "Data" / "Opponents" / "roster.json"
    doc = read_json(path)
    duelists = doc["duelists"]

    if not any(d["id"] == "sheppard" for d in duelists):
        duelists.append({
            "id": "sheppard",
            "name": "Chancellor Sheppard",
            "aliases": ["Chancellor"],
            "role": "event",
            "dorm": "Staff",
            "year": 3,
            "title": "Chancellor",
            "ai_profile": "dragon",
            "decks": ["sheppard_year1"],
            "default_deck": "sheppard_year1",
            "evolution_rules": [],
            "locations": [
                {"zone": "academy", "interior": "academy_chancellor_office", "name": "Chancellor's office"}
            ],
            "schedule": [
                {"weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                 "periods": ["AM", "PM", "Night"], "zone": "academy",
                 "interior": "academy_chancellor_office"},
                {"weekdays": ["Saturday", "Sunday"],
                 "periods": ["AM", "PM", "Night"], "zone": "academy",
                 "interior": "academy_chancellor_office"},
            ],
            "access": {
                "requires_flag": "post_game",
                "requires_title": "",
                "requires_dorm": "",
                "event_only": True,
            },
            "walk_home": {"enabled": False},
            "ante": [],
            "signature_card_ids": [],
            "signature_cards": [],
            "canon_gift_card_ids": [],
            "confidence": "high",
            "source": "GBA Event 33 promotion duel; deck from Canon/decks.json sheppard_year1",
            "notes": "Event-only E33 promotion duel. His canon deck is the Dragon list in Canon/decks.json.",
        })

    write_json(path, doc)
    print("roster duelists:", len(duelists))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
