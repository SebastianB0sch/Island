"""Build curated system canon: calendar, titles, DP rules, emails, locations."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from canon_common import (
    CANON_DIR, DEFAULT_ROM, ascii_strings, ensure_dirs, load_rom, read_json,
    utc_now, write_json,
)

SCHOOL_START = date(2006, 10, 1)  # Sunday, matches the guide's Event 1 date
SCHOOL_END = date(2007, 9, 30)
MONTH_ORDER = [
    (2006, 10), (2006, 11), (2006, 12), (2007, 1), (2007, 2), (2007, 3),
    (2007, 4), (2007, 5), (2007, 6), (2007, 7), (2007, 8), (2007, 9),
]
MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November",
    12: "December",
}
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIODS = ["AM", "PM", "Night"]

TITLES = [
    {
        "order": 1, "id": "dropout_boy", "name": "Dropout Boy", "permanent": False,
        "conditions": [{"type": "fail_exam"}],
        "confidence": "high", "notes": "Penalty state after failing a monthly exam.",
    },
    {
        "order": 2, "id": "apprentice_duelist", "name": "Apprentice Duelist", "permanent": True,
        "conditions": [{"type": "start"}, {"type": "recover_from_dropout", "event": "E29"}],
        "confidence": "high",
    },
    {
        "order": 3, "id": "novice_duelist", "name": "Novice Duelist", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 5}],
        "confidence": "low", "notes": "Threshold is not stated in the public guide; 5 wins is a working assumption.",
    },
    {
        "order": 4, "id": "average_duelist", "name": "Average Duelist", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 10}],
        "confidence": "high",
    },
    {
        "order": 5, "id": "fiery_duelist", "name": "Fiery Duelist", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 30}],
        "confidence": "high",
    },
    {
        "order": 6, "id": "calm_duelist", "name": "Calm Duelist", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 30},
                       {"type": "timed_clears", "count": 25}],
        "confidence": "medium", "notes": "GameFAQs board list; not corroborated by the official event page.",
    },
    {
        "order": 7, "id": "superior_duelist", "name": "Superior Duelist", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 50},
                       {"type": "timed_clears", "count": 50}],
        "confidence": "high",
    },
    {
        "order": 8, "id": "shrewd_duelist", "name": "Shrewd Duelist", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 100}],
        "confidence": "high", "notes": "Used by E22 gate.",
    },
    {
        "order": 9, "id": "honored_duelist", "name": "Honored Duelist", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 100},
                       {"type": "written_correct", "count": 40}],
        "confidence": "medium", "notes": "Guide says 40 written answers (20%); GameFAQs says 100 wins.",
    },
    {
        "order": 10, "id": "elite_duelist", "name": "Elite Duelist", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 100},
                       {"type": "timed_clears", "count": 100}],
        "confidence": "medium",
    },
    {
        "order": 11, "id": "celebrity_duelist", "name": "Celebrity Duelist", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 150}],
        "confidence": "low", "notes": "No public threshold found; 150 wins is a placeholder that must be verified.",
    },
    {
        "order": 12, "id": "prince_of_games", "name": "Prince of Games", "permanent": True,
        "conditions": [{"type": "collection", "count": 1200},
                       {"type": "written_correct_percent", "percent": 40}],
        "confidence": "medium", "notes": "Event 19 also calls 200 wins 'Duel Prince'; reconcile in game.",
    },
    {
        "order": 13, "id": "king_of_games", "name": "King of Games", "permanent": True,
        "conditions": [{"type": "wins_total", "count": 200},
                       {"type": "wins_against_each", "count": 10, "duelists": 20},
                       {"type": "written_correct_percent", "percent": 60},
                       {"type": "after_ending"}],
        "confidence": "high",
    },
    {
        "order": 14, "id": "occult_duelist", "name": "Occult Duelist", "permanent": False,
        "conditions": [{"type": "event", "event": "E07"}],
        "confidence": "high", "notes": "Temporary story title; reverts after E08.",
    },
]

DP_RULES = {
    "starting_dp": 3000,
    "win": {
        "base": 100,
        "per_100_lp_lost": 1,
        "per_100_battle_damage": 1,
        "per_monster_destroyed_by_battle": 50,
        "notes": [
            "Masterplan formula: 100 base + 1 per 100 LP lost + 1 per 100 battle damage + 50 per battle-destroyed monster.",
            "LP/damage branch wording is ambiguous; verify whether 'lost' means player LP lost or opponent LP lost.",
        ],
    },
    "special_victory_bonuses": {
        "exodia": "unresolved amount",
        "deck_out": "unresolved amount",
        "final_countdown": "unresolved amount",
        "destiny_board": "unresolved amount",
    },
    "turn_multiplier": {
        "status": "unresolved",
        "notes": "Turn-count multiplier exists per masterplan but exact table is not extracted.",
    },
    "event_rewards": {
        "E01": {"dp": 3000},
        "E05": {"dp": 3000},
        "E09": {"dp": 15000},
        "E20": {"dp_multiplier": 2},
        "E21": {"dp": 1000},
        "E28": {"dp": 10000},
        "E29": {"dp_equal_remaining_lp": True},
    },
    "confidence": "medium",
    "source": "Docs/PORT_MASTERPLAN.md section 2.3 plus event guide",
}

LOCATION_ROWS = [
    ("Duel Academy", "Academy plaza / main entrance", "academy_plaza"),
    ("Front of School", "Academy plaza / main entrance", "academy_plaza"),
    ("Classroom", "Academy interior classroom", "academy_classroom"),
    ("Test Room", "Academy interior exam room", "academy_test_room"),
    ("Duel Arena", "Grand Duel Arena", "duel_arena"),
    ("Gym", "Duel Gym & Beach", "gym"),
    ("Shop", "Academy Card Shop", "card_shop"),
    ("Principal's Office", "Chancellor's office", "chancellors_office"),
    ("Dr. Crowler's Room", "Academy staff office", "crowler_office"),
    ("Slifer Red Dorm", "Slifer Red Dorm exterior", "slifer_dorm"),
    ("Front of Dorm", "Dorm exterior (context-specific)", "dorm_front"),
    ("Lobby", "Dorm lobby (context-specific)", "dorm_lobby"),
    ("Cafeteria", "Dorm cafeteria (context-specific)", "dorm_cafeteria"),
    ("Your Room", "Dorm room (context-specific)", "dorm_room"),
    ("Headmaster's Room", "Dorm headmaster room (context-specific)", "dorm_headmaster"),
    ("Jaden's Room", "Slifer interior bunk room", "slifer_jaden_room"),
    ("Zane's Room", "Obelisk interior room", "obelisk_zane_room"),
    ("Ra Yellow Dorm", "Ra Yellow Dorm exterior", "ra_dorm"),
    ("Obelisk Blue - Boys' Dorm", "Obelisk Blue Dorm exterior", "obelisk_boys_dorm"),
    ("Obelisk Blue - Girls' Dorm", "Obelisk Blue Girls' Dorm exterior", "obelisk_girls_dorm"),
    ("Ocean", "Beach / shore / lake overlook", "ocean"),
    ("Next to Ocean", "Beach / shore / lake overlook", "ocean"),
    ("Volcano", "Volcano viewpoint / crater", "volcano"),
    ("Near Crater", "Volcano viewpoint / crater", "volcano_crater"),
    ("Harbor", "Harbor & Lighthouse", "harbor"),
    ("Abandoned Dorm", "Abandoned Dorm", "abandoned_dorm"),
]


def weekday_name(value: date) -> str:
    # Python weekday(): Monday=0..Sunday=6. WEEKDAYS is Sunday=0..Saturday=6.
    return WEEKDAYS[(value.weekday() + 1) % 7]


def month_record(year: int, month: int) -> dict:
    first = date(year, month, 1)
    next_month = date(year + (month == 12), (month % 12) + 1, 1)
    last = next_month - timedelta(days=1)
    fridays = []
    cursor = first
    while cursor <= last:
        if cursor.weekday() == 4:  # Monday=0
            fridays.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return {
        "index": MONTH_ORDER.index((year, month)) + 1,
        "year": year,
        "month": month,
        "name": MONTH_NAMES[month],
        "start": first.isoformat(),
        "end": last.isoformat(),
        "start_weekday": weekday_name(first),
        "days": (last - first).days + 1,
        "fridays": fridays,
        "exam_friday_default": fridays[-1],
        "exam_friday_rule": "last Friday (working default; exact rule unresolved)",
        "exam_confidence": "low",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    args = parser.parse_args()
    ensure_dirs()

    months = [month_record(year, month) for year, month in MONTH_ORDER]
    write_json(CANON_DIR / "calendar.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {
            "rom": "0x146CCD8 weekdays, 0x146CD6A months, 0x146CD16 periods",
            "guide": "https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events",
        },
        "school_year": {
            "year_label": "Year 1",
            "start": SCHOOL_START.isoformat(),
            "end": SCHOOL_END.isoformat(),
            "start_weekday": weekday_name(SCHOOL_START),
            "first_playable_day": "2006-10-07",
            "first_playable_weekday": "Saturday",
            "months": months,
        },
        "week": {"days": WEEKDAYS, "school_days": WEEKDAYS[1:6],
                 "weekend": [WEEKDAYS[0], WEEKDAYS[6]]},
        "periods": PERIODS,
        "multi_year": {
            "years_supported": [1, 2, 3],
            "note": "Year 1 is 2006-10..2007-09. Year 2/3 repeat the month/weekday rules; recompute dates because 2008 is a leap year.",
            "confidence": "medium",
        },
        "exam_rule": {
            "day": "Friday",
            "week": "unresolved; last Friday is the working default",
            "confidence": "low",
        },
        "fixed_dates": [
            {"event": "E01", "date": "2006-10-01", "note": "Opening ceremony"},
            {"event": "E01_free_roam", "date": "2006-10-07", "note": "First playable day"},
            {"event": "E09", "date": "third Friday of November", "note": "Duel Festival"},
            {"event": "E10", "date": "2006-12-25", "note": "Christmas"},
            {"event": "E11", "date": "2007-01-01", "note": "New Year"},
            {"event": "E28", "date": "2007-02-14", "note": "Valentine"},
            {"event": "E28b", "date": "2007-03-14", "note": "Reverse Valentine"},
        ],
    })

    # Attach ROM offsets to the title names when the title string table exists.
    title_offsets = {}
    title_path = CANON_DIR / "text" / "title_strings.json"
    if title_path.exists():
        for item in read_json(title_path)["titles"]:
            title_offsets[item["text"]] = item["offset"]
    for title in TITLES:
        raw_offset = title_offsets.get(title["name"])
        if raw_offset is None and title["name"] == "Prince of Games":
            raw_offset = title_offsets.get("Prince of Games")
        title["rom_offset"] = f"0x{int(raw_offset):06X}" if raw_offset is not None else None

    write_json(CANON_DIR / "titles.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {"rom": "0x146C858..0x146C92A", "guide": "Yugipedia Events + GameFAQs board list"},
        "permanent_count_excluding_dropout": 12,
        "temporary_count": 1,
        "titles": TITLES,
    })

    write_json(CANON_DIR / "dp_rules.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": DP_RULES.pop("source"),
        **DP_RULES,
    })

    # Emails derived from event rewards.
    events = read_json(CANON_DIR / "events.json")["events"] if (CANON_DIR / "events.json").exists() else []
    contacts = {}
    for event in events:
        for reward in event.get("rewards", []):
            if reward.get("type") == "email_unlock":
                for contact in reward.get("contacts", []):
                    contacts.setdefault(contact, {"contact": contact, "unlocked_by": []})
                    contacts[contact]["unlocked_by"].append(event["id"])
    write_json(CANON_DIR / "emails.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": "Derived from events.json email_unlock rewards",
        "note": "Message bodies live in the local-only dialogue dump; only contact/unlock facts are committed.",
        "contacts": [contacts[key] for key in sorted(contacts)],
    })

    rom = load_rom(args.rom)
    location_strings = ascii_strings(rom, 0x13F6FD0, 0x13F7420, 4)
    write_json(CANON_DIR / "locations.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {"rom": "0x13F6FD0 location-name pool", "mapping": "Docs/PORT_MASTERPLAN.md Appendix B"},
        "rom_strings": location_strings,
        "mapping": [
            {"gba_name": gba, "gx_zone": gx, "zone_id": zone}
            for gba, gx, zone in LOCATION_ROWS
        ],
    })
    print(f"months: {len(months)}  titles: {len(TITLES)}  locations: {len(LOCATION_ROWS)}")
    return 0


if __name__ == "__main__":
    main()
