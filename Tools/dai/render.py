"""
Whole-island preview renders (Cycles, CPU) assembled from the exported data:
terrain + water + every placed location mesh + all scattered instances
(Geometry-Nodes point instancing), lit by a sky + sun.

    python Tools/build_island.py render
"""

import json
import math
import os

import bpy
import numpy as np
from mathutils import Vector

from . import blend
from . import config as C
from . import terrain_mesh
from .assets import load_placements
from .assets import props as P


def _from_ue(loc):
    return (loc[0] / 100.0, -loc[1] / 100.0, loc[2] / 100.0)


def _instance_object(name, proto, items):
    """Mesh of points (one per instance) + GN 'instance on points' using `proto`."""
    pts = np.array([[it[0] / 100.0, -it[1] / 100.0, it[2] / 100.0] for it in items], np.float32)
    rot = np.array([[0.0, 0.0, math.radians(-it[3])] for it in items], np.float32)
    scl = np.array([[it[4]] * 3 for it in items], np.float32)
    me = bpy.data.meshes.new(name + "_pts")
    me.vertices.add(len(pts))
    me.vertices.foreach_set("co", pts.ravel())
    a_rot = me.attributes.new("inst_rot", "FLOAT_VECTOR", "POINT")
    a_rot.data.foreach_set("vector", rot.ravel())
    a_scl = me.attributes.new("inst_scale", "FLOAT_VECTOR", "POINT")
    a_scl.data.foreach_set("vector", scl.ravel())
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new("inst", "NODES")
    ng = bpy.data.node_groups.new(name + "_gn", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gin = ng.nodes.new("NodeGroupInput")
    gout = ng.nodes.new("NodeGroupOutput")
    iop = ng.nodes.new("GeometryNodeInstanceOnPoints")
    oi = ng.nodes.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = proto
    oi.inputs["As Instance"].default_value = True
    ar = ng.nodes.new("GeometryNodeInputNamedAttribute")
    ar.data_type = "FLOAT_VECTOR"
    ar.inputs["Name"].default_value = "inst_rot"
    asc = ng.nodes.new("GeometryNodeInputNamedAttribute")
    asc.data_type = "FLOAT_VECTOR"
    asc.inputs["Name"].default_value = "inst_scale"
    ng.links.new(gin.outputs[0], iop.inputs["Points"])
    ng.links.new(oi.outputs["Geometry"], iop.inputs["Instance"])
    ng.links.new(ar.outputs["Attribute"], iop.inputs["Rotation"])
    ng.links.new(asc.outputs["Attribute"], iop.inputs["Scale"])
    ng.links.new(iop.outputs["Instances"], gout.inputs[0])
    mod.node_group = ng
    return ob


def build_scene(log=print, scatter=True, detail_props=True):
    blend.reset_scene()
    with open(os.path.join(C.OUT_DATA, "layout.json")) as fp:
        lay = json.load(fp)
    h = np.load(os.path.join(C.CACHE_DIR, "height.npy"))
    # terrain with baked colour map
    t = terrain_mesh.build_preview_terrain(h, quads=1008)
    mat = blend.material("M_Terrain")
    nt = mat.node_tree
    img = bpy.data.images.load(os.path.join(C.OUT_TEXTURES, "T_TerrainColor.png"))
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs[0], nt.nodes["Principled BSDF"].inputs["Base Color"])
    terrain_mesh.build_water(h, export=False, log=lambda *_: None)
    for wname in ("M_Ocean", "M_LakeWater"):
        m = blend.material(wname)
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Alpha"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.08
    # location meshes, rebuilt from the AssetSets (identical geometry to the FBX exports)
    placements = load_placements(log)
    static_by_mesh = {}
    for s in lay["static"]:
        static_by_mesh.setdefault(s["mesh"], []).append(s)
    floating_by_mesh = {}
    for f in lay["floating"]:
        floating_by_mesh.setdefault(f["mesh"], []).append(f)
    n = 0
    for key, fn in placements.items():
        if key not in C.LOCATIONS:
            continue
        aset = fn()
        for name, mb in aset.meshes.items():
            if not mb.verts:
                continue
            nm = "SM_" + name
            entries = static_by_mesh.get(nm, []) + floating_by_mesh.get(nm, [])
            if not entries:
                continue
            ob = mb.build(nm)
            for i, e in enumerate(entries):
                o = ob if i == 0 else bpy.data.objects.new(nm, ob.data)
                if i:
                    bpy.context.scene.collection.objects.link(o)
                o.location = _from_ue(e["loc"])
                o.rotation_euler = (0, 0, math.radians(-e["yaw"]))
                n += 1
    log(f"  preview: {n} location meshes")
    # roads (world-space FBX)
    for e in lay["static"]:
        if e["folder"] == "Roads":
            path = os.path.join(C.OUT_MESHES, "Roads", e["mesh"] + ".fbx")
            if os.path.exists(path):
                bpy.ops.import_scene.fbx(filepath=path)
    # instances
    protos = {}
    hidden = bpy.data.collections.new("Protos")
    bpy.context.scene.collection.children.link(hidden)
    hidden.hide_render = True
    for asset, g in lay["instances"].items():
        if not scatter and asset not in ("SM_LampPost",):
            continue
        if asset not in P.REGISTRY:
            continue
        mb, _ = P.get(asset)
        proto = mb.build(asset + "_proto", collection=hidden)
        protos[asset] = proto
        _instance_object(asset + "_inst", proto, g["items"])
    for f in lay["floating"]:
        if f["mesh"] in P.REGISTRY:
            if f["mesh"] not in protos:
                mb, _ = P.get(f["mesh"])
                protos[f["mesh"]] = mb.build(f["mesh"] + "_proto", collection=hidden)
            o = bpy.data.objects.new(f["mesh"], protos[f["mesh"]].data)
            bpy.context.scene.collection.objects.link(o)
            o.location = _from_ue(f["loc"])
            o.rotation_euler = (0, 0, math.radians(-f["yaw"]))
    log(f"  preview: {sum(len(g['items']) for g in lay['instances'].values())} instances")
    return lay


