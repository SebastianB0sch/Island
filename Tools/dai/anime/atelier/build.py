"""
One design -> one skinned character mesh on the shared cast skeleton.

build_character() paints the design's textures, cuts its outfit, builds the skin the outfit leaves visible,
combs the hair and joins everything (mesh.assemble). Spring / cloth helper bones are added to the armature
on demand; they are named per character (hair) or shared (hem chains), so every character of the cast
lives on one union skeleton.
"""

import os

import numpy as np

from ... import config as C
from ... import palette
from .. import skeleton as S
from . import body as BD
from . import hair as HR
from . import head as HD
from . import mesh as M
from . import outfit as OF
from . import paint as P

TEX_REL = "Characters"
OUTLINE_COLOR = (0.16, 0.09, 0.10)
HEAD_KINDS = {"hairband", "glasses", "hairbow"}
# Proportions fitted to anime reference figures (measured, not copied): the parts are modelled in the
# skeleton's design space and then warped - legs lengthened, shoulders brought in, head enlarged.
HEAD_SCALE = {False: 1.15, True: 1.24}      # head size over the design head (boys ~7.5, girls ~7 heads tall)
HEAD_PIVOT = (0.0, 0.0, S.HEAD)
LEG_STRETCH = 0.09                           # metres added between ankle and hip
SHOULDER_IN = 0.05                           # metres each shoulder joint moves towards the spine
_CROWN = S.HEAD_CENTER[2] + 0.113 - S.HEAD


def height_of(female):
    """Crown height (m, without hair) of an atelier body."""
    return S.HEAD + _CROWN * HEAD_SCALE[bool(female)] + LEG_STRETCH


HEIGHT = height_of(False)


def warp(p):
    """Design space -> final proportions for points (K, 3)."""
    p = np.array(p, np.float64).reshape(-1, 3)
    z = p[:, 2].copy()
    k = (S.HIP - S.ANKLE + LEG_STRETCH) / (S.HIP - S.ANKLE)
    p[:, 2] = np.where(z < S.ANKLE, z, np.where(z < S.HIP, S.ANKLE + (z - S.ANKLE) * k, z + LEG_STRETCH))
    ax = np.abs(p[:, 0])
    r = (S.SHOULDER_X - SHOULDER_IN - 0.05) / (S.SHOULDER_X - 0.05)
    new = np.where(ax < 0.05, ax, np.where(ax < S.SHOULDER_X, 0.05 + (ax - 0.05) * r, ax - SHOULDER_IN))
    w = M.smooth((z - 1.08) / 0.14) * (1.0 - M.smooth((z - 1.445) / 0.03))
    p[:, 0] = np.sign(p[:, 0]) * (ax + (new - ax) * w)
    return p


