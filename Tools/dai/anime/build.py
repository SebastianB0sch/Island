"""
Builds the anime cast: one shared skeleton, the retargeted / authored animation takes, a skinned
SK_Anime_<Name> mesh per cast member (+ the duel disk attachment), the face textures, and
Data/cast.json for the Unreal importer. Also annotates layout.json's NPC markers with who stands
where (cast.assign_npcs).

    python Tools/build_island.py cast             # build + export the cast
    python Tools/preview_anime.py [ids...]          # Cycles lineup render
"""

import json
import os

import bpy

from .. import config as C
from .. import palette, thirdparty
from ..character import export_skeletal
from . import body as B
from . import cast as CAST
from . import face as FACE
from . import gait as GAIT
from . import hair as HAIR
from . import head as HEAD
from . import models as M
from . import retarget as RT
from . import skeleton as S
from . import skin as K

OUT_REL = "Meshes/Characters/Anime"
TEX_REL = "Characters"
OUTLINE_COLOR = (0.09, 0.06, 0.07)

# Authored takes (world-space aims, see retarget.pose_action) -------------------------------------
_ARM_DOWN = {"upperarm_l": {"aim": (0.35, 0.05, -1)}, "upperarm_r": {"aim": (-0.35, 0.05, -1)},
             "lowerarm_l": {"aim": (0.25, -0.15, -1)}, "lowerarm_r": {"aim": (-0.25, -0.15, -1)}}


def _duel_keys(rig=None):
    """Duel stance: disk arm across the chest, card hand raised, slight crouch; gentle breathing loop."""
    keys = []
    for f, br in ((0, 0.0), (30, 1.0), (60, 0.0)):
        keys.append((f, {
            "_pelvis_offset": (0.0, 0.0, -0.012 - 0.004 * br),
            "spine_01": (4 + 2 * br, 0, 6), "spine_03": (2 - 1.5 * br, 0, 8),
            "head": (-2 + 2 * br, 0, -10),
            "upperarm_l": {"aim": (0.55, -0.75, -0.35), "roll": -10},
            "lowerarm_l": {"aim": (-0.75, -0.62, 0.08), "roll": -15},
            "hand_l": {"aim": (-0.8, -0.55, 0.0)},
            "upperarm_r": {"aim": (-0.45, -0.55, 0.15 + 0.03 * br)},
            "lowerarm_r": {"aim": (-0.05, -0.45, 0.9)},
            "hand_r": {"aim": (0.0, -0.3, 1.0)},
            "thigh_l": {"aim": (0.18, -0.12, -1)}, "thigh_r": {"aim": (-0.18, 0.1, -1)},
            "calf_l": {"aim": (0.12, 0.05, -1)}, "calf_r": {"aim": (-0.12, 0.08, -1)},
        }))
    return keys


def _swim_keys(rig=None):
    """Front crawl, authored upright (the avatar component pitches the body forward in the water)."""
    import math
    keys = []
    for k in range(9):
        a = 2 * math.pi * k / 8
        f = k * 6
        aim_l = (0.28, -math.sin(a) * 0.9, math.cos(a))
        aim_r = (-0.28, -math.sin(a + math.pi) * 0.9, math.cos(a + math.pi))
        kick = 14 * math.sin(a * 3)
        keys.append((f, {
            "upperarm_l": {"aim": aim_l}, "upperarm_r": {"aim": aim_r},
            "lowerarm_l": {"aim": aim_l}, "lowerarm_r": {"aim": aim_r},
            "thigh_l": (kick, 0, 0), "thigh_r": (-kick, 0, 0),
            "head": (0, 0, 12 * math.sin(a)),
        }))
    return keys


# state -> (source registry key | None for authored, take, loop)
TAKES = [
    ("Jump", "A_Anime_Jump", False), ("Fall", "A_Anime_Fall", True), ("Land", "A_Anime_Land", False),
    ("Wave", "A_Anime_Wave", False), ("Yes", "A_Anime_Yes", False), ("No", "A_Anime_No", False),
    ("Sit", "A_Anime_Sit", True), ("Clap", "A_Anime_Clap", False), ("Interact", "A_Anime_Interact", False),
]
# state -> (key generator, loop, authored ground speed in cm/s or None)
AUTHORED = {
    "Idle": (GAIT.idle_keys, True, 0.0),
    "Walk": (GAIT.walk_keys, True, GAIT.WALK.speed * 100.0),
    "Run": (GAIT.run_keys, True, GAIT.RUN.speed * 100.0),
    "Duel": (_duel_keys, True, None),
    "Swim": (_swim_keys, True, None),
}


