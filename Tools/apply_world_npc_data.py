"""Apply layout.json / spawns.json NPC data to the existing island level.

This is a fast alternative to a full Build Island pass when only NPC appearance,
names, dialogue or count changed.  Run it with the editor:

    UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript -script=Tools/apply_world_npc_data.py -unattended -nosplash -nullrhi

It loads the island map, updates every ADAStudentNPC / ADANpcSpawnPoint from the
data files, spawns any layout NPC markers missing from the level, and saves the
map.  It does not rebuild meshes, materials or terrain.
"""

from __future__ import annotations

import json
import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYOUT = os.path.join(REPO, "DuelAcademyIsland", "SourceAssets", "Data", "layout.json")
CAST = os.path.join(REPO, "DuelAcademyIsland", "SourceAssets", "Data", "cast.json")
SPAWNS = os.path.join(REPO, "DuelAcademyIsland", "Content", "Data", "World", "spawns.json")
MAP = "/Game/DuelAcademy/Maps/DuelAcademyIsland"
GENERATED_TAG = "DA_Generated"


def load(path):
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def label_for(name):
    return name.replace(" ", "_").replace(".", "")


def dorm_enum(value):
    return getattr(unreal.DADorm, str(value or "slifer").upper(), unreal.DADorm.SLIFER)


def set_if(obj, name, value):
    try:
        obj.set_editor_property(name, value)
    except Exception as exc:  # noqa: BLE001 - keep the pass going and report the field
        unreal.log_warning(f"apply_world_npc_data: {type(obj).__name__}.{name}: {exc}")


def apply_npc(actor, entry, cast):
    look = cast.get(entry.get("cast", ""), {})
    set_if(actor, "dorm", dorm_enum(entry.get("dorm")))
    set_if(actor, "wander_radius", float(entry.get("wander", 800.0)))
    set_if(actor, "display_name", entry.get("name", ""))
    set_if(actor, "lines", list(entry.get("lines", [])))
    if look:
        set_if(actor, "cast_mesh", look.get("name", ""))
        set_if(actor, "anim_group", look.get("group", ""))
        set_if(actor, "dorm_tint", bool(entry.get("tint", True)))
        set_if(actor, "body_scale", float(entry.get("scale", look.get("scale", 1.0))))
    if entry.get("hair"):
        set_if(actor, "hair_color", unreal.LinearColor(*entry["hair"], 1.0))
        set_if(actor, "override_hair_color", True)
    else:
        set_if(actor, "override_hair_color", False)
    points = entry.get("points") or []
    set_if(actor, "wander_points", [unreal.Vector(*p) for p in points])
    set_if(actor, "wander_points_only", bool(points))


def apply_spawn_point(actor, spawn, cast):
    look = cast.get(spawn.get("cast", ""), {})
    set_if(actor, "dorm", dorm_enum(spawn.get("dorm")))
    set_if(actor, "display_name", spawn.get("display_name", ""))
    if look:
        set_if(actor, "cast_mesh", look.get("name", ""))
        set_if(actor, "anim_group", look.get("group", ""))
        set_if(actor, "dorm_tint", bool(spawn.get("tint", True)))
        set_if(actor, "body_scale", float(spawn.get("scale", look.get("scale", 1.0))))
    if spawn.get("lines"):
        set_if(actor, "lines", list(spawn["lines"]))
    if spawn.get("hair"):
        set_if(actor, "hair_color", unreal.LinearColor(*spawn["hair"], 1.0))
        set_if(actor, "override_hair_color", True)
    else:
        set_if(actor, "override_hair_color", False)


def main() -> int:
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level.load_level(MAP):
        unreal.log_error(f"apply_world_npc_data: FAIL could not load {MAP}")
        return 1

    layout = load(LAYOUT)
    cast = load(CAST).get("meshes", {})
    spawns = load(SPAWNS).get("spawns", [])
    by_label = {label_for(n["name"]): n for n in layout.get("npcs", []) if n.get("name")}
    by_loc = {tuple(round(float(v), 1) for v in n["loc"]): n
              for n in layout.get("npcs", []) if n.get("loc")}
    spawn_by_label = {f"Spawn_{s['id']}": s for s in spawns}

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    npc_cls = unreal.load_class(None, "/Script/DuelAcademyIsland.DAStudentNPC")
    if npc_cls is None:
        unreal.log_error("apply_world_npc_data: FAIL missing DAStudentNPC")
        return 1

    actors = actor_subsystem.get_all_level_actors()
    matched = set()
    stale = []
    updated_npcs = 0
    updated_points = 0

    for actor in actors:
        cls_name = actor.get_class().get_name()
        if cls_name == "DAStudentNPC":
            loc = actor.get_actor_location()
            entry = by_loc.get((round(loc.x, 1), round(loc.y, 1), round(loc.z, 1)))
            if entry is None:
                entry = by_label.get(actor.get_actor_label())
            if entry is None:
                best = None
                best_d = 25.0  # cm
                for candidate in layout.get("npcs", []):
                    c = candidate.get("loc")
                    if not c:
                        continue
                    d = (loc.x - c[0]) ** 2 + (loc.y - c[1]) ** 2 + (loc.z - c[2]) ** 2
                    if d < best_d:
                        best, best_d = candidate, d
                entry = best
            if entry is None:
                # Old generated ambient marker that the current layout no
                # longer contains.  Remove it so the level matches the data.
                label = actor.get_actor_label()
                tags = list(actor.get_editor_property("tags") or [])
                if label.startswith("Student_") and GENERATED_TAG in tags:
                    stale.append(actor)
                continue
            apply_npc(actor, entry, cast)
            actor.set_actor_label(label_for(entry["name"]))
            matched.add(tuple(round(float(v), 1) for v in entry["loc"]))
            updated_npcs += 1

        elif cls_name == "DANpcSpawnPoint":
            spawn = spawn_by_label.get(actor.get_actor_label())
            if spawn is None:
                continue
            apply_spawn_point(actor, spawn, cast)
            updated_points += 1

    # The level may predate a layout with more ambient markers: spawn the rest.
    spawned = 0
    for entry in layout.get("npcs", []):
        key = tuple(round(float(v), 1) for v in entry.get("loc", []))
        if not key or key in matched:
            continue
        loc = unreal.Vector(*entry["loc"])
        rot = unreal.Rotator(0.0, float(entry.get("yaw", 0.0)), 0.0)
        actor = actor_subsystem.spawn_actor_from_class(npc_cls, loc, rot)
        if actor is None:
            unreal.log_warning(f"apply_world_npc_data: could not spawn {entry.get('name')}")
            continue
        actor.set_actor_label(label_for(entry["name"]))
        actor.set_folder_path("Gameplay/npcs")
        tags = list(actor.get_editor_property("tags") or [])
        if GENERATED_TAG not in tags:
            tags.append(GENERATED_TAG)
        actor.set_editor_property("tags", tags)
        apply_npc(actor, entry, cast)
        spawned += 1

    for actor in stale:
        actor_subsystem.destroy_actor(actor)

    if not level.save_current_level():
        unreal.log_error("apply_world_npc_data: FAIL could not save the level")
        return 1
    unreal.log(f"apply_world_npc_data: PASS updated {updated_npcs} NPCs, spawned {spawned}, "
               f"removed {len(stale)} stale, updated {updated_points} spawn points; saved {MAP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