def ensure_bones(arm, specs):
    """Add missing helper bones [(name, parent, head, tail[, deform])] to the armature (rest pose)."""
    import bpy
    specs = [s for s in specs if s[0] not in arm.data.bones]
    if not specs:
        return 0
    for o in bpy.context.scene.objects:
        o.select_set(o is arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for spec in specs:
        name, parent, head, tail = spec[:4]
        b = eb.new(name)
        b.head, b.tail = head, tail
        b.parent = eb[parent]
        b.use_connect = False
        b.use_deform = spec[4] if len(spec) > 4 else True
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return len(specs)


def material_names(key, design):
    tint = set(design.get("tint", ()))
    return dict(face=f"M_Anime_{key}_Face", skin=f"M_Anime_{key}_Skin",
                hair=f"M_Anime_{key}_HairTint" if "hair" in tint else f"M_Anime_{key}_Hair",
                cloth=f"M_Anime_{key}_Cloth",
                tint=f"M_Anime_{key}_JacketTint" if "jacket" in tint else None)


def build_character(key, design, arm, material_fn, log=print, outline=0.0028):
    """Build design `key` on armature `arm`; returns the mesh object. Writes the textures and registers the
    palette materials."""
    mats = material_names(key, design)
    tex_dir = C.OUT_TEXTURES
    rel = f"{TEX_REL}/{key}"
    skin = design.get("skin", (1.0, 0.89, 0.80))
    hair = design["hair"]
    hcol = hair["color"]
    tinted_hair = "hair" in design.get("tint", ())

    head = HD.Head(design.get("head"), design.get("eyes"))
    body = BD.Body(design.get("female", True), design.get("build", 1.0), design.get("bust", 1.0))

    # ---- textures / materials
    P.face(os.path.join(tex_dir, f"{rel}/T_{mats['face'][2:]}.png"), skin, eyes=design.get("eyes"),
           iris=design.get("iris", (0.30, 0.55, 0.85)), iris2=design.get("iris2"),
           lash=design.get("lash", P.shade(hcol, v=0.24, s=0.8) if not tinted_hair else (0.13, 0.10, 0.11)),
           brow=design.get("brow", P.shade(hcol, v=0.62, s=0.9) if not tinted_hair else (0.30, 0.24, 0.24)),
           blush=design.get("blush", 0.26), lips=design.get("lips"), mole=design.get("mole"),
           bang_shadow=design.get("bang_shadow", 0.5), female=design.get("female", True),
           size=design.get("face_size", 2048))
    paint_col = (0.93, 0.93, 0.93) if tinted_hair else hcol
    P.hair(os.path.join(tex_dir, f"{rel}/T_{mats['hair'][2:]}.png"), paint_col,
           None if tinted_hair else hair.get("color2"), highlight=hair.get("highlight"),
           ombre=hair.get("ombre", (0.45, 0.30)), seed=hair.get("seed", 3))
    specs = {
        mats["face"]: dict(kind="toon", color=(1.0, 1.0, 1.0), rough=0.85, fill=0.6, base=f"{rel}/T_{mats['face'][2:]}"),
        mats["hair"]: dict(kind="toon", color=(1.0, 1.0, 1.0), rough=0.85, fill=0.45, ring=0.0,
                           base=f"{rel}/T_{mats['hair'][2:]}"),
        mats["skin"]: dict(kind="toon", color=tuple(skin), rough=0.85, fill=0.5),
        M.OUTLINE_MAT: dict(kind="outline", color=OUTLINE_COLOR),
    }

    # ---- outfit
    kit = OF.Kit(body, key, mats)
    body_wear = [(k, p) for k, p in design.get("outfit", ()) if k not in HEAD_KINDS]
    kit.wear(body_wear)
    n_body = len(kit.parts)
    for kind, params in design.get("outfit", ()):
        if kind == "hairband":
            OF.hairband(kit, head=head, **params)
        elif kind == "glasses":
            OF.glasses(kit, head=head, **params)
        elif kind == "hairbow":
            at = params.get("at", (150.0, 0.30))
            pos = head.scalp(np.radians(at[0]), at[1], params.get("loft", 0.030))[0]
            OF.bow(kit, params["color"], z=float(pos[2]), y=float(pos[1]), x=float(pos[0]), bone="head",
                   size=params.get("size", 1.0), tails=params.get("tails", 0.05), knot=params.get("knot"))
    specs.update(kit.save(tex_dir, rel))
    palette.register(specs)

    # ---- skin
    head_parts = head.build(mats["face"], design.get("brows"), design.get("mouth"))
    HD.bake_expression(head_parts, design.get("expression"))
    parts = list(head_parts)
    sk = mats["skin"]
    parts.append(body.neck(sk))
    if kit.skin["torso"] < 1.40:
        parts.append(body.torso(sk, kit.skin["torso"], 1.41))
    for side in ("l", "r"):
        for x0, x1 in kit.skin["arms"]:
            parts.append(body.arm(sk, side, x0, x1))
        if kit.skin["hands"]:
            parts.append(body.hand(sk, side))
        for z0, z1 in kit.skin["legs"]:
            parts.append(body.leg(sk, side, z0, z1))

    # ---- hair
    hr = HR.Hair(head, body, seed=hair.get("seed", 1))
    HR.style(hr, hair["style"], mats["hair"])
    hair_parts, bones = hr.build(mats["hair"], key, cap_line=hair.get("cap", (0.27, 0.50, 0.74)))
    k = design.get("head_scale", HEAD_SCALE[bool(design.get("female", True))])
    pivot = np.array(HEAD_PIVOT)
    for p in head_parts + kit.parts[n_body:] + hair_parts:
        p.v = pivot + (p.v - pivot) * k
        p.morphs = {m: d * k for m, d in p.morphs.items()}
        p.round_c = pivot + (p.round_c - pivot) * k
    bones = [(n, par, tuple(pivot + (np.array(a) - pivot) * k), tuple(pivot + (np.array(b) - pivot) * k))
             for n, par, a, b in bones]
    for prefix in sorted(kit.cloth_prefixes):
        bones += OF.cloth_bone_specs(prefix)
    bones = [(b[0], b[1], tuple(warp(b[2])[0]), tuple(warp(b[3])[0])) + tuple(b[4:]) for b in bones]
    ensure_bones(arm, bones)
    everything = parts + kit.parts + hair_parts
    for p in everything:
        p.round_c = warp(p.round_c)[0]
        p.v = warp(p.v)

    obj = M.assemble(f"SK_Anime_{key}", everything, arm, material_fn, outline=outline, log=log)
    return obj


def create_skeleton(name="root"):
    """The cast skeleton in its final proportions (skeleton.py's rest pose, warped)."""
    import bpy
    arm = S.create(name)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for b in arm.data.edit_bones:
        roll = b.roll
        b.head, b.tail = warp(np.array(b.head))[0], warp(np.array(b.tail))[0]
        b.roll = roll
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm
