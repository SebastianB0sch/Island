"""Pure VRM / glTF manifest parsing (stdlib-only, no Blender imports).

The lookups in here only read the glTF JSON chunk of a ``.vrm`` / ``.glb`` file,
so they are unit-testable on any machine (the same pattern as
``duel_academy/asset_paths.py``); ``dai.anime.models`` re-exports them for the
Blender-side helpers and pose baking.

A corrupt or truncated GLB must not crash a build, so every consumer of the
parsed document validates its shape (the equivalent of ``_gltf_json``'s
"return something empty on failure" contract).
"""

from __future__ import annotations

import json
import struct


def _gltf_json(path):
    """glTF JSON chunk of a .glb/.vrm file ({} for anything unreadable).

    Guards against a truncated / corrupt header: the signalled chunk length must
    be sane and fully present, and the payload must decode to a JSON object.
    """
    try:
        with open(path, "rb") as fp:
            head = fp.read(20)
            if len(head) < 20 or head[:4] != b"glTF":
                return {}
            n = struct.unpack_from("<I", head, 12)[0]
            if n < 2 or n > 64 * 1024 * 1024:
                return {}
            chunk = fp.read(n)
            if len(chunk) < n:
                return {}
            value = json.loads(chunk)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _node_names(j):
    """(validated) node names of the glTF document."""
    return [nd["name"] for nd in _list(j.get("nodes"))
            if isinstance(nd, dict) and isinstance(nd.get("name"), str) and nd["name"]]


def _node_index(value, names):
    """Index into `names`, or None for an out-of-bounds / non-integer node id."""
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(names):
        return value
    return None


def alpha_modes(path):
    """{material name: OPAQUE | MASK | BLEND} from a .vrm/.glb file ({} for other formats). VRM 0.x keeps the
    MToon render mode (_BlendMode: 0 opaque, 1 cutout, 2/3 transparent) in its own extension."""
    j = _gltf_json(path)
    out = {}
    for m in _list(j.get("materials")):
        if not isinstance(m, dict):
            continue
        name = m.get("name")
        if not isinstance(name, str) or not name:
            continue
        mode = m.get("alphaMode", "OPAQUE")
        out[name] = mode if isinstance(mode, str) and mode else "OPAQUE"
    vrm0 = _dict(_dict(j.get("extensions")).get("VRM"))
    for mp in _list(vrm0.get("materialProperties")):
        if not isinstance(mp, dict) or not isinstance(mp.get("name"), str) or mp["name"] not in out:
            continue
        mode = _dict(mp.get("floatProperties")).get("_BlendMode", 0)
        if isinstance(mode, (int, float)) and not isinstance(mode, bool) and mode >= 1:
            out[mp["name"]] = "MASK" if mode == 1 else "BLEND"
    return out


def read_vrm(path):
    """(version 0 | 1 | None, {humanBone: node name}) from a .vrm/.glb file.

    Returns ``None, {}`` for other formats / corrupt files; entries whose node
    id is out of bounds or whose bone name is missing are dropped instead of
    raising IndexError / KeyError on the rigged model's manifest.
    """
    j = _gltf_json(path)
    if not j:
        return None, {}
    names = _node_names(j)
    ext = _dict(j.get("extensions"))
    if "VRMC_vrm" in ext:
        human_bones = _dict(_dict(_dict(ext.get("VRMC_vrm")).get("humanoid")).get("humanBones"))
        human = {}
        for bone, spec in human_bones.items():
            node = _node_index(spec.get("node"), names) if isinstance(spec, dict) else None
            if node is not None:
                human[str(bone)] = names[node]
        return 1, human
    if "VRM" in ext:
        human_bones = _dict(_dict(ext.get("VRM")).get("humanoid")).get("humanBones")
        human = {}
        for bone_spec in _list(human_bones):
            if not isinstance(bone_spec, dict):
                continue
            node = _node_index(bone_spec.get("node"), names)
            bone = bone_spec.get("bone")
            if node is not None and isinstance(bone, str) and bone:
                human[bone] = names[node]
        return 0, human
    return None, {}


def target_names(path):
    """{mesh name: [blendshape name per glTF morph target]} (VRoid keeps them in the mesh extras).

    Names that are not a non-empty list of strings are ignored; malformed
    primitives / extras no longer raise IndexError / Key/Type errors.
    """
    j = _gltf_json(path)
    out = {}
    for m in _list(j.get("meshes")):
        if not isinstance(m, dict):
            continue
        names = _dict(m.get("extras")).get("targetNames")
        if not isinstance(names, list):
            primitives = _list(m.get("primitives"))
            first = _dict(primitives[0]) if primitives else {}
            names = _dict(first.get("extras")).get("targetNames")
        if isinstance(names, list) and names and all(isinstance(n, str) for n in names):
            name = m.get("name")
            out[(name if isinstance(name, str) else "").split(".")[0]] = names
    return out
