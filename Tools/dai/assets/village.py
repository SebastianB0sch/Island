"""
The three villages along the Academy River: Millbrook (water mill at the forest-path bridge), Willow Pond
(market square and jetty on the pond) and Fisher's Cove (net sheds, stilt huts and a pier at the river mouth).

Like features.py these AssetSets are ABSOLUTE in height (aset.absolute = True): local XY is relative to
config.LOCATIONS[key]["pos"], Z is the world height sampled from the terrain cache when the set is built -
nothing here hard-codes a height. Positions are authored as slots around the village centre and then settled:
a house, stall or person whose slot turns out to be in the water, on a path, on a steep bank or on top of
something already placed is moved to the nearest spot that is free (or dropped), so the villages survive the
river, the pads and the lanes being re-cut.

House kit (all closed: solid, a door leaf modelled shut - there are no interiors):
  cottage()      plastered / timber-framed / stone / plank walls, thatch or tile gable and hip roofs, chimney,
                 shuttered windows, porch, lean-to; every house on its own stone plinth down into the slope
  stilt_hut()    fisher's hut on a timber platform
plus the mill (wheel = its own mesh round the axle, turned by a "spinner" socket), wells, market stalls, a
jetty / pier builder, beached boats, net racks, woodpiles and vegetable plots.

Meshes: <Prefix>_House<n> / _Mill / _Square / _Jetty ... carry collision; <Prefix>_Detail_NoCol is the walk-
through dressing. Millbrook_MillWheel_NoCol is modelled round its own origin (axle along local Y) and must
only be placed by its spinner socket, never as a static mesh.
"""

import math
import os
import random

import numpy as np

from . import AssetSet
from .. import config as C
from .. import jsonio, palette, terrain
from .. import waterways as WW
from ..geo import MeshBuilder, TAU
from .props import blob

palette.register({
    # walls
    "M_VillagePlaster":   dict(kind="opaque", color=(0.93, 0.89, 0.78), rough=0.9, detail="Plaster", tiling=0.5),
    "M_VillageOchre":     dict(kind="opaque", color=(0.88, 0.72, 0.46), rough=0.9, detail="Plaster", tiling=0.5),
    "M_VillageRose":      dict(kind="opaque", color=(0.86, 0.68, 0.60), rough=0.9, detail="Plaster", tiling=0.5),
    "M_VillageStone":     dict(kind="opaque", color=(0.58, 0.55, 0.50), rough=0.95, detail="Bricks", tiling=0.6),
    "M_VillageStoneLight": dict(kind="opaque", color=(0.74, 0.71, 0.64), rough=0.9, detail="Rock", tiling=0.6),
    "M_VillageTimber":    dict(kind="opaque", color=(0.25, 0.17, 0.11), rough=0.9, detail="Planks", tiling=0.6),
    "M_VillagePlank":     dict(kind="opaque", color=(0.52, 0.42, 0.31), rough=0.95, detail="Planks", tiling=0.5),
    "M_VillagePlankGrey": dict(kind="opaque", color=(0.56, 0.55, 0.51), rough=0.95, detail="Planks", tiling=0.5),
    # roofs
    "M_Thatch":           dict(kind="opaque", color=(0.76, 0.64, 0.38), rough=1.0, detail="Grass", tiling=1.0),
    "M_ThatchDark":       dict(kind="opaque", color=(0.50, 0.41, 0.25), rough=1.0, detail="Grass", tiling=1.0),
    "M_VillageTile":      dict(kind="opaque", color=(0.70, 0.33, 0.19), rough=0.75, detail="RoofTiles", tiling=0.5),
    "M_VillageSlate":     dict(kind="opaque", color=(0.31, 0.34, 0.39), rough=0.7, detail="RoofTiles", tiling=0.5),
    # paint (doors, shutters, boats)
    "M_VillageGreen":     dict(kind="opaque", color=(0.20, 0.42, 0.30), rough=0.7, detail=None),
    "M_VillageBlue":      dict(kind="opaque", color=(0.22, 0.42, 0.64), rough=0.7, detail=None),
    "M_VillageRed":       dict(kind="opaque", color=(0.64, 0.17, 0.13), rough=0.7, detail=None),
    "M_VillageYellow":    dict(kind="opaque", color=(0.90, 0.72, 0.22), rough=0.7, detail=None),
    "M_VillageWhite":     dict(kind="opaque", color=(0.93, 0.92, 0.88), rough=0.7, detail=None),
    # cloth, nets, goods
    "M_AwningRed":        dict(kind="opaque", color=(0.74, 0.20, 0.15), rough=0.95, detail="Fabric", tiling=1.0),
    "M_AwningCream":      dict(kind="opaque", color=(0.93, 0.89, 0.76), rough=0.95, detail="Fabric", tiling=1.0),
    "M_AwningBlue":       dict(kind="opaque", color=(0.24, 0.42, 0.66), rough=0.95, detail="Fabric", tiling=1.0),
    "M_FishNet":          dict(kind="foliage", color=(0.38, 0.42, 0.34), rough=0.95, detail=None),
    "M_NetFloat":         dict(kind="opaque", color=(0.92, 0.48, 0.14), rough=0.6, detail=None),
    "M_Sack":             dict(kind="opaque", color=(0.74, 0.65, 0.48), rough=1.0, detail="Fabric", tiling=2.0),
    "M_GoodsOrange":      dict(kind="opaque", color=(0.94, 0.52, 0.12), rough=0.6, detail=None),
    "M_GoodsRed":         dict(kind="opaque", color=(0.80, 0.14, 0.12), rough=0.5, detail=None),
    "M_GoodsGreen":       dict(kind="opaque", color=(0.36, 0.62, 0.20), rough=0.6, detail=None),
    "M_GoodsBread":       dict(kind="opaque", color=(0.78, 0.56, 0.30), rough=0.9, detail=None),
    "M_GoodsFish":        dict(kind="opaque", color=(0.62, 0.69, 0.76), rough=0.3, metallic=0.4, detail=None),
    "M_Hay":              dict(kind="opaque", color=(0.84, 0.72, 0.36), rough=1.0, detail="Grass", tiling=1.0),
    "M_Cobble":           dict(kind="opaque", color=(0.62, 0.59, 0.54), rough=0.95, detail="Paving", tiling=0.7),
    "M_Rope":             dict(kind="opaque", color=(0.62, 0.50, 0.32), rough=0.95, detail="Fabric", tiling=1.0),
})

STONE, STONE_L, TIMBER = "M_VillageStone", "M_VillageStoneLight", "M_VillageTimber"
THATCH, THATCH_D, TILE, SLATE = "M_Thatch", "M_ThatchDark", "M_VillageTile", "M_VillageSlate"
PLANK, PLANK_G, DECK, DARK = "M_VillagePlank", "M_VillagePlankGrey", "M_PierWood", "M_DarkWood"
GLASS, GLOW, IRON, ROPE = "M_Glass", "M_LampGlow", "M_DarkMetal", "M_Rope"
PAINTS = ["M_VillageGreen", "M_VillageBlue", "M_VillageRed", "M_VillageYellow", "M_VillageWhite"]
WARM = (1.0, 0.74, 0.44)

# --------------------------------------------------------------------------- terrain / world helpers
_cache = {}


def _terrain():
    if "t" not in _cache:
        _cache["t"] = terrain.load_cached()
    return _cache["t"]


def H(x, y):
    return float(_terrain()[0](x, y))


def _paths():
    """[(xy array, half width)] of every path the terrain stage laid."""
    if "paths" not in _cache:
        out = []
        for p in _terrain()[3].get("paths", []):
            s = np.asarray(p["samples"], np.float64)[:, :2]
            out.append((s, float(p["width"]) / 2.0))
        _cache["paths"] = out
    return _cache["paths"]


def path_gap(x, y):
    """Metres from (x, y) to the edge of the nearest path (negative on it)."""
    best = 1e9
    for s, hw in _paths():
        d = float(np.min(np.hypot(s[:, 0] - x, s[:, 1] - y))) - hw
        best = min(best, d)
    return best


def nearest_path_point(x, y):
    best, pt = 1e9, (x, y)
    for s, hw in _paths():
        d = np.hypot(s[:, 0] - x, s[:, 1] - y)
        i = int(np.argmin(d))
        if d[i] < best:
            best, pt = float(d[i]), (float(s[i, 0]), float(s[i, 1]))
    return pt


def rot2(x, y, yaw_deg):
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    return x * c - y * s, x * s + y * c


def face_yaw(fx, fy):
    """Yaw (deg) that turns a model's front (-Y) towards the direction (fx, fy)."""
    return math.degrees(math.atan2(fx, -fy))


