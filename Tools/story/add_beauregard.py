import json
import pathlib

path = pathlib.Path(r"C:\dev\GX\DuelAcademyIsland\Content\Data\World\spawns.json")
doc = json.loads(path.read_text(encoding="utf-8"))
spawns = doc["spawns"]
by_id = {s["id"]: s for s in spawns}
for sid in ("slifer_jaden_room_chumley", "slifer_banner_room_banner", "chancellor_office_sheppard"):
    if sid in by_id:
        by_id[sid]["spawn_on_begin_play"] = True
if "ra_cafeteria_beauregard" not in by_id:
    spawns.append({
        "id": "ra_cafeteria_beauregard",
        "location_id": "ra_cafeteria",
        "zone_id": "ra",
        "interior_id": "ra_cafeteria",
        "anchor_id": "ra_cafeteria_seat_01",
        "schedule_id": "beauregard",
        "schedule_tags": ["default", "weekday_am", "weekday_pm"],
        "role": "student",
        "dorm": "ra",
        "wander_radius_cm": 50,
        "event_override": "",
        "spawn_on_begin_play": True,
        "npc_class": "ADAStudentNPC",
        "display_name": "Beauregard",
        "notes": "E16 talk/duel contact.",
        "spawn_z_offset_cm": 90.0,
    })
path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("spawns", len(spawns))