def key_name(cid):
    return "".join(p.capitalize() for p in cid.split("_"))


# --------------------------------------------------------------------------- materials
def _toon(name, color, **kw):
    palette.register({name: dict(kind="toon", color=tuple(color), rough=0.85, fill=kw.pop("fill", 0.5), **kw)})
    return name


def materials(cid, entry, log=print):
    """Role -> palette material name for one cast member (registers palette entries, paints the face)."""
    key = key_name(cid)
    col = entry["colors"]
    tint = set(entry.get("tint", []))
    m = {}
    for role in ("jacket", "trim", "inner", "pants", "shoes", "sole", "skirt", "socks", "boots"):
        if role in col:
            suffix = "JacketTint" if (role == "jacket" and "jacket" in tint) else role.capitalize()
            m[role] = _toon(f"M_Anime_{key}_{suffix}", col[role])
    m["skin"] = _toon("M_Anime_Skin", CAST.SKIN)
    hc = entry["hair"]
    if "hair" in tint:
        m["hair"] = m["hair2"] = _toon(f"M_Anime_{key}_HairTint", hc["color"], fill=0.45)
    else:
        m["hair"] = _toon(f"M_Anime_{key}_Hair", hc["color"], fill=0.45)
        m["hair2"] = _toon(f"M_Anime_{key}_Hair2", hc.get("color2", hc["color"]), fill=0.45)
    tex = os.path.join(C.OUT_TEXTURES, TEX_REL, f"T_AnimeFace_{key}.png")
    FACE.paint(dict(entry["face"], skin=CAST.SKIN), tex)
    m["face"] = _toon(f"M_Anime_{key}_Face", (1.0, 1.0, 1.0), base=f"{TEX_REL}/T_AnimeFace_{key}", fill=0.6)
    m["glasses"] = _toon("M_Anime_Glasses", (0.20, 0.22, 0.28))
    m["ruff"] = _toon("M_Anime_Ruff", (0.97, 0.97, 0.96))
    palette.register({K.OUTLINE_MAT: dict(kind="outline", color=OUTLINE_COLOR)})
    return m


def disk_materials():
    return dict(disk=_toon("M_Anime_DuelDisk", (0.78, 0.80, 0.84)), gold=_toon("M_Anime_DiskGold", (0.95, 0.72, 0.22)),
                glow=_register_glow())


def _register_glow():
    palette.register({"M_Anime_DiskGlow": dict(kind="emissive", color=(0.25, 0.85, 1.0), strength=6.0)})
    return "M_Anime_DiskGlow"