SHOTS = {
    # name: (camera location, target, lens)
    "aerial":        ((-1650.0, -2350.0, 1350.0), (60.0, 120.0, 40.0), 32),
    "harbor":        ((330.0, -1650.0, 70.0), (0.0, -700.0, 60.0), 30),
    "academy":       ((-35.0, -130.0, 52.0), (0.0, 150.0, 48.0), 22),
    "slifer":        ((-1235.0, -330.0, 38.0), (-1065.0, -262.0, 34.0), 30),
    "lake_volcano":  ((-120.0, 640.0, 60.0), (520.0, 760.0, 120.0), 24),
    "obelisk":       ((-450.0, 360.0, 60.0), (-600.0, 520.0, 45.0), 28),
    "map":           ((0.0, 0.0, 6000.0), (0.0, 0.01, 0.0), 50),
}


def render_island(log=print, shots=None, res=(1600, 900), samples=40):
    os.makedirs(C.RENDER_DIR, exist_ok=True)
    build_scene(log)
    blend.setup_world(sun_elev=28.0, sun_azim=235.0, strength=1.0, sun_strength=4.5)
    blend.setup_render(res, samples)
    bpy.context.scene.cycles.max_bounces = 3
    try:
        bpy.context.scene.render.use_persistent_data = True
    except Exception:
        pass
    for name, (loc, tgt, lens) in SHOTS.items():
        if shots and name not in shots:
            continue
        cam = blend.camera("Cam_" + name, loc, tgt, lens=lens, clip_end=30000.0)
        if name == "map":
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = C.WORLD_SIZE * 0.92
            cam.rotation_euler = (0, 0, 0)
            bpy.context.scene.render.resolution_x = 1400
            bpy.context.scene.render.resolution_y = 1400
        else:
            bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = res
        sc = bpy.context.scene
        sc.render.image_settings.file_format = "JPEG"
        sc.render.image_settings.quality = 90
        path = os.path.join(C.RENDER_DIR, f"{name}.jpg")
        blend.render(cam, path)
        log(f"  render -> {path}")
