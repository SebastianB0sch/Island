"""
Natural landmarks that depend on the generated terrain: volcano crater (lava,
smoke, viewpoint), waterfall + spring stream, lake dressing, Sunset Point
cliffs viewpoint, beach furniture, forest spirit shrine.

These AssetSets are ABSOLUTE in height (aset.absolute = True): local XY is
relative to the location point, Z is world height sampled from the terrain.
"""

import math
import random

from mathutils import Vector

from . import AssetSet
from .. import config as C
from .. import terrain
from ..geo import MeshBuilder, TAU
from .props import blob, tube

_cache = {}


def _terrain():
    if "t" not in _cache:
        _cache["t"] = terrain.load_cached()
    return _cache["t"]


def H(x, y):
    hf = _terrain()[0]
    return float(hf(x, y))


def new_set(key):
    a = AssetSet(key)
    a.absolute = True
    a.origin = C.LOCATIONS[key]["pos"]
    return a


def L(a, wx, wy):
    """world XY -> local XY of the asset set"""
    return wx - a.origin[0], wy - a.origin[1]


def ground(a, wx, wy, dz=0.0):
    lx, ly = L(a, wx, wy)
    return (lx, ly, H(wx, wy) + dz)


def rot2(x, y, yaw_deg):
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    return x * c - y * s, x * s + y * c


def disk(mb, center, radius, mat, seg=32, z=None):
    cx, cy, cz = center
    pts = [(cx + math.cos(TAU * i / seg) * radius, cy + math.sin(TAU * i / seg) * radius, cz) for i in range(seg)]
    mb.poly(pts, mat)


def fence_line(a, pts_world, asset="SM_Fence_Wood", seg_len=4.0):
    """Place fence segments along a polyline of world XY points."""
    for i in range(len(pts_world) - 1):
        ax, ay = pts_world[i]
        bx, by = pts_world[i + 1]
        d = math.hypot(bx - ax, by - ay)
        n = max(1, int(round(d / seg_len)))
        yaw = math.degrees(math.atan2(by - ay, bx - ax))
        for k in range(n):
            t = (k + 0.5) / n
            wx, wy = ax + (bx - ax) * t, ay + (by - ay) * t
            a.prop(asset, ground(a, wx, wy), yaw)


# --------------------------------------------------------------------------- volcano
def build_volcano():
    a = new_set("volcano")
    info = _terrain()[3]["info"]["volcano"]
    lava_z = info["lava"]
    lava = a.mesh("Volcano_Lava_NoCol")
    disk(lava, (0, 0, lava_z), 62.0, "M_Lava", seg=40)
    # lava crust islands
    rnd = random.Random(4)
    for k in range(9):
        ang = rnd.uniform(0, TAU)
        r = rnd.uniform(8, 42)
        a.prop("SM_VolcanicRock_A", (math.cos(ang) * r, math.sin(ang) * r, lava_z - 1.2), rnd.uniform(0, 360),
               rnd.uniform(0.8, 1.8))
    a.light((0, 0, lava_z + 18), color=(1.0, 0.42, 0.12), intensity=200000.0, radius=260.0)
    a.light((0, 0, lava_z + 4), color=(1.0, 0.35, 0.1), intensity=60000.0, radius=90.0)
    a.emitter("smoke", (0, 0, info["rim"] + 2), scale=7.0, rate=1.0)
    a.emitter("smoke", (25, -15, lava_z + 3), scale=3.5, rate=0.6)
    a.audio("A_Volcano", (0, 0, info["rim"]), radius=420.0, volume=1.0)
    # fumaroles on the flanks
    vx, vy = C.VOLCANO_CENTER
    for ang, r in ((200, 230), (300, 260), (20, 210), (120, 250)):
        wx, wy = vx + math.cos(math.radians(ang)) * r, vy + math.sin(math.radians(ang)) * r
        p = ground(a, wx, wy, 0.5)
        a.emitter("steam", p, scale=1.6, rate=0.7)
        a.prop("SM_VolcanicRock_A", ground(a, wx + 3, wy + 2), ang, 1.2)
    # viewpoint at the end of the volcano trail
    vpx, vpy = 850.0, 690.0
    base = H(vpx, vpy)
    vp = a.mesh("Volcano_Viewpoint")
    lx, ly = L(a, vpx, vpy)
    dir_in = Vector((vx - vpx, vy - vpy, 0)).normalized()
    yaw = math.degrees(math.atan2(dir_in.y, dir_in.x))
    with vp.at((lx, ly, base), rot=yaw):
        vp.box((0, 0, -1.5), (8, 10, 3.2), "M_VolcanicRock")
        vp.railing([(4, -5, 1.7), (4, 5, 1.7)], 1.0, "M_RustMetal", post_spacing=1.25)
        vp.sign_board((-2.0, -4.0, 1.4), 2.6, 1.2, "M_LighthouseRed", "M_DarkMetal")
    ox, oy = rot2(-2.0, -4.09, yaw)
    a.text("DANGER - ACTIVE VOLCANO", (lx + ox, ly + oy, base + 1.4), yaw, size=0.26, color=(1, 1, 1))
    a.interact("sign", (lx, ly, base + 1.7), yaw, title="Duel Academy Volcano",
               text="Still active! The crater glows at night and the hot springs below are heated by its magma. "
                    "Stay behind the railing.")
    a.special("clearing", (lx, ly, base), radius=10.0)
    return a