class Village:
    """An absolute AssetSet plus the bookkeeping that keeps things out of the water, off the paths and off
    each other. Coordinates passed in are village-local XY (relative to the location point)."""

    def __init__(self, key, prefix):
        self.key, self.prefix = key, prefix
        self.a = AssetSet(key)
        self.a.absolute = True
        self.ox, self.oy = C.LOCATIONS[key]["pos"]
        self.a.origin = (self.ox, self.oy)
        self.nc = self.a.mesh(f"{prefix}_Detail_NoCol")
        self.taken = []          # (lx, ly, r)
        self.n_house = 0
        self.rnd = random.Random(sum(ord(c) for c in key))
        self.log = []

    # ---- terrain
    def h(self, lx, ly):
        return H(self.ox + lx, self.oy + ly)

    def p(self, lx, ly, dz=0.0):
        return (lx, ly, self.h(lx, ly) + dz)

    def span(self, lx, ly, r, yaw=0.0, w=None, d=None):
        """(lowest, highest) ground under a footprint: a w x d box turned by yaw, or a disc of radius r."""
        pts = [(0.0, 0.0)]
        if w is not None:
            for sx in (-0.5, 0.0, 0.5):
                for sy in (-0.5, 0.0, 0.5):
                    pts.append(rot2(sx * w, sy * d, yaw))
        else:
            pts += [(math.cos(TAU * k / 8) * r, math.sin(TAU * k / 8) * r) for k in range(8)]
        hs = [self.h(lx + x, ly + y) for x, y in pts]
        return min(hs), max(hs)

    # ---- free ground
    def ok(self, lx, ly, r, water=2.0, path=0.5, max_dz=2.4, min_h=0.9):
        wx, wy = self.ox + lx, self.oy + ly
        for k in range(-1, 8):
            x, y = (wx, wy) if k < 0 else (wx + math.cos(TAU * k / 8) * r, wy + math.sin(TAU * k / 8) * r)
            if WW.clearance(x, y) < water or path_gap(x, y) < path or H(x, y) < min_h:
                return False
        lo, hi = self.span(lx, ly, r)
        if hi - lo > max_dz:
            return False
        return all(math.hypot(lx - tx, ly - ty) >= r + tr for tx, ty, tr in self.taken)

    def find(self, lx, ly, r, reach=14.0, **kw):
        """The free spot nearest to (lx, ly), or None."""
        if self.ok(lx, ly, r, **kw):
            return lx, ly
        rr = 1.0
        while rr <= reach:
            n = max(8, int(TAU * rr / 1.5))
            for k in range(n):
                x, y = lx + math.cos(TAU * k / n) * rr, ly + math.sin(TAU * k / n) * rr
                if self.ok(x, y, r, **kw):
                    return x, y
            rr += 1.0
        return None

    def claim(self, lx, ly, r, clearing=True):
        self.taken.append((lx, ly, r))
        if clearing:
            self.a.special("clearing", self.p(lx, ly), radius=r + 1.5)

    # ---- placing
    def prop(self, asset, lx, ly, yaw=0.0, scale=1.0, r=0.0, dz=0.0, search=True):
        """A catalog prop on the ground at (or near) the slot; returns its local position or None."""
        if r > 0.0:
            spot = self.find(lx, ly, r, reach=6.0) if search else ((lx, ly) if self.ok(lx, ly, r) else None)
            if spot is None:
                return None
            lx, ly = spot
            self.claim(lx, ly, r, clearing=r >= 1.0)
        pos = self.p(lx, ly, dz)
        self.a.prop(asset, pos, yaw, scale)
        return pos

    def person(self, lx, ly, yaw, dorm, wander=5.0):
        spot = self.find(lx, ly, 0.75, reach=5.0, max_dz=0.5)
        if spot is None:
            self.log.append(f"no room for an NPC near ({lx:.0f}, {ly:.0f})")
            return
        self.claim(spot[0], spot[1], 0.6, clearing=False)
        self.a.npc(self.p(*spot), yaw, dorm, wander)

    def fence(self, pts, asset="SM_Fence_Wood", seg_len=4.0):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            d = math.hypot(bx - ax, by - ay)
            n = max(1, int(round(d / seg_len)))
            yaw = math.degrees(math.atan2(by - ay, bx - ax))
            for k in range(n):
                t = (k + 0.5) / n
                x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                if WW.clearance(self.ox + x, self.oy + y) > 1.0 and path_gap(self.ox + x, self.oy + y) > 0.3:
                    self.a.prop(asset, self.p(x, y), yaw)

    def house(self, lx, ly, face, kind, seed, name=None, **kw):
        """Settle a cottage near the slot, facing `face` (a yaw in degrees, a local (x, y) to look at, or
        "path"). Returns dict(pos, yaw, floor, anchors -> local positions) or None when there is no room."""
        spec = dict(COTTAGES[kind], **kw)
        w, d = spec["w"], spec["d"]
        r = math.hypot(w, d) / 2.0 + 0.9
        spot = self.find(lx, ly, r, water=3.0, path=1.2)
        if spot is None:
            self.log.append(f"no room for a {kind} house near ({lx:.0f}, {ly:.0f})")
            return None
        lx, ly = spot
        if face == "path":
            px, py = nearest_path_point(self.ox + lx, self.oy + ly)
            face = (px - self.ox, py - self.oy)
        yaw = face_yaw(face[0] - lx, face[1] - ly) if isinstance(face, (tuple, list)) else float(face)
        lo, hi = self.span(lx, ly, r, yaw, w + 0.4, d + 0.4)
        floor = hi + 0.22
        self.n_house += 1
        mb = self.a.mesh(name or f"{self.prefix}_House{self.n_house}")
        fx, fy = rot2(spec.get("door_x", 0.0), -d / 2 - 1.2, yaw)
        step = floor - self.h(lx + fx, ly + fy)
        with mb.at((lx, ly, floor), rot=yaw), self.nc.at((lx, ly, floor), rot=yaw):
            anchors = cottage(mb, self.nc, seed=seed, drop=floor - lo + 0.9, step=step, **spec)
        self.claim(lx, ly, r - 0.4)
        out = {}
        for k, v in anchors.items():
            if isinstance(v, list):
                out[k] = [self._world(lx, ly, floor, yaw, q) for q in v]
            else:
                out[k] = self._world(lx, ly, floor, yaw, v)
        # life: a lantern by the door, a lit window, smoke from the chimney
        self.a.light(out["lamp"], color=WARM, intensity=900.0, radius=7.0, night_only=True)
        for q in out["windows"][:2]:
            self.a.light(q, color=(1.0, 0.70, 0.38), intensity=420.0, radius=4.5, night_only=True)
        if "chimney" in out and seed % 3 != 2:
            self.a.emitter("steam", out["chimney"], scale=0.75, rate=0.55)
        return dict(pos=(lx, ly), yaw=yaw, floor=floor, **out)

    @staticmethod
    def _world(lx, ly, z, yaw, q):
        x, y = rot2(q[0], q[1], yaw)
        return (lx + x, ly + y, z + q[2])

    def finish(self, audio=()):
        for line in self.log:
            print(f"   !! {self.key}: {line}")
        return self.a


# --------------------------------------------------------------------------- house kit
COTTAGES = {
    # w x d footprint, wall height, wall style, roof (kind, material)
    "thatch":   dict(w=7.2, d=5.4, wall_h=2.55, style="plaster", roof="gable", roof_mat=THATCH, chimney="end",
                     porch=True),
    "timber":   dict(w=7.6, d=5.8, wall_h=2.6, style="timber", roof="gable", roof_mat=TILE, chimney="end",
                     upper=2.2, lean_to="right"),
    "stone":    dict(w=6.6, d=6.2, wall_h=2.9, style="stone", roof="hip", roof_mat=SLATE, chimney="centre",
                     lean_to="left"),
    "long":     dict(w=10.0, d=5.2, wall_h=2.4, style="plaster", roof="gable", roof_mat=THATCH, chimney="end",
                     barn_door=True, door_x=-2.6),
    "plank":    dict(w=5.4, d=4.2, wall_h=2.3, style="plank", roof="gable", roof_mat=PLANK_G, chimney=None,
                     porch=False),
    "shed":     dict(w=4.6, d=3.6, wall_h=2.1, style="plank", roof="gable", roof_mat=THATCH_D, chimney=None,
                     windows=False),
}


def _faces(w, d):
    """Wall frames: name -> (offset, rot, length). Inside `at(offset, rot)` local X runs along the wall
    (centred) and local -Y points out of the house."""
    return {"front": ((0.0, -d / 2), 0.0, w), "right": ((w / 2, 0.0), 90.0, d),
            "back": ((0.0, d / 2), 180.0, w), "left": ((-w / 2, 0.0), -90.0, d)}


def _window(nc, u, z0, w, h, frame, shutter=None, box=None, rnd=None):
    """Window in a wall frame (see _faces): dark pane, frame with a glazing cross, sill, optional shutters
    and a flower box."""
    nc.box((u, -0.025, z0 + h / 2), (w, 0.05, h), GLASS, skip=("+y",))
    fw = 0.08
    for sx in (-1, 1):
        nc.box((u + sx * (w / 2 + fw / 2), -0.04, z0 + h / 2), (fw, 0.1, h + 2 * fw), frame, skip=("+y",))
    nc.box((u, -0.04, z0 + h + fw / 2), (w, 0.1, fw), frame, skip=("+y",))
    nc.box((u, -0.07, z0 - fw / 2), (w + 0.3, 0.18, fw), frame, skip=("+y",))
    nc.box((u, -0.055, z0 + h / 2), (0.04, 0.03, h), frame, skip=("+y",))
    nc.box((u, -0.055, z0 + h * 0.55), (w, 0.03, 0.04), frame, skip=("+y",))
    if shutter:
        sw = w * 0.5
        for sx in (-1, 1):
            cx = u + sx * (w / 2 + fw + sw / 2 + 0.02)
            nc.box((cx, -0.035, z0 + h / 2), (sw, 0.05, h + 0.04), shutter, skip=("+y",))
            for k in (0.22, 0.78):
                nc.box((cx, -0.065, z0 + h * k), (sw, 0.02, 0.07), TIMBER, skip=("+y",))
    if box:
        nc.box((u, -0.2, z0 - 0.2), (w + 0.16, 0.24, 0.2), DARK)
        nc.box((u, -0.2, z0 - 0.095), (w + 0.06, 0.16, 0.02), "M_Soil")
        n = max(3, int(w / 0.22))
        for k in range(n):
            x = u - w / 2 + w * (k + 0.5) / n
            nc.sphere((x, -0.2, z0 - 0.02), 0.1, "M_LeavesBush", seg=6, rings=4)
            nc.sphere((x + 0.03, -0.24, z0 + 0.06), 0.055, box[k % len(box)], seg=5, rings=4)


def _door(nc, u, w, h, leaf, frame, barn=False):
    """A shut door leaf in a wall frame, with frame, lintel, strap hinges and a handle."""
    fw = 0.12
    nc.box((u, -0.035, h / 2), (w, 0.07, h), leaf, skip=("+y",))
    for sx in (-1, 1):
        nc.box((u + sx * (w / 2 + fw / 2), -0.05, h / 2 + fw / 2), (fw, 0.14, h + fw), frame, skip=("+y",))
    nc.box((u, -0.05, h + fw / 2), (w + 2 * fw, 0.16, fw), frame, skip=("+y",))
    if barn:
        nc.box((u, -0.08, h / 2), (0.05, 0.03, h), TIMBER, skip=("+y",))          # the two leaves meet here
        for sx in (-1, 1):
            nc.beam((u + sx * 0.08, -0.08, 0.15), (u + sx * (w / 2 - 0.08), -0.08, h - 0.15), 0.03, 0.12, TIMBER)
            for k in (0.25, 0.8):
                nc.box((u + sx * w / 4, -0.085, h * k), (w / 2 - 0.1, 0.02, 0.09), IRON, skip=("+y",))
    else:
        for k in (0.2, 0.8):
            nc.box((u - w * 0.12, -0.08, h * k), (w * 0.7, 0.02, 0.07), IRON, skip=("+y",))
        for k in range(1, 4):
            nc.box((u - w / 2 + w * k / 4, -0.075, h / 2), (0.02, 0.012, h - 0.06), TIMBER, skip=("+y",))
        nc.sphere((u + w * 0.33, -0.11, h * 0.48), 0.045, "M_Gold", seg=6, rings=4)


def _lantern(nc, x, y, z, out=(0.0, -1.0)):
    """Wall lantern on a bracket; (out) = direction away from the wall. Returns the glass position."""
    gx, gy = x + out[0] * 0.3, y + out[1] * 0.3
    nc.beam((x, y, z + 0.22), (gx, gy, z + 0.22), 0.04, 0.04, IRON)
    nc.box((gx, gy, z + 0.17), (0.2, 0.2, 0.03), IRON)
    nc.box((gx, gy, z), (0.15, 0.15, 0.28), GLOW)
    nc.box((gx, gy, z - 0.16), (0.2, 0.2, 0.03), IRON)
    return (gx, gy, z)


def _roof_z(roof, w, d, wall_h, rh, x, y):
    """Height of the roof surface over (x, y) (ridge along X)."""
    f = 1.0 - min(abs(y) / (d / 2), 1.0)
    if roof == "hip":
        ridge = max(0.0, (w - d) / 2)
        f = min(f, 1.0 - min(max(abs(x) - ridge, 0.0) / (d / 2), 1.0))
    return wall_h + rh * f


