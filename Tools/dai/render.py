"""
Whole-island preview renders (Cycles, CPU) assembled from the exported data:
terrain + water + every placed location mesh + all scattered instances
(Geometry-Nodes point instancing), lit by a sky + sun.

    python Tools/build_island.py render
"""

import math
import os

import bpy
import numpy as np
from mathutils import Vector

from . import blend
from . import config as C
from . import jsonio, terrain_mesh
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


# same layer -> splat channel mapping as the Unreal terrain material (materials.TERRAIN_LAYERS)
TERRAIN_SPLAT = [("Grass", None), ("ForestFloor", ("B", 1)), ("Sand", ("A", 0)), ("WetSand", ("B", 2)),
                 ("Ash", ("B", 0)), ("Rock", ("A", 1)), ("Dirt", ("A", 2)), ("Paving", ("A", 3))]


# (height influence, softness) per layer: materials.LAYER_BLEND / BLEND_NOISE of the Unreal terrain material
LAYER_BLEND = {"ForestFloor": (0.6, 0.7), "Sand": (0.5, 0.9), "WetSand": (0.4, 1.0), "Ash": (0.5, 0.8),
               "Rock": (0.7, 0.5), "Dirt": (0.6, 0.6), "Paving": (0.3, 0.35)}
BLEND_NOISE = 0.5


def _terrain_material(mat, road=False):
    """Preview version of M_DA_Terrain: photo layers chosen by the splat maps and blended by height, fading
    to the baked colour map with camera distance (avoids tiling / moire in the aerial shots).
    road=True: M_DA_Road - the same surface looked up by world position, with the Paving layer laid over it
    by the mesh's vertex colour (road ribbons, paved bridge decks)."""
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = os.path.join(C.OUT_TEXTURES, "{}")
    info = jsonio.read_json(os.path.join(C.OUT_DATA, "terrain_layers.json"))
    if road:
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Location"].default_value = (0.5, 0.5, 0.0)
        mp.inputs["Scale"].default_value = (1.0 / C.WORLD_SIZE, 1.0 / C.WORLD_SIZE, 0.0)
        nt.links.new(geo.outputs["Position"], mp.inputs["Vector"])
        uv_out = mp.outputs["Vector"]
    else:
        uv_out = nt.nodes.new("ShaderNodeUVMap").outputs["UV"]

    def image(name, vector, colour=True, alpha=False):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(tex.format(name), check_existing=True)
        if not colour:
            n.image.colorspace_settings.name = "Non-Color"
        if alpha:
            n.image.alpha_mode = "CHANNEL_PACKED"
        nt.links.new(vector, n.inputs["Vector"])
        return n

    def scaled(tiles):
        m = nt.nodes.new("ShaderNodeVectorMath")
        m.operation = "SCALE"
        nt.links.new(uv_out, m.inputs[0])
        m.inputs["Scale"].default_value = tiles
        return m.outputs[0]

    def mix(a, b, fac, kind="RGBA"):
        m = nt.nodes.new("ShaderNodeMix")
        m.data_type = kind
        nt.links.new(fac, m.inputs["Factor"])
        nt.links.new(a, m.inputs[6 if kind == "RGBA" else 0])
        nt.links.new(b, m.inputs[7 if kind == "RGBA" else 1])
        return m.outputs[2 if kind == "RGBA" else 0]

    def calc(op, a, b=None, clamp=False):
        m = nt.nodes.new("ShaderNodeMath")
        m.operation = op
        m.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                nt.links.new(v, m.inputs[i])
        return m.outputs[0]

    def red(colour):
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(colour, sep.inputs[0])
        return sep.outputs[0]

    fray = calc("ADD", calc("MULTIPLY", red(image("T_Noise.png", scaled(C.WORLD_SIZE / 7.0), colour=False).outputs["Color"]), 0.6),
                calc("MULTIPLY", red(image("T_Noise.png", scaled(C.WORLD_SIZE / 2.6), colour=False).outputs["Color"]), 0.4))

    def height_blend(weight, h, below, layer):
        """materials._height_blend: saturate((2 w - 1 + (h - below) k) / s + 0.5), w frayed by noise."""
        k, soft = LAYER_BLEND[layer]
        soft = min(soft, 2.0 * (1.0 - k))
        bell = calc("MULTIPLY", calc("MULTIPLY", weight, calc("SUBTRACT", 1.0, weight)), 4.0 * BLEND_NOISE)
        w = calc("ADD", weight, calc("MULTIPLY", calc("SUBTRACT", fray, 0.5), bell), clamp=True)
        x = calc("ADD", calc("SUBTRACT", calc("MULTIPLY", w, 2.0), 1.0), calc("MULTIPLY", calc("SUBTRACT", h, below), k))
        return calc("ADD", calc("DIVIDE", x, soft), 0.5, clamp=True)

    splat = {}
    for key, fname in (("A", "T_TerrainSplatA.png"), ("B", "T_TerrainSplatB.png")):
        img = image(fname, uv_out, colour=False, alpha=True)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(img.outputs["Color"], sep.inputs[0])
        splat[key] = [sep.outputs[0], sep.outputs[1], sep.outputs[2], img.outputs["Alpha"]]
    color = normal = rough = height = None
    paving = None
    for layer, ch in TERRAIN_SPLAT:
        vec = scaled(C.WORLD_SIZE / info.get(layer, {}).get("tile_m", 4.0))
        c = image(f"T_Terrain_{layer}_BC.jpg", vec).outputs["Color"]
        n = image(f"T_Terrain_{layer}_N.png", vec, colour=False).outputs["Color"]
        r = image(f"T_Terrain_{layer}_R.png", vec, colour=False).outputs["Color"]
        h = red(image(f"T_Terrain_{layer}_H.png", vec, colour=False).outputs["Color"])
        if layer == "Paving":
            paving = (c, n, r, h)
        if ch is None:
            color, normal, rough, height = c, n, r, h
            continue
        fac = height_blend(splat[ch[0]][ch[1]], h, height, layer)
        color, normal, rough = mix(color, c, fac), mix(normal, n, fac), mix(rough, r, fac)
        height = mix(height, h, fac, "FLOAT")
    if road:
        c, n, r, h = paving
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        fac = height_blend(red(vc.outputs["Color"]), h, height, "Paving")
        color, normal, rough = mix(color, c, fac), mix(normal, n, fac), mix(rough, r, fac)
    # far blend to the colour map
    cam = nt.nodes.new("ShaderNodeCameraData")
    far = nt.nodes.new("ShaderNodeMapRange")
    far.inputs["From Min"].default_value = 150.0
    far.inputs["From Max"].default_value = 900.0
    far.inputs["To Max"].default_value = 0.85
    nt.links.new(cam.outputs["View Distance"], far.inputs["Value"])
    macro = image("T_TerrainColor.png", uv_out).outputs["Color"]
    nt.links.new(mix(color, macro, far.outputs[0]), bsdf.inputs["Base Color"])
    rm = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(rough, rm.inputs[0])
    nt.links.new(rm.outputs[0], bsdf.inputs["Roughness"])
    # the layer normals are DirectX (green down) for Unreal - flip green back for Blender
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(normal, sep.inputs[0])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(sep.outputs[1], inv.inputs[1])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(sep.outputs[0], comb.inputs[0])
    nt.links.new(inv.outputs[0], comb.inputs[1])
    nt.links.new(sep.outputs[2], comb.inputs[2])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.8
    nt.links.new(comb.outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])


