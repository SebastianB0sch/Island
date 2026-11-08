"""Headless regression check for the optional native-cast Fab locomotion retarget.

Run with the editor:
    UnrealEditor-Cmd DuelAcademyIsland/DuelAcademyIsland.uproject -run=pythonscript -script=Tools/test_fab_locomotion.py -unattended -nosplash -nullrhi

The retargeted takes are local-only (``Tools/thirdparty/fab_anime/retargeted`` is
gitignored).  Without that folder a fresh checkout keeps the procedural gait clips and
this check skips.  Otherwise it verifies every cast group's ``A_Anime_<Group>_Idle/Walk/Run``
sequence: it exists on the group's cast skeleton, has the expected play length, the
Walk/Run pair has the expected long-walk/short-run lengths (the
``UDAAvatarComponent::SetupCast`` Fab detection), and its pelvis track stays in the
skeleton's metre convention after the /100 import normalisation.
"""

import json
import math
import os

import unreal

DEST = "/Game/DuelAcademy/Characters"
TAG = "FabLocomotionTest"
STATES = {
    "Idle": (4.5, 5.5),
    "Walk": (1.05, 1.30),
    "Run": (0.55, 0.75),
}
PELVIS_LIMIT = 2.0


def _repo_root():
    """The project lives one level below the repository root."""
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.dirname(os.path.normpath(project))


def _load_groups(repo):
    path = os.path.join(repo, "DuelAcademyIsland", "SourceAssets", "Data", "cast.json")
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp).get("groups") or {}


def _skeleton(asset):
    try:
        return asset.get_editor_property("skeleton")
    except Exception:  # noqa: BLE001 - older/property-less assets
        return None


def check_pelvis(sequence):
    """Sample the pelvis track and verify the metre-scale bake (see apply_fab_locomotion)."""
    count = unreal.AnimationLibrary.get_num_frames(sequence)
    if count <= 0:
        return "has no animation frames"
    largest = 0.0
    for frame in sorted({0, count // 2, count - 1}):
        try:
            pose = unreal.AnimationLibrary.get_bone_pose_for_frame(sequence, "pelvis", frame, False)
        except Exception as exc:  # noqa: BLE001 - a missing track must fail the check
            return "pelvis sample at frame %d failed: %s" % (frame, exc)
        values = (pose.translation.x, pose.translation.y, pose.translation.z)
        if not all(math.isfinite(value) for value in values):
            return "pelvis at frame %d is not finite: %s" % (frame, values)
        if any(abs(value) > PELVIS_LIMIT for value in values):
            return "pelvis at frame %d is outside the metre range: %s" % (frame, values)
        largest = max(largest, max(abs(value) for value in values))
    if largest < 0.1:
        return "pelvis track is empty or stuck at the origin (max %.3f m)" % largest
    return None


def main() -> int:
    repo = _repo_root()
    retarget_dir = os.path.join(repo, "Tools", "thirdparty", "fab_anime", "retargeted")
    if not os.path.isdir(retarget_dir):
        unreal.log("%s: SKIP (no local retargeted takes)" % TAG)
        return 0
    try:
        groups = _load_groups(repo)
    except Exception as exc:  # noqa: BLE001 - a broken manifest is a real failure here
        unreal.log_error("%s: FAIL could not read cast.json: %s" % (TAG, exc))
        return 1

    failures = 0
    for group, spec in groups.items():
        mesh_name = spec.get("skeleton_mesh")
        mesh = unreal.load_asset("%s/%s" % (DEST, mesh_name)) if mesh_name else None
        if mesh is None:
            unreal.log_error("%s: FAIL %s: missing cast mesh %s" % (TAG, group, mesh_name))
            failures += 1
            continue
        mesh_skeleton = _skeleton(mesh)
        if mesh_skeleton is None:
            unreal.log_error("%s: FAIL %s: cast mesh %s has no skeleton" % (TAG, group, mesh_name))
            failures += 1
            continue

        problems = []
        summary = []
        for state, (low, high) in STATES.items():
            name = "A_Anime_%s_%s" % (group, state)
            sequence = unreal.load_asset("%s/%s" % (DEST, name))
            if sequence is None:
                problems.append("%s is missing" % name)
                continue
            if not isinstance(sequence, unreal.AnimSequence):
                problems.append("%s is not an AnimSequence (%s)" % (
                    name, sequence.get_class().get_name()))
                continue
            skeleton = _skeleton(sequence)
            if skeleton is None or skeleton.get_path_name() != mesh_skeleton.get_path_name():
                actual = skeleton.get_path_name() if skeleton else "none"
                problems.append("%s skeleton %s does not match %s" % (
                    name, actual, mesh_skeleton.get_path_name()))
                continue
            length = sequence.get_play_length()
            summary.append("%s %.3fs" % (state, length))
            if not low <= length <= high:
                problems.append("%s length %.3f s outside %.2f-%.2f s" % (
                    name, length, low, high))
            if state == "Walk" and length <= 1.05:
                problems.append(
                    "%s length %.3f s does not trigger the SetupCast Fab detection (> 1.05 s)"
                    % (name, length))
            if state == "Run" and length >= 0.68:
                problems.append(
                    "%s length %.3f s does not trigger the SetupCast Fab detection (< 0.68 s)"
                    % (name, length))
            problem = check_pelvis(sequence)
            if problem:
                problems.append("%s %s" % (name, problem))

        if problems:
            for problem in problems:
                unreal.log_error("%s: FAIL %s: %s" % (TAG, group, problem))
            failures += 1
        else:
            unreal.log("%s: PASS %s -> %s" % (TAG, group, ", ".join(summary)))

    if failures:
        unreal.log_error("%s: FAILURES PRESENT (%d)" % (TAG, failures))
        return 1
    unreal.log("%s: PASS ALL" % TAG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