def cottage(mb, nc, w, d, wall_h, style, roof, roof_mat, seed=0, drop=1.2, step=0.3, chimney="end", porch=False,
            lean_to=None, upper=0.0, barn_door=False, door_x=None, windows=True, plinth=True):
    """One cottage in its own frame: origin = centre of the footprint at floor level, front (door) facing -Y.
    drop = how far the plinth goes down, step = floor height above the ground in front of the door.
    Returns anchors (house-local): lamp, door, windows [..], chimney."""
    rnd = random.Random(seed * 7919 + int(w * 10))
    wall = {"plaster": rnd.choice(["M_VillagePlaster", "M_VillageOchre", "M_VillageRose", "M_VillagePlaster"]),
            "timber": "M_VillagePlaster", "stone": STONE, "plank": rnd.choice([PLANK, PLANK_G])}[style]
    paint = rnd.choice(PAINTS[:4])
    paint2 = rnd.choice([p for p in PAINTS if p != paint])
    frame = TIMBER if style in ("timber", "plank") else "M_VillageWhite"
    flowers = [rnd.choice(["M_FlowerRed", "M_FlowerYellow", "M_FlowerBlue", "M_FlowerWhite"]) for _ in range(3)]
    thatch = roof_mat in (THATCH, THATCH_D)
    over = 0.6 if thatch else 0.45
    pitch = 1.08 if thatch else (0.62 if roof == "hip" else 0.78)
    total_h = wall_h + upper
    rh = d / 2 * pitch
    if door_x is None:
        door_x = rnd.choice([-0.22, 0.0, 0.22]) * w
    anchors = dict(windows=[])

    # ---- plinth, walls
    if plinth:
        mb.box_mm((-w / 2 - 0.18, -d / 2 - 0.18, -drop), (w / 2 + 0.18, d / 2 + 0.18, 0.0), STONE, skip=("-z",))
    mb.box_mm((-w / 2, -d / 2, 0.0), (w / 2, d / 2, wall_h), wall, skip=("-z", "+z") if upper else ("-z",))
    uw, ud = w, d
    if upper:                                    # jettied upper storey
        uw, ud = w + 0.5, d + 0.5
        mb.box_mm((-uw / 2, -ud / 2, wall_h), (uw / 2, ud / 2, total_h), wall, skip=())
        for k in range(int(uw / 0.9) + 1):       # joist ends under the jetty
            x = -uw / 2 + 0.15 + (uw - 0.3) * k / int(uw / 0.9)
            for sy in (-1, 1):
                nc.box((x, sy * (ud / 2 - 0.12), wall_h - 0.09), (0.14, 0.3, 0.18), TIMBER)
    # ---- roof
    if roof == "hip":
        mb.hip_roof((0, 0, total_h), uw, ud, rh, roof_mat, overhang=over, thick=0.4 if thatch else 0.22)
        ridge_half = max(0.0, (uw - ud) / 2)
    else:
        mb.gable_roof((0, 0, total_h), uw, ud, rh, roof_mat, overhang=over, thick=0.4 if thatch else 0.2,
                      gable_mat=wall)
        ridge_half = uw / 2 + over
    if thatch:
        with nc.at((0, 0, total_h + rh - 0.12), rot_x=45):
            nc.box((0, 0, 0), (2 * ridge_half + 0.1, 0.5, 0.5), THATCH_D)
        for k in range(int(2 * ridge_half / 0.9)):        # hazel spars pinning the ridge
            x = -ridge_half + 0.45 + 0.9 * k
            for sy in (-1, 1):
                nc.beam((x, sy * 0.05, total_h + rh + 0.2), (x, sy * 0.5, total_h + rh - 0.28), 0.04, 0.04, TIMBER)
    elif ridge_half > 0.05:
        nc.box((0, 0, total_h + rh + 0.03), (2 * ridge_half + 0.1, 0.26, 0.14), roof_mat)
    if roof == "gable" and not thatch:                    # barge boards
        for sx in (-1, 1):
            for sy in (-1, 1):
                nc.beam((sx * (uw / 2 + over + 0.02), sy * (ud / 2 + over), total_h - rh * over / (ud / 2) - 0.1),
                        (sx * (uw / 2 + over + 0.02), 0, total_h + rh - 0.1), 0.05, 0.22, frame)

    # ---- wall dressing per style
    faces = _faces(w, d)
    for name, ((ox, oy), rot, ln) in faces.items():
        with nc.at((ox, oy, 0.0), rot=rot):
            if style == "timber":
                n = max(2, int(round(ln / 1.9)))
                for k in range(n + 1):
                    nc.box((-ln / 2 + ln * k / n, -0.035, wall_h / 2), (0.16, 0.07, wall_h), TIMBER, skip=("+y",))
                for z in (0.09, 1.0, wall_h - 0.09):
                    nc.box((0, -0.03, z), (ln, 0.06, 0.16), TIMBER, skip=("+y",))
                for sx in (-1, 1):
                    nc.beam((sx * (ln / 2 - 0.1), -0.04, 1.05), (sx * (ln / 2 - ln / n + 0.1), -0.04, wall_h - 0.15),
                            0.05, 0.14, TIMBER)
            elif style == "stone":
                for sx in (-1, 1):                         # quoins
                    for k in range(int(wall_h / 0.36)):
                        lw = 0.5 if k % 2 == 0 else 0.3
                        nc.box((sx * (ln / 2 - lw / 2 + 0.02), -0.03, 0.18 + 0.36 * k), (lw, 0.07, 0.32), STONE_L,
                               skip=("+y",))
            elif style == "plank":
                n = max(3, int(ln / 0.42))
                for k in range(n + 1):
                    nc.box((-ln / 2 + ln * k / n, -0.02, wall_h / 2), (0.05, 0.04, wall_h), TIMBER, skip=("+y",))
            else:                                           # plaster: a tarred plinth band
                nc.box((0, -0.02, 0.2), (ln, 0.04, 0.4), STONE, skip=("+y",))
        if upper:
            ux, uy = (ox * uw / w, oy * ud / d)
            uln = ln + 0.5
            with nc.at((ux, uy, wall_h), rot=rot):
                n = max(2, int(round(uln / 1.5)))
                for k in range(n + 1):
                    nc.box((-uln / 2 + uln * k / n, -0.035, upper / 2), (0.15, 0.07, upper), TIMBER, skip=("+y",))
                for z in (0.08, upper - 0.08):
                    nc.box((0, -0.03, z), (uln, 0.06, 0.16), TIMBER, skip=("+y",))
                for k in range(n):
                    a = -uln / 2 + uln * k / n + 0.1
                    b = -uln / 2 + uln * (k + 1) / n - 0.1
                    if k % 2 == 0:
                        nc.beam((a, -0.04, 0.2), (b, -0.04, upper - 0.2), 0.05, 0.12, TIMBER)
                if name in ("front", "back"):
                    for k in range(n):
                        if k % 2 == 1 or n == 2:
                            u = -uln / 2 + uln * (k + 0.5) / n
                            _window(nc, u, 0.75, 0.7, 0.9, frame, shutter=paint)
                            if name == "front":
                                q = rot2(u, -0.5, rot)
                                anchors["windows"].append((ux + q[0], uy + q[1], wall_h + 1.2))

    # ---- door + windows
    dw, dh = (1.9, 2.1) if barn_door else (0.95, 2.0)
    with nc.at((0, -d / 2, 0.0)):
        _door(nc, door_x, dw, dh, paint, frame, barn=barn_door)
        if not porch:
            nc.box((door_x, -0.3, dh + 0.32), (dw + 0.7, 0.6, 0.06), roof_mat if not thatch else TIMBER)   # hood
            for sx in (-1, 1):
                nc.beam((door_x + sx * (dw / 2 + 0.25), -0.02, dh - 0.1), (door_x + sx * (dw / 2 + 0.25), -0.5, dh + 0.28),
                        0.05, 0.05, TIMBER)
    lamp_x = door_x + (dw / 2 + 0.45) * (1 if door_x <= 0 else -1)
    anchors["lamp"] = _lantern(nc, lamp_x, -d / 2, 1.9)
    anchors["door"] = (door_x, -d / 2 - 1.3, -step)
    if windows:
        sill, wh = 0.95, 0.95
        for name, ((ox, oy), rot, ln) in faces.items():
            spots = []
            n = max(1, int((ln - 1.2) / 2.3))
            for k in range(n):
                u = -ln / 2 + ln * (k + 0.5) / n
                if name == "front" and abs(u - door_x) < dw / 2 + 0.95:
                    continue
                if lean_to and name == lean_to:
                    continue
                if chimney == "end" and name == "right" and abs(u) < 0.9:
                    continue
                spots.append(u)
            with nc.at((ox, oy, 0.0), rot=rot):
                for i, u in enumerate(spots):
                    _window(nc, u, sill, 0.85, wh, frame, shutter=paint2 if style != "plank" else None,
                            box=flowers if (name == "front" and style != "plank") else None)
            if name in ("front", "left"):
                for u in spots:
                    q = rot2(u, -0.5, rot)
                    anchors["windows"].append((ox + q[0], oy + q[1], sill + wh / 2))
    if not anchors["windows"]:
        anchors["windows"].append((door_x, -d / 2 - 0.6, 1.6))

    # ---- stone landing at the door and steps down to the ground, porch
    if plinth:
        sw = dw + 0.9
        y_land = -d / 2 - 0.18
        mb.box_mm((door_x - sw / 2, y_land - 0.9, -drop), (door_x + sw / 2, y_land, 0.0), STONE_L, skip=("-z",))
        n_rise = int(math.ceil(max(step - 0.02, 0.0) / 0.19))
        for k in range(1, n_rise):
            mb.box_mm((door_x - sw / 2, y_land - 0.9 - 0.32 * k, -drop),
                      (door_x + sw / 2, y_land - 0.9 - 0.32 * (k - 1), -step * k / n_rise), STONE_L, skip=("-z",))
    if porch:
        py = -d / 2 - 0.95
        for sx in (-1, 1):
            mb.box((door_x + sx * 0.95, py, 1.1), (0.14, 0.14, 2.2), TIMBER)
            nc.beam((door_x + sx * 0.95, py, 1.75), (door_x + sx * 0.5, py, 2.18), 0.06, 0.08, TIMBER)
        mb.gable_roof((door_x, -d / 2 - 0.5, 2.2), 2.3, 1.2, 0.75, roof_mat, overhang=0.18,
                      thick=0.22 if thatch else 0.12, ridge_axis="y")

    # ---- chimney
    if chimney:
        cx, cy = (w / 2 - 0.55, d * 0.12) if chimney == "end" else (0.0, 0.0)
        top = max(_roof_z(roof, uw, ud, total_h, rh, cx, cy) + 1.0, total_h + rh + 0.45)
        mb.box_mm((cx - 0.38, cy - 0.38, total_h - 0.4), (cx + 0.38, cy + 0.38, top), STONE)
        mb.box((cx, cy, top + 0.06), (0.96, 0.96, 0.12), STONE_L)
        nc.cylinder((cx, cy, top + 0.12), 0.16, 0.32, "M_VillageTile", seg=8)
        anchors["chimney"] = (cx, cy, top + 0.7)

    # ---- lean-to (wood store) on one gable end
    if lean_to:
        sx = 1 if lean_to == "right" else -1
        x0, x1 = sx * w / 2, sx * (w / 2 + 2.1)
        yb, yf = d / 2 - 0.6, -d / 2 + 1.2
        mb.ramp((x0, (yb + yf) / 2, 2.25), (x1 + sx * 0.25, (yb + yf) / 2, 1.6), yb - yf + 0.5,
                roof_mat if not thatch else THATCH_D, thick=0.12)
        for y in (yb, yf):
            mb.box((x1, y, 0.8 - drop / 2), (0.14, 0.14, 1.6 + drop), TIMBER)
        mb.box_mm((min(x0, x1), yb - 0.06, -drop), (max(x0, x1), yb + 0.06, 1.75), PLANK, skip=("-z",))     # back wall
        mb.box_mm((min(x0, x1), yf, -drop), (max(x0, x1), yb, 0.0), STONE, skip=("-z",))                    # floor
        woodpile(mb, nc, (x0 + sx * 1.0, (yb + yf) / 2 + 0.5, 0.0), 1.5, 1.15, rot=90.0)
    return anchors