# --------------------------------------------------------------------------- waterfall
def build_waterfall():
    a = new_set("waterfall")
    t = _terrain()
    info = t[3]["info"]
    pad_h = info["pads"]["waterfall"]
    wx0, wy0 = C.LOCATIONS["waterfall"]["pos"]
    lcx, lcy = C.LAKE_CENTER
    d = Vector((lcx - wx0, lcy - wy0, 0)).normalized()
    side = Vector((-d.y, d.x, 0))
    # walk from the pad centre towards the lake to find the lip and the plunge point
    lip = None
    bottom = None
    for i in range(0, 400):
        s = i * 0.5
        px, py = wx0 + d.x * s, wy0 + d.y * s
        h = H(px, py)
        if lip is None and h < pad_h - 0.6:
            lip = (s - 0.5, pad_h)
        if lip is not None and h <= C.LAKE_LEVEL + 0.3:
            bottom = s
            break
    if lip is None:
        lip = (22.0, pad_h)
    if bottom is None:
        bottom = lip[0] + 25.0
    s_lip = lip[0]
    drop = pad_h - C.LAKE_LEVEL
    # falling sheet: parabola from the lip, landing at `bottom`
    fall = a.mesh("Waterfall_Water_NoCol")
    rows = []
    n = 16
    reach = max(bottom - s_lip, 4.0) + 2.0
    for i in range(n + 1):
        tt = i / n
        out = s_lip - 2.0 + (reach + 2.0) * tt
        z = pad_h + 0.25 - drop * max(0.0, (out - s_lip) / reach) ** 1.8 - (0.0 if out > s_lip else 0.0)
        width = 9.0 + 4.0 * tt
        rows.append([(out, -width / 2), (out, 0.0), (out, width / 2)])
        rows[-1] = [(o, w, z - (0.6 if abs(w) > 0.1 else 0.0) * tt) for (o, w) in rows[-1]]
    pts_rows = []
    for row in rows:
        pr = []
        for (o, w, z) in row:
            p = Vector((wx0, wy0, 0)) + d * o + side * w
            lx, ly = L(a, p.x, p.y)
            pr.append((lx, ly, z))
        pts_rows.append(pr)
    fall.grid_faces(pts_rows, "M_Waterfall", smooth=True)
    # spring stream across the pad to the lip
    back = Vector((wx0, wy0, 0)) - d * 16.0
    lipp = Vector((wx0, wy0, 0)) + d * (s_lip - 1.0)
    stream_pts = [back + (lipp - back) * (k / 8) + side * math.sin(k * 0.9) * 1.5 for k in range(9)]
    srow_l, srow_r = [], []
    for k, p in enumerate(stream_pts):
        w = 2.0 + 1.5 * k / 8
        l = p + side * w
        r = p - side * w
        srow_l.append((*L(a, l.x, l.y), pad_h + 0.18))
        srow_r.append((*L(a, r.x, r.y), pad_h + 0.18))
    fall.grid_faces([[srow_l[k], srow_r[k]] for k in range(9)], "M_LakeWater", smooth=False)
    # foam ring at the plunge pool
    pp = Vector((wx0, wy0, 0)) + d * (s_lip + reach * 0.85)
    plx, ply = L(a, pp.x, pp.y)
    disk(fall, (plx, ply, C.LAKE_LEVEL + 0.08), 9.0, "M_Waterfall", seg=20)
    # rocks: spring source + lip boulders
    blx, bly = L(a, back.x, back.y)
    rocks = a.mesh("Waterfall_Rocks")
    blob(rocks, (blx, bly, pad_h + 1.5), 5.0, "M_Rock", seed=31, seg=12, rings=8, scale=(1.3, 1.0, 0.8), rough=0.4)
    for sgn in (-1, 1):
        q = lipp + side * sgn * 7.5
        qx, qy = L(a, q.x, q.y)
        blob(rocks, (qx, qy, pad_h + 1.0), 3.2, "M_Rock", seed=40 + sgn, seg=11, rings=7, scale=(1.0, 1.2, 1.0), rough=0.4)
    a.emitter("mist", (plx, ply, C.LAKE_LEVEL + 1.0), scale=3.0, rate=1.2)
    a.emitter("mist", (plx, ply, C.LAKE_LEVEL + 6.0), scale=2.0, rate=0.8)
    a.audio("A_Waterfall", (plx, ply, C.LAKE_LEVEL + 3), radius=140.0)
    a.light((plx, ply, C.LAKE_LEVEL + 3.0), color=(0.6, 0.85, 1.0), intensity=3000.0, radius=30.0, night_only=True)
    a.special("waterfall", (plx, ply, C.LAKE_LEVEL), yaw=math.degrees(math.atan2(d.y, d.x)),
              lip=[*L(a, lipp.x, lipp.y), pad_h], height=drop)
    a.interact("sign", (blx + side.x * 6, bly + side.y * 6, pad_h + 1.2), 0.0, title="Volcano Falls",
               text="Spring water warmed by the volcano tumbles into Academy Lake. Legend says duel spirits gather here.")
    return a


