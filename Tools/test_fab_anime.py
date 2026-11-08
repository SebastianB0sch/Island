"""Headless check for the optional Fab Anime Character Pack integration.

Run with the editor:
    UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript -script=Tools/test_fab_anime.py -unattended -nosplash -nullrhi

It loads the pack Blueprint, spawns temporary ADAStudentNPC actors in the editor
world, activates every Fab look, and verifies the requested head/hair/top/bottom
meshes, sizing, outline pairing, movement state and native-avatar restore. It does
not save the level.
"""

import unreal

BLUEPRINT = "/Game/AnimeCharacters/Blueprints/Characters/bp_AnimeCharacter.bp_AnimeCharacter_C"
LOOKS = (
    "fab_male_a", "fab_male_b", "fab_male_c", "fab_male_d",
    "fab_female_a", "fab_female_b", "fab_female_c", "fab_female_d",
)
COMPONENTS = ("CharacterMesh0", "Hair", "Top", "Bottom")
AVATAR_CLASS = "/Script/DuelAcademyIsland.DAAvatarComponent"
EXPECTED_MESHES = {
    "fab_male_a": ("skl_AnimeM_Head_0", "sk_AnimeHair_M1", "skl_AnimeM_Top_Tshirt", "skl_AnimeM_Bottom_Pants"),
    "fab_male_b": ("skl_AnimeM_Head_0", "skl_AnimeHair_M2", "skl_AnimeM_Top_tank", "skl_AnimeM_Bottom_Shorts"),
    "fab_male_c": ("skl_AnimeM_Head_0", "sk_AnimeHair_M1", "skl_AnimeM_Top_tank", "skl_AnimeM_Bottom_Pants"),
    "fab_male_d": ("skl_AnimeM_Head_0", "skl_AnimeHair_M2", "skl_AnimeM_Top_Tshirt", "skl_AnimeM_Bottom_Shorts"),
    "fab_female_a": ("skl_AnimeF_Head_1", "skl_AnimeHair_F1", "skl_AnimeF_top_tank", "skl_AnimeF_bottom_skirt"),
    "fab_female_b": ("skl_AnimeF_Head_1", "skl_AnimeHair_F2", "skl_AnimeF_top_TurtleNeck", "skl_AnimeF_bottom_skirt"),
    "fab_female_c": ("skl_AnimeF_Head_1", "skl_AnimeHair_F2", "skl_AnimeF_top_tank", "skl_AnimeF_bottom_shorts"),
    "fab_female_d": ("skl_AnimeF_Head_1", "skl_AnimeHair_F1", "skl_AnimeF_top_TurtleNeck", "skl_AnimeF_bottom_shorts"),
}


def _mesh_bounds(mesh):
    try:
        return mesh.get_imported_bounds()
    except Exception:
        return mesh.get_bounds()


def _host_floor(npc):
    capsule = npc.get_component_by_class(unreal.CapsuleComponent)
    half = 92.0
    if capsule:
        try:
            half = capsule.get_scaled_capsule_half_height()
        except Exception:
            pass
    return npc.get_actor_location().z - half


def assembled_bounds(npc, found):
    """Visible top and bottom of the puppet above the host capsule floor (cm)."""
    floor = _host_floor(npc)
    top = 0.0
    bottom = 1.0e9
    for name in COMPONENTS:
        component = found[name]
        mesh = component.get_skeletal_mesh_asset()
        if mesh is None:
            unreal.log_error("FabAnimeTest: assembled_bounds: %s has no mesh" % name)
            continue
        bounds = _mesh_bounds(mesh)
        transform = component.get_world_transform()
        local_top = unreal.Vector(bounds.origin.x, bounds.origin.y,
                                  bounds.origin.z + bounds.box_extent.z)
        local_bottom = unreal.Vector(bounds.origin.x, bounds.origin.y,
                                     bounds.origin.z - bounds.box_extent.z)
        top = max(top, transform.transform_location(local_top).z - floor)
        bottom = min(bottom, transform.transform_location(local_bottom).z - floor)
    return top, bottom