def woodpile(mb, nc, pos, length, height, rot=0.0):
    """Stacked firewood: a solid block with the log ends showing on both faces."""
    with mb.at(pos, rot=rot), nc.at(pos, rot=rot):
        mb.box((0, 0, height / 2), (length, 0.55, height), DARK)
        rows = int(height / 0.2)
        cols = int(length / 0.2)
        for j in range(rows):
            for i in range(cols):
                x = -length / 2 + 0.1 + (length - 0.2) * (i + (0.5 if j % 2 else 0.0)) / cols
                if abs(x) > length / 2 - 0.08:
                    continue
                for sy in (-1, 1):
                    with nc.at((x, sy * 0.28, 0.1 + j * 0.2), rot_x=90.0 * sy):
                        nc.cylinder((0, 0, 0), 0.09, 0.03, "M_Wood", seg=6, cap_mat="M_VillagePlank")


def well(mb, nc, pos, roof_mat=TILE):
    """Round stone well with a windlass under a little roof."""
    x, y, z = pos
    mb.lathe([(1.05, -0.8), (1.05, 0.0), (0.98, 0.78), (0.72, 0.78), (0.72, -0.2)], STONE, seg=14, cap_top=False,
             cap_bottom=False, center=(x, y, z), smooth=False)
    mb.lathe([(1.02, 0.78), (1.02, 0.9), (0.68, 0.9), (0.68, 0.78)], STONE_L, seg=14, cap_top=False, cap_bottom=False,
             center=(x, y, z), smooth=False)
    nc.poly([(x + math.cos(TAU * i / 14) * 0.72, y + math.sin(TAU * i / 14) * 0.72, z + 0.25) for i in range(14)],
            "M_FountainWater")
    for sx in (-1, 1):
        mb.box((x + sx * 1.0, y, z + 1.25), (0.14, 0.14, 2.5), TIMBER)
    mb.gable_roof((x, y, z + 2.45), 2.4, 1.5, 0.7, roof_mat, overhang=0.15, thick=0.14)
    with nc.at((x, y, z + 1.75), rot_y=90):
        nc.cylinder((0, 0, -0.95), 0.09, 1.9, DARK, seg=8)
    nc.beam((x + 1.0, y, z + 1.75), (x + 1.3, y, z + 1.55), 0.04, 0.04, IRON)
    nc.box((x + 0.1, y, z + 1.42), (0.02, 0.02, 0.5), ROPE)
    nc.cylinder((x + 0.1, y, z + 0.92), 0.16, 0.28, DARK, seg=8, radius_top=0.19)


def stall(mb, nc, pos, yaw, awning, goods="fruit", seed=0):
    """Market stall: trestle table, four posts, striped awning sloping to the front (-Y), goods on display."""
    rnd = random.Random(seed)
    with mb.at(pos, rot=yaw), nc.at(pos, rot=yaw):
        mb.box((0, 0, 0.84), (2.6, 1.1, 0.07), "M_Wood")
        mb.box((0, 0, 0.42), (2.4, 0.9, 0.78), DARK, skip=("+z",))
        for sx in (-1, 1):
            mb.box((sx * 1.3, 0.6, 1.2), (0.09, 0.09, 2.4), TIMBER)
            mb.box((sx * 1.3, -0.6, 1.0), (0.09, 0.09, 2.0), TIMBER)
        n = 6
        for k in range(n):
            x0, x1 = -1.5 + 3.0 * k / n, -1.5 + 3.0 * (k + 1) / n
            mat = awning if k % 2 == 0 else "M_AwningCream"
            a, b, c, e = (x0, -0.95, 1.95), (x1, -0.95, 1.95), (x1, 0.75, 2.45), (x0, 0.75, 2.45)
            nc.quad(a, b, c, e, mat)
            nc.quad(e, c, b, a, mat)
            nc.quad((x0, -0.95, 1.95), (x0, -0.95, 1.72), (x1, -0.95, 1.72), (x1, -0.95, 1.95), mat)       # valance
            nc.quad((x1, -0.95, 1.95), (x1, -0.95, 1.72), (x0, -0.95, 1.72), (x0, -0.95, 1.95), mat)
        palette_ = dict(fruit=["M_GoodsOrange", "M_GoodsRed", "M_GoodsGreen", "M_VillageYellow"],
                        bread=["M_GoodsBread", "M_GoodsBread", "M_Sack"],
                        fish=["M_GoodsFish", "M_GoodsFish", "M_VillageBlue"],
                        cloth=["M_AwningRed", "M_AwningBlue", "M_AwningCream", "M_VillageGreen"])[goods]
        for k in range(4):                                         # shallow boxes of wares
            cx = -0.95 + 0.63 * k
            nc.box((cx, 0.0, 0.93), (0.56, 0.8, 0.12), "M_VillagePlank", skip=("-z",))
            mat = palette_[k % len(palette_)]
            if goods == "fruit":
                for i in range(3):
                    for j in range(4):
                        nc.sphere((cx - 0.17 + 0.17 * i, -0.27 + 0.18 * j, 1.03 + rnd.uniform(0, 0.03)), 0.085, mat,
                                  seg=6, rings=4)
            elif goods == "bread":
                for j in range(4):
                    nc.sphere((cx, -0.27 + 0.18 * j, 1.03), 0.1, mat, seg=6, rings=4, scale=(2.2, 0.8, 0.7))
            elif goods == "fish":
                nc.box((cx, 0.0, 1.0), (0.5, 0.74, 0.03), "M_VillageWhite")
                for j in range(4):
                    with nc.at((cx, -0.27 + 0.18 * j, 1.04), rot=rnd.uniform(-20, 20)):
                        nc.sphere((0, 0, 0), 0.07, mat, seg=6, rings=4, scale=(3.0, 0.9, 0.6))
            else:
                for j in range(3):
                    nc.box((cx, -0.24 + 0.24 * j, 1.02 + 0.03 * j), (0.5, 0.22, 0.06), palette_[(k + j) % len(palette_)])
        # a crate and a basket beside the stall
        nc.box((1.75, 0.2, 0.25), (0.55, 0.55, 0.5), "M_VillagePlank")
        nc.cylinder((-1.75, -0.1, 0.0), 0.3, 0.36, "M_Hay", seg=10, radius_top=0.36)
        for i in range(5):
            nc.sphere((-1.75 + rnd.uniform(-0.15, 0.15), -0.1 + rnd.uniform(-0.15, 0.15), 0.4), 0.09, palette_[i % len(palette_)],
                      seg=6, rings=4)


def boat(mb, pos, yaw, heel, hull, seed=0, length=4.2):
    """Clinker rowing boat lying on the ground, heeled over on its bilge (a model, not the floating prop)."""
    with mb.at(pos, rot=yaw, rot_x=heel):
        n = 9
        outer, inner = [], []
        for i in range(n):
            t = i / (n - 1)
            x = (t - 0.5) * length
            b = 0.78 * (1.0 - abs(2 * t - 1) ** 2.6) + 0.03
            hgt = 0.62 + 0.14 * abs(2 * t - 1) ** 2
            keel = 0.06 * abs(2 * t - 1) ** 2 * 3
            outer.append([(x, -b, hgt), (x, -b * 0.82, hgt * 0.42 + keel), (x, 0.0, keel),
                          (x, b * 0.82, hgt * 0.42 + keel), (x, b, hgt)])
            bi = max(b - 0.05, 0.01)
            inner.append([(x, -bi, hgt), (x, -bi * 0.8, hgt * 0.42 + keel + 0.05), (x, 0.0, keel + 0.05),
                          (x, bi * 0.8, hgt * 0.42 + keel + 0.05), (x, bi, hgt)])
        mb.grid_faces(outer, hull, smooth=True, flip=True)
        mb.grid_faces(inner, "M_Wood", smooth=True)
        for i in range(n - 1):                      # gunwale
            for s in (0, 4):
                a, b_ = outer[i][s], outer[i + 1][s]
                mb.beam((a[0], a[1], a[2]), (b_[0], b_[1], b_[2]), 0.07, 0.05, "M_VillageWhite")
        for x in (-0.9, 0.3, 1.3):
            t = x / length + 0.5
            b = 0.74 * (1.0 - abs(2 * t - 1) ** 2.6)
            mb.box((x, 0, 0.42), (0.24, 2 * b, 0.04), "M_Wood")


def net_rack(mb, nc, pos, yaw, length=4.5, seed=0):
    """Drying rack: two trestles and a pole with a fishing net hung over it, cork floats along its foot."""
    rnd = random.Random(seed)
    with mb.at(pos, rot=yaw), nc.at(pos, rot=yaw):
        for sx in (-1, 1):
            x = sx * length / 2
            mb.beam((x, -0.55, -0.3), (x, 0.0, 1.95), 0.09, 0.09, TIMBER)
            mb.beam((x, 0.55, -0.3), (x, 0.0, 1.95), 0.09, 0.09, TIMBER)
        mb.beam((-length / 2 - 0.25, 0, 1.92), (length / 2 + 0.25, 0, 1.92), 0.08, 0.08, DARK)
        n = 10
        for side in (-1, 1):
            rows = []
            for j in range(5):
                t = j / 4
                y = side * (0.05 + 0.75 * t ** 1.4)
                z = 1.95 - 1.7 * t
                rows.append([(-length / 2 + 0.2 + (length - 0.4) * i / n, y + 0.06 * math.sin(i * 1.7 + j), z
                              - 0.05 * math.sin(i * 0.9)) for i in range(n + 1)])
            nc.grid_faces(rows, "M_FishNet", smooth=True)
            for i in range(0, n + 1, 2):
                p = rows[-1][i]
                nc.sphere((p[0], p[1], p[2] - 0.02), 0.07, "M_NetFloat", seg=6, rings=4)
        if rnd.random() < 0.7:
            nc.cylinder((length / 2 + 0.7, 0.3, 0.0), 0.32, 0.12, ROPE, seg=10)       # coiled rope


