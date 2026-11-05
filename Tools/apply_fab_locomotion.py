"""Install the retargeted Fab locomotion takes into the Unreal project (local-only).

Run with the editor after ``Tools/retarget_fab_anime.py``:

    UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript \
        -script=Tools/apply_fab_locomotion.py -unattended -nosplash -nullrhi

It imports ``Tools/thirdparty/fab_anime/retargeted/<Group>_<State>.fbx`` over the cast's
``A_Anime_<Group>_Idle/Walk/Run`` sequences.  The FBXs are derived from licensed Fab
content, so they are gitignored and never shipped.  Without them the existing gait takes
stay in place and the project behaves exactly as before.
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


def main() -> int:
    if not os.path.isdir(RETARGET_DIR):
        unreal.log("apply_fab_locomotion: no retargeted takes; keeping the gait animations")
        return 0
    info = _load_cast()
    groups = info.get("groups") or {}
    installed = 0
    for group, spec in groups.items():
        mesh_name = spec.get("skeleton_mesh")
        mesh = unreal.load_asset(f"{DEST}/{mesh_name}") if mesh_name else None
        if mesh is None:
            unreal.log_warning(f"apply_fab_locomotion: {group}: missing cast mesh {mesh_name}")
            continue
        skeleton = mesh.get_editor_property("skeleton")
        if skeleton is None:
            unreal.log_warning(f"apply_fab_locomotion: {group}: cast mesh has no skeleton")
            continue
        for state in STATES:
            source = os.path.join(RETARGET_DIR, f"{group}_{state}.fbx")
            if not os.path.isfile(source):
                continue
            name = f"A_Anime_{group}_{state}"
            try:
                _import_animation(source, name, skeleton)
            except Exception as exc:  # noqa: BLE001 - one take must not abort the rest
                unreal.log_error(f"apply_fab_locomotion: {group} {state}: import failed: {exc}")
                continue
            sequence = unreal.load_asset(f"{DEST}/{name}")
            if sequence is None:
                unreal.log_error(f"apply_fab_locomotion: {group} {state}: import produced no sequence")
                continue
            _normalise_bake(sequence)
            installed += 1
            unreal.log(
                f"apply_fab_locomotion: {group} {state}: "
                f"{sequence.get_play_length():.3f}s, {unreal.AnimationLibrary.get_num_frames(sequence)} frames"
            )
    if installed:
        unreal.log(f"apply_fab_locomotion: PASS ({installed} takes)")
    else:
        unreal.log("apply_fab_locomotion: no takes installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
