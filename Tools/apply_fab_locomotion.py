"""Install the retargeted Fab locomotion takes into the Unreal project (local-only).

Run with the editor after ``Tools/retarget_fab_anime.py``:

    UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript \
        -script=Tools/apply_fab_locomotion.py -unattended -nosplash -nullrhi

It imports ``Tools/thirdparty/fab_anime/retargeted/<Group>_<State>.fbx`` over the cast's
``A_Anime_<Group>_Idle/Walk/Run`` sequences.  Each group is imported into temporary
assets, normalised and then swapped in as a set (backup/rollback), so a failed take
never leaves one Fab state beside two gait states.  The FBXs are derived from licensed
Fab content, so they are gitignored and never shipped.  Without them the existing gait
takes stay in place and the project behaves exactly as before.

This module is also called by ``duel_academy.importer.import_cast`` after a full cast
rebuild, so a local install of the retargeted takes survives that rebuild.
"""

from __future__ import annotations

import json
import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RETARGET_DIR = os.path.join(REPO, "Tools", "thirdparty", "fab_anime", "retargeted")
CAST_JSON = os.path.join(REPO, "DuelAcademyIsland", "SourceAssets", "Data", "cast.json")
DEST = "/Game/DuelAcademy/Characters"
STATES = ("Idle", "Walk", "Run")


def _load_cast():
    with open(CAST_JSON, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _import_animation(source, name, skeleton):
    pipe = unreal.new_object(unreal.InterchangeGenericAssetsPipeline)
    common = pipe.get_editor_property("common_skeletal_meshes_and_animations_properties")
    common.set_editor_property("skeleton", skeleton)
    common.set_editor_property("import_only_animations", True)
    common.set_editor_property("try_auto_select_skeleton", False)
    animation = pipe.get_editor_property("animation_pipeline")
    animation.set_editor_property("import_animations", True)
    animation.set_editor_property("import_bone_tracks", True)
    override = unreal.new_object(unreal.InterchangePipelineStackOverride)
    override.add_pipeline(pipe)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", source)
    task.set_editor_property("destination_path", DEST)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("options", override)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])


def _normalise_bake(sequence):
    """The cast skeleton is authored in metres but imported with a 100x root scale.

    The FBX bake's pelvis track comes in at that 100x unit; pull the pelvis back to the
    skeleton's metre convention and clear the baked scale so the root's 100x is the only
    unit conversion left.  Everything below the pelvis then lines up with the mesh.
    """
    count = unreal.AnimationLibrary.get_num_frames(sequence)
    positions, rotations, scales = [], [], []
    for index in range(count):
        transform = unreal.AnimationLibrary.get_bone_pose_for_frame(sequence, "pelvis", index, False)
        positions.append(unreal.Vector(
            transform.translation.x / 100.0,
            transform.translation.y / 100.0,
            transform.translation.z / 100.0,
        ))
        rotations.append(transform.rotation)
        scales.append(unreal.Vector(1.0, 1.0, 1.0))
    controller = sequence.controller
    controller.open_bracket("normalise Fab pelvis")
    controller.set_bone_track_keys("pelvis", positions, rotations, scales)
    controller.close_bracket()
    unreal.EditorAssetLibrary.save_loaded_asset(sequence)


def _delete_asset(path):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)


def _import_temp(source, name, skeleton):
    """Import one take under a temporary name and normalise it before touching the target."""
    temp_name = f"{name}__DAFabNew"
    _delete_asset(f"{DEST}/{temp_name}")
    _import_animation(source, temp_name, skeleton)
    sequence = unreal.load_asset(f"{DEST}/{temp_name}")
    if sequence is None:
        raise RuntimeError("import produced no temporary sequence")
    _normalise_bake(sequence)
    return temp_name, sequence


def _replace_with_temp(temp_name, target_name):
    """Back up the target, rename the prepared temp over it, and restore on failure."""
    temp_path = f"{DEST}/{temp_name}"
    target_path = f"{DEST}/{target_name}"
    backup_name = f"{target_name}__DAFabOld"
    backup_path = f"{DEST}/{backup_name}"
    _delete_asset(backup_path)
    had_target = unreal.EditorAssetLibrary.does_asset_exist(target_path)
    if had_target and not unreal.EditorAssetLibrary.rename_asset(target_path, backup_path):
        _delete_asset(temp_path)
        raise RuntimeError("could not back up the existing take")
    if not unreal.EditorAssetLibrary.rename_asset(temp_path, target_path):
        if had_target:
            unreal.EditorAssetLibrary.rename_asset(backup_path, target_path)
        _delete_asset(temp_path)
        raise RuntimeError("could not install the prepared take")
    # Keep the backup until the whole group has been replaced successfully.
    return unreal.load_asset(target_path)


