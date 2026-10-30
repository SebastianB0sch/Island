"""Build the 34-event story canon (E01..E33 plus E28b).

Primary source: Yugipedia's translated official event list. Secondary:
GameFAQs event FAQ for translations and a few thresholds. Every record
carries structured conditions where the source is unambiguous and a plain
condition list where it is not.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from canon_common import CANON_DIR, ensure_dirs, read_json, utc_now, write_json

GUIDE = "https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events"
FAQ = "https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41359"


def n(name: str) -> str:
    name = name.replace("’", "'")
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load_cards() -> tuple[dict[str, int], dict[int, str]]:
    cards = read_json(CANON_DIR.parent / "cards.json")
    by_name = {n(c["name"]): int(c["id"]) for c in cards}
    by_id = {int(c["id"]): c["name"] for c in cards}
    return by_name, by_id


def card_refs(names: list[str], by_name: dict[str, int], by_id: dict[int, str]) -> list[dict]:
    refs = []
    for name in names:
        cid = by_name.get(n(name))
        refs.append({"name": name, "card_id": cid, "resolved": cid is not None})
    return refs


EVENTS = [
    {
        "id": "E01", "number": 1, "title": "School Registration",
        "where": ["Gym", "Slifer Red cafeteria", "Shop", "Classroom"],
        "when": {"date": {"year": 1, "month": 10, "day": 1}, "weekday": "Sunday",
                 "note": "Opening ceremony; first free-roam day is Saturday, October 7."},
        "requirements": [{"type": "new_game"}],
        "duels": [],
        "rewards": [{"type": "dp", "amount": 3000, "source": "Lyman Banner"},
                    {"type": "email_unlock", "contacts": ["jaden", "syrus", "chumley"]},
                    {"type": "tutorial", "topic": "duel basics", "teacher": "syrus"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Opening: Sheppard speech, name entry, registration, dorm intro, Banner grant, Syrus tutorial.",
        "keywords": ["Welcome, elite duelists", "registration", "Slifer Red"],
    },
    {
        "id": "E02", "number": 2, "title": "Pharaoh's True Power",
        "where": ["Lyman Banner's Room"], "when": {"weekday": "Saturday"},
        "requirements": [{"type": "dorm", "value": "Slifer Red"},
                         {"type": "wins_against", "opponent": "jaden", "count": 3},
                         {"type": "wins_against", "opponent": "syrus", "count": 3},
                         {"type": "wins_against", "opponent": "chumley", "count": 3},
                         {"type": "talk", "npc": "banner"}],
        "duels": [{"opponent": "pharaoh", "deck": "pharaoh_year1", "mode": "story"}],
        "rewards": [{"type": "card_by_result", "win": "Panther Warrior",
                     "lose": "Bone Mouse", "draw": "Outstanding Dog Marron"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Banner's cat duel; reward depends on result.",
        "keywords": ["Pharaoh", "Banner"],
    },
    {
        "id": "E03", "number": 3, "title": "A New Hero Summoned",
        "where": ["Jaden's Room"], "when": {"weekday": "Weekdays", "automatic": True},
        "requirements": [{"type": "dorm", "value": "Slifer Red"},
                         {"type": "wins_against", "opponent": "syrus", "count": 10},
                         {"type": "wins_against", "opponent": "jaden", "count": 5}],
        "duels": [{"opponent": "jaden", "deck": "jaden_improved", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Elemental Hero Flame Wingman"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Jaden debuts an improved Elemental HERO deck.",
        "keywords": ["Flame Wingman", "new hero"],
    },
    {
        "id": "E04", "number": 4, "title": "Old Memories, Part 1",
        "where": ["Anywhere"], "when": {"weekday": "Sunday", "period": "AM"},
        "requirements": [{"type": "title_at_least", "value": "Average Duelist"},
                         {"type": "talk", "npc": "syrus"},
                         {"type": "duel_trigger", "opponent": "syrus", "chance": "1/3", "period": "AM"}],
        "duels": [{"opponent": "syrus", "deck": "syrus_year1", "mode": "story_special",
                   "player_deck_override": "jaden_year1", "objective": "one_turn_win",
                   "solution": "Summon Elemental Hero Thunder Giant, destroy Steam Gyroid, attack directly."}],
        "rewards": [{"type": "card", "name": "Power Bond"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Uses Jaden's deck and a fixed one-turn puzzle; no incorrect solution allowed.",
        "keywords": ["Old Memories", "Steam Gyroid", "Thunder Giant"],
    },
    {
        "id": "E04b", "number": 4.5, "title": "Old Memories, Part 2",
        "where": ["Next to Ocean"], "when": {"weekday": "Sunday", "period": "Night", "automatic": True},
        "requirements": [{"type": "event_cleared", "event": "E04"}],
        "duels": [{"opponent": "zane", "deck": "zane_year1", "mode": "story"}],
        "rewards": [{"type": "email_unlock", "contacts": ["zane"]}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Zane email unlocks regardless of result.",
        "keywords": ["Zane", "ocean"],
    },
    {
        "id": "E05", "number": 5, "title": "The Power of the Kaiser",
        "where": ["Anywhere"], "when": {"weekday": "Weekdays", "automatic": True},
        "requirements": [{"type": "event_cleared", "event": "E04"},
                         {"type": "wins_against", "opponent": "zane", "count": 1},
                         {"type": "dorm", "value": "Obelisk Blue"}],
        "duels": [{"opponent": "zane", "deck": "zane_year1", "mode": "story"}],
        "rewards": [{"type": "dp", "amount": 3000}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Crowler wants to see you beat Zane again.",
        "keywords": ["Kaiser", "Crowler", "Zane"],
    },
    {
        "id": "E06", "number": 6, "title": "Dark Fiend Deck",
        "where": ["Harbor", "Ocean"], "when": {"weekday": "Weekdays", "period": "PM", "automatic": True},
        "requirements": [{"type": "title_at_least", "value": "Fiery Duelist"},
                         {"type": "dorm_in", "values": ["Slifer Red", "Ra Yellow"]},
                         {"type": "wins_against_group", "group": "Obelisk Blue students", "count": 10}],
        "duels": [{"opponent": "shadow_duelist", "deck": "shadow_duelist_year1", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Jinzo"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Crowler hires Titan; Jaden and friends escort you to the ocean.",
        "keywords": ["Titan", "Dark Fiend", "Jinzo"],
    },
    {
        "id": "E07", "number": 7, "title": "Occult Recommendation",
        "where": ["Classroom"], "when": {"weekday": "Weekdays", "automatic": True},
        "requirements": [{"type": "event_cleared", "event": "E06"},
                         {"type": "card_in_main_deck", "name": "Jinzo"},
                         {"type": "met_npc", "npc": "torrey"}],
        "duels": [{"opponent": "torrey", "deck": "torrey_year1", "mode": "story",
                   "player_deck_override": "torrey_special"}],
        "rewards": [{"type": "card", "name": "Destiny Board"},
                    {"type": "temporary_title", "value": "Occult Duelist"}],
        "choices": [{"id": "accept", "options": ["Accept", "Refuse"]}],
        "once": True, "confidence": "high",
        "notes": "Temporary title reverts after E08.",
        "keywords": ["Seance", "Occult", "Destiny Board"],
    },
    {
        "id": "E08", "number": 8, "title": "Jinzo",
        "where": ["Your Room"], "when": {"period": "PM", "after_event": "E07", "automatic": True},
        "requirements": [{"type": "event_cleared", "event": "E07"}],
        "duels": [{"opponent": "jinzo", "deck": "jinzo_spirit", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Final Countdown"},
                    {"type": "restore_title"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Torrey's pursuer is the spirit of Jinzo.",
        "keywords": ["Jinzo", "spirit"],
    },
    {
        "id": "E09", "number": 9, "title": "Duel Festival",
        "where": ["Classroom", "Duel Arena"],
        "when": {"weekday": "Friday", "rule": "third Friday of November"},
        "requirements": [{"type": "date_rule", "rule": "third Friday of November"}],
        "duels": [{"opponent": "festival_bracket", "mode": "story_tournament"}],
        "rewards": [{"type": "dp", "amount": 15000}],
        "choices": [], "once": False, "repeatable_yearly": True, "confidence": "high",
        "notes": "Dueling extravaganza; 15,000 DP on win.",
        "keywords": ["Duel Academy Festival", "festival"],
    },
    {
        "id": "E10", "number": 10, "title": "Merry Christmas",
        "where": ["Headmaster's Room (current dorm)"],
        "when": {"date": {"year": 1, "month": 12, "day": 25}},
        "requirements": [{"type": "title_at_least", "value": "Average Duelist"},
                         {"type": "visit", "npc": "dorm_headmaster"}],
        "duels": [],
        "rewards": [{"type": "pack_by_dorm",
                     "Slifer Red": "master_fusions", "Ra Yellow": "special_ways",
                     "Obelisk Blue": "basic_1a"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Free pack from your dorm headmaster.",
        "keywords": ["Christmas", "present"],
    },
    {
        "id": "E11", "number": 11, "title": "New Year's Duel",
        "where": ["Your Room"], "when": {"date": {"year": 2, "month": 1, "day": 1}},
        "requirements": [{"type": "date", "month": 1, "day": 1}],
        "duels": [{"opponent_by_dorm": {
            "Slifer Red": ["jaden", "syrus", "chumley"],
            "Ra Yellow": ["bastion"],
            "Obelisk Blue": ["zane", "alexis", "chazz"]}, "mode": "story"}],
        "rewards": [], "choices": [], "once": True, "confidence": "high",
        "notes": "A friend visits and duels you.",
        "keywords": ["New Year", "resolution"],
    },
    {
        "id": "E12", "number": 12, "title": "Pride of the Elite",
        "where": ["Front of Obelisk Blue Boys' Dorm"],
        "when": {"weekday": "Weekdays", "automatic": True},
        "requirements": [{"type": "title_at_least", "value": "Superior Duelist"},
                         {"type": "dorm", "value": "Slifer Red"}],
        "duels": [{"opponent": "topher", "mode": "story"},
                  {"opponent": "conklin", "mode": "story"},
                  {"opponent": "chazz", "deck": "chazz_year1", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Return Zombie"},
                    {"type": "card", "name": "Inpachi"},
                    {"type": "card", "name": "Injection Fairy Lily"},
                    {"type": "email_unlock", "contacts": ["chazz"]}],
        "choices": [{"id": "refuse_duel", "options": ["Accept", "Refuse"],
                     "note": "A refusal can still escalate with a 1/3 chance."}],
        "once": True, "confidence": "high",
        "notes": "Chazz and his two lackeys.",
        "keywords": ["Pride of the Elite", "Topher", "Conklin"],
    },
    {
        "id": "E13", "number": 13, "title": "Battle against Chazz",
        "where": ["Classroom", "Duel Arena", "Harbor"],
        "when": {"weekday": "Weekdays", "automatic": True},
        "requirements": [{"type": "dorm_in", "values": ["Slifer Red", "Ra Yellow"]},
                         {"type": "wins_against", "opponent": "chazz", "count": 10}],
        "duels": [{"opponent": "chazz", "deck": "chazz_year1", "mode": "story"}],
        "rewards": [{"type": "dorm_unlock", "value": "Obelisk Blue"},
                    {"type": "exam_exemption", "scope": "monthly exams"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Beating Chazz in front of Crowler admits you to Obelisk Blue.",
        "keywords": ["Battle against Chazz", "Obelisk Blue"],
    },
    {
        "id": "E14", "number": 14, "title": "Revenge of the Obelisk Blues",
        "where": ["Obelisk Blue Boys' Lobby", "Duel Arena"],
        "when": {"weekday": "Weekdays", "period": "PM", "automatic": True},
        "requirements": [{"type": "event_cleared", "event": "E13"}],
        "duels": [{"opponent": "jaden", "deck": "jaden_year1", "mode": "story"}],
        "rewards": [{"type": "card", "name": "X-Head Cannon"},
                    {"type": "card", "name": "Y-Dragon Head"},
                    {"type": "card", "name": "Z-Metal Tank"}],
        "choices": [{"id": "help_lackeys", "options": ["Accept", "Refuse"]}],
        "once": True, "confidence": "high",
        "notes": "Topher and Conklin ask you to beat Jaden for them.",
        "keywords": ["Revenge", "Topher", "Conklin"],
    },
    {
        "id": "E15", "number": 15, "title": "Chazz Reborn",
        "where": ["Chancellor's Office", "Duel Arena"],
        "when": {"weekday": "Weekdays", "automatic": True},
        "requirements": [{"type": "event_cleared", "event": "E14"},
                         {"type": "title_at_least", "value": "Honored Duelist"},
                         {"type": "written_correct", "count": 40},
                         {"type": "calendar_since_event", "event": "E14", "days": 21}],
        "duels": [{"opponent": "chazz", "deck": "chazz_ojama", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Ojama Yellow"},
                    {"type": "card", "name": "Ojama Green"},
                    {"type": "card", "name": "Ojama Black"},
                    {"type": "card", "name": "Ojama Trio"},
                    {"type": "card", "name": "Ojama Delta Hurricane!!"},
                    {"type": "email_unlock", "contacts": ["chazz"]}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Chazz's Ojama deck; Honored requires 40 written answers (20%).",
        "keywords": ["Chazz Reborn", "Ojama"],
    },
    {
        "id": "E16", "number": 16, "title": "Brier and Beauregard",
        "where": ["Duel Arena"], "when": {"weekday": "Saturday", "period": "PM"},
        "requirements": [{"type": "dorm", "value": "Ra Yellow"},
                         {"type": "wins_against", "opponent": "brier", "count": 5},
                         {"type": "wins_against", "opponent": "beauregard", "count": 5},
                         {"type": "see_npc", "npc": "brier", "location": "Duel Arena"},
                         {"type": "talk", "npc": "brier"}],
        "duels": [{"opponent": "brier", "deck": "brier_year1", "mode": "story"},
                  {"opponent": "beauregard", "deck": "beauregard_year1", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Robbin' Goblin"},
                    {"type": "card", "name": "Goblin Thief"}],
        "choices": [], "once": True, "confidence": "high",
        "keywords": ["Brier", "Beauregard", "Goblin"],
    },
    {
        "id": "E17", "number": 17, "title": "The Goblin King",
        "where": ["Classroom", "Front of Duel Academy", "Harbor"],
        "when": {"weekday": "Weekdays", "period": "PM/Night", "automatic": True},
        "requirements": [{"type": "event_cleared", "event": "E16"},
                         {"type": "title_at_least", "value": "Superior Duelist"},
                         {"type": "dorm", "value": "Ra Yellow"},
                         {"type": "calendar_since_event", "event": "E16", "days": 30}],
        "duels": [{"opponent": "goblin_king", "mode": "story_timed",
                   "solution": "Use Change of Heart on Toon Goblin Attack Force and attack directly."},
                  {"opponent": "brier", "deck": "brier_year1", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Goblin Attack Force"},
                    {"type": "card", "name": "Goblin Elite Attack Force"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Ante/forbidden-rules timed duel, then Brier.",
        "keywords": ["Goblin King", "Toon Goblin", "Change of Heart"],
    },
    {
        "id": "E18", "number": 18, "title": "Who Are You?",
        "where": ["Your Room", "Next to Ocean", "Ra Yellow Cafeteria", "Duel Arena"],
        "when": {"note": "Talk to Sartyr once, wait 60 days, then talk again."},
        "requirements": [{"type": "dorm", "value": "Ra Yellow"},
                         {"type": "talk", "npc": "sartyr"},
                         {"type": "calendar_since_talk", "npc": "sartyr", "days": 60}],
        "duels": [], "rewards": [{"type": "card", "name": "Soitsu"},
                                 {"type": "card", "name": "Aitsu", "confidence": "medium"},
                                 {"type": "card", "name": "Koitsu", "confidence": "medium"}],
        "choices": [], "once": True, "confidence": "medium",
        "notes": "Yugipedia lists Soitsu only; GameFAQs adds Aitsu/Koitsu.",
        "keywords": ["Sartyr", "Soitsu"],
    },
    {
        "id": "E19", "number": 19, "title": "A Suspicious Character",
        "where": ["Classroom", "Front of Obelisk Blue Girls' Dorm"],
        "when": {"weekday": "Saturday", "period": "Night"},
        "requirements": [{"type": "talk", "npc": "alexis", "location": "Front of Obelisk Blue Girls' Dorm"},
                         {"type": "calendar_since_visit", "location": "Front of Obelisk Blue Girls' Dorm", "days": 90}],
        "duels": [{"opponent": "alexis", "deck": "alexis_year1", "mode": "story"},
                  {"opponent": "jasmine", "deck": "jasmine_year1", "mode": "story"},
                  {"opponent": "mindy", "deck": "mindy_year1", "mode": "story"}],
        "rewards": [{"type": "email_unlock", "contacts": ["alexis"]},
                    {"type": "unlock_duel", "opponents": ["jasmine", "mindy"],
                     "requires_title": "Prince of Games"}],
        "choices": [], "once": True, "confidence": "medium",
        "notes": "Guide says 3 months; exact trigger ambiguity flagged.",
        "keywords": ["card thief", "Alexis", "Jasmine", "Mindy"],
    },
    {
        "id": "E20", "number": 20, "title": "A Shadow Game",
        "where": ["Ocean", "Volcano", "Gym"], "when": {"weekday": "Weekend", "period": "PM"},
        "requirements": [{"type": "event_cleared", "event": "E19"},
                         {"type": "talk", "npc": "shadow_duelist"}],
        "duels": [{"opponent": "shadow_duelist", "deck": "shadow_duelist_year1",
                   "mode": "ante", "count": 3}],
        "rewards": [{"type": "dp_multiplier", "multiplier": 2, "note": "double current DP on clear"}],
        "choices": [], "once": True, "confidence": "medium",
        "notes": "Visit three locations; ante rule; exact order not fixed.",
        "keywords": ["Shadow Game", "Titan", "ante"],
    },
    {
        "id": "E21", "number": 21, "title": "Suspicious Classmate",
        "where": ["Your Room"], "when": {"weekday": "Weekdays", "period": "PM", "automatic": True},
        "requirements": [{"type": "event_cleared", "event": "E19"},
                         {"type": "met_npcs", "npcs": ["jaden", "syrus", "chumley", "bastion",
                                                      "dimitri", "brier", "beauregard", "blair", "gerard"]}],
        "duels": [], "rewards": [{"type": "dp", "amount": 1000}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Gerard's 9-question quiz; answers in exams.json.",
        "keywords": ["Gerard", "quiz", "question"],
    },
    {
        "id": "E22", "number": 22, "title": "Draw, Draw, Draw",
        "where": ["Shop", "Front of Obelisk Blue Boys' Dorm"],
        "when": {"weekday": "Weekdays", "period": "PM", "automatic": True},
        "requirements": [{"type": "title_at_least", "value": "Shrewd Duelist"},
                         {"type": "dorm", "value": "Obelisk Blue"},
                         {"type": "wins_against", "opponent": "damon", "count": 5},
                         {"type": "event_cleared", "event": "E17"}],
        "duels": [{"opponent": "damon", "deck": "damon_exodia", "mode": "story",
                   "player_deck_override": "damon_exodia"}],
        "rewards": [{"type": "card", "name": "Poison Draw Frog"},
                    {"type": "card", "name": "White Magical Hat"},
                    {"type": "card", "name": "Reload"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "Both sides use Damon's draw/Exodia deck.",
        "keywords": ["Draw, draw, draw", "Damon", "Exodia"],
    },
    {
        "id": "E23", "number": 23, "title": "Yugi's Legendary Deck",
        "where": ["Your Room", "Next to Ocean"],
        "when": {"weekday": "Weekdays", "period": "PM", "automatic": True},
        "requirements": [{"type": "event_cleared", "event": "E04"},
                         {"type": "event_cleared", "event": "E22"},
                         {"type": "dorm_in", "values": ["Ra Yellow", "Obelisk Blue"]},
                         {"type": "calendar_since_met", "npc": "dimitri", "days": 30}],
        "duels": [{"opponent": "dimitri", "deck": "yugi_deck", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Kuriboh"},
                    {"type": "card", "name": "Multiply"},
                    {"type": "exam_exemption", "scope": "next monthly exam"}],
        "choices": [], "once": True, "confidence": "high",
        "keywords": ["Yugi", "legendary Deck", "Dimitri"],
    },
    {
        "id": "E24", "number": 24, "title": "Missing Hero",
        "where": ["Harbor"], "when": {"weekday": "Saturday"},
        "requirements": [{"type": "dorm", "value": "Slifer Red"},
                         {"type": "calendar_since_met", "npc": "blair", "days": 30},
                         {"type": "win_rate_against", "opponent": "jaden", "percent": 50},
                         {"type": "meet_npc", "npc": "jaden", "location": "Harbor"},
                         {"type": "choice", "value": "Insist on talking"}],
        "duels": [{"opponent": "jaden", "deck": "jaden_year1", "mode": "story"}],
        "rewards": [{"type": "card", "name": "A Hero Emerges"},
                    {"type": "flag", "value": "blair_revealed"}],
        "choices": [{"id": "insist", "options": ["Insist", "Leave"]}],
        "once": True, "confidence": "high",
        "notes": "Blair reveals herself after the duel.",
        "keywords": ["Blair", "Missing Hero", "Harbor"],
    },
    {
        "id": "E25", "number": 25, "title": "The Power of a Maiden's Love",
        "where": ["Front of Obelisk Blue Boys' Dorm", "Your Room", "Harbor"],
        "when": {"weekday": "Saturday", "period": "PM"},
        "requirements": [{"type": "event_cleared", "event": "E24"},
                         {"type": "event_cleared", "event": "E23"},
                         {"type": "not_same_day", "events": ["E24"]},
                         {"type": "title_at_least", "value": "Shrewd Duelist"},
                         {"type": "go_to", "location": "Front of Obelisk Blue Boys' Dorm"}],
        "duels": [{"opponent": "blair", "deck": "blair_year1", "mode": "story"}],
        "rewards": [{"type": "card", "name": "White Magician Pikeru"},
                    {"type": "card", "name": "Ebon Magician Curran"},
                    {"type": "card", "name": "A Rival Appears!"}],
        "choices": [], "once": True, "confidence": "medium",
        "notes": "Exact timing is ambiguous in the guide.",
        "keywords": ["Maiden", "Blair", "Pikeru"],
    },
    {
        "id": "E26", "number": 26, "title": "The 7th Deck",
        "where": ["Classroom"], "when": {"weekday": "Saturday"},
        "requirements": [{"type": "event_cleared", "event": "E25"},
                         {"type": "go_to", "location": "Classroom"}],
        "duels": [{"opponent": "bastion", "deck": "bastion_seventh", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Mispolymerization"}],
        "choices": [], "once": True, "confidence": "high",
        "keywords": ["Seventh Deck", "Bastion"],
    },
    {
        "id": "E27", "number": 27, "title": "The Truth Behind Gerard",
        "where": ["Front of Slifer Red Dorm"], "when": {"automatic": True},
        "requirements": [{"type": "event_won", "event": "E09"}],
        "duels": [], "rewards": [{"type": "card", "name": "Skyscraper"}],
        "choices": [], "once": True, "confidence": "high",
        "keywords": ["Gerard", "Skyscraper"],
    },
    {
        "id": "E28", "number": 28, "title": "Battle for the Chocolate!",
        "where": ["Classroom", "Duel Arena"], "when": {"date": {"year": 2, "month": 2, "day": 14}},
        "requirements": [{"type": "met_npcs", "npcs": ["fontaine", "alexis", "jasmine", "mindy", "blair"]},
                         {"type": "participate"}],
        "duels": [{"opponent": "chocolate_bracket", "mode": "story_tournament", "rounds": 4}],
        "rewards": [{"type": "dp", "amount": 10000},
                    {"type": "item", "name": "Queen's chocolate"}],
        "choices": [], "once": True, "confidence": "high",
        "keywords": ["Valentine", "chocolate", "Queen"],
    },
    {
        "id": "E28b", "number": 28.2, "title": "Reversal Valentine's Day",
        "where": ["Obelisk Blue Girls' Dorm"], "when": {"date": {"year": 2, "month": 3, "day": 14}},
        "requirements": [{"type": "event_participated", "event": "E28"}],
        "duels": [],
        "rewards": [{"type": "choice_reward", "note": "Give the Queen one Level 4+ monster not in your Deck."}],
        "choices": [{"id": "give_gift", "options": ["Give gift", "Do not give gift"]}],
        "once": True, "confidence": "high",
        "keywords": ["Reverse Valentine", "chocolate"],
    },
    {
        "id": "E29", "number": 29, "title": "Helping the Dropout",
        "where": ["Gym"], "when": {"weekday": "Saturday", "period": "PM"},
        "requirements": [{"type": "title", "value": "Dropout Boy"},
                         {"type": "dorm", "value": "Slifer Red"},
                         {"type": "talk", "npc": "fontaine"}],
        "duels": [{"opponent": "fontaine", "deck": "fontaine_year1", "mode": "story"}],
        "rewards": [{"type": "dp_equal_remaining_lp"},
                    {"type": "title", "value": "Apprentice Duelist"}],
        "choices": [], "once": True, "confidence": "high",
        "keywords": ["Dropout", "Fontaine", "Ayukawa"],
    },
    {
        "id": "E30", "number": 30, "title": "A Friend's Concern",
        "where": ["Your Room (Slifer Red)"], "when": {"weekday": "Weekdays", "automatic": True},
        "requirements": [{"type": "dorm", "value": "Slifer Red"},
                         {"type": "stay_in_room_weekends", "count": 3}],
        "duels": [{"opponent": "chumley", "deck": "chumley_year1", "mode": "story"}],
        "rewards": [{"type": "card", "name": "Master of Oz"},
                    {"type": "card", "name": "Des Kangaroo", "confidence": "medium"}],
        "choices": [], "once": True, "confidence": "high",
        "keywords": ["Chumley", "room", "worried"],
    },
    {
        "id": "E31", "number": 31, "title": "The Walk Home",
        "where": ["Front of Duel Academy", "Next to Ocean"],
        "when": {"weekday": "Weekdays", "period": "PM", "automatic": True},
        "requirements": [{"type": "walk_home_same_character", "count": 3}],
        "duels": [{"opponent": "walk_home_partner", "mode": "story"}],
        "rewards": [{"type": "card_by_partner", "cards": {
            "jaden": "Wroughtweiler", "syrus": "Patroid", "chumley": "Des Wombat",
            "bastion": "Ring of Destruction", "alexis": "Fusion Weapon",
            "chazz": "Mefist the Infernal General", "zane": "Cyber Dragon"}}],
        "choices": [], "once": True, "confidence": "high",
        "keywords": ["walk home", "Let's go home"],
    },
    {
        "id": "E32", "number": 32, "title": "Help Miss Dorothy",
        "where": ["Front of Duel Academy"], "when": {"weekday": "Friday", "exam_day": True, "chance": "2/5"},
        "requirements": [{"type": "exam_day"}, {"type": "random_chance", "value": "2/5"}],
        "duels": [],
        "rewards": [{"type": "pack", "pack": "dorothys_gift", "note": "free pack from the shop afterwards"}],
        "choices": [], "once": False, "confidence": "high",
        "keywords": ["Dorothy", "truck", "delivery"],
    },
    {
        "id": "E33", "number": 33, "title": "The Duel King",
        "where": ["Chancellor's Office"], "when": {"weekday": "Saturday", "post_game": True},
        "requirements": [{"type": "wins_total", "count": 200},
                         {"type": "wins_against_each", "count": 10, "duelists": 20},
                         {"type": "written_correct_percent", "percent": 60},
                         {"type": "after_ending"}],
        "duels": [],
        "rewards": [{"type": "title", "value": "King of Games"},
                    {"type": "name_change"}],
        "choices": [], "once": True, "confidence": "high",
        "notes": "King of Games ending; name change and continued play.",
        "keywords": ["King of Games", "Duel King", "chancellor"],
    },
]


def attach_dialogue(events: list[dict], dialogue_previews: dict[int, str]) -> None:
    for event in events:
        keywords = event.pop("keywords", [])
        candidates = []
        for index, preview in dialogue_previews.items():
            if any(keyword.lower() in preview.lower() for keyword in keywords):
                candidates.append({"index": index, "preview": preview[:80]})
                if len(candidates) >= 8:
                    break
        event["dialogue_candidates"] = candidates
        event["dialogue_match"] = "keyword-preview" if candidates else "none"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path,
                        default=Path(r"C:\Users\Sebas\AppData\Local\Temp\opencode\gxcanon\guide_wikitext.json"))
    args = parser.parse_args()
    ensure_dirs()
    by_name, by_id = load_cards()

    dialogue_index_path = CANON_DIR / "text" / "dialogue_index.json"
    previews = {}
    if dialogue_index_path.exists():
        previews = {e["index"]: e["text_preview"] for e in read_json(dialogue_index_path)["entries"]}

    events = []
    for event in EVENTS:
        record = dict(event)
        record.setdefault("source", GUIDE)
        rewards = []
        for reward in record.get("rewards", []):
            reward = dict(reward)
            if reward.get("type") == "card":
                reward["cards"] = card_refs([reward["name"]], by_name, by_id)
            elif reward.get("type") == "card_by_result":
                reward["cards"] = card_refs(
                    [reward["win"], reward["lose"], reward["draw"]], by_name, by_id
                )
            elif reward.get("type") == "card_by_partner":
                reward["cards"] = [
                    {"partner": partner, **card_refs([name], by_name, by_id)[0]}
                    for partner, name in reward.get("cards", {}).items()
                ]
            rewards.append(reward)
        record["rewards"] = rewards
        events.append(record)
    attach_dialogue(events, previews)

    write_json(CANON_DIR / "events.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {"primary": GUIDE, "secondary": FAQ,
                   "notes": "Yugipedia numbering is authoritative; GameFAQs ordering differs."},
        "summary": {"count": len(events), "numbered_1_to_33": 33,
                    "extra_records": ["E04b", "E28b"]},
        "events": events,
    })
    print(f"events: {len(events)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
