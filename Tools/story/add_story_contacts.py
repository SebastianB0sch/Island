import json
import pathlib

path = pathlib.Path(r"C:\dev\GX\DuelAcademyIsland\Content\Data\World\spawns.json")
doc = json.loads(path.read_text(encoding="utf-8"))
spawns = doc["spawns"]
by_id = {s["id"]: s for s in spawns}

# Ensure named story contacts are present at world start.
for sid in ("slifer_banner_room_banner", "slifer_jaden_room_chumley", "chancellor_office_sheppard"):
    if sid in by_id:
        by_id[sid]["spawn_on_begin_play"] = True

# The E20 Shadow Game contact must exist before its talk event starts.
shadow = by_id.get("volcano_shadow_duelist")
if shadow:
    shadow["event_override"] = ""
    shadow["spawn_on_begin_play"] = True
    tags = shadow.get("schedule_tags", [])
    if "default" not in tags:
        tags.insert(0, "default")
    shadow["schedule_tags"] = tags
    shadow["notes"] = "Visible Shadow Game contact for E20; also an E24 staging point."

# Missing talk contacts for E16, E18 and E29.
new_spawns = [
    {
        "id": "academy_classroom_brier",
        "location_id": "academy_classroom",
        "zone_id": "academy",
        "interior_id": "academy_classroom",
        "anchor_id": "academy_classroom_student",
        "schedule_id": "brier",
        "schedule_tags": ["default", "weekday_am", "weekday_pm"],
        "role": "student",
        "dorm": "ra",
        "wander_radius_cm": 60,
        "event_override": "",
        "spawn_on_begin_play": True,
        "npc_class": "ADAStudentNPC",
        "display_name": "Brier",
        "notes": "E16 talk contact (quiz duel).",
        "spawn_z_offset_cm": 90.0,
    },
    {
        "id": "ra_cafeteria_sartyr",
        "location_id": "ra_cafeteria",
        "zone_id": "ra",
        "interior_id": "ra_cafeteria",
        "anchor_id": "ra_cafeteria_seat_02",
        "schedule_id": "sartyr",
        "schedule_tags": ["default", "weekday_am", "weekday_pm"],
        "role": "teacher",
        "dorm": "ra",
        "wander_radius_cm": 40,
        "event_override": "",
        "spawn_on_begin_play": True,
        "npc_class": "ADAStudentNPC",
        "display_name": "Sartyr",
        "notes": "E18 talk contact (Ra Yellow only).",
        "spawn_z_offset_cm": 90.0,
    },
    {
        "id": "academy_classroom_fontaine",
        "location_id": "academy_classroom",
        "zone_id": "academy",
        "interior_id": "academy_classroom",
        "anchor_id": "academy_classroom_student_02",
        "schedule_id": "fontaine",
        "schedule_tags": ["default", "weekday_am", "weekday_pm"],
        "role": "nurse",
        "dorm": "white",
        "wander_radius_cm": 40,
        "event_override": "",
        "spawn_on_begin_play": True,
        "npc_class": "ADAStudentNPC",
        "display_name": "Nurse Fontaine",
        "notes": "E29 talk contact after a failed exam.",
        "spawn_z_offset_cm": 90.0,
    },
]
for entry in new_spawns:
    if entry["id"] not in by_id:
        spawns.append(entry)

path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("updated spawns:", len(spawns))