# --------------------------------------------------------------------------- lake
def build_lake():
    a = new_set("lake")
    rnd = random.Random(17)
    lcx, lcy = C.LAKE_CENTER
    rx, ry = C.LAKE_RADII
    ang0 = math.radians(C.LAKE_ROT)
    pads = a.mesh("Lake_LilyPads_NoCol")
    for k in range(70):
        th = rnd.uniform(0, TAU)
        rr = math.sqrt(rnd.uniform(0.55, 0.92))
        lx = math.cos(th) * rx * rr
        ly = math.sin(th) * ry * rr
        wx = lcx + lx * math.cos(ang0) - ly * math.sin(ang0)
        wy = lcy + lx * math.sin(ang0) + ly * math.cos(ang0)
        if H(wx, wy) > C.LAKE_LEVEL - 0.5:
            continue
        px, py = L(a, wx, wy)
        r = rnd.uniform(0.4, 0.9)
        disk(pads, (px, py, C.LAKE_LEVEL + 0.03), r, "M_LeavesBush", seg=9)
        if rnd.random() < 0.2:
            pads.sphere((px, py, C.LAKE_LEVEL + 0.12), 0.12, rnd.choice(["M_FlowerWhite", "M_FlowerRed"]), seg=6, rings=4)
    # reeds / grass along the shore
    for k in range(140):
        th = rnd.uniform(0, TAU)
        rr = rnd.uniform(1.0, 1.12)
        lx = math.cos(th) * rx * rr
        ly = math.sin(th) * ry * rr
        wx = lcx + lx * math.cos(ang0) - ly * math.sin(ang0)
        wy = lcy + lx * math.sin(ang0) + ly * math.cos(ang0)
        h = H(wx, wy)
        if h < C.LAKE_LEVEL - 0.3 or h > C.LAKE_LEVEL + 3.0:
            continue
        a.prop("SM_GrassClump_A", (*L(a, wx, wy), h), rnd.uniform(0, 360), rnd.uniform(1.0, 1.8))
    # benches along the lake walk
    for wx, wy, yaw in ((-30.0, 646.0, 10.0), (110.0, 606.0, 0.0), (232.0, 646.0, -30.0)):
        a.prop("SM_Bench", ground(a, wx, wy + 5.0), yaw + 180.0)
        a.special("clearing", ground(a, wx, wy + 5.0), radius=4.0)
    a.interact("sign", ground(a, -150.0, 712.0, 1.2), 0.0, title="Academy Lake",
               text="Fed by Volcano Falls. Rowing boats are available at the girls' dorm jetty - with permission.")
    a.prop("SM_Signpost", ground(a, -146.0, 712.0), 30.0)
    a.audio("A_Forest", (0, 0, C.LAKE_LEVEL + 5), radius=220.0, volume=0.6)
    return a


