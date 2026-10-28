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


def set_props(obj, **kwargs):
    """set_editor_property for each kwarg; logs (doesn't raise) on failures."""
    for k, v in kwargs.items():
        try:
            obj.set_editor_property(k, v)
        except Exception as e:  # noqa: BLE001
            warn(f"could not set {type(obj).__name__}.{k}: {e}")


def lc(c, a=1.0):
    return unreal.LinearColor(float(c[0]), float(c[1]), float(c[2]), float(a))


def vec(v):
    return unreal.Vector(float(v[0]), float(v[1]), float(v[2]))


def rot(yaw=0.0, pitch=0.0, roll=0.0):
    return unreal.Rotator(roll=float(roll), pitch=float(pitch), yaw=float(yaw))