# --------------------------------------------------------------------------- preview materials (Cycles)
def preview_material(name):
    """Toon look for Blender previews: banded diffuse + flat fill light, inverted-hull ink lines."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    spec = palette.MATERIALS.get(name, dict(kind="opaque", color=(1, 0, 1)))
    kind = spec.get("kind")
    if kind not in ("toon", "outline"):
        from .. import blend
        return blend.material(name)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    lin = palette.srgb_to_linear(spec["color"])
    if kind == "outline":
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        ink = nt.nodes.new("ShaderNodeEmission")
        ink.inputs["Color"].default_value = (*lin, 1.0)
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
        nt.links.new(ink.outputs[0], mix.inputs[1])
        nt.links.new(tr.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
        return mat
    col = nt.nodes.new("ShaderNodeRGB")
    col.outputs[0].default_value = (*lin, 1.0)
    src = col.outputs[0]
    if spec.get("base"):
        img_path = os.path.join(C.OUT_TEXTURES, spec["base"] + ".png")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(img_path, check_existing=True)
        src = tex.outputs["Color"]
    alpha = tex.outputs["Alpha"] if spec.get("base") and spec.get("masked") else None
    toon = nt.nodes.new("ShaderNodeBsdfToon")
    toon.component = "DIFFUSE"
    toon.inputs["Size"].default_value = 0.85
    toon.inputs["Smooth"].default_value = 0.12
    nt.links.new(src, toon.inputs["Color"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = spec.get("fill", 0.3)
    nt.links.new(src, em.inputs["Color"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(toon.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    if alpha is not None:
        cut = nt.nodes.new("ShaderNodeMath")
        cut.operation = "GREATER_THAN"
        cut.inputs[1].default_value = 0.5
        nt.links.new(alpha, cut.inputs[0])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(cut.outputs[0], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(add.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
    else:
        nt.links.new(add.outputs[0], out.inputs[0])
    mat.diffuse_color = (*lin, 1.0)
    return mat


# --------------------------------------------------------------------------- characters
def build_character(cid, entry, arm):
    m = materials(cid, entry)
    bd = entry.get("body", {})
    shape = entry.get("head", {})
    asm = K.Assembly(f"SK_Anime_{key_name(cid)}")
    asm.add(HEAD.head(m["face"], m["skin"], shape), K.rigid("head"), 1.0)
    asm.add(HEAD.neck(m["skin"]), lambda p: K.spine(p) if p.z < S.NECK else
            {"neck_01": 1.0 - K._smooth((p.z - S.NECK) / 0.08), "head": K._smooth((p.z - S.NECK) / 0.08)}, 0.0)
    hc = entry["hair"]
    short, long = HAIR.build(hc["style"], m["hair"], m["hair2"], shape)
    asm.add(short, K.rigid("head"), 1.25)
    asm.add(long, K.head_and_body(), 1.25)
    for parts in (B.jacket(m, bd), B.arms(m), B.legs(m, bd)):
        for mb, fn, ol in parts:
            asm.add(mb, fn, ol)
    for ex in entry.get("extras", []):
        for mb, fn, ol in (B.glasses(m["glasses"], shape) if ex == "glasses" else B.ruff(m["ruff"]) if ex == "ruff" else []):
            asm.add(mb, fn, ol)
    return asm.build(arm, face_mats=[m["face"]], material_fn=preview_material)


def build_disk(arm, name="SK_Anime_DuelDisk"):
    """Duel disk skinned to this skeleton's left forearm (separate mesh, follows the body in Unreal)."""
    asm = K.Assembly(name)
    for mb, fn, ol in B.duel_disk(disk_materials(), *_disk_bones(arm)):
        asm.add(mb, fn, ol)
    return asm.build(arm, material_fn=preview_material)


def bake_takes(arm, log=print):
    """All animation takes onto `arm`. Returns {state: (action, loop, speed)}."""
    reg = thirdparty.registry().get("anime", {})
    sources = {}
    out = {}
    for state, reg_key, loop in TAKES:
        spec = reg.get(reg_key)
        if not spec:
            log(f"  !! anime: no source registered for {reg_key}")
            continue
        path = thirdparty.tp_path(spec["file"])
        if path not in sources:
            sources[path] = RT.Source(path)
        rng = tuple(spec["frames"]) if spec.get("frames") else None
        out[state] = (RT.bake(sources[path], spec["take"], arm, reg_key, frames=rng, speed=spec.get("speed", 1.0),
                              arm_drop=spec.get("arm_drop", 0.0)), loop, None)
    for src in sources.values():
        src.remove()
    for state, (fn, loop, speed) in AUTHORED.items():
        act = RT.pose_action(arm, f"A_Anime_{state}", fn(arm))
        if state in ("Walk", "Run"):
            metrics = GAIT.validate(arm, act, GAIT.WALK if state == "Walk" else GAIT.RUN, log)
            speed = metrics["speed"] * 100.0
        out[state] = (act, loop, speed)
    RT._assign(arm, None)
    return out


def _ground_speed(arm, action):
    """Natural ground speed (cm/s) of a locomotion cycle: how fast a planted foot slides backwards."""
    RT._assign(arm, action)
    scene = bpy.context.scene
    f0, f1 = (int(round(v)) for v in action.frame_range)
    ys = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        ys.append((arm.matrix_world @ arm.pose.bones["foot_l"].head).y)
    RT._assign(arm, None)
    dur = max(1, f1 - f0) / scene.render.fps
    return round(2.0 * (max(ys) - min(ys)) / dur * 100.0, 1)


# --------------------------------------------------------------------------- stage
PROCEDURAL = "Proc"      # skeleton group of the procedural fallback characters


