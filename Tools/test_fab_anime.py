"""Headless check for the optional Fab Anime Character Pack integration.

Run with the editor:
    UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript -script=Tools/test_fab_anime.py -unattended -nosplash -nullrhi

It loads the pack Blueprint, spawns temporary ADAStudentNPC actors in the editor
world, activates every Fab look, and verifies the puppet head/hair/top/bottom
components. It does not save the level.
"""

import unreal

BLUEPRINT = "/Game/AnimeCharacters/Blueprints/Characters/bp_AnimeCharacter.bp_AnimeCharacter_C"
LOOKS = (
    "fab_male_a", "fab_male_b", "fab_male_c", "fab_male_d",
    "fab_female_a", "fab_female_b", "fab_female_c", "fab_female_d",
)
COMPONENTS = ("CharacterMesh0", "Hair", "Top", "Bottom")


def main() -> int:
    cls = unreal.load_class(None, BLUEPRINT)
    if cls is None:
        unreal.log_error("FabAnimeTest: FAIL could not load the pack Blueprint")
        return 1
    unreal.log("FabAnimeTest: PASS Blueprint %s" % cls.get_name())

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    npc_cls = unreal.load_class(None, "/Script/DuelAcademyIsland.DAStudentNPC")
    comp_cls = unreal.load_class(None, "/Script/DuelAcademyIsland.DAFabAnimeComponent")
    if world is None or npc_cls is None or comp_cls is None:
        unreal.log_error("FabAnimeTest: FAIL missing world/NPC/component class")
        return 1

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    failures = 0
    for look in LOOKS:
        npc = actors.spawn_actor_from_class(npc_cls, unreal.Vector(0, 0, 2000), unreal.Rotator(0, 0, 0))
        if npc is None:
            unreal.log_error("FabAnimeTest: FAIL could not spawn ADAStudentNPC for %s" % look)
            failures += 1
            continue
        npc.set_editor_property("fab_look", look)
        comp = npc.get_component_by_class(comp_cls)
        ok = bool(comp and comp.activate_look(look))
        puppet = None
        if ok:
            for candidate in actors.get_all_level_actors():
                if candidate != npc and candidate.get_owner() == npc:
                    puppet = candidate
                    break
        if puppet is None:
            unreal.log_error("FabAnimeTest: FAIL no puppet for %s" % look)
            failures += 1
            actors.destroy_actor(npc)
            continue
        found = {c.get_name(): c.get_skeletal_mesh_asset()
                 for c in puppet.get_components_by_class(unreal.SkeletalMeshComponent)}
        missing = [name for name in COMPONENTS if found.get(name) is None]
        if missing:
            unreal.log_error("FabAnimeTest: FAIL %s missing %s" % (look, ",".join(missing)))
            failures += 1
        else:
            unreal.log("FabAnimeTest: PASS %s -> %s" % (
                look, ", ".join("%s=%s" % (name, found[name].get_name()) for name in COMPONENTS)))
        actors.destroy_actor(puppet)
        actors.destroy_actor(npc)

    if failures:
        unreal.log_error("FabAnimeTest: FAILURES PRESENT (%d)" % failures)
        return 1
    unreal.log("FabAnimeTest: PASS ALL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