def _rollback_replaced(replaced):
    """Restore every target a group-level replacement already overwrote."""
    for target_name, backup_name in replaced:
        target_path = f"{DEST}/{target_name}"
        backup_path = f"{DEST}/{backup_name}"
        _delete_asset(target_path)
        if unreal.EditorAssetLibrary.does_asset_exist(backup_path):
            unreal.EditorAssetLibrary.rename_asset(backup_path, target_path)


def main() -> int:
    if not os.path.isdir(RETARGET_DIR):
        unreal.log("apply_fab_locomotion: no retargeted takes; keeping the gait animations")
        return 0
    info = _load_cast()
    groups = info.get("groups") or {}
    installed = 0
    failures = 0
    for group, spec in groups.items():
        mesh_name = spec.get("skeleton_mesh")
        mesh = unreal.load_asset(f"{DEST}/{mesh_name}") if mesh_name else None
        if mesh is None:
            unreal.log_warning(f"apply_fab_locomotion: {group}: missing cast mesh {mesh_name}")
            failures += 1
            continue
        skeleton = mesh.get_editor_property("skeleton")
        if skeleton is None:
            unreal.log_warning(f"apply_fab_locomotion: {group}: cast mesh has no skeleton")
            failures += 1
            continue
        # Never mix one Fab state with two gait states: a partial local retarget set
        # would make the Walk/Run speed table and the SetupCast detection disagree.
        missing = [state for state in STATES
                   if not os.path.isfile(os.path.join(RETARGET_DIR, f"{group}_{state}.fbx"))]
        if missing:
            unreal.log_warning(
                f"apply_fab_locomotion: {group}: incomplete retarget set (missing "
                f"{', '.join(missing)}); keeping the gait takes for this group")
            failures += 1
            continue

        # Prepare all three takes before replacing any, so a failed group never leaves
        # one Fab state beside two gait states.
        prepared = []
        try:
            for state in STATES:
                source = os.path.join(RETARGET_DIR, f"{group}_{state}.fbx")
                target_name = f"A_Anime_{group}_{state}"
                temp_name, sequence = _import_temp(source, target_name, skeleton)
                prepared.append((state, temp_name, target_name, sequence))
        except Exception as exc:  # noqa: BLE001 - keep the gait set for this group
            unreal.log_error(f"apply_fab_locomotion: {group}: preparing takes failed: {exc}")
            for _state, temp_name, _target, _sequence in prepared:
                _delete_asset(f"{DEST}/{temp_name}")
            failures += 1
            continue

        replaced = []
        try:
            for state, temp_name, target_name, _sequence in prepared:
                backup_name = f"{target_name}__DAFabOld"
                sequence = _replace_with_temp(temp_name, target_name)
                replaced.append((target_name, backup_name))
                if sequence is None:
                    raise RuntimeError(f"{target_name}: replacement produced no sequence")
                installed += 1
                unreal.log(
                    f"apply_fab_locomotion: {group} {state}: "
                    f"{sequence.get_play_length():.3f}s, "
                    f"{unreal.AnimationLibrary.get_num_frames(sequence)} frames"
                )
            for _target_name, backup_name in replaced:
                _delete_asset(f"{DEST}/{backup_name}")
        except Exception as exc:  # noqa: BLE001 - restore the whole group
            unreal.log_error(f"apply_fab_locomotion: {group}: installing takes failed: {exc}")
            _rollback_replaced(replaced)
            installed = max(0, installed - len(replaced))
            for _state, temp_name, _target, _sequence in prepared:
                _delete_asset(f"{DEST}/{temp_name}")
            failures += 1
            continue

    if installed:
        unreal.log(f"apply_fab_locomotion: PASS ({installed} takes)")
    else:
        unreal.log("apply_fab_locomotion: no takes installed")
    if failures:
        unreal.log_error(f"apply_fab_locomotion: FAILURES PRESENT ({failures} group(s))")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