def build_scene(log=print, scatter=True, detail_props=True):
    blend.reset_scene()
    lay = jsonio.read_json(os.path.join(C.OUT_DATA, "layout.json"))
    h = np.load(os.path.join(C.CACHE_DIR, "height.npy"))
    # terrain with baked colour map
    t = terrain_mesh.build_preview_terrain(h, quads=1008)
    _terrain_material(blend.material("M_Terrain"))
    _terrain_material(blend.material("M_RoadPaving"), road=True)
    terrain_mesh.build_water(h, export=False, log=lambda *_: None)
    for wname in ("M_Ocean", "M_LakeWater", "M_River"):
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
    for sp in lay.get("specials", []):          # turning meshes (water wheels) stand still in a preview
        if sp["kind"] == "spinner":
            floating_by_mesh.setdefault(sp["props"]["mesh"], []).append(sp)
    n = 0
    for key, fn in placements.items():
        if key not in C.LOCATIONS:
            continue
        aset = fn()
        placed = None
        from .layout import split_translucent
        floating = {s["props"].get("mesh") for s in aset.sockets if s["type"] in ("floating", "spinner")}
        for name, mb in split_translucent(aset.meshes, skip=floating).items():
            if not mb.verts:
                continue
            nm = "SM_" + name
            entries = static_by_mesh.get(nm, []) + floating_by_mesh.get(nm, [])
            if entries and nm in static_by_mesh and placed is None:
                placed = static_by_mesh[nm][0]
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
        if placed is not None:     # closed door leaves (ADADoor in Unreal)
            from .assets import doors as DR
            for o in DR.preview_objects(aset, open_deg=0.0):
                o.location = _from_ue(placed["loc"])
                o.rotation_euler = (0, 0, math.radians(-placed["yaw"]))
    log(f"  preview: {n} location meshes")
    # roads, bridges and waterside dressing (world-space FBX)
    for e in lay["static"]:
        if e["folder"] == "Roads" or e.get("group") == "waterside":
            path = os.path.join(C.OUT_MESHES, e["folder"], e["mesh"] + ".fbx")
            if os.path.exists(path):
                bpy.ops.import_scene.fbx(filepath=path)
    # the road material on everything that carries it (an imported FBX brings its own copy of each material);
    # a mesh without vertex colours is paved all over, as in Unreal
    road_mat = bpy.data.materials["M_RoadPaving"]
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        for slot in ob.material_slots:
            if slot.material is not None and slot.material.name.split(".")[0] == "M_RoadPaving":
                slot.material = road_mat
                if "Col" not in ob.data.color_attributes:
                    layer = ob.data.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
                    for d in layer.data:
                        d.color = (1.0, 1.0, 1.0, 1.0)
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
        proto = P.build_object(asset, asset + "_proto", collection=hidden)
        protos[asset] = proto
        _instance_object(asset + "_inst", proto, g["items"])
    for f in lay["floating"]:
        if f["mesh"] in P.REGISTRY:
            if f["mesh"] not in protos:
                protos[f["mesh"]] = P.build_object(f["mesh"], f["mesh"] + "_proto", collection=hidden)
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