# --------------------------------------------------------------------------- cliffs (Sunset Point)
def build_cliffs():
    a = new_set("cliffs")
    end = C.PATHS[[p["id"] for p in C.PATHS].index("to_cliffs")]["pts"][-1]
    ex, ey = end
    base = H(ex, ey)
    # find the sea direction: steepest descent towards the west
    dpl = a.mesh("Cliffs_Viewpoint")
    lx, ly = L(a, ex, ey)
    yaw = -90.0   # frame rotated so local -Y points west, over the sea
    with dpl.at((lx, ly, base), rot=yaw):
        dpl.box((0, -3, -0.6), (10, 8, 1.4), "M_PierWood")
        for x in (-4.6, 4.6):
            for y in (-6.6, 0.6):
                dpl.box((x, y, -3.0), (0.3, 0.3, 5.0), "M_DarkWood")
        dpl.railing([(-5, -7, 0.1), (5, -7, 0.1)], 1.05, "M_DarkWood", post_spacing=1.25)
        dpl.railing([(-5, -7, 0.1), (-5, 0.5, 0.1)], 1.05, "M_DarkWood", post_spacing=1.25)
        dpl.railing([(5, -7, 0.1), (5, 0.5, 0.1)], 1.05, "M_DarkWood", post_spacing=1.25)
        # coin binoculars
        dpl.cylinder((2.5, -5.8, 0.1), 0.08, 1.1, "M_Metal", seg=8)
        with dpl.at((2.5, -5.8, 1.3), rot_x=10):
            dpl.box((0, 0, 0), (0.42, 0.3, 0.22), "M_ShipStripe")
            for sx in (-0.1, 0.1):
                dpl.cylinder((sx, -0.15, 0), 0.07, 0.25, "M_Black", seg=8)
    for bx in (-2.0, 2.0):
        ox, oy = rot2(bx, -3.0, yaw)
        a.prop("SM_Bench", (lx + ox, ly + oy, base + 0.1), yaw)
    ox, oy = rot2(-3.5, 1.5, yaw)
    a.interact("sign", (lx + ox, ly + oy, base + 1.4), yaw + 180.0, title="Sunset Point",
               text="The best sunset on the island. On a clear day you can almost see Domino City.")
    a.prop("SM_Signpost", (lx + ox, ly + oy, base), yaw + 180.0)
    a.audio("A_Ocean", (lx - 30, ly, base - 10), radius=150.0)
    a.audio("A_Wind", (lx, ly, base + 5), radius=80.0, volume=0.5)
    a.special("clearing", (lx, ly, base), radius=12.0)
    return a