def pier(v, mb, nc, start, yaw, length, deck_z, width=2.4, tee=0.0, floor=None, rail="left", lantern=True):
    """Timber jetty from the local point `start` along yaw: one deck slab at deck_z (the walking surface) on
    pairs of piles driven into the bed (floor(x, y) -> bed height, default the terrain). Returns the local
    position of its end."""
    floor = floor or (lambda lx, ly: v.h(lx, ly))
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def W(u, t=0.0):
        return start[0] + c * u - s * t, start[1] + s * u + c * t

    with mb.at((start[0], start[1], deck_z), rot=yaw), nc.at((start[0], start[1], deck_z), rot=yaw):
        mb.box((length / 2, 0, -0.06), (length, width, 0.12), DECK)
        for k in range(1, int(length / 0.3)):
            nc.box((0.3 * k, 0, 0.002), (0.02, width - 0.1, 0.004), DARK, skip=("-z",))
        for sy in (-1, 1):
            mb.box((length / 2, sy * (width / 2 - 0.08), -0.24), (length, 0.16, 0.24), DARK)
        n = max(2, int(round(length / 3.0)) + 1)
        for k in range(n):
            u = 0.25 + (length - 0.5) * k / (n - 1)
            mb.box((u, 0, -0.2), (0.2, width + 0.5, 0.2), TIMBER)
            for sy in (-1, 1):
                x, y = W(u, sy * (width / 2 + 0.12))
                bed = min(floor(x, y), deck_z - 0.6) - 1.3
                top = 0.9 if (k == n - 1 or (k % 2 == 0 and sy < 0 and rail == "posts")) else 0.05
                mb.box((u, sy * (width / 2 + 0.12), (top + bed - deck_z) / 2), (0.22, 0.22, top - (bed - deck_z)), TIMBER)
        if rail in ("left", "right"):
            sy = 1 if rail == "left" else -1
            pts = [(0.3, sy * (width / 2 - 0.1), 0.0), (length - 0.3, sy * (width / 2 - 0.1), 0.0)]
            mb.railing(pts, 1.05, TIMBER, post_spacing=2.2, post_size=0.1, rail_size=0.08)
        if tee > 0.0:
            mb.box((length + 1.2, 0, -0.06), (2.4, tee, 0.12), DECK)
            for sy in (-1, 1):
                for sx in (0.15, 2.25):
                    x, y = W(length + sx, sy * (tee / 2 - 0.15))
                    bed = min(floor(x, y), deck_z - 0.6) - 1.3
                    mb.box((length + sx, sy * (tee / 2 - 0.15), (0.75 + bed - deck_z) / 2), (0.22, 0.22, 0.75 - (bed - deck_z)),
                           TIMBER)
            nc.cylinder((length + 1.9, tee / 2 - 0.7, 0.0), 0.3, 0.1, ROPE, seg=10)
        end_u = length + (2.4 if tee > 0 else 0.0)
        lamp = None
        if lantern:
            lx_, ly_ = length - 0.2, (width / 2 + 0.12)
            mb.box((lx_, ly_, 1.3), (0.12, 0.12, 2.6), TIMBER)
            lamp = _lantern(nc, lx_, ly_, 2.3, out=(0.0, -1.0))
    if lamp:
        q = rot2(lamp[0], lamp[1], yaw)
        v.a.light((start[0] + q[0], start[1] + q[1], deck_z + lamp[2]), color=WARM, intensity=1400.0, radius=10.0,
                  night_only=True)
    ex, ey = W(end_u - 1.2)
    return (ex, ey, deck_z)


def steps(v, mb, nc, p0, p1, width=1.6, rail=True):
    """Timber steps down a bank from local p0 to p1: one tread every 0.36 m, each set on the ground under it."""
    (x0, y0), (x1, y1) = p0, p1
    ln = math.hypot(x1 - x0, y1 - y0)
    yaw = math.degrees(math.atan2(y1 - y0, x1 - x0))
    n = max(2, int(ln / 0.36))
    zs = []
    for k in range(n):
        t = (k + 0.5) / n
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        ox, oy = rot2(0.0, width / 2, yaw)
        zs.append(max(v.h(x, y), v.h(x + ox, y + oy), v.h(x - ox, y - oy)) + 0.06)
    for k in range(1, n):                       # never step up on the way down, never a riser over 0.2 m
        zs[k] = min(zs[k], zs[k - 1])
    for k in range(n - 2, -1, -1):
        zs[k] = min(zs[k], zs[k + 1] + 0.2)
    for k in range(n):
        t = (k + 0.5) / n
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        with mb.at((x, y, zs[k]), rot=yaw):
            mb.box((0, 0, -0.3), (ln / n + 0.02, width, 0.6), DECK)
            mb.box((ln / n / 2 - 0.02, 0, -0.06), (0.05, width + 0.06, 0.12), DARK)
    if rail:
        ox, oy = rot2(0.0, width / 2 + 0.08, yaw)
        prev = None
        for k in range(0, n, max(1, n // max(2, int(ln / 2.2)))):
            t = (k + 0.5) / n
            x, y = x0 + (x1 - x0) * t + ox, y0 + (y1 - y0) * t + oy
            mb.box((x, y, zs[k] + 0.5), (0.1, 0.1, 1.1), TIMBER)
            if prev:
                nc.beam(prev, (x, y, zs[k] + 1.0), 0.07, 0.07, TIMBER)
            prev = (x, y, zs[k] + 1.0)
    return zs[0], zs[-1]


def veg_plot(v, mb, nc, lx, ly, yaw, w=6.0, d=4.0, seed=0):
    """Fenced vegetable plot: raised soil beds with rows of greens, pumpkins and bean poles."""
    spot = v.find(lx, ly, math.hypot(w, d) / 2 + 0.3, reach=8.0, max_dz=0.8)
    if spot is None:
        return None
    lx, ly = spot
    rnd = random.Random(seed)
    z = v.span(lx, ly, 1.0)[1]
    with mb.at((lx, ly, z), rot=yaw), nc.at((lx, ly, z), rot=yaw):
        rows = 4
        for j in range(rows):
            y = -d / 2 + 0.55 + (d - 1.1) * j / (rows - 1)
            nc.box((0, y, 0.06), (w - 0.9, 0.6, 0.16), "M_Soil")
            kind = (j + seed) % 3
            for i in range(int((w - 1.2) / 0.5)):
                x = -w / 2 + 0.75 + 0.5 * i
                if kind == 0:
                    nc.sphere((x, y, 0.22), 0.16, "M_GoodsGreen", seg=6, rings=4, scale=(1, 1, 0.8))
                elif kind == 1:
                    nc.cone((x, y, 0.12), 0.14, 0.42, "M_LeavesBush", seg=5)
                elif i % 3 == 0:
                    nc.sphere((x, y + rnd.uniform(-0.1, 0.1), 0.26), 0.2, "M_GoodsOrange", seg=7, rings=4, scale=(1, 1, 0.75))
                else:
                    nc.sphere((x, y, 0.18), 0.13, "M_LeavesBush", seg=5, rings=4, scale=(1.6, 1.2, 0.5))
        for i in range(4):                                   # bean poles along the back
            x = -w / 2 + 1.0 + (w - 2.0) * i / 3
            nc.beam((x - 0.25, d / 2 - 0.45, 0.1), (x, d / 2 - 0.3, 1.9), 0.03, 0.03, TIMBER)
            nc.beam((x + 0.25, d / 2 - 0.45, 0.1), (x, d / 2 - 0.3, 1.9), 0.03, 0.03, TIMBER)
            nc.cone((x, d / 2 - 0.38, 0.2), 0.3, 1.4, "M_LeavesBush", seg=6)
    hw, hd = w / 2 + 0.2, d / 2 + 0.2
    corners = [rot2(sx, sy, yaw) for sx, sy in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))]
    corners = [(lx + x, ly + y) for x, y in corners]
    v.fence([corners[1], corners[2], corners[3], corners[0]])     # open towards the front
    v.claim(lx, ly, math.hypot(w, d) / 2)
    return lx, ly


def sign(v, mb, lx, ly, yaw, title, text, lines=None, r=0.9):
    """Wooden notice board with a text and an interact prompt."""
    spot = v.find(lx, ly, r, reach=6.0, max_dz=0.6)
    if spot is None:
        return
    lx, ly = spot
    z = v.h(lx, ly)
    with mb.at((lx, ly, z), rot=yaw):
        mb.sign_board((0, 0, 1.45), 1.7, 0.95, "M_VillagePlank", TIMBER, posts=True, post_mat=TIMBER)
        mb.gable_roof((0, 0, 2.02), 1.9, 0.3, 0.2, THATCH_D, overhang=0.1, thick=0.06)
    ox, oy = rot2(0.0, -0.08, yaw)
    for i, line in enumerate(lines or [title.upper()]):
        v.a.text(line, (lx + ox, ly + oy, z + 1.62 - 0.26 * i), yaw, size=0.2 if i == 0 else 0.11,
                 color=(0.16, 0.10, 0.06))
    ox, oy = rot2(0.0, -0.6, yaw)
    v.a.interact("sign", (lx + ox, ly + oy, z + 1.3), yaw, title=title, text=text)
    v.claim(lx, ly, r, clearing=True)


