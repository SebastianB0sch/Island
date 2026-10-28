"""
bpy utilities: scene reset, palette materials, UVs, FBX export, preview renders.
"""

import math
import os

import bpy
import numpy as np
from mathutils import Vector

from . import palette


# --------------------------------------------------------------------------- scene
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


# --------------------------------------------------------------------------- materials
def material(name):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    spec = palette.MATERIALS.get(name, dict(kind="opaque", color=(1.0, 0.0, 1.0)))
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.get("Material Output") or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    lin = palette.srgb_to_linear(spec["color"])
    kind = spec.get("kind", "opaque")
    bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
    bsdf.inputs["Roughness"].default_value = spec.get("rough", 0.8)
    bsdf.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
    if kind in ("emissive", "lava", "hologram", "beam"):
        _set_input(bsdf, ("Emission Color", "Emission"), (*lin, 1.0))
        _set_input(bsdf, ("Emission Strength",), min(spec.get("strength", 1.0), 30.0))
    if kind in ("glass", "water", "waterfall", "smoke", "beam", "hologram"):
        alpha = spec.get("opacity", 0.4 if kind != "water" else 0.85)
        bsdf.inputs["Alpha"].default_value = alpha
        try:
            mat.surface_render_method = "BLENDED"
        except Exception:
            pass
    if kind == "water":
        bsdf.inputs["Roughness"].default_value = 0.03
        _set_input(bsdf, ("Transmission Weight", "Transmission"), 0.0)
    mat.diffuse_color = (*lin, 1.0)
    return mat


def _set_input(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


# --------------------------------------------------------------------------- uv
def box_uv(mesh, scale=1.0, name="UVMap"):
    """Box-project UVs (metres) per face, oriented so textures are upright on walls."""
    if len(mesh.polygons) == 0:
        return
    uvl = mesh.uv_layers.get(name) or mesh.uv_layers.new(name=name)
    nl = len(mesh.loops)
    vidx = np.empty(nl, dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", vidx)
    co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    pn = np.empty(len(mesh.polygons) * 3, dtype=np.float32)
    mesh.polygons.foreach_get("normal", pn)
    pn = pn.reshape(-1, 3)
    totals = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_total", totals)
    poly_of_loop = np.repeat(np.arange(len(mesh.polygons)), totals)
    n = pn[poly_of_loop]
    p = co[vidx]
    ax = np.argmax(np.abs(n), axis=1)
    sgn = np.sign(n[np.arange(nl), ax])
    sgn[sgn == 0] = 1
    u = np.where(ax == 0, p[:, 1] * sgn, np.where(ax == 1, -p[:, 0] * sgn, p[:, 0]))
    v = np.where(ax == 2, p[:, 1] * sgn, p[:, 2])
    uv = np.stack([u * scale, v * scale], axis=1).astype(np.float32)
    uvl.data.foreach_set("uv", uv.ravel())


# --------------------------------------------------------------------------- objects
def join(objs, name):
    """Join mesh objects into one (keeps material slots)."""
    objs = [o for o in objs if o is not None and o.type == "MESH"]
    if not objs:
        return None
    if len(objs) == 1:
        objs[0].name = name
        objs[0].data.name = name
        return objs[0]
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs,
                                   selected_objects=objs):
        bpy.ops.object.join()
    o = objs[0]
    o.name = name
    o.data.name = name
    return o


def delete(objs):
    for o in list(objs):
        if o is None:
            continue
        data = o.data if o.type == "MESH" else None
        bpy.data.objects.remove(o, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.meshes.remove(data)


def apply_transform(obj):
    mw = obj.matrix_world.copy()
    obj.data.transform(mw)
    obj.matrix_world.identity()


# --------------------------------------------------------------------------- export
def export_fbx(objs, path):
    """Export the given objects (at their current transforms) to a binary FBX for UE."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH"},
        apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
        mesh_smooth_type="FACE", use_mesh_modifiers=True, add_leaf_bones=False,
        bake_anim=False, path_mode="STRIP", embed_textures=False, use_custom_props=False,
        use_tspace=False, colors_type="LINEAR")
    for o in objs:
        o.select_set(False)


# --------------------------------------------------------------------------- rendering
def setup_render(res=(1600, 900), samples=48, scene=None):
    scene = scene or bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    try:
        scene.cycles.use_denoising = True
    except Exception:
        pass
    scene.cycles.max_bounces = 4
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in
        bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    scene.view_settings.look = "None"
    return scene


def setup_world(sun_elev=35.0, sun_azim=210.0, strength=1.0, sun_strength=4.0):
    """Sky + sun. Uses the sky texture when available, falls back to a gradient."""
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs[0])
    sky_ok = False
    try:
        sky = nt.nodes.new("ShaderNodeTexSky")
        items = [i.identifier for i in sky.bl_rna.properties["sky_type"].enum_items]
        for pref in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA", "HOSEK_WILKIE", "PREETHAM"):
            if pref in items:
                sky.sky_type = pref
                break
        if hasattr(sky, "sun_elevation"):
            sky.sun_elevation = math.radians(sun_elev)
            sky.sun_rotation = math.radians(sun_azim)
        if hasattr(sky, "sun_disc"):
            sky.sun_disc = False
        nt.links.new(sky.outputs[0], bg.inputs[0])
        bg.inputs["Strength"].default_value = 0.35 * strength
        sky_ok = True
    except Exception:
        sky_ok = False
    if not sky_ok:
        bg.inputs[0].default_value = (0.45, 0.65, 0.95, 1.0)
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = sun_strength
    sun_data.angle = math.radians(1.5)
    sun_data.color = (1.0, 0.96, 0.9)
    sun = bpy.data.objects.new("Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    # point the sun: elevation/azimuth (azimuth measured from +Y clockwise like a compass)
    el, az = math.radians(sun_elev), math.radians(sun_azim)
    d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    return sun


def camera(name, loc, target, lens=35.0, clip_end=20000.0):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_data.clip_end = clip_end
    cam_data.clip_start = 0.5
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return cam


def render(cam, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def preview_asset(objs, path, res=(1000, 750), samples=24, azim=-35.0, elev=22.0, dist_mul=1.6,
                  ground=True, target_z_frac=0.35):
    """Frame a set of objects from a 3/4 view and render to `path`."""
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector((min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)))
            mx = Vector((max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)))
    center = (mn + mx) / 2
    size = (mx - mn).length
    target = Vector((center.x, center.y, mn.z + (mx.z - mn.z) * target_z_frac))
    az, el = math.radians(azim), math.radians(elev)
    dist = size * dist_mul
    loc = target + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
    if ground:
        g = bpy.data.meshes.new("PreviewGround")
        s = size * 4
        g.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        go = bpy.data.objects.new("PreviewGround", g)
        gz = -0.02 if mn.z < 0.0 < mx.z else mn.z - 0.02   # local-space assets: ground is z = 0
        go.location = (center.x, center.y, gz)
        go.data.materials.append(material("M_Grass"))
        bpy.context.scene.collection.objects.link(go)
    setup_render(res, samples)
    if bpy.context.scene.world is None:
        setup_world()
    cam = camera("PreviewCam", loc, target, lens=40)
    render(cam, path)
