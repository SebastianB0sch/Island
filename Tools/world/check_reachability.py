#!/usr/bin/env python3
"""Walk-in reachability audit: can the player capsule reach every interior, storey, door and mark?

Pure Python + numpy (no Blender, no Unreal).  It reads what the editor build imports:

  * SourceAssets/Data/layout.json + assets.json   placements, collision flags, doors, NPCs, zones
  * SourceAssets/Meshes/**/*.fbx                   the exported collision geometry itself
        - location / terrain / road meshes: every triangle (Unreal uses complex-as-simple for them)
        - furniture blocker meshes (hidden, collision only)
        - prop instances: their UCX_ hulls (simple collision); props without a hull do not collide
        - *_NoCol meshes, water and door leaves (pawns ignore them) are left out
  * Content/Data/World/*.json                      portal cells, portals, anchors, spawns

For every location (and every portal cell) the collision triangles are rasterised into a voxel field
(see navgrid.py) and flooded from the outdoor arrival point with the *largest* character envelope
(ADAStudentCharacter: capsule radius 38 cm, 184 cm tall, MaxStepHeight 45 cm, walkable floor 46 deg;
the capsule does not scale with the avatar's BodyScale, so the envelope is the same for every cast
member).  Checked per location:

  doors      both sides of every automatic door are reachable; the opening measured on the collision
             mesh (exact ray casts) is wide and tall enough for the capsule
  storeys    every indoor floor level; an enclosed, walkable space of a building that the flood does not
             reach is an unreachable room (FAIL unless listed in reachability_accept.json)
  marks      NPC markers and their wander points, fast-travel arrivals, interactables, story anchors,
             schedule spawns and portal triggers stand on reachable floor

    python Tools/world/check_reachability.py                # everything
    python Tools/world/check_reachability.py slifer ra      # selected locations / cells
    python Tools/world/check_reachability.py --cell 0.05    # finer grid (slower)
    python Tools/world/check_reachability.py --json out.json

Exit code 0 when everything passes, 1 on any failure, 2 on bad input.

Limits: voxel resolution (see navgrid.py: passages between about 2r - 2 cells and 2r wide are decided
by grid alignment; doors are measured exactly instead); stairs are walked as geometry (step rise against
MaxStepHeight per 10 cm column), not with Unreal's step-up sweep; triangle meshes are treated as
two-sided obstacles; moving things (door leaves, floating boats) are ignored; Fab replacement props the
editor may swap in are not in the repository and are not checked.  It does not replace a navmesh bake or
a play-through.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fbx_lite  # noqa: E402
import navgrid  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "DuelAcademyIsland" / "SourceAssets"
WORLD = ROOT / "DuelAcademyIsland" / "Content" / "Data" / "World"
ACCEPT = Path(__file__).resolve().parent / "reachability_accept.json"

# ADAStudentCharacter (DAStudentCharacter.cpp) - the larger of the two capsules; ADAStudentNPC is 36 x 92.
PLAYER = navgrid.Agent(radius=0.38, height=1.84, step=0.45, slope=46.0)
NPC_RADIUS = 0.36
DOOR_MARGIN = 0.02            # clear width / height a door must leave beyond the capsule (m)
OUTDOOR_GROUPS = {"terrain", "roads", "water", "paths"}
MARGIN = 4.0                  # metres of surroundings kept round a location
MIN_ROOM_AREA = 4.0           # m2 of standable floor before an unreached space counts as a room (2 x 2 m)
MIN_ROOM_WIDTH = 0.5          # m: mean width of the capsule-centre area (area / longest side); under it: a strip
ROOM_WALLED = 0.7             # ... and this share of its rim must be wall (the rest: drops) to be a room
STOREY_BAND = 1.2             # floors closer than this in height are one storey
MIN_STOREY_AREA = 6.0         # m2 of level floor at one height before it is listed as a storey
NPC_Z = 0.95                  # layout.json NPC markers / wander points are this far above the feet (layout.py)
ARRIVAL_Z = 1.0               # ... and fast-travel arrival points this far
NPC_TALK = 2.4                # ADAStudentNPC::GetInteractRadius is 260 cm: the player must get this close


# --------------------------------------------------------------------------- coordinates
def from_ue(p):
    """UE centimetres (Y south) -> pipeline metres (Y north)."""
    return np.array([p[0] / 100.0, -p[1] / 100.0, p[2] / 100.0])


def to_ue(p):
    return [round(float(p[0]) * 100.0, 1), round(-float(p[1]) * 100.0, 1), round(float(p[2]) * 100.0, 1)]


def rot_z(points, yaw_deg):
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    out = np.array(points, np.float64, copy=True)
    x, y = out[..., 0].copy(), out[..., 1].copy()
    out[..., 0] = x * c - y * s
    out[..., 1] = x * s + y * c
    return out


# --------------------------------------------------------------------------- world model
class World:
    def __init__(self, src=SRC, world=WORLD):
        self.src = Path(src)
        self.layout = json.loads((self.src / "Data" / "layout.json").read_text(encoding="utf-8"))
        self.assets = {a["name"]: a for a in json.loads((self.src / "Data" / "assets.json").read_text(encoding="utf-8"))}
        self.world = {}
        for name in ("interiors", "portals", "anchors", "spawns"):
            path = Path(world) / f"{name}.json"
            self.world[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self._mesh = {}
        self.statics = []
        for e in self.layout["static"]:
            if e.get("collision") == "none" or e.get("group") == "water":
                continue
            entry = self.assets.get(e["mesh"])
            if entry is None or entry.get("collision") == "none":
                continue
            if e.get("group") in OUTDOOR_GROUPS:
                cls = navgrid.SRC_TERRAIN
            elif e.get("hidden"):
                cls = navgrid.SRC_PROP
            else:
                cls = navgrid.SRC_BUILDING
            self.statics.append(dict(e, cls=cls, pos=from_ue(e["loc"]), yaw_b=-float(e["yaw"]), bounds=None))
        self.props = []
        for name, g in self.layout["instances"].items():
            mesh = g.get("mesh", name)
            if not g.get("collision") or mesh not in self.assets or g.get("rot"):
                continue
            items = np.asarray(g["items"], np.float64).reshape(-1, 5)
            if len(items):
                self.props.append((mesh, items))

    def mesh(self, name, hulls=False):
        """Collision triangles (T, 3, 3) of a mesh asset in its local frame (metres)."""
        key = (name, hulls)
        if key not in self._mesh:
            entry = self.assets[name]
            parts = fbx_lite.read_meshes(self.src / entry["file"])
            tris = [v[t] for n, v, t in parts if n.startswith("UCX_") == hulls and len(t)]
            self._mesh[key] = np.concatenate(tris) if tris else np.zeros((0, 3, 3))
        return self._mesh[key]

    def static_tris(self, e):
        t = self.mesh(e["mesh"])
        return rot_z(t, e["yaw_b"]) + e["pos"]

    def static_bounds(self, e):
        if e["bounds"] is None:
            t = self.static_tris(e)
            e["bounds"] = (t.reshape(-1, 3).min(0), t.reshape(-1, 3).max(0)) if len(t) else (e["pos"], e["pos"])
        return e["bounds"]

    def gather(self, lo, hi):
        """Collision triangles and source classes inside the box lo .. hi (pipeline metres)."""
        tris, cls, ids, names = [], [], [], []

        def add(t, c, name):
            if len(t) == 0:
                return
            mn, mx = t.min(1), t.max(1)
            keep = np.all(mx >= lo, axis=1) & np.all(mn <= hi, axis=1)
            if keep.any():
                if not names or names[-1] != name:
                    names.append(name)
                tris.append(t[keep])
                cls.append(np.full(int(keep.sum()), c, np.int8))
                ids.append(np.full(int(keep.sum()), len(names) - 1, np.int32))

        for e in self.statics:
            mn, mx = self.static_bounds(e)
            if np.any(mx < lo) or np.any(mn > hi):
                continue
            add(self.static_tris(e), e["cls"], e["mesh"])
        for mesh, items in self.props:
            hull = self.mesh(mesh, hulls=True)
            if len(hull) == 0:
                continue                                   # no UCX hull: the prop does not collide in Unreal
            reach = float(np.abs(hull).max()) * float(items[:, 4].max()) * 1.5
            x, y = items[:, 0] / 100.0, -items[:, 1] / 100.0
            near = (x > lo[0] - reach) & (x < hi[0] + reach) & (y > lo[1] - reach) & (y < hi[1] + reach)
            for (ux, uy, uz, yaw, sc) in items[near]:
                add(rot_z(hull * sc, -yaw) + from_ue((ux, uy, uz)), navgrid.SRC_PROP, mesh)
        if not tris:
            return np.zeros((0, 3, 3)), np.zeros(0, np.int8), np.zeros(0, np.int32), names
        return np.concatenate(tris), np.concatenate(cls), np.concatenate(ids), names


# --------------------------------------------------------------------------- exact door measurement
def ray_hits(orig, direction, tris, tmax):
    """Nearest hit distance of one ray against triangles (Moller-Trumbore, two-sided); tmax when clear."""
    if len(tris) == 0:
        return tmax
    v0, e1, e2 = tris[:, 0], tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    p = np.cross(direction, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = orig - v0
    u = np.einsum("ij,ij->i", s, p) * inv
    q = np.cross(s, e1)
    v = (q @ direction) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-6) & (t < tmax)
    return float(t[hit].min()) if hit.any() else tmax


def measure_door(pos, yaw_b, width, height, tris):
    """(clear width, clear height) of the opening in the collision mesh at a door socket: the narrowest /
    lowest of a fan of rays through the wall plane (and 6 cm either side of it)."""
    c, s = math.cos(math.radians(yaw_b)), math.sin(math.radians(yaw_b))
    along = np.array([c, s, 0.0])
    normal = np.array([-s, c, 0.0])
    near = tris[np.all(np.abs(tris.mean(1) - (pos + [0, 0, height / 2])) < [width + 3, width + 3, height + 3], axis=1)]
    w = None
    for off in (-0.06, 0.0, 0.06):
        for h in (0.5, 0.9, 1.3, 1.7):
            if h >= height:
                continue
            o = pos + normal * off + np.array([0, 0, h])
            d = ray_hits(o, along, near, width) + ray_hits(o, -along, near, width)
            w = d if w is None else min(w, d)
    hgt = None
    for off in (-0.06, 0.0, 0.06):
        for a in (-0.25, 0.0, 0.25):
            o = pos + normal * off + along * (a * width) + np.array([0, 0, 0.3])
            d = 0.3 + ray_hits(o, np.array([0, 0, 1.0]), near, height + 3.0)
            hgt = d if hgt is None else min(hgt, d)
    return w, hgt


# --------------------------------------------------------------------------- one region
class Region:
    def __init__(self, world, name, lo, hi, cell, log):
        self.world, self.name, self.cell, self.log = world, name, cell, log
        lo = np.asarray(lo, np.float64)
        hi = np.asarray(hi, np.float64)
        self.tris, cls, self.tri_mesh, self.mesh_names = world.gather(lo, hi)
        self.tri_cls = cls
        zmin = float(self.tris[:, :, 2].min()) if len(self.tris) else float(lo[2])
        self.origin = np.array([lo[0], lo[1], min(zmin, lo[2]) - 1.0])
        self.field = navgrid.build_field(self.tris, cls, self.origin, hi - self.origin, cell, PLAYER)
        self.reached = np.zeros(self.field.n, bool)
        self.loose = None

    def local(self, p):
        return np.asarray(p, np.float64) - self.origin

    def snap(self, p, reach=0.5, dz=0.6, standable=True):
        q = self.local(p)
        return self.field.snap(q[0], q[1], q[2], reach, dz, standable)

    def seed(self, p, reach=3.0):
        i = self.snap(p, reach=reach, dz=1.5)
        if i >= 0:
            self.reached |= self.field.flood([i])
        return i

    def status(self, p, reach=0.5, dz=0.6):
        """None when a standable, reached floor lies within reach of p, else why not."""
        i = self.snap(p, reach, dz)
        if i >= 0 and self.reached[i]:
            return None
        # any reached floor nearby?  (snap returns the nearest only)
        q = self.local(p)
        f = self.field
        d2 = ((f.fi + 0.5) * f.cs - q[0]) ** 2 + ((f.fj + 0.5) * f.cs - q[1]) ** 2
        near = (d2 <= (reach + f.cs) ** 2) & (np.abs(f.fz - q[2]) <= dz)
        if (near & self.reached).any():
            return None
        if (near & f.stand).any():
            return "floor not connected to the entrance"
        if near.any():
            return "no room for the capsule (wall / furniture / low ceiling within its radius)"
        return "no floor"


def check_mark(reg, p, reach=0.5, dz=0.6, talk=0.0):
    """None when the mark at feet position p is fine.  talk > 0: somebody *stands* there and the player
    only has to get within `talk` metres (NPCs behind a counter); otherwise the player walks to it."""
    if talk <= 0.0:
        return reg.status(p, reach, dz)
    if reg.snap(p, reach, dz) < 0:
        return reg.status(p, reach, dz) if reg.snap(p, reach, dz, standable=False) < 0 else \
            "no room for the capsule (wall / furniture / low ceiling within its radius)"
    if reg.status(p, talk, 1.5):
        return f"cannot be approached: no reachable floor within {talk:.1f} m"
    return None


LOOSE_RADIUS = 0.20           # "a 40 cm wide body": what still connects with this is a pinch, not a wall
LOOSE_STEP = 1.0              # ... and with steps up to this high: a ledge / missing step
FINE_CELL = 0.025             # grid used to re-test narrow spots (decides to about +-2.5 cm)
FINE_PAD = 0.9                # metres of surroundings kept round a narrow spot
FINE_MAX_AREA = 150.0         # m2: larger detours are not re-tested (they are not "a narrow spot")


def obstacles(reg, p, radius=0.5):
    """What reaches into the body band round the feet position p: [(mesh, bbox min, bbox max)]."""
    t = reg.tris
    mn, mx = t.min(1), t.max(1)
    lo = np.array([p[0] - radius, p[1] - radius, p[2] + PLAYER.step])
    hi = np.array([p[0] + radius, p[1] + radius, p[2] + PLAYER.height])
    hit = np.all(mx >= lo, axis=1) & np.all(mn <= hi, axis=1)
    out = []
    for m in np.unique(reg.tri_mesh[hit]):
        sel = hit & (reg.tri_mesh == m)
        out.append((reg.mesh_names[m], np.maximum(mn[sel].min(0), lo - 0.5), np.minimum(mx[sel].max(0), hi + 0.5)))
    return out


def find_bridges(reg):
    """Standable sheets the strict flood did not reach although a relaxed envelope gets there.  One dict
    per sheet: kind ("narrow": a thinner body walks there, "step": it also needs a higher step), near /
    far (floor index where the relaxed route leaves the reached area / enters the sheet), path (floor
    indices of that route), bad (the route's floors the real capsule cannot use), area (m2)."""
    f = reg.field
    out = []
    if f.n == 0 or not reg.reached.any():
        return out
    if reg.loose is None:
        reg.loose = (f.stand_mask(LOOSE_RADIUS), f.neighbours(LOOSE_STEP))
    loose, nb2 = reg.loose
    seen = reg.reached.copy()
    for kind, stand, nb in (("narrow", loose, f.nb), ("step", loose, nb2)):
        parent = np.full(f.n, -1, np.int64)
        depth = np.zeros(f.n, np.int32)
        before = seen.copy()
        seen = f.flood(np.flatnonzero(before), stand=stand, nb=nb, parent=parent, seen=seen, depth=depth)
        new = seen & ~before & f.stand
        lab, n = f.components(new)
        if n == 0:
            continue
        sizes = np.bincount(lab[lab >= 0], minlength=n) * f.cs * f.cs
        idx = np.flatnonzero(lab >= 0)
        order = idx[np.argsort(depth[idx], kind="stable")]
        first = np.full(n, -1, np.int64)
        first[lab[order[::-1]]] = order[::-1]          # shallowest floor of each sheet
        for k in np.argsort(-sizes):
            if sizes[k] < 0.3:
                break
            cur, path, bad, rise = int(first[k]), [], [], 0.0
            while cur >= 0 and not before[cur]:
                prev = int(parent[cur])
                dz = abs(f.fz[cur] - f.fz[prev]) if prev >= 0 else 0.0
                if not f.stand[cur] or dz > PLAYER.step + 1e-3:
                    bad.append(cur)
                    rise = max(rise, dz)
                path.append(cur)
                cur = prev
            if cur < 0 or not bad:
                continue
            out.append(dict(kind=kind, near=cur, far=int(first[k]), path=np.asarray(path, np.int64),
                            bad=np.asarray(bad, np.int64), rise=float(rise), area=float(sizes[k]),
                            depth=int(depth[first[k]])))
    return out


def cell_pos(reg, i):
    f = reg.field
    return np.array([(f.fi[i] + 0.5) * f.cs, (f.fj[i] + 0.5) * f.cs, f.fz[i]]) + reg.origin


def refine(reg, max_rounds=8):
    """Re-test every narrow spot on a fine grid: the coarse grid cannot tell an 80 cm passage from a
    70 cm one (see navgrid.py), a FINE_CELL grid over just the spot can.  Where the capsule gets through
    on the fine grid the flood continues behind it.  Returns the number of spots that were opened."""
    f = reg.field
    opened = 0
    dead = set()
    for _ in range(max_rounds):
        todo = [b for b in find_bridges(reg) if b["kind"] == "narrow" and (b["near"], b["far"]) not in dead]
        if not todo:
            break
        progress = False
        for b in sorted(todo, key=lambda b: b["depth"]):
            if reg.reached[b["far"]]:
                continue
            if not reg.reached[b["near"]]:
                continue
            pts = np.array([cell_pos(reg, i) for i in np.concatenate((b["path"], [b["near"], b["far"]]))])
            lo = pts.min(0) - [FINE_PAD, FINE_PAD, 0.6]
            hi = pts.max(0) + [FINE_PAD, FINE_PAD, PLAYER.height + 0.6]
            ok = False
            if (hi[0] - lo[0]) * (hi[1] - lo[1]) <= FINE_MAX_AREA:
                mn, mx = reg.tris.min(1), reg.tris.max(1)
                sel = np.all(mx >= lo, axis=1) & np.all(mn <= hi, axis=1)
                fine = navgrid.build_field(reg.tris[sel], reg.tri_cls[sel], lo, hi - lo, FINE_CELL, PLAYER)
                pa, pb = cell_pos(reg, b["near"]) - lo, cell_pos(reg, b["far"]) - lo
                ia = fine.snap(pa[0], pa[1], pa[2], reach=0.2, dz=0.25)
                ib = fine.snap(pb[0], pb[1], pb[2], reach=0.2, dz=0.25)
                ok = ia >= 0 and ib >= 0 and bool(fine.flood([ia])[ib])
            if ok:
                reg.reached |= f.flood([b["far"]])
                opened += 1
                progress = True
            else:
                dead.add((b["near"], b["far"]))
        if not progress:
            break
    return opened


def storeys(field, mask):
    """[(z, area m2)] level floors among the masked ones: heights that carry at least MIN_STOREY_AREA."""
    if not mask.any():
        return []
    zq = np.round(field.fz[mask] / 0.1).astype(np.int64)
    base = int(zq.min())
    hist = np.bincount(zq - base) * field.cs * field.cs
    out = []
    for k in np.flatnonzero(hist >= MIN_STOREY_AREA):
        z = (k + base) * 0.1
        if out and z - out[-1][0] < STOREY_BAND:
            if hist[k] > out[-1][1]:
                out[-1] = (z, float(hist[k]) + 0.0)
            continue
        out.append((z, float(hist[k])))
    return out


def audit_location(world, group, cell, log, accept):
    statics = [e for e in world.statics if e.get("group") == group]
    if not statics:
        return None
    lo = np.min([world.static_bounds(e)[0] for e in statics], axis=0) - MARGIN
    hi = np.max([world.static_bounds(e)[1] for e in statics], axis=0) + MARGIN
    zone = next((z for z in world.layout["zones"] if z["id"] == group), None)
    spawn = from_ue(zone["spawn"]["loc"]) if zone else None
    if spawn is not None:
        lo[:2] = np.minimum(lo[:2], spawn[:2] - MARGIN)
        hi[:2] = np.maximum(hi[:2], spawn[:2] + MARGIN)
    t0 = time.time()
    reg = Region(world, group, lo, hi, cell, log)
    f = reg.field
    res = dict(name=group, kind="location", failures=[], warnings=[], lines=[], skipped=[], causes=[])
    fail, warn, line = res["failures"].append, res["warnings"].append, res["lines"].append
    want = []                                   # feet positions the failures are about (for explain)

    # ---- entrance: the location's outdoor arrival point
    if spawn is None or reg.seed(spawn - [0, 0, ARRIVAL_Z], reach=1.0) < 0:
        # no zone spawn (or it is not standable): start from the largest outdoor sheet
        lab, n = f.components(f.stand & (f.fsrc == navgrid.SRC_TERRAIN))
        if n == 0:
            lab, n = f.components(f.stand)
        if n == 0:
            fail("no standable floor at all")
            return res
        big = np.bincount(lab[lab >= 0]).argmax()
        reg.reached |= f.flood([int(np.flatnonzero(lab == big)[0])])
        if spawn is not None:
            warn(f"arrival point {to_ue(spawn)} is not standable; flooded from the largest outdoor area instead")
    n_fine = refine(reg)
    if n_fine:
        line(f"info  {n_fine} narrow spots decided on the {FINE_CELL * 100:.1f} cm grid")
    origin_e = statics[0]

    def loc_local(p):
        return rot_z(np.asarray(p) - origin_e["pos"], -origin_e["yaw_b"])

    def where(p):
        q = loc_local(p)
        return f"UE {to_ue(p)} / local ({q[0]:.1f}, {q[1]:.1f}, {q[2]:.1f}) m"

    # ---- doors
    doors = [d for d in world.layout["doors"] if d.get("group") == group]
    bad_doors = 0
    for d in doors:
        pos = from_ue(d["loc"])
        yaw_b = -float(d["yaw"])
        w, h = d["width"] / 100.0, d["height"] / 100.0
        label = f"door {d['width']:.0f}x{d['height']:.0f} at {where(pos)}"
        cw, chh = measure_door(pos, yaw_b, w, h, reg.tris)
        need_w, need_h = 2 * PLAYER.radius + DOOR_MARGIN, PLAYER.height + DOOR_MARGIN
        problems = []
        if cw < need_w:
            problems.append(f"clear width {cw * 100:.0f} cm < {need_w * 100:.0f} cm")
        if chh < need_h:
            problems.append(f"clear height {chh * 100:.0f} cm < {need_h * 100:.0f} cm")
        c, s = math.cos(math.radians(yaw_b)), math.sin(math.radians(yaw_b))
        normal = np.array([-s, c, 0.0])
        for side, sgn in (("inside", 1.0), ("outside", -1.0)):
            why = reg.status(pos + normal * sgn * 0.75, reach=0.45, dz=0.5)
            if why:
                problems.append(f"{side}: {why}")
        if problems:
            bad_doors += 1
            fail(f"{label}: " + "; ".join(problems))
            want.extend([pos + normal * 0.75, pos - normal * 0.75])
    line(f"doors: {len(doors) - bad_doors}/{len(doors)} passable from the entrance")

    # ---- storeys and rooms
    indoor = np.isfinite(f.fceil) & (f.fceil - f.fz < 40.0) & (f.fsrc != navgrid.SRC_TERRAIN)
    for z, area in storeys(f, reg.reached & indoor):
        zl = z + reg.origin[2] - origin_e["pos"][2]
        line(f"PASS storey at {zl:+6.2f} m: {area:8.1f} m2 of indoor floor reachable at that level")
    lab, n = f.components(f.stand & ~reg.reached & (f.fsrc == navgrid.SRC_BUILDING))
    if n:
        sizes = np.bincount(lab[lab >= 0], minlength=n) * f.cs * f.cs
        # how much of each sheet's rim is a wall (floor goes on but the capsule does not fit) rather than a
        # drop (no floor within a step): rooms are walled in, shelf / beam / counter tops end in drops
        walled = np.zeros(n)
        rim = np.zeros(n)
        own = lab >= 0
        for d in range(4):
            nbd = f.nb[d]
            drop = own & (nbd < 0)
            wall = own & (nbd >= 0)
            wall[wall] &= ~f.stand[nbd[wall]]
            walled += np.bincount(lab[wall], minlength=n)
            rim += np.bincount(lab[wall | drop], minlength=n)
        for k in np.argsort(-sizes):
            if sizes[k] < 1.0:
                break
            m = lab == k
            share = float((indoor & m).sum()) / float(m.sum())
            enclosed = walled[k] / max(rim[k], 1.0)
            ci = np.array([(f.fi[m].mean() + 0.5) * f.cs, (f.fj[m].mean() + 0.5) * f.cs, np.median(f.fz[m])]) + reg.origin
            q = loc_local(ci)
            ext = ((f.fi[m].max() - f.fi[m].min() + 1) * f.cs, (f.fj[m].max() - f.fj[m].min() + 1) * f.cs)
            desc = (f"{sizes[k]:.1f} m2 at {where(ci)}, {ext[0]:.1f} x {ext[1]:.1f} m, "
                    f"{enclosed * 100:.0f} % walled")
            ok = accepted(accept, group, q)
            if share <= 0.5:
                res["skipped"].append(f"outdoor surface (roof / terrace / ledge): {desc}")
            elif enclosed < ROOM_WALLED:
                res["skipped"].append(f"indoor ledge (top of furniture / beam / sill): {desc}")
            elif sizes[k] / max(ext) < MIN_ROOM_WIDTH:
                res["skipped"].append(f"strip (kerb / fender ledge / gap between walls): {desc}")
            elif sizes[k] < MIN_ROOM_AREA:
                res["skipped"].append(f"nook behind furniture / closed void under {MIN_ROOM_AREA:.0f} m2: {desc}")
            elif ok:
                line(f"info  accepted closed space ({ok}): {desc}")
            else:
                fail(f"unreachable room: {desc}")
                want.append(cell_pos(reg, int(np.flatnonzero(m)[0])))

    # ---- marks
    def mark(kind, name, p, reach=0.5, dz=0.6, talk=0.0):
        why = check_mark(reg, p, reach, dz, talk)
        if why:
            fail(f"{kind} {name} at {where(p)}: {why}")
            want.append(np.asarray(p, np.float64))
        return why is None

    def inside(p):
        return bool(np.all(p[:2] > lo[:2] + 1.0) and np.all(p[:2] < hi[:2] - 1.0))

    n_ok = n_all = n_out = 0
    for npc in world.layout["npcs"]:
        if npc.get("group") != group:
            continue
        nm = npc.get("name") or npc.get("roster_id") or npc.get("cast") or "student"
        home = from_ue(npc["loc"]) - [0, 0, NPC_Z]
        if not inside(home):
            n_out += 1
            continue
        n_all += 1
        n_ok += mark("npc", nm, home, talk=NPC_TALK)
        hi_ = reg.snap(home)
        sheet = f.flood([hi_]) if hi_ >= 0 else None
        for k, pt in enumerate(npc.get("points") or []):
            q = from_ue(pt) - [0, 0, NPC_Z]
            if not inside(q):
                continue
            n_all += 1
            qi = reg.snap(q)
            if qi < 0:
                fail(f"npc wander point {nm}#{k} at {where(q)}: {reg.status(q) or 'no room for the capsule'}")
                continue
            n_ok += 1
            if sheet is not None and not sheet[qi]:
                warn(f"npc wander point {nm}#{k} at {where(q)}: not on the same walkable sheet as the NPC's home "
                     f"for the player-sized capsule (the pipeline's straight-line check passed it)")
    for z in world.layout["zones"]:
        if z.get("parent") == group:
            n_all += 1
            n_ok += mark("fast-travel arrival", z["id"], from_ue(z["spawn"]["loc"]) - [0, 0, ARRIVAL_Z])
    for it in world.layout["interacts"]:
        if it.get("group") == group:
            p = from_ue(it["loc"])
            if not inside(p):
                n_out += 1
                continue
            n_all += 1
            r = min(float(it.get("radius", 300.0)) / 100.0, 3.0)
            n_ok += mark("interactable", it.get("title") or it.get("kind"), p, reach=r, dz=max(r, 1.2))
    for a in world.world["anchors"].get("anchors", []):
        if a.get("interior_id") or a.get("kind") in ("camera", "prop") or a.get("zone_id") != group:
            continue
        p = from_ue(a["position_ue"])
        if not inside(p):
            n_out += 1
            continue
        # exterior anchors are authored on the floor or up to a capsule centre above it
        n_all += 1
        n_ok += mark(f"anchor ({a['kind']})", a["id"], p - [0, 0, 0.5], reach=0.6, dz=1.0,
                     talk=NPC_TALK if a["kind"] == "npc" else 0.0)
    for pt in world.world["portals"].get("portals", []):
        if pt.get("role") != "entrance" or pt.get("zone_id") != group:
            continue
        p = from_ue(pt["location_ue"])
        if not inside(p):
            n_out += 1
            continue
        ext = pt.get("trigger_extent", [110, 110, 120])
        n_all += 1
        n_ok += mark("portal trigger", pt["id"], p, reach=max(ext[0], ext[1]) / 100.0 - 0.2,
                     dz=ext[2] / 100.0 + 0.9)
    if n_out:
        line(f"info  {n_out} marks of this zone lie on open terrain outside the audited box (not checked)")
    if res["failures"]:
        explain(reg, res, where, want)
    line(f"marks: {n_ok}/{n_all} reachable (NPCs, wander points, fast travel, interactables, anchors, portals)")
    res["seconds"] = round(time.time() - t0, 1)
    res["floors"] = int(f.n)
    return res


def explain(reg, res, where, want):
    """Add the spots behind the failures: where a thinner body, or a higher step, would get through."""
    f = reg.field
    lab, _ = f.components(f.stand & ~reg.reached)
    wanted = set()
    for p in want:
        q = reg.local(p)
        d2 = ((f.fi + 0.5) * f.cs - q[0]) ** 2 + ((f.fj + 0.5) * f.cs - q[1]) ** 2
        near = (d2 <= 0.7 ** 2) & (np.abs(f.fz - q[2]) <= 0.7) & (lab >= 0)
        wanted.update(np.unique(lab[near]).tolist())
    found = {}
    for b in find_bridges(reg):
        if lab[b["far"]] not in wanted:
            continue
        p = cell_pos(reg, int(b["bad"][-1]))           # the bad floor nearest to the reached side
        item = found.setdefault(tuple(np.round(p / 0.6).astype(int)),
                                dict(kind=b["kind"], p=p, rise=0.0, area=0.0, cells=0))
        item["area"] += b["area"]
        item["rise"] = max(item["rise"], b["rise"])
        item["cells"] = max(item["cells"], len(b["bad"]))
    for d in sorted(found.values(), key=lambda d: -d["area"])[:25]:
        obs = obstacles(reg, d["p"])
        what = "; ".join(f"{n} {np.round(a - d['p'], 2).tolist()}..{np.round(b - d['p'], 2).tolist()}" for n, a, b in obs[:4])
        if d["kind"] == "step" and d["rise"] > PLAYER.step:
            why = f"step of {d['rise'] * 100:.0f} cm (max {PLAYER.step * 100:.0f})"
        else:
            why = f"too narrow / too low for the capsule over {d['cells'] * f.cs:.1f} m"
        res["causes"].append(f"{why} at {where(d['p'])}, {d['area']:.0f} m2 behind it"
                             + (f"; in the way (offsets from that spot, m): {what}" if what else ""))


def accepted(accept, group, q):
    for a in accept.get(group, []):
        b = a["box"]
        if b[0] <= q[0] <= b[3] and b[1] <= q[1] <= b[4] and b[2] <= q[2] <= b[5]:
            return a["reason"]
    return None


def audit_cell(world, cell, grid, log):
    cid = cell["id"]
    b = cell["bounds_ue"]
    lo = np.minimum(from_ue(b[:3]), from_ue(b[3:])) - 1.5
    hi = np.maximum(from_ue(b[:3]), from_ue(b[3:])) + 1.5
    t0 = time.time()
    reg = Region(world, cid, lo, hi, grid, log)
    f = reg.field
    res = dict(name=cid, kind="cell", failures=[], warnings=[], lines=[], skipped=[], causes=[])
    fail, line = res["failures"].append, res["lines"].append
    portals = [p for p in world.world["portals"].get("portals", []) if p.get("interior_id") == cid]
    entrance = next((p for p in portals if p.get("role") == "entrance"), None)
    leave = next((p for p in portals if p.get("role") == "exit"), None)
    if entrance is None or leave is None:
        fail("portal pair missing")
        return res
    arrive = from_ue(entrance["target_location_ue"]) - [0, 0, 1.0]       # arrival is the capsule centre
    if reg.seed(arrive, reach=0.4) < 0:
        fail(f"arrival point UE {entrance['target_location_ue']}: {reg.status(arrive) or 'not standable'}")
        return res
    room = np.isfinite(f.fceil)                                           # not the top of the ceiling slab
    refine(reg)
    area = float((reg.reached & room).sum()) * f.cs * f.cs
    total = float((f.stand & room).sum()) * f.cs * f.cs
    line(f"{'PASS' if area > 0.5 * total else 'FAIL'} room: {area:.1f} m2 walkable from the arrival point "
         f"({total:.1f} m2 standable)")
    if area <= 0.5 * total:
        fail(f"only {area:.1f} of {total:.1f} m2 of the room is reachable from the arrival point")

    def mark(kind, name, p, reach=0.5, dz=0.6, talk=0.0):
        why = check_mark(reg, p, reach, dz, talk)
        if why:
            fail(f"{kind} {name} at UE {to_ue(p)}: {why}")
        return why is None

    ext = leave.get("trigger_extent", [110, 110, 120])
    n_all = 1
    n_ok = int(mark("exit portal trigger", leave["id"], from_ue(leave["location_ue"]) - [0, 0, 1.0],
                    reach=max(ext[0], ext[1]) / 100.0 - 0.2, dz=ext[2] / 100.0))
    for a in world.world["anchors"].get("anchors", []):
        if a.get("interior_id") != cid or a.get("kind") in ("camera", "prop"):
            continue
        n_all += 1
        n_ok += mark(f"anchor ({a['kind']})", a["id"], from_ue(a["position_ue"]) - [0, 0, 1.0], reach=0.4, dz=0.5,
                     talk=NPC_TALK if a["kind"] == "npc" else 0.0)
    for it in world.layout["interacts"]:
        if it.get("group") == cid:
            n_all += 1
            r = min(float(it.get("radius", 300.0)) / 100.0, 3.0)
            n_ok += mark("interactable", it.get("title") or it.get("kind"), from_ue(it["loc"]), reach=r, dz=max(r, 1.2))
    line(f"marks: {n_ok}/{n_all} reachable (exit trigger, anchors, interactables)")
    res["seconds"] = round(time.time() - t0, 1)
    res["floors"] = int(f.n)
    return res


# --------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("names", nargs="*", help="locations (layout groups) and/or portal cell ids; default: all")
    ap.add_argument("--cell", type=float, default=0.10, help="grid cell size in metres (default 0.10)")
    ap.add_argument("--json", default=None, help="write the full result as JSON")
    ap.add_argument("--no-cells", action="store_true", help="skip the portal cells")
    ap.add_argument("--quiet", action="store_true", help="only print failures and the summary")
    args = ap.parse_args(argv)
    try:
        world = World()
    except (OSError, ValueError) as e:
        print(f"check_reachability: {e}", file=sys.stderr)
        return 2
    accept = json.loads(ACCEPT.read_text(encoding="utf-8")) if ACCEPT.exists() else {}
    groups = []
    for e in world.statics:
        g = e.get("group")
        if g and g not in OUTDOOR_GROUPS and g != "interiors" and g not in groups:
            groups.append(g)
    cells = [] if args.no_cells else world.world["interiors"].get("cells", [])
    known = set(groups) | {c["id"] for c in cells}
    unknown = [n for n in args.names if n not in known]
    if unknown:
        print(f"check_reachability: unknown location / cell: {', '.join(unknown)}\n"
              f"known: {', '.join(sorted(known))}", file=sys.stderr)
        return 2
    log = print
    print(f"Reachability audit - capsule r={PLAYER.radius * 100:.0f} cm h={PLAYER.height * 100:.0f} cm, "
          f"step {PLAYER.step * 100:.0f} cm, slope {PLAYER.slope:.0f} deg, grid {args.cell * 100:.0f} cm")
    results = []
    t0 = time.time()
    for g in groups:
        if args.names and g not in args.names:
            continue
        r = audit_location(world, g, args.cell, log, accept)
        if r:
            results.append(r)
            report(r, args.quiet)
    for c in cells:
        if args.names and c["id"] not in args.names:
            continue
        r = audit_cell(world, c, args.cell, log)
        results.append(r)
        report(r, args.quiet)
    failed = [r for r in results if r["failures"]]
    n_fail = sum(len(r["failures"]) for r in results)
    print(f"\n{len(results) - len(failed)}/{len(results)} locations pass, {n_fail} failures "
          f"({time.time() - t0:.0f} s)")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 1 if failed else 0


def report(r, quiet=False):
    head = "PASS" if not r["failures"] else "FAIL"
    print(f"[{head}] {r['kind']} {r['name']}  ({r.get('seconds', 0)} s, {r.get('floors', 0)} floor cells)")
    if not quiet:
        for ln in r["lines"]:
            print(f"   {ln}")
    for w in r["warnings"]:
        print(f"   warn  {w}")
    for x in r["failures"]:
        print(f"   FAIL  {x}")
    for x in r.get("causes", []):
        print(f"   cause {x}")


if __name__ == "__main__":
    raise SystemExit(main())