# --------------------------------------------------------------------------- Millbrook
def _mill(v):
    """The water mill on the river's bank nearest the village, its wheel in the stream. Returns the local
    position in front of its door, or None when no bank was found."""
    a = v.a
    hit = WW.nearest(v.ox - 82.0, v.oy - 4.0) if len(WW.RIVERS) else None
    if hit is None or hit[2] > 60.0:
        v.log.append("no river near the mill site")
        return None
    rid, s, _d, (rx, ry), (tx, ty), wl, half = hit
    nx, ny = -ty, tx                                   # bank normal, turned towards the village
    if nx * (v.ox - rx) + ny * (v.oy - ry) < 0:
        nx, ny = -nx, -ny
    R = 2.35                                           # wheel radius
    wx, wy = rx + nx * (half - 1.7), ry + ny * (half - 1.7)        # wheel centre: 1.7 m inside the water's edge
    axle_z = wl + R - 0.42                             # lower rim 0.42 m in the stream
    yaw_w = math.degrees(math.atan2(-nx, ny))          # wheel frame: local +Y = the axle, towards the mill
    # local +X of that frame is (ny, -nx): downstream or upstream; the bottom of the wheel runs with the water
    downstream = (ny * tx - nx * ty) > 0
    rpm = -5.5 if downstream else 5.5                  # right-handed about local +Y (Blender axes)

    # ---- the mill house: back wall to the river, door to the village
    bw, bd = 8.4, 6.4
    back = half + 1.3                                  # back wall this far from the river's centre line
    cx, cy = rx + nx * (back + bd / 2), ry + ny * (back + bd / 2)
    yaw_b = face_yaw(nx, ny)
    lx, ly = cx - v.ox, cy - v.oy
    lo, hi = v.span(lx, ly, 0, yaw_b, bw + 0.4, bd + 0.4)
    floor = max(hi + 0.22, axle_z - 1.2)
    mb = a.mesh(f"{v.prefix}_Mill")
    nc = v.nc
    fx, fy = rot2(-1.6, -bd / 2 - 1.2, yaw_b)
    step = floor - v.h(lx + fx, ly + fy)
    with mb.at((lx, ly, floor), rot=yaw_b), nc.at((lx, ly, floor), rot=yaw_b):
        an = cottage(mb, nc, bw, bd, 2.7, "stone", "gable", TILE, seed=5, drop=floor - min(lo, wl - 1.6) + 0.5,
                     step=step, chimney="end", upper=2.3, door_x=-1.6, lean_to=None)
        # hoist beam and sack door in the gable, sacks and a millstone by the door
        nc.box((-bw / 2 - 0.5, 0, 5.75), (1.6, 0.16, 0.16), TIMBER)
        nc.box((-bw / 2 - 1.15, 0, 5.45), (0.03, 0.03, 0.5), ROPE)
        nc.sphere((-bw / 2 - 1.15, 0, 5.05), 0.26, "M_Sack", seg=7, rings=6, scale=(1, 1, 1.25))
        with nc.at((-bw / 2 - 0.26, 0, 3.0), rot=-90):
            _door(nc, 0.0, 1.0, 1.5, "M_VillageGreen", TIMBER)
        for i, (sx, sy) in enumerate(((0.6, -3.75), (1.25, -3.8), (0.9, -3.72))):
            nc.sphere((sx, sy, -step + 0.3 + (0.42 if i == 2 else 0.0)), 0.3, "M_Sack", seg=7, rings=6, scale=(1.1, 0.8, 1.0))
        with nc.at((3.3, -bd / 2 - 0.14, -step + 0.62), rot_x=80):
            nc.cylinder((0, 0, 0), 0.62, 0.2, STONE_L, seg=14)
            nc.cylinder((0, 0, 0.2), 0.1, 0.02, IRON, seg=8)
        # bearing block where the axle enters the back wall
        mb.box((0.0, bd / 2 + 0.2, axle_z - floor - 0.25), (1.0, 0.45, 0.5), STONE_L)
    v.claim(lx, ly, math.hypot(bw, bd) / 2 + 0.3)
    for k in ("lamp",):
        q = v._world(lx, ly, floor, yaw_b, an[k])
        a.light(q, color=WARM, intensity=1100.0, radius=8.0, night_only=True)
    for q in an["windows"][:3]:
        a.light(v._world(lx, ly, floor, yaw_b, q), color=(1.0, 0.70, 0.38), intensity=420.0, radius=4.5, night_only=True)
    a.emitter("smoke", v._world(lx, ly, floor, yaw_b, an["chimney"]), scale=0.28, rate=0.7)

    # ---- outer bearing: a timber frame standing in the stream on the far side of the wheel
    wlx, wly = wx - v.ox, wy - v.oy
    with mb.at((wlx, wly, axle_z), rot=yaw_w):
        for sx in (-1, 1):
            mb.beam((sx * 1.25, -1.05, wl - axle_z - 1.9), (sx * 0.22, -1.05, 0.1), 0.2, 0.2, TIMBER)
        mb.box((0, -1.05, -0.02), (0.9, 0.3, 0.26), TIMBER)
        mb.box((0, -1.05, wl - axle_z + 0.35), (2.3, 0.14, 0.16), "M_DarkWood")
        # walkway from the bank to the wheel for the miller, with a rail
        mb.box((2.9, 0.25, wl - axle_z + 1.25), (1.2, 3.2, 0.1), DECK)
        for sy in (-1.2, 1.6):
            mb.box((3.4, sy, wl - axle_z - 0.3), (0.16, 0.16, 3.2), TIMBER)
        mb.railing([(3.45, -1.3, wl - axle_z + 1.3), (3.45, 1.8, wl - axle_z + 1.3)], 1.0, TIMBER, post_spacing=1.6)

    # ---- the wheel: its own mesh round the axle (local Y), turned in the engine by the spinner socket
    wheel = a.mesh(f"{v.prefix}_MillWheel_NoCol")
    axle_len = (back - (half - 1.7)) + 0.35
    with wheel.at((0, 0, 0), rot_x=-90):                # cylinder axis Z -> local +Y
        wheel.cylinder((0, 0, -1.2), 0.17, axle_len + 1.2, TIMBER, seg=10)
        wheel.cylinder((0, 0, -0.75), 0.36, 1.5, "M_DarkWood", seg=10)
    nseg, npad = 16, 16
    for sy in (-0.62, 0.62):
        for k in range(nseg):
            a0, a1 = TAU * k / nseg, TAU * (k + 1) / nseg
            for rr, th in ((R - 0.08, 0.16), (R - 0.62, 0.12)):
                wheel.beam((math.cos(a0) * rr, sy, math.sin(a0) * rr), (math.cos(a1) * rr, sy, math.sin(a1) * rr),
                           0.09, th, "M_DarkWood")
        for k in range(8):
            ang = TAU * k / 8
            wheel.beam((math.cos(ang) * 0.3, sy, math.sin(ang) * 0.3), (math.cos(ang) * (R - 0.1), sy, math.sin(ang) * (R - 0.1)),
                       0.09, 0.13, TIMBER)
    for k in range(npad):
        with wheel.at((0, 0, 0), rot_y=360.0 * k / npad):
            wheel.box((R - 0.32, 0, 0), (0.62, 1.36, 0.045), "M_VillagePlank")
            wheel.box((R - 0.6, 0, 0.14), (0.04, 1.3, 0.3), "M_VillagePlank")
    a.special("spinner", (wlx, wly, axle_z), yaw_w, mesh=f"{v.prefix}_MillWheel_NoCol", axis="y", rpm=rpm)
    a.audio("A_Waterfall", (wlx, wly, wl + 1.0), radius=32.0, volume=0.45)
    a.emitter("mist", (wlx, wly, wl + 0.3), scale=0.45, rate=1.0)
    ox, oy = rot2(-1.6, -bd / 2 - 0.12, yaw_b)
    a.text("MILLBROOK MILL", (lx + ox, ly + oy, floor + 2.42), yaw_b, size=0.2, color=(0.2, 0.13, 0.08))
    dx, dy = rot2(-1.6, -bd / 2 - 2.4, yaw_b)
    a.interact("sign", (lx + dx, ly + dy, floor - step + 1.3), yaw_b, title="Millbrook Mill",
               text="The wheel has turned since before the Academy was built. The miller grinds the island's "
                    "rice flour here - and swears the stones run smoother on duel days.")
    return dict(door=(lx + dx, ly + dy), pos=(lx, ly), yaw=yaw_b, wheel=(wlx, wly, axle_z), yaw_w=yaw_w)


def build_millbrook():
    v = Village("millbrook", "Millbrook")
    a = v.a
    deco = a.mesh("Millbrook_Green")
    mill = _mill(v)
    # cottages either side of the lane through the green (slots; each settles clear of lane, river, each other)
    slots = [(-24.0, 24.0, "thatch", 1), (-4.0, 20.0, "timber", 2), (17.0, 14.0, "stone", 3),
             (-22.0, -11.0, "long", 4), (2.0, -17.0, "thatch", 6), (26.0, -19.0, "timber", 7)]
    houses = [h for h in (v.house(x, y, "path", kind, seed) for x, y, kind, seed in slots) if h]
    # the green: well, benches, a big tree, lamps along the lane
    spot = v.find(-12.0, -1.0 - 8.0, 2.2, reach=10.0, max_dz=0.5)
    if spot:
        well(deco, v.nc, v.p(*spot))
        v.claim(spot[0], spot[1], 2.0)
        a.light((spot[0], spot[1], v.h(*spot) + 2.2), color=WARM, intensity=700.0, radius=7.0, night_only=True)
        v.prop("SM_Bench", spot[0] + 3.2, spot[1] - 0.5, 90.0, r=1.2)
    v.prop("SM_BroadTree_C", 12.0, -9.0, 30.0, 1.25, r=1.6)
    v.prop("SM_Bench", 12.0, -12.4, 180.0, r=1.1)
    v.prop("SM_BroadTree_A", 36.0, 6.0, 80.0, 0.8, r=2.0)
    for (x, y) in ((-30.0, 9.0), (-6.0, 7.5), (20.0, 1.5), (40.0, -8.0)):
        px, py = nearest_path_point(v.ox + x, v.oy + y)
        dx, dy = x - (px - v.ox), y - (py - v.oy)
        ln = math.hypot(dx, dy) or 1.0
        v.prop("SM_LampPost", px - v.ox + dx / ln * 3.6, py - v.oy + dy / ln * 3.6, 0.0, r=0.5)
    # woodpiles, vegetable plots, flowers and fences behind the houses
    for i, hs in enumerate(houses):
        bx, by = rot2(0.0, 5.0, hs["yaw"])
        if i % 2 == 0:
            veg_plot(v, deco, v.nc, hs["pos"][0] + bx * 1.5, hs["pos"][1] + by * 1.5, hs["yaw"], seed=i)
        else:
            sx, sy = rot2(-5.6, 1.0, hs["yaw"])
            sp = v.find(hs["pos"][0] + sx, hs["pos"][1] + sy, 1.3, reach=4.0, max_dz=0.5)
            if sp:
                woodpile(deco, v.nc, v.p(*sp), 2.2, 1.2, rot=hs["yaw"] + 90.0)
                v.claim(sp[0], sp[1], 1.2)
        fx, fy = rot2(2.9, -4.3, hs["yaw"])
        v.prop(["SM_FlowerBush_Red", "SM_FlowerBush_Yellow", "SM_FlowerBush_Blue", "SM_FlowerBush_White"][i % 4],
               hs["pos"][0] + fx, hs["pos"][1] + fy, 0.0, 0.8, r=0.7)
    if mill:
        mx, my = mill["door"]
        sign(v, deco, mx + 4.0, my - 3.0, mill["yaw"] + 20.0, "Millbrook",
             "Millbrook - six hearths, one mill. Flour, firewood and fresh bread for the Academy kitchens. "
             "Cross the stone bridge for the campus, follow the lane east for the old dorm (off limits!).",
             lines=["MILLBROOK", "mill - bakery - bridge"])
        v.prop("SM_Barrel", mx + 2.6, my + 1.2, 0.0, r=0.6)
        v.prop("SM_Crate", mx - 2.8, my + 0.6, 15.0, r=0.8)
        v.person(mx + 1.0, my - 1.5, mill["yaw"] + 180.0, "ra", 4.0)
        a.emitter("fireflies", (mill["wheel"][0], mill["wheel"][1] - 9.0, mill["wheel"][2] - 0.6), scale=1.6)
        a.emitter("fireflies", (mill["wheel"][0] + 2.0, mill["wheel"][1] + 12.0, mill["wheel"][2] + 0.4), scale=1.4)
    for (x, y, yaw, dorm, wd) in ((-10.0, -4.0, 60.0, "slifer", 6.0), (8.0, 8.0, -110.0, "obelisk", 5.0),
                                  (24.0, -7.0, 150.0, "slifer", 6.0), (-27.0, 4.0, -20.0, "ra", 4.0)):
        v.person(x, y, yaw, dorm, wd)
    a.audio("A_Forest", (0.0, 0.0, v.h(0, 0) + 4.0), radius=90.0, volume=0.5)
    arr = v.find(-36.0, 20.0, 1.2, reach=8.0, max_dz=0.5) or (-36.0, 20.0)
    a.special("arrival", v.p(*arr), -20.0)
    a.special("clearing", v.p(*arr), radius=4.0)
    return v.finish()


# --------------------------------------------------------------------------- Willow Pond
def _shore(v, lx, ly, dx, dy, limit=140.0):
    """Walk from (lx, ly) along (dx, dy) to the fresh-water edge. Returns (distance, water level) or None."""
    for i in range(int(limit / 0.5)):
        d = 0.5 * i
        x, y = v.ox + lx + dx * d, v.oy + ly + dy * d
        if WW.clearance(x, y) <= 0.0:
            wl = None
            for j in range(1, 12):
                wl = WW.water_level(x + dx * j, y + dy * j)
                if wl is not None:
                    break
            return d, wl
    return None


