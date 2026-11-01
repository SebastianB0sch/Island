"""Shared paths / helpers for the Duel Academy Island editor build scripts."""

import json
import os

import unreal

ROOT = "/Game/DuelAcademy"
MAT_DIR = ROOT + "/Materials"
TEX_DIR = ROOT + "/Textures"
MESH_DIR = ROOT + "/Meshes"
AUDIO_DIR = ROOT + "/Audio"
MAP_PATH = ROOT + "/Maps/DuelAcademyIsland"
GENERATED_TAG = "DA_Generated"

# Gameplay constants shared by the editor scripts and the C++ module - keep in
# sync on both sides (the Blender side's mirror is Tools/dai/config.py).
# cm/s the Walk / Run clips cover at play rate 1 after import (UDAAvatarComponent)
REF_SPEED = {"Walk": 300.0, "Run": 600.0}
# Island edge length in metres: Tools/dai/config.py WORLD_SIZE, used as the
# terrain-UV scale fallback when layout.json is not (re)built
WORLD_SIZE_M = 3072.0


def project_dir():
    return os.path.abspath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def source_dir():
    return os.path.join(project_dir(), "SourceAssets")


def data_path(name):
    return os.path.join(source_dir(), "Data", name)


def load_json(name):
    with open(data_path(name), "r", encoding="utf-8") as fp:
        return json.load(fp)


def log(msg):
    unreal.log(f"[DuelAcademy] {msg}")


def warn(msg):
    unreal.log_warning(f"[DuelAcademy] {msg}")


def error(msg):
    unreal.log_error(f"[DuelAcademy] {msg}")


def asset_tools():
    return unreal.AssetToolsHelpers.get_asset_tools()


def eal():
    return unreal.EditorAssetLibrary


def exists(path):
    return unreal.EditorAssetLibrary.does_asset_exist(path)


def load(path):
    if not path:
        return None
    if exists(path):
        return unreal.EditorAssetLibrary.load_asset(path)
    return None


def ensure_dir(path):
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def native_class(name):
    """C++ classes from the DuelAcademyIsland module (None if the module isn't compiled)."""
    cls = getattr(unreal, name, None)
    if cls is None:
        try:
            cls = unreal.load_class(None, f"/Script/DuelAcademyIsland.{name}")
        except Exception:
            cls = None
    return cls


def set_props(obj, strict=False, **kwargs):
    """set_editor_property for each kwarg.

    Failures are logged by default.  With ``strict=True`` the failure is logged -
    and then re-raised: use it for gameplay-relevant properties where
    silently keeping the engine default yields a broken actor (manager wiring,
    collider / import flags), rather than decoration.
    """
    for k, v in kwargs.items():
        try:
            obj.set_editor_property(k, v)
        except Exception as e:  # noqa: BLE001
            warn(f"could not set {type(obj).__name__}.{k}: {e}")
            if strict:
                raise RuntimeError(f"{type(obj).__name__}: could not set property {k} "
                                   f"({v!r}): {e}") from e


def lc(c, a=1.0):
    return unreal.LinearColor(float(c[0]), float(c[1]), float(c[2]), float(a))


def vec(v):
    return unreal.Vector(float(v[0]), float(v[1]), float(v[2]))


def rot(yaw=0.0, pitch=0.0, roll=0.0):
    return unreal.Rotator(roll=float(roll), pitch=float(pitch), yaw=float(yaw))