def _export_takes(arm, group, out_dir, log):
    scene = bpy.context.scene
    takes = bake_takes(arm, log)
    anims = {}
    for state, (act, loop, speed) in takes.items():
        RT._assign(arm, act)
        f0, f1 = (int(round(v)) for v in act.frame_range)
        scene.frame_start, scene.frame_end = f0, max(f1, f0 + 1)
        name = f"A_Anime_{group}_{state}"
        export_skeletal([arm], arm, os.path.join(out_dir, f"{name}.fbx"), {"ARMATURE"}, anim=act, simplify=1.0)
        entry = dict(name=name, file=f"{OUT_REL}/{name}.fbx", loop=loop,
                     seconds=round((f1 - f0) / scene.render.fps, 3))
        if state in ("Walk", "Run"):
            entry["speed"] = round(speed if speed else _ground_speed(arm, act), 1)
        anims[state] = entry
    RT._assign(arm, None)
    log(f"  anime: {group}: {len(takes)} takes, walk {anims.get('Walk', {}).get('speed')} cm/s, "
        f"run {anims.get('Run', {}).get('speed')} cm/s")
    return anims


def _disk_bones(arm):
    b = arm.data.bones["lowerarm_l"]
    return tuple(b.head_local), tuple(b.tail_local)


def build(log=print, only=None):
    """Every cast member, grouped by skeleton: all members built on the same base model (or the procedural
    fallback rig) share one skeleton, one set of A_Anime_<Group>_<State> takes and one duel disk."""
    import shutil
    from .. import blend
    out_dir = os.path.join(C.OUT_DIR, OUT_REL)
    for d in (out_dir, os.path.join(C.OUT_TEXTURES, TEX_REL)):      # fully generated: start clean
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)
    entries = CAST.all_entries()
    order = [CAST.PLAYER] + [c for c in entries if c != CAST.PLAYER]
    if only:
        order = [c for c in order if c in only or c == CAST.PLAYER]
    groups = {}
    for cid in order:
        e = entries[cid]
        g = key_name(e["model"]) if M.model_available(e) else PROCEDURAL
        groups.setdefault(g, []).append(cid)
    info = dict(player=CAST.PLAYER, groups={}, meshes={}, materials={})
    used = set()
    for group, cids in groups.items():
        blend.reset_scene()
        bpy.context.scene.render.fps = 30
        if group == PROCEDURAL:
            arm = S.create("root")
        else:
            arm, first = M.build_model(cids[0], entries[cids[0]], key_name, log)
            bpy.data.objects.remove(first, do_unlink=True)
        g = dict(skeleton_mesh=None, anims=_export_takes(arm, group, out_dir, log))
        disk = build_disk(arm, f"SK_Anime_{group}_DuelDisk")
        export_skeletal([arm, disk], arm, os.path.join(out_dir, disk.name + ".fbx"), {"ARMATURE", "MESH"})
        g["duel_disk"] = dict(name=disk.name, file=f"{OUT_REL}/{disk.name}.fbx",
                              materials=[s.material.name for s in disk.material_slots if s.material])
        used.update(g["duel_disk"]["materials"])
        bpy.data.objects.remove(disk, do_unlink=True)
        for cid in cids:
            e = entries[cid]
            if group == PROCEDURAL:
                a, obj = arm, build_character(cid, e, arm)
            else:
                a, obj = M.build_model(cid, e, key_name, log)
            name = obj.name
            mats = [s.material.name for s in obj.material_slots if s.material]
            used.update(mats)
            entry = dict(name=name, group=group, display=e["name"], dorm=e["dorm"], scale=e.get("scale", 1.0),
                         tint=e.get("tint", []), female=bool(e.get("body", {}).get("female")), materials=mats)
            # every member is tailored / restyled individually: one FBX each, all on the group's skeleton (the
            # first member's import creates it in Unreal, the others and the takes reuse it)
            export_skeletal([a, obj], a, os.path.join(out_dir, f"{name}.fbx"), {"ARMATURE", "MESH"})
            entry["file"] = f"{OUT_REL}/{name}.fbx"
            info["meshes"][cid] = entry
            g["skeleton_mesh"] = g["skeleton_mesh"] or name
            log(f"  anime: {name:24s} [{group}] {K.tri_count(obj):6d} tris, {len(mats)} materials")
            bpy.data.objects.remove(obj, do_unlink=True)
            if a is not arm:
                bpy.data.objects.remove(a, do_unlink=True)
        info["groups"][group] = g
    mats = palette.material_json()
    info["materials"] = {k: mats[k] for k in sorted(used) if k in mats}
    os.makedirs(C.OUT_DATA, exist_ok=True)
    with open(os.path.join(C.OUT_DATA, "cast.json"), "w") as fp:
        json.dump(info, fp, indent=1)
    annotate_layout(log)
    return info