def build_willow_pond():
    v = Village("willow_pond", "WillowPond")
    a = v.a
    sq = a.mesh("WillowPond_Square")
    # ---- market square: a cobbled octagon beside the lane's end, well in the middle
    centre = v.find(6.0, -14.0, 8.5, reach=12.0, path=0.2, max_dz=0.7) or (6.0, -14.0)
    cx, cy = centre
    z = v.span(cx, cy, 8.0)[1] + 0.05
    ring = [(cx + math.cos(TAU * (k + 0.5) / 8) * 9.2, cy + math.sin(TAU * (k + 0.5) / 8) * 9.2) for k in range(8)]
    sq.prism(ring, z - 1.2, z, STONE, top_mat="M_Cobble", cap_bottom=False)
    inner = [(cx + math.cos(TAU * (k + 0.5) / 8) * 3.4, cy + math.sin(TAU * (k + 0.5) / 8) * 3.4) for k in range(8)]
    v.nc.poly([(x, y, z + 0.006) for x, y in inner], "M_VillageStoneLight")
    well(sq, v.nc, (cx, cy, z), roof_mat=THATCH_D)
    a.light((cx, cy, z + 2.3), color=WARM, intensity=1500.0, radius=11.0, night_only=True)
    v.claim(cx, cy, 2.0)
    stalls = [(-5.6, 3.2, 200.0, "M_AwningRed", "fruit"), (5.4, 4.2, 150.0, "M_AwningBlue", "fish"),
              (-5.8, -4.4, -35.0, "M_AwningCream", "bread"), (5.6, -4.6, 35.0, "M_AwningRed", "cloth")]
    for i, (sx, sy, yaw, awn, goods) in enumerate(stalls):
        stall(sq, v.nc, (cx + sx, cy + sy, z), yaw, awn, goods, seed=i)
        v.claim(cx + sx, cy + sy, 1.9, clearing=False)
        a.light((cx + sx, cy + sy, z + 1.8), color=WARM, intensity=500.0, radius=5.0, night_only=True)
    square = (cx, cy, 9.6)      # houses keep off the square (people still stand on it: see persons below)
    # ---- cottages round it
    slots = [(-25.0, 18.0, "thatch", 11), (-8.0, 21.0, "timber", 12), (10.0, 21.5, "thatch", 13),
             (27.0, 17.0, "stone", 14), (-27.0, -8.0, "long", 15), (-14.0, -29.0, "stone", 16),
             (22.0, -27.0, "timber", 17)]
    v.taken.append(square)
    houses = [h for h in (v.house(x, y, (cx, cy), kind, seed) for x, y, kind, seed in slots) if h]
    v.taken.remove(square)
    for i, hs in enumerate(houses):
        fx, fy = rot2(-2.8, -4.4, hs["yaw"])
        v.prop(["SM_FlowerBush_Yellow", "SM_FlowerBush_Red", "SM_FlowerBush_White", "SM_FlowerBush_Blue"][i % 4],
               hs["pos"][0] + fx, hs["pos"][1] + fy, 0.0, 0.8, r=0.7)
        if i % 3 == 0:
            bx, by = rot2(0.0, 7.2, hs["yaw"])
            veg_plot(v, sq, v.nc, hs["pos"][0] + bx, hs["pos"][1] + by, hs["yaw"], w=5.0, d=3.6, seed=10 + i)
    for k, ang in enumerate((25.0, 115.0, 205.0, 295.0)):
        x, y = cx + math.cos(math.radians(ang)) * 10.6, cy + math.sin(math.radians(ang)) * 10.6
        v.prop("SM_LampPost", x, y, ang + 90.0, r=0.5)
    for ang in (70.0, 250.0):
        x, y = cx + math.cos(math.radians(ang)) * 7.6, cy + math.sin(math.radians(ang)) * 7.6
        a.prop("SM_Bench", (x, y, z), ang + 90.0)
        v.claim(x, y, 1.1, clearing=False)
    v.prop("SM_BroadTree_C", cx - 12.5, cy + 1.0, 0.0, 1.3, r=1.6)
    # ---- down to the pond: steps off the pad, a boardwalk over the shore meadow, the jetty
    jet = a.mesh("WillowPond_Jetty")
    shore = _shore(v, 30.0, 6.0, 1.0, 0.0)
    if shore and shore[1] is not None:
        dist, wl = shore
        sx = 30.0 + dist                                  # local x of the water's edge on the line y = 6
        y = 6.0
        deck = wl + 0.55
        top = next((x for x in np.arange(30.0, sx, 0.5) if v.h(x, y) < v.h(30.0, y) - 0.25), 40.0)
        foot = next((x for x in np.arange(top, sx, 0.5) if v.h(x, y) <= deck + 2.4), sx - 4.0)
        land = next((x for x in np.arange(foot, sx + 3.0, 0.25) if v.h(x, y) <= deck + 0.05), sx)
        if foot - top > 1.0:
            steps(v, jet, v.nc, (top - 0.4, y), (foot, y), width=1.8)
        # boardwalk: ramps from the foot of the steps to the jetty's landward end
        n = max(1, int((land - foot) / 2.0))
        prev = (foot - 0.1, y, v.h(foot, y) + 0.08)
        for k in range(1, n + 1):
            x = foot + (land - foot) * k / n
            cur = (x, y, max(v.h(x, y) + 0.1, deck) if k < n else deck)
            jet.ramp(prev, cur, 2.0, DECK, thick=0.14)
            for s_ in (-1, 1):
                jet.box((x, y + s_ * 0.9, cur[2] - 0.8), (0.14, 0.14, 1.6), TIMBER)
            prev = cur
        bed = wl - 1.25

        def floor(lx, ly, _bed=bed):
            return min(v.h(lx, ly), _bed) if WW.clearance(v.ox + lx, v.oy + ly) < 0 else v.h(lx, ly)
        ln = 17.0
        while ln > 6.0 and WW.clearance(v.ox + land + ln + 3.0, v.oy + y) > -2.0:
            ln -= 1.0
        end = pier(v, jet, v.nc, (land - 0.05, y), 0.0, ln, deck, width=2.2, tee=5.0, floor=floor, rail="left")
        a.prop("SM_Rowboat", (land + ln * 0.55, y - 2.4, wl), 8.0)
        a.prop("SM_Rowboat", (land + ln + 1.4, y + 4.1, wl), 95.0)
        a.special("clearing", (land, y, deck), radius=5.0)
        a.npc((end[0] - 1.0, end[1] - 0.6, deck), 0.0, "obelisk", 1.5)
        a.interact("sign", (end[0] - 2.5, end[1] + 0.9, deck + 1.2), 180.0, title="Willow Pond",
                   text="The Academy River rests here before its last run to the sea. Carp as long as your arm - "
                        "the villagers say they only bite for duelists who have lost today.")
        a.emitter("fireflies", (land + 2.0, y + 6.0, wl + 0.8), scale=2.0)
        a.emitter("fireflies", (land - 4.0, y - 9.0, wl + 1.2), scale=1.6)
        a.emitter("fireflies", (land + ln * 0.6, y + 3.0, wl + 0.7), scale=1.4)
        for (ox_, oy_) in ((-6.0, 7.0), (-9.0, -6.0), (-3.0, -12.0), (-7.0, 15.0)):
            px_, py_ = land + ox_, y + oy_
            if WW.clearance(v.ox + px_, v.oy + py_) > 1.5 and v.h(px_, py_) > wl + 0.3:
                a.prop("SM_GrassClump_A", v.p(px_, py_), 0.0, 1.5)
        v.prop("SM_BroadTree_B", land - 8.0, y + 12.0, 0.0, 0.75, r=2.0)
    else:
        v.log.append("no pond shore east of the square - the jetty was left out")
    sign(v, sq, cx - 9.5, cy + 8.6, face_yaw(1.0, -0.6), "Willow Pond",
         "Willow Pond market: fruit from the terraces, bread from Millbrook's flour, fish from the Cove. "
         "Students get a discount if they can name three Field Spell Cards.",
         lines=["WILLOW POND", "market every day"])
    for (ox_, oy_, yaw, dorm, wd) in ((-2.6, 3.4, -60.0, "slifer", 3.0), (3.1, -2.6, 120.0, "ra", 3.0),
                                      (-7.4, 0.2, 0.0, "obelisk", 2.0), (0.6, -7.2, 90.0, "slifer", 4.0),
                                      (7.6, 1.0, 180.0, "ra", 2.0)):
        v.person(cx + ox_, cy + oy_, yaw, dorm, wd)
    a.audio("A_Crowd", (cx, cy, z + 2.0), radius=38.0, volume=0.35)
    a.audio("A_Forest", (cx + 30.0, cy + 10.0, z), radius=110.0, volume=0.45)
    a.special("arrival", (cx - 1.6, cy + 6.6, z), -90.0)      # on the cobbles, facing the well
    a.special("clearing", v.p(cx, cy), radius=11.0)
    return v.finish()


# --------------------------------------------------------------------------- Fisher's Cove
def stilt_hut(v, lx, ly, yaw, deck_z, seed, land=None, gang=-1):
    """Fisher's hut on a timber platform at deck_z, its veranda (front, -Y) looking where yaw points it.
    `land` = local point on firm ground: a gangway runs to it from the back edge of the platform, at its
    left (gang = -1) or right (+1) corner."""
    a = v.a
    v.n_house += 1
    mb = a.mesh(f"{v.prefix}_Hut{v.n_house}")
    pw, pd = 7.4, 6.6
    posts = []
    for sx in (-1, 0, 1):
        for sy in (-1, 1):
            ox, oy = rot2(sx * (pw / 2 - 0.3), sy * (pd / 2 - 0.3), yaw)
            g = v.h(lx + ox, ly + oy)
            posts.append((lx + ox, ly + oy, g))
            mb.box((lx + ox, ly + oy, (deck_z - 0.14 + g - 1.2) / 2), (0.24, 0.24, deck_z - 0.14 - (g - 1.2)), TIMBER)
    for i in (0, 2, 4):                                     # cross braces under the deck, front to back
        p, q = posts[i], posts[i + 1]
        if deck_z - max(p[2], q[2]) > 1.4:
            mb.beam((p[0], p[1], p[2] + 0.2), (q[0], q[1], deck_z - 0.5), 0.07, 0.16, DARK)
            mb.beam((q[0], q[1], q[2] + 0.2), (p[0], p[1], deck_z - 0.5), 0.07, 0.16, DARK)
    with mb.at((lx, ly, deck_z), rot=yaw), v.nc.at((lx, ly, deck_z), rot=yaw):
        mb.box((0, 0, -0.07), (pw, pd, 0.14), DECK)
        for k in range(1, int(pw / 0.32)):
            v.nc.box((-pw / 2 + 0.32 * k, 0, 0.003), (0.02, pd - 0.1, 0.006), DARK, skip=("-z",))
        for sx in (-1, 0, 1):
            mb.box((sx * (pw / 2 - 0.3), 0, -0.26), (0.2, pd, 0.24), TIMBER)
        with mb.at((0, 0.8, 0.0)), v.nc.at((0, 0.8, 0.0)):
            an = cottage(mb, v.nc, 5.0, 3.9, 2.25, "plank", "gable", THATCH_D if seed % 2 else PLANK_G, seed=seed,
                         drop=0.05, step=0.0, chimney=None, windows=True, plinth=False)
        # veranda rail down both sides and across the front; the back edge (to the land) stays open
        mb.railing([(-pw / 2 + 0.1, pd / 2 - 0.1, 0.0), (-pw / 2 + 0.1, -pd / 2 + 0.1, 0.0), (pw / 2 - 0.1, -pd / 2 + 0.1, 0.0),
                    (pw / 2 - 0.1, pd / 2 - 0.1, 0.0)], 1.0, TIMBER, post_spacing=1.7)
        rows = [[(-1.6 + 0.4 * i, -pd / 2 + 0.04 - 0.05 * j, 1.0 - 0.3 * j - 0.04 * math.sin(i * 1.3)) for i in range(9)]
                for j in range(4)]
        v.nc.grid_faces(rows, "M_FishNet", smooth=True)                        # a net over the rail
        for i in range(0, 9, 2):
            v.nc.sphere(rows[-1][i], 0.07, "M_NetFloat", seg=6, rings=4)
        v.nc.box((2.9, -2.4, 0.26), (0.6, 0.6, 0.5), "M_VillagePlank")
        v.nc.cylinder((-2.8, -2.5, 0.0), 0.3, 0.1, ROPE, seg=10)
    lamp = v._world(lx, ly, deck_z, yaw, (an["lamp"][0], an["lamp"][1] + 0.8, an["lamp"][2]))
    a.light(lamp, color=WARM, intensity=900.0, radius=7.0, night_only=True)
    if land is not None:                                    # gangway from the back edge to firm ground
        gx, gy = rot2(gang * (pw / 2 - 0.8), pd / 2, yaw)
        p0 = (lx + gx, ly + gy, deck_z)
        p1 = (land[0], land[1], v.h(*land) + 0.06)
        mb.ramp(p1, p0, 1.5, DECK, thick=0.12)
        ln = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) or 1.0
        ux, uy = (p0[0] - p1[0]) / ln, (p0[1] - p1[1]) / ln
        for s_ in (-1, 1):
            pts = [(p1[0] - uy * 0.72 * s_, p1[1] + ux * 0.72 * s_, p1[2]), (p0[0] - uy * 0.72 * s_, p0[1] + ux * 0.72 * s_, p0[2])]
            mb.railing(pts, 1.0, TIMBER, post_spacing=1.8)
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        g = v.h(*mid)
        mb.box((mid[0], mid[1], ((p0[2] + p1[2]) / 2 - 0.12 + g - 1.0) / 2), (0.2, 0.2, (p0[2] + p1[2]) / 2 - 0.12 - (g - 1.0)), TIMBER)
    v.claim(lx, ly, 4.6)
    return dict(pos=(lx, ly), yaw=yaw, deck=deck_z)