def check_size_and_parts(npc, avatar, puppet, found, look):
    """Verify requested meshes, host height, feet, leader poses and outline meshes."""
    target = avatar.get_standing_height() if avatar else 170.0
    expected = EXPECTED_MESHES[look]
    for name, expected_mesh in zip(COMPONENTS, expected):
        mesh = found[name].get_skeletal_mesh_asset()
        if mesh is None or mesh.get_name() != expected_mesh:
            actual = mesh.get_name() if mesh else "None"
            return "%s mesh %s, expected %s" % (name, actual, expected_mesh)

    actual_scale = found["CharacterMesh0"].get_editor_property("relative_scale3d").x
    for name in ("Top", "Bottom"):
        scale = found[name].get_editor_property("relative_scale3d").x
        if abs(scale - actual_scale) > 0.005:
            return "%s scale %.3f does not match the head %.3f" % (name, scale, actual_scale)

    # The body garments are separate meshes driven by the pack's abp_Subsegment copy-pose
    # graph; verify their own anim instance is present rather than forcing a leader pose.
    for name in ("Top", "Bottom"):
        if found[name].get_editor_property("anim_class") is None:
            return "%s has no copy-pose AnimBlueprint" % name

    top, bottom = assembled_bounds(npc, found)
    if abs(top - target) > 2.0:
        return "visible height %.1f cm, expected %.1f cm" % (top, target)
    if abs(bottom) > 3.0:
        return "feet at %.1f cm from the host floor" % bottom

    components = puppet.get_components_by_class(unreal.SkeletalMeshComponent)
    for name in COMPONENTS:
        part = found[name]
        outlines = [
            c for c in components
            if c != part and c.get_name().startswith("SkeletalMeshComponent_")
            and (c.get_attach_parent() == part
                 or c.get_editor_property("leader_pose_component") == part)
        ]
        if not outlines:
            return "%s has no outline component" % name
        for outline in outlines:
            mesh = outline.get_skeletal_mesh_asset()
            if mesh is None or mesh.get_name() != part.get_skeletal_mesh_asset().get_name():
                return "%s outline mesh does not match %s" % (name, name)
            leader = outline.get_editor_property("leader_pose_component")
            if leader is None or leader.get_name() != name:
                return "%s outline is not leader-posed to %s" % (name, name)
    return None


def check_movement(puppet, comp):
    movement = puppet.get_component_by_class(unreal.CharacterMovementComponent)
    if movement is None:
        return "puppet has no CharacterMovementComponent"
    mode = movement.get_editor_property("movement_mode")
    if "WALKING" not in str(mode):
        return "movement mode %s is not walking" % mode
    if comp.is_puppet_movement_tick_enabled():
        return "movement component tick is enabled"
    return None


def check_switching(npc_cls, comp_cls, avatar_cls, actors):
    """Look A -> B keeps one puppet with B's meshes; an unknown id keeps the current look."""
    npc = actors.spawn_actor_from_class(npc_cls, unreal.Vector(0, 0, 2000), unreal.Rotator(0, 0, 0))
    if npc is None:
        return "could not spawn the switch-test NPC"
    avatar = npc.get_component_by_class(avatar_cls) if avatar_cls else None
    if avatar:
        avatar.set_editor_property("body_scale", 0.96)
    comp = npc.get_component_by_class(comp_cls)
    if comp is None:
        actors.destroy_actor(npc)
        return "missing Fab component"
    try:
        if not comp.activate_look("fab_male_a"):
            return "could not activate fab_male_a"
        if not comp.activate_look("fab_female_a"):
            return "could not switch to fab_female_a"
        comp.refresh_puppet_look()
        puppets = [a for a in actors.get_all_level_actors()
                   if a != npc and a.get_owner() == npc]
        if len(puppets) != 1:
            return "look switch left %d puppets" % len(puppets)
        found = {c.get_name(): c
                 for c in puppets[0].get_components_by_class(unreal.SkeletalMeshComponent)}
        head = found.get("CharacterMesh0")
        if head is None or head.get_skeletal_mesh_asset() is None:
            return "look switch left no head mesh"
        if head.get_skeletal_mesh_asset().get_name() != EXPECTED_MESHES["fab_female_a"][0]:
            return "look switch kept %s" % head.get_skeletal_mesh_asset().get_name()
        if not comp.activate_look("not_a_look"):
            if not comp.is_look_active():
                return "unknown look destroyed the active look"
        else:
            return "unknown look unexpectedly succeeded"
        return None
    finally:
        if comp:
            comp.deactivate_look()
        actors.destroy_actor(npc)


