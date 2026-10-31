import json
import pathlib

WORLD = pathlib.Path(r"C:\dev\GX\DuelAcademyIsland\Content\Data\World")

# ---------------------------------------------------------------- anchors
anchors_path = WORLD / "anchors.json"
anchors_doc = json.loads(anchors_path.read_text(encoding="utf-8"))
anchors = anchors_doc["anchors"]
by_id = {a["id"]: a for a in anchors}

new_anchors = [
    ("academy_classroom_student_03", "Classroom Student 03", "academy_classroom", "academy",
     "academy_classroom", [300480, 299690, -29900], 90.0, "Story duelist desk 3."),
    ("academy_classroom_student_04", "Classroom Student 04", "academy_classroom", "academy",
     "academy_classroom", [300600, 299530, -29900], 90.0, "Story duelist desk 4."),
    ("academy_classroom_student_05", "Classroom Student 05", "academy_classroom", "academy",
     "academy_classroom", [300720, 299370, -29900], 90.0, "Story duelist desk 5."),
    ("ra_cafeteria_seat_03", "Ra Cafeteria Seat 03", "ra_cafeteria", "ra",
     None, [-70830, 63850, 2295], 130.0, "Story duelist seat 3."),
    ("ra_cafeteria_seat_04", "Ra Cafeteria Seat 04", "ra_cafeteria", "ra",
     None, [-70610, 63850, 2295], 130.0, "Story duelist seat 4."),
    ("slifer_cafeteria_seat_04", "Slifer Cafeteria Seat 04", "slifer_cafeteria", "slifer",
     None, [-106170, 27900, 2945], 0.0, "Story duelist seat 4."),
    ("gym_assembly_student_04", "Gym Assembly Student 04", "academy_gym", "gym",
     None, [69950, 71650, 620], 157.0, "Story duelist crowd 4."),
    ("gym_assembly_student_05", "Gym Assembly Student 05", "academy_gym", "gym",
     None, [70150, 71500, 620], 157.0, "Story duelist crowd 5."),
]
for anchor_id, name, location_id, zone_id, interior_id, position, yaw, note in new_anchors:
    if anchor_id in by_id:
        continue
    anchors.append({
        "id": anchor_id,
        "name": name,
        "location_id": location_id,
        "zone_id": zone_id,
        "interior_id": interior_id,
        "kind": "npc",
        "position_ue": position,
        "yaw": yaw,
        "fov": 50.0,
        "look_at_ue": None,
        "tags": ["story", "duelist"],
        "notes": note,
    })
anchors_path.write_text(json.dumps(anchors_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

# ---------------------------------------------------------------- spawns
spawns_path = WORLD / "spawns.json"
spawns_doc = json.loads(spawns_path.read_text(encoding="utf-8"))
spawns = spawns_doc["spawns"]
spawn_by_id = {s["id"]: s for s in spawns}

# Give the contacts added earlier their own desks so they do not stack on generic students.
spawn_by_id["academy_classroom_brier"]["anchor_id"] = "academy_classroom_student_03"
spawn_by_id["academy_classroom_fontaine"]["anchor_id"] = "academy_classroom_student_04"

def add_spawn(spawn_id, anchor_id, location_id, zone_id, interior_id, display_name, dorm, note, wander=60):
    if spawn_id in spawn_by_id:
        return
    entry = {
        "id": spawn_id,
        "location_id": location_id,
        "zone_id": zone_id,
        "interior_id": interior_id,
        "anchor_id": anchor_id,
        "schedule_id": spawn_id,
        "schedule_tags": ["default", "weekday_am", "weekday_pm"],
        "role": "student",
        "dorm": dorm,
        "wander_radius_cm": wander,
        "event_override": "",
        "spawn_on_begin_play": True,
        "npc_class": "ADAStudentNPC",
        "display_name": display_name,
        "notes": note,
        "spawn_z_offset_cm": 90.0,
    }
    spawns.append(entry)
    spawn_by_id[spawn_id] = entry

add_spawn("academy_classroom_dimitri", "academy_classroom_student_05", "academy_classroom",
          "academy", "academy_classroom", "Dimitri", "ra", "Copycat duelist and E33 opponent.")
add_spawn("slifer_cafeteria_blair", "slifer_cafeteria_seat_04", "slifer_cafeteria",
          "slifer", None, "Blair Flannigan", "slifer", "Blair contact (E24/E28).")
add_spawn("ra_cafeteria_topher", "ra_cafeteria_seat_03", "ra_cafeteria",
          "ra", None, "Topher", "ra", "Goblin King contact (E17, E33 opponent).")
add_spawn("ra_cafeteria_gerard", "ra_cafeteria_seat_04", "ra_cafeteria",
          "ra", None, "Gerard", "ra", "Quiz duelist and E33 opponent.")
add_spawn("gym_assembly_conklin", "gym_assembly_student_04", "academy_gym",
          "gym", None, "Conklin", "ra", "Dinosaur duelist and E33 opponent.")
add_spawn("gym_assembly_damon", "gym_assembly_student_05", "academy_gym",
          "gym", None, "Damon", "slifer", "Wanderer duelist and E33 opponent.")

spawns_path.write_text(json.dumps(spawns_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("anchors:", len(anchors), "spawns:", len(spawns))