def _sea_dir(v, lx, ly):
    """Direction (unit, local) in which the sea bed drops below -2.5 m soonest from (lx, ly), and how far."""
    best = None
    for k in range(48):
        ang = TAU * k / 48
        dx, dy = math.cos(ang), math.sin(ang)
        for i in range(1, 90):
            if v.h(lx + dx * i, ly + dy * i) < -2.5:
                if best is None or i < best[0]:
                    best = (i, dx, dy)
                break
    return best


def build_fishers_cove():
    v = Village("fishers_cove", "FishersCove")
    a = v.a
    yard = a.mesh("FishersCove_Yard")
    pad_z = v.h(0.0, 0.0)
    # ---- huts and sheds on the green above the beach
    slots = [(-16.0, 15.0, "plank", 21), (3.0, 17.0, "thatch", 22), (-24.0, -9.0, "long", 23),
             (-3.0, -15.0, "plank", 24), (17.0, -13.0, "shed", 25), (22.0, 13.0, "shed", 26)]
    houses = [h for h in (v.house(x, y, (0.0, 2.0), kind, seed, porch=False) for x, y, kind, seed in slots) if h]
    # ---- the beach: find it going east from the green, then the direction of deep water
    beach = next(((x, 0.0) for x in np.arange(30.0, 130.0, 1.0) if v.h(x, 0.0) < 1.6), None)
    edge = next(((x, 0.0) for x in np.arange(20.0, 120.0, 0.5) if v.h(x, 0.0) < pad_z - 0.4), (44.0, 0.0))
    if beach:
        bx, by = beach
        # stilt huts on the bank between the green and the sand, a gangway to each from the edge of the green
        for i, dy in enumerate((13.0, -11.0)):
            ex = next((x for x in np.arange(20.0, 120.0, 0.5) if v.h(x, dy) < pad_z - 0.4), edge[0])
            hx = ex + 6.6
            if v.h(hx + 3.0, dy) > 0.9 and WW.clearance(v.ox + hx, v.oy + dy) > 3.0:
                g = -1 if i == 0 else 1           # gangways on the sides facing each other
                stilt_hut(v, hx, dy, 90.0, pad_z + 0.12, 31 + i, land=(ex - 1.4, dy + g * 2.9), gang=g)
        # steps down the bank to the sand
        steps(v, yard, v.nc, (edge[0] - 0.6, 1.0), (max(bx - 4.0, edge[0] + 4.0), 1.0), width=1.8)
        # drying racks, boats pulled up, crates and barrels on the sand
        for i, (ox_, oy_, yaw) in enumerate(((2.0, 13.0, 80.0), (7.0, -12.0, 100.0), (-1.0, -22.0, 70.0))):
            x, y = bx + ox_, by + oy_
            if v.h(x, y) > 0.7 and v.ok(x, y, 2.6, max_dz=1.2):
                net_rack(yard, v.nc, v.p(x, y), yaw, seed=i)
                v.claim(x, y, 2.6)
        for i, (ox_, oy_, yaw, heel, col) in enumerate(((9.0, 6.0, 20.0, 16.0, "M_VillageBlue"),
                                                        (11.0, -4.5, -10.0, -14.0, "M_VillageRed"),
                                                        (4.0, -17.0, 35.0, 18.0, "M_VillageWhite"),
                                                        (13.0, 15.0, 5.0, -12.0, "M_VillageGreen"))):
            x, y = bx + ox_, by + oy_
            if v.h(x, y) > 0.35 and v.ok(x, y, 2.3, max_dz=1.2, min_h=0.15):
                boat(yard, v.p(x, y, 0.05), yaw, heel, col, seed=i)
                v.claim(x, y, 2.3)
        for (ox_, oy_, asset, yaw) in ((0.5, 5.0, "SM_Crate", 10.0), (1.6, 6.3, "SM_Crate", 40.0), (0.2, 7.4, "SM_Barrel", 0.0),
                                       (5.0, -7.0, "SM_Barrel", 0.0), (5.9, -7.6, "SM_Barrel", 0.0), (3.0, 9.5, "SM_Driftwood_A", 60.0)):
            v.prop(asset, bx + ox_, by + oy_, yaw, r=0.7)
        # ---- the pier towards deep water
        sea = _sea_dir(v, bx + 8.0, by - 4.0)
        if sea:
            dist, dx, dy = sea
            yaw_p = math.degrees(math.atan2(dy, dx))
            start = next(((bx + 8.0 + dx * i, by - 4.0 + dy * i) for i in np.arange(-12.0, dist, 0.5)
                          if v.h(bx + 8.0 + dx * i, by - 4.0 + dy * i) < 1.25), (bx + 8.0, by - 4.0))
            ln = float(min(max(math.hypot(bx + 8.0 + dx * dist - start[0], by - 4.0 + dy * dist - start[1]) + 3.0, 14.0), 32.0))
            pr = a.mesh("FishersCove_Pier")
            end = pier(v, pr, v.nc, (start[0] - dx * 1.0, start[1] - dy * 1.0), yaw_p, ln, 1.35, width=2.6, tee=6.0, rail="right")
            ex_, ey_ = end[0], end[1]
            a.prop("SM_FishingBoat", (ex_ + dx * 9.0 - dy * 6.0, ey_ + dy * 9.0 + dx * 6.0, 0.0), yaw_p + 100.0)
            a.prop("SM_Rowboat", (ex_ - dx * 6.0 + dy * 3.4, ey_ - dy * 6.0 - dx * 3.4, 0.0), yaw_p + 5.0)
            a.prop("SM_Buoy", (ex_ + dx * 22.0, ey_ + dy * 22.0, 0.0), 0.0)
            a.npc((end[0] - dx * 1.0, end[1] - dy * 1.0, 1.35), yaw_p, "slifer", 1.5)
            a.special("clearing", (start[0], start[1], 1.0), radius=4.0)
            a.special("birds", (ex_, ey_, 9.0), radius=55.0, height=22.0, count=14, kind="gull")
            a.audio("A_Ocean", (ex_, ey_, 1.0), radius=150.0, volume=0.9)
            a.interact("sign", (start[0] + dx * 3.0, start[1] + dy * 3.0, 2.5), yaw_p + 90.0, title="Fisher's Cove",
                       text="Boats go out before dawn and are back for breakfast. The catch feeds all three dorms - "
                            "the Slifers get the heads, or so they say.")
        v.person(bx + 4.0, by + 2.0, 0.0, "ra", 5.0)
        v.person(bx + 8.0, by - 9.0, 120.0, "slifer", 5.0)
    else:
        v.log.append("no beach east of the green - racks, boats and the pier were left out")
    # ---- the yard on the green: net shed, fish stall, crates, benches, lamps
    cxy = v.find(4.0, 0.0, 3.0, reach=8.0, path=0.3, max_dz=0.5) or (4.0, 0.0)
    stall(yard, v.nc, v.p(cxy[0] + 5.5, cxy[1] - 3.0), 160.0, "M_AwningBlue", "fish", seed=7)
    v.claim(cxy[0] + 5.5, cxy[1] - 3.0, 2.0)
    net_rack(yard, v.nc, v.p(cxy[0] - 7.0, cxy[1] - 5.5), 15.0, seed=5)
    v.claim(cxy[0] - 7.0, cxy[1] - 5.5, 2.6)
    for (x, y, asset, yaw, r) in ((9.0, 5.5, "SM_Crate", 20.0, 0.8), (10.4, 6.2, "SM_Crate", 55.0, 0.8),
                                  (-10.0, 5.0, "SM_Barrel", 0.0, 0.6), (-10.9, 5.6, "SM_Barrel", 0.0, 0.6),
                                  (30.0, -2.0, "SM_Bench", 90.0, 1.1), (12.0, 22.0, "SM_PalmTree_B", 0.0, 1.2),
                                  (-30.0, 14.0, "SM_PalmTree_A", 40.0, 1.2), (30.0, -17.0, "SM_PalmTree_B", 200.0, 1.2),
                                  (-8.0, 9.0, "SM_LampPost", 0.0, 0.5), (16.0, 2.5, "SM_LampPost", 0.0, 0.5),
                                  (34.0, 6.0, "SM_LampPost", 0.0, 0.5)):
        v.prop(asset, x, y, yaw, r=r)
    sign(v, yard, cxy[0] - 3.0, cxy[1] + 6.5, face_yaw(0.2, -1.0), "Fisher's Cove",
         "Fisher's Cove: nets, salt and patience. The river brings the fresh water, the tide brings the fish, "
         "and the gulls bring opinions.", lines=["FISHER'S COVE", "fresh catch daily"])
    for (x, y, yaw, dorm, wd) in ((cxy[0] + 2.0, cxy[1] + 2.0, 200.0, "slifer", 5.0), (cxy[0] + 6.0, cxy[1] - 5.6, 70.0, "obelisk", 2.0),
                                  (cxy[0] - 8.0, cxy[1] - 1.0, 30.0, "ra", 4.0)):
        v.person(x, y, yaw, dorm, wd)
    a.audio("A_Wind", (0.0, 0.0, pad_z + 6.0), radius=90.0, volume=0.4)
    a.emitter("fireflies", (-20.0, 22.0, pad_z + 1.0), scale=1.5)
    arr = v.find(-6.0, 3.0, 1.0, reach=6.0, max_dz=0.5, path=-9.0) or (-6.0, 3.0)
    a.special("arrival", v.p(*arr), 0.0)
    a.special("clearing", v.p(*arr), radius=4.0)
    return v.finish()


PLACEMENTS = {
    "millbrook": build_millbrook,
    "willow_pond": build_willow_pond,
    "fishers_cove": build_fishers_cove,
}