def annotate_layout(log=print):
    """Assign cast members / generic looks to the NPC markers of an existing layout.json."""
    path = os.path.join(C.OUT_DATA, "layout.json")
    if not os.path.exists(path):
        return
    with open(path) as fp:
        layout = json.load(fp)
    CAST.assign_npcs(layout.get("npcs", []))
    with open(path, "w") as fp:
        json.dump(layout, fp, separators=(",", ":"))
    named = [n["cast"] for n in layout.get("npcs", []) if not n.get("tint", True)]
    log(f"  anime: layout.json npcs cast ({len(named)} named: {', '.join(named)})")


# --------------------------------------------------------------------------- preview render
def render_lineup(path, ids=None, state="Idle", frame=12, res=(1800, 720), samples=32, view=0.0, log=print,
                  portrait=False):
    """Cycles toon render of the cast standing in a row (for Docs/renders and quick iteration). portrait: a
    head-and-shoulders close-up of the first character instead (to compare with official portraits)."""
    import math
    from .. import blend
    blend.reset_scene()
    scene = bpy.context.scene
    scene.render.fps = 30
    entries = CAST.all_entries()
    ids = ids or list(CAST.CAST)
    src_key = dict((s, k) for s, k, _ in TAKES).get(state)
    src = spec = None
    if src_key:
        spec = thirdparty.registry()["anime"][src_key]
        src = RT.Source(thirdparty.tp_path(spec["file"]))
    shared = None
    spacing = 0.85
    for i, cid in enumerate(ids):
        e = entries[cid]
        if M.model_available(e):
            a, obj = M.build_model(cid, e, key_name)
            act = None
        else:
            if shared is None:
                shared = S.create("root")
                a = shared
            else:
                a = shared.copy()
                a.data = shared.data
                scene.collection.objects.link(a)
            obj = build_character(cid, e, a)
        if src is not None:
            act = RT.bake(src, spec["take"], a, f"{src_key}_{cid}", arm_drop=spec.get("arm_drop", 0.0))
        elif state in AUTHORED:
            act = RT.pose_action(a, f"pose_{cid}", AUTHORED[state][0](a))
        RT._assign(a, act)
        sc = e.get("scale", 1.0)
        a.location = ((i - (len(ids) - 1) / 2) * spacing, 0.0, 0.0)
        a.scale = (sc, sc, sc)
        obj.parent = a
    if src is not None:
        src.remove()
    scene.frame_set(frame)
    for o in scene.objects:
        if o.type == "MESH":
            o.visible_shadow = True
    blend.setup_render(res, samples, scene)
    scene.view_settings.view_transform = "Standard"     # flat anime colours, no filmic desaturation
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("cast")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.62, 0.74, 0.92, 1.0)
    bg.inputs[1].default_value = 0.9
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 2.6
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(48), 0, math.radians(-22))
    scene.collection.objects.link(sun)
    ground = bpy.data.meshes.new("ground")
    ground.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("ground", ground)
    gm = bpy.data.materials.new("groundmat")
    gm.diffuse_color = (0.55, 0.62, 0.45, 1)
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.50, 0.26, 1)
    ground.materials.append(gm)
    scene.collection.objects.link(g)
    width = len(ids) * spacing
    dist = max(3.6, width * 1.45)
    a = math.radians(view)
    if portrait:
        first = next(o for o in scene.objects if o.type == "ARMATURE")
        bpy.context.view_layer.update()
        head = first.matrix_world @ first.pose.bones["head"].head          # posed (the take moves the hips)
        bust = portrait == "bust"                    # head and chest (uniform details) instead of the face
        tgt = (head.x, head.y, head.z + (-0.12 if bust else 0.08) * first.scale.z)   # the head bone sits at the jaw
        d = 1.45 if bust else 0.9
        cam = blend.camera("cam", (tgt[0] + math.sin(a) * d, -math.cos(a) * d, tgt[2]), tgt, lens=50.0)
    else:
        cam = blend.camera("cam", (math.sin(a) * dist, -math.cos(a) * dist, 1.25), (0.0, 0.0, 0.92), lens=50.0)
    blend.render(cam, path)
    log(f"  lineup -> {path}")