def main() -> int:
    cls = unreal.load_class(None, BLUEPRINT)
    if cls is None:
        unreal.log_error("FabAnimeTest: FAIL could not load the pack Blueprint")
        return 1
    unreal.log("FabAnimeTest: PASS Blueprint %s" % cls.get_name())

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    npc_cls = unreal.load_class(None, "/Script/DuelAcademyIsland.DAStudentNPC")
    comp_cls = unreal.load_class(None, "/Script/DuelAcademyIsland.DAFabAnimeComponent")
    avatar_cls = unreal.load_class(None, AVATAR_CLASS)
    if world is None or npc_cls is None or comp_cls is None or avatar_cls is None:
        unreal.log_error("FabAnimeTest: FAIL missing world/NPC/component/avatar class")
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
        avatar = npc.get_component_by_class(avatar_cls)
        comp = npc.get_component_by_class(comp_cls)
        if avatar is None or comp is None:
            unreal.log_error("FabAnimeTest: FAIL %s missing avatar/component" % look)
            failures += 1
            actors.destroy_actor(npc)
            continue
        # A deterministic non-default size proves the puppet inherits the host scale.
        avatar.set_editor_property("body_scale", 0.96)
        problem = None
        try:
            if not comp.activate_look(look):
                problem = "activate_look failed"
            else:
                # The pack rebuilds some runtime components during BeginPlay; the
                # component reapplies the look on its first tick / 0.3 s timer.
                comp.refresh_puppet_look()
                if avatar.is_visible():
                    problem = "native avatar is still visible"
                puppets = [a for a in actors.get_all_level_actors()
                           if a != npc and a.get_owner() == npc]
                if len(puppets) != 1:
                    problem = problem or "expected one puppet, found %d" % len(puppets)
                else:
                    found = {c.get_name(): c
                             for c in puppets[0].get_components_by_class(unreal.SkeletalMeshComponent)}
                    missing = [name for name in COMPONENTS
                               if found.get(name) is None
                               or found[name].get_skeletal_mesh_asset() is None]
                    if missing:
                        problem = "missing %s" % ",".join(missing)
                    else:
                        problem = check_size_and_parts(npc, avatar, puppets[0], found, look)
                        problem = problem or check_movement(puppets[0], comp)
                        for name in ("CharacterMesh0", "Top", "Bottom"):
                            if found[name].get_editor_property("anim_class") is None:
                                problem = problem or "%s has no AnimBlueprint" % name
        finally:
            if comp:
                comp.deactivate_look()
            if avatar and not avatar.is_visible():
                problem = problem or "native avatar was not restored"
            actors.destroy_actor(npc)

        if problem:
            unreal.log_error("FabAnimeTest: FAIL %s: %s" % (look, problem))
            failures += 1
        else:
            unreal.log("FabAnimeTest: PASS %s" % look)

    switch_problem = check_switching(npc_cls, comp_cls, avatar_cls, actors)
    if switch_problem:
        unreal.log_error("FabAnimeTest: FAIL look switching: %s" % switch_problem)
        failures += 1
    else:
        unreal.log("FabAnimeTest: PASS look switching")

    if failures:
        unreal.log_error("FabAnimeTest: FAILURES PRESENT (%d)" % failures)
        return 1
    unreal.log("FabAnimeTest: PASS ALL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