# --------------------------------------------------------------------------- beach
def build_beach():
    a = new_set("beach")
    rnd = random.Random(8)
    seg = C.BEACH_SEGMENT
    spots = []
    for i in range(len(seg) - 1):
        ax, ay = seg[i]
        bx, by = seg[i + 1]
        for k in range(3):
            t = (k + 0.5) / 3
            px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            # move inland/outward until we are on dry sand (1.2 .. 3.5 m)
            cx, cy = 300.0, -200.0
            dirv = Vector((cx - px, cy - py, 0)).normalized()
            for s in range(0, 200):
                h = H(px, py)
                if h > 1.4:
                    break
                px += dirv.x
                py += dirv.y
            if 1.0 < H(px, py) < 6.0:
                spots.append((px, py, math.degrees(math.atan2(-dirv.y, -dirv.x))))
    for i, (px, py, yaw_sea) in enumerate(spots):
        lx, ly = L(a, px, py)
        z = H(px, py)
        a.prop("SM_BeachUmbrella", (lx, ly, z), rnd.uniform(0, 360))
        for s in (-1, 1):
            cxp = lx + math.cos(math.radians(yaw_sea + 90)) * 1.4 * s
            cyp = ly + math.sin(math.radians(yaw_sea + 90)) * 1.4 * s
            a.prop("SM_BeachChair", (cxp, cyp, H(px + cxp - lx, py + cyp - ly)), yaw_sea + 90)
        a.special("clearing", (lx, ly, z), radius=5.0)
    # lifeguard tower + volleyball net near the middle of the beach
    if spots:
        mx, my, yaw_sea = spots[len(spots) // 2]
        mx2, my2, _ = spots[min(len(spots) - 1, len(spots) // 2 + 2)]
        lg = a.mesh("Beach_Lifeguard")
        lx, ly = L(a, mx + 12, my + 6)
        z = H(mx + 12, my + 6)
        with lg.at((lx, ly, z), rot=yaw_sea + 90):
            for x in (-1.2, 1.2):
                for y in (-1.2, 1.2):
                    lg.beam((x, y, -0.5), (x * 0.8, y * 0.8, 3.0), 0.15, 0.15, "M_WindowFrame")
            lg.box((0, 0, 3.05), (2.6, 2.6, 0.15), "M_Wood")
            lg.railing([(-1.3, -1.3, 3.1), (1.3, -1.3, 3.1), (1.3, 1.3, 3.1), (-1.3, 1.3, 3.1)], 0.9, "M_WindowFrame")
            lg.box((0, 0, 4.4), (2.4, 2.4, 0.08), "M_LighthouseRed")
            for x in (-1.1, 1.1):
                for y in (-1.1, 1.1):
                    lg.box((x, y, 3.75), (0.08, 0.08, 1.3), "M_WindowFrame")
            lg.stairs((0, 2.4, 0), -90, 0.9, 12, 0.25, 0.2, "M_Wood", solid=False)
        a.special("clearing", (lx, ly, z), radius=6.0)
        net = a.mesh("Beach_Volleyball")
        nx, ny = L(a, mx2, my2)
        nz = H(mx2, my2)
        with net.at((nx, ny, nz), rot=yaw_sea):
            for y in (-4.5, 4.5):
                net.cylinder((0, y, -0.5), 0.06, 3.0, "M_Metal", seg=8)
            net.box((0, 0, 1.95), (0.02, 9.0, 0.9), "M_WindowFrame")
        a.special("clearing", (nx, ny, nz), radius=9.0)
        # beach duel court marked with rope posts
        bx, by, _ = spots[max(0, len(spots) // 2 - 2)]
        dx, dy = L(a, bx, by)
        dz = H(bx, by)
        court = a.mesh("Beach_DuelCourt_NoCol")
        with court.at((dx, dy, dz + 0.05), rot=yaw_sea):
            for (x0, y0, x1, y1) in ((-6, -10, 6, -10), (6, -10, 6, 10), (6, 10, -6, 10), (-6, 10, -6, -10)):
                court.beam((x0, y0, 0), (x1, y1, 0), 0.12, 0.02, "M_DuelFieldGlow")
        a.interact("duel_field", (dx, dy, dz), yaw_sea, title="Beach Duel Court",
                   text="Sand, sun and a holographic duel. What else do you need?")
        a.special("clearing", (dx, dy, dz), radius=13.0)
    a.interact("sign", ground(a, 640.0, -760.0, 1.2), 0.0, title="South-East Beach",
               text="White sand and warm water. No duelling in the water, please.")
    a.audio("A_Ocean", (0, 0, 2), radius=260.0)
    return a


# --------------------------------------------------------------------------- forest shrine
def build_forest():
    a = new_set("forest")
    wx, wy = 712.0, 348.0
    base = H(wx, wy)
    lx, ly = L(a, wx, wy)
    sh = a.mesh("Forest_Shrine")
    with sh.at((lx, ly, base), rot=-40):
        sh.box((0, 0, -0.8), (9, 9, 1.6), "M_OnsenRock")
        sh.stairs((0, -6.2, -0.8), 90, 3.0, 4, 0.2, 0.4, "M_OnsenRock")
        # small wooden shrine
        sh.box((0, 1.5, 0.6), (3.0, 2.4, 1.2), "M_DarkWood")
        sh.box((0, 1.5, 1.5), (2.6, 2.0, 0.6), "M_Wood")
        sh.gable_roof((0, 1.5, 1.8), 3.0, 2.4, 1.1, "M_OldRoof", overhang=0.6, thick=0.15, gable_mat="M_DarkWood")
        sh.box((0, 0.28, 1.0), (0.9, 0.05, 0.9), "M_Gold")
        # gate posts
        for x in (-1.8, 1.8):
            sh.cylinder((x, -3.6, 0.0), 0.16, 3.4, "M_LighthouseRed", seg=10)
        sh.box((0, -3.6, 3.25), (4.8, 0.3, 0.3), "M_LighthouseRed")
        sh.box((0, -3.6, 2.7), (4.0, 0.2, 0.2), "M_LighthouseRed")
    c = math.cos(math.radians(-40))
    s = math.sin(math.radians(-40))
    for x in (-2.5, 2.5):
        px, py = lx + x * c - (-1.2) * s, ly + x * s + (-1.2) * c
        a.prop("SM_StoneLantern", (px, py, base), -40)
    a.light((lx, ly, base + 2.0), color=(0.55, 0.85, 1.0), intensity=1500.0, radius=12.0, night_only=True)
    a.emitter("mist", (lx, ly, base + 0.5), scale=1.5, rate=0.5)
    a.interact("sign", (lx - 3.0 * s, ly + 3.0 * c, base + 1.0), -40, title="Forest Shrine",
               text="A tiny shrine hidden in the woods. Students leave their favourite cards here for luck - "
                    "some swear the cards whisper back.")
    a.special("clearing", (lx, ly, base), radius=10.0)
    a.audio("A_Forest", (lx, ly, base + 4), radius=200.0)
    return a


PLACEMENTS = {
    "volcano": build_volcano,
    "waterfall": build_waterfall,
    "lake": build_lake,
    "cliffs": build_cliffs,
    "beach": build_beach,
    "forest": build_forest,
}
