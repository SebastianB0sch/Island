"""
Building layout check: the main academy building (dai/assets/academy.py), the Slifer Red dorm
(dai/assets/slifer.py), the Ra Yellow dorm (dai/assets/ra.py) or the Obelisk Blue boys' dorm (dai/assets/obelisk.py)
audited as a walkable building.

    python Tools/academy_check.py                       # everything (academy)
    python Tools/academy_check.py --location slifer     # the Slifer Red dorm
    python Tools/academy_check.py --location ra         # the Ra Yellow dorm
    python Tools/academy_check.py --location obelisk_boys  # the Obelisk Blue boys' dorm
    python Tools/academy_check.py --only doors,npcs     # a subset
    python Tools/academy_check.py --json out.json --limit 40

Checks (all in the academy's local metres):

  doors   every door socket against its real wall opening:
          * leaf width / height == the clear opening (jambs and head found by ray casts, 2 cm tolerance),
          * the leaf sits on the wall's middle plane (2 cm),
          * an architrave frames the opening on both faces (jambs + head),
          * the leaf is person sized and in proportion (single leaf 0.8 - 1.3 m, double leaf 0.7 - 1.3 m per
            leaf, 2.0 - 4.5 m high; interior doors lower than the ceiling),
          * the leaf's swing (92 deg, both ways for "auto") is free of walls, built-ins, furniture and props.
  paths   a 0.2 m walk grid of the whole building (every storey, stairs and tiers; a person is a 0.34 m
          radius, 1.85 m tall column that steps up to 0.45 m) flood-filled from the front steps:
          * both sides of every door are reachable,
          * every NPC spot and fast-travel arrival is reachable,
          * every interior camera's room is reachable,
          * nothing stands in a doorway (furniture / props within the doorway column).
  npcs    every NPC as authored (before the layout stage nudges it): standing room (placement.capsule),
          not in a doorway, not inside furniture, and its wander radius reaches clear floor.
  walls   * leaks: horizontal rays from inside the building that escape to the sky without passing a doorway
            or window (a gap between walls / a missing wall),
          * back faces: rays from walkable floor that hit the inside of a solid (a missing face / open box;
            catalog props are bounding boxes, so their back faces are not counted),
          * coplanar faces with different materials (z-fighting) of 0.02 m2 or more,
          * wall-face steps: two large wall faces on (almost) the same plane that meet edge to edge
            0.3 - 4 cm apart (misaligned wall segments).

Exit code 0 when every check passes. Run with the Blender-as-a-module interpreter (pip install bpy).
"""

import argparse
import collections
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,F401
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

from dai import blend, inspect, palette, placement  # noqa: E402
from dai.assets import interior as K  # noqa: E402

GRID = 0.2
RADIUS = 0.34
HEADROOM = 1.85
STEP = 0.45
PROBE_Z = (0.5, 1.0, 1.7)
SOFT_KINDS = {"water", "smoke", "beam", "hologram", "waterfall", "flow", "lava", "foliage"}
TOL = 0.02

# per location: module, seed points for the walk flood (outdoor ground in front of the entrances), the lowest
# building floor whose rays are tested for leaks, and the walk-grid clamp
LOCATIONS = {
    "academy": dict(module="academy", seeds=[(0.0, -76.0, 0.0)], seed_r=3.0, leak_z=1.9,
                    clamp=((-125.0, -95.0), (125.0, 90.0))),
    "slifer": dict(module="slifer", seeds=[(0.0, -12.0, 0.0), (-4.0, 12.0, 0.0)], seed_r=2.0, leak_z=0.2,
                   clamp=((-30.0, -24.0), (30.0, 26.0))),
    "ra": dict(module="ra", seeds=[(0.0, -13.5, 0.05), (-14.0, 10.0, 0.0)], seed_r=2.0, leak_z=0.6,
               clamp=((-28.0, -24.0), (42.0, 15.0))),
    "obelisk_boys": dict(module="obelisk", seeds=[(0.0, -20.0, 0.05), (0.0, -70.0, 0.05)], seed_r=2.5, leak_z=1.9,
                         clamp=((-50.0, -90.0), (50.0, 70.0))),
}
LOC = LOCATIONS["academy"]

# --------------------------------------------------------------------------- recorded wall openings
OPENINGS = []          # every K.Door cut through a K.wall (also the open doorways without a leaf)
SPIRALS = []           # every K.spiral_stairs: (cx, cy, z0, z1, r_in, r_out, a0, step_deg)


def _record_openings():
    orig = K.wall

    def wall(aset, mb, p0, p1, z0, h, thick, mat, inner=None, openings=(), trim=None, trim_in=None, base=None,
             base_h=0.12):
        L, (ux, uy), (nx, ny), yaw = K._frame2d(p0, p1)
        for o in openings:
            if isinstance(o, K.Door):
                OPENINGS.append(dict(pos=(p0[0] + ux * o.c + nx * thick / 2, p0[1] + uy * o.c + ny * thick / 2,
                                          z0 + o.z0), yaw=yaw, w=o.w, h=o.h, thick=thick, style=o.style))
            else:
                OPENINGS.append(dict(pos=(p0[0] + ux * o.c + nx * thick / 2, p0[1] + uy * o.c + ny * thick / 2,
                                          z0 + o.z0), yaw=yaw, w=o.w, h=o.z1 - o.z0, thick=thick, style="window"))
        return orig(aset, mb, p0, p1, z0, h, thick, mat, inner, openings, trim, trim_in, base, base_h)

    K.wall = wall
    orig_sp = K.spiral_stairs

    def spiral_stairs(mb, cx, cy, z0, z1, r_in, r_out, a0=0.0, step_deg=20.0, **kw):
        SPIRALS.append((cx, cy, z0, z1, r_in, r_out, a0, step_deg))
        return orig_sp(mb, cx, cy, z0, z1, r_in, r_out, a0, step_deg, **kw)

    K.spiral_stairs = spiral_stairs


# --------------------------------------------------------------------------- geometry
def _soft(mat):
    return palette.MATERIALS.get(mat, {}).get("kind", "opaque") in SOFT_KINDS or "Water" in mat


class Geo:
    """BVH trees of the academy: `arch` = solid meshes, `all` = every mesh + catalog props as boxes."""

    def __init__(self, aset):
        t = time.time()
        sc = inspect.build_scene(aset, door_angle=0.0, doors=False)
        self.prop_names = []
        boxes = []
        for s, o in sc["props"]:
            if s["props"]["asset"] in placement.SOFT_PROPS:
                continue
            boxes.append(inspect._prop_box(o))
            self.prop_names.append(s["props"]["asset"])
        solid = [o for o in sc["objs"] if not o.get("nocol")]
        self.arch, self.arch_mats = self._tree(solid)
        allo = list(sc["objs"])
        # the invisible collision boxes the layout gives furniture modelled into no-collision meshes
        from dai import collision as COL
        self.blockers = [b for bs in COL.asset_blockers(aset).values() for b in bs]
        self.all, self.all_mats = self._tree(allo, boxes, self.blockers)
        self.boxes = boxes
        print(f"  scene: {len(sc['objs'])} meshes, {len(boxes)} prop boxes, {len(self.blockers)} furniture collision boxes "
              f"({time.time() - t:.1f} s)")

    def _tree(self, objs, boxes=(), obbs=()):
        verts, polys, mats = [], [], []
        for o in objs:
            if o.type != "MESH":
                continue
            me = o.data
            mw = o.matrix_world
            base = len(verts)
            verts.extend(mw @ v.co for v in me.vertices)
            names = [m.name if m else "" for m in me.materials]
            for p in me.polygons:
                m = names[p.material_index] if p.material_index < len(names) else ""
                if _soft(m):
                    continue
                polys.append([base + i for i in p.vertices])
                mats.append(m)
        for k, (mn, mx) in enumerate(boxes):
            base = len(verts)
            for z in (mn.z, mx.z):
                verts += [Vector((mn.x, mn.y, z)), Vector((mx.x, mn.y, z)), Vector((mx.x, mx.y, z)),
                          Vector((mn.x, mx.y, z))]
            for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                polys.append([base + i for i in f])
                mats.append("PROP:" + self.prop_names[k])
        for (c, h, yaw) in obbs:
            base = len(verts)
            ca, sa = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            for sz in (-1, 1):
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    lx, ly = sx * h[0], sy * h[1]
                    verts.append(Vector((c[0] + lx * ca - ly * sa, c[1] + lx * sa + ly * ca, c[2] + sz * h[2])))
            for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                polys.append([base + i for i in f])
                mats.append("BLOCKER (collision box of no-collision furniture)")
        return BVHTree.FromPolygons(verts, polys, all_triangles=False), mats

    def ray(self, tree, o, d, dist):
        h = (self.arch if tree == "arch" else self.all).ray_cast(Vector(o), Vector(d), dist)
        if h[0] is None:
            return None
        mats = self.arch_mats if tree == "arch" else self.all_mats
        return h[3], h[0], h[1], mats[h[2]]


# --------------------------------------------------------------------------- doors
def _framing(mat):
    return any(k in mat for k in ("Gold", "Trim", "Frame", "Metal"))


def check_doors(aset, G, log):
    out = []
    for s in aset.sockets:
        if s["type"] != "door":
            continue
        p = Vector(s["pos"])
        pr = s["props"]
        w, h = pr["width"], pr["height"]
        a = math.radians(s["yaw"])
        u = Vector((math.cos(a), math.sin(a), 0.0))
        n_in = Vector((-math.sin(a), math.cos(a), 0.0))
        lab = f"door {pr['style']} {w:.2f}x{h:.2f}{' double' if pr['double'] else ''} @ ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})"
        # ---- opening: jambs and head
        widths = []
        jamb_mats = []
        filled = False
        for zz in (0.3, min(1.2, h * 0.5), h - 0.12):
            c = p + Vector((0, 0, zz))
            dl = G.ray("arch", c, -u, w + 0.3)
            dr = G.ray("arch", c, u, w + 0.3)
            # a hit on a back face: the ray started inside a solid - the opening is (partly) walled up
            filled |= bool(dl and dl[2].dot(-u) > 0.3) or bool(dr and dr[2].dot(u) > 0.3)
            widths.append(((dl[0] if dl else None), (dr[0] if dr else None)))
            jamb_mats += [hh[3] for hh in (dl, dr) if hh]
        # straight through the doorway (the leaves are not in the scene): nothing within the wall's thickness
        for zz in (0.3, 1.0, h - 0.2):
            for du in (-w / 4.0, 0.0, w / 4.0):
                c = p + u * du + Vector((0, 0, zz))
                for nn in (n_in, -n_in):
                    hit = G.ray("arch", c, nn, 0.12)
                    filled |= hit is not None
        if filled:
            out.append(f"{lab}: the doorway is walled up (solid wall inside the opening)")
        miss = [k for k, (l_, r_) in enumerate(widths) if l_ is None or r_ is None]
        if miss:
            out.append(f"{lab}: no jamb within {w + 0.3:.2f} m on {'both sides' if len(miss) == 3 else 'one side'}")
        else:
            meas = [l_ + r_ for l_, r_ in widths]
            off = [(r_ - l_) / 2 for l_, r_ in widths]
            wm = min(meas)
            if abs(wm - w) > TOL + 0.01:
                out.append(f"{lab}: leaf {w:.2f} m wide in a {wm:.2f} m opening")
            elif max(abs(o) for o in off) > TOL:
                out.append(f"{lab}: leaf {max(off, key=abs) * 100:+.0f} cm off the opening's centre")
        hh = G.ray("arch", p + Vector((0, 0, 0.6)), Vector((0, 0, 1)), h + 2.0)
        # a door in a glazed screen / shop front is framed by its posts and transom (flush frame members)
        posts = bool(jamb_mats) and all(_framing(m) for m in jamb_mats) and hh is not None and _framing(hh[3])
        if hh is None:
            out.append(f"{lab}: no head above the opening")
        else:
            hm = hh[0] + 0.6
            if abs(hm - h) > TOL + 0.01:
                out.append(f"{lab}: leaf {h:.2f} m high in a {hm:.2f} m opening")
        # ---- wall middle plane (from the reveal: rays from inside the wall beside each jamb) and architraves
        zt = min(1.9, h - 0.3)
        reveal = []

        def face_dist(q, nn, far=1.0):
            """Distance from q (on the leaf plane, beside the jamb) to the wall face on the nn side, seen from
            the room: the first surface that is not framing (architraves and portal frames stand proud)."""
            o = q + nn * far
            t = 0.0
            for _ in range(8):
                hit = G.ray("arch", o + (-nn) * t, -nn, far + 0.5 - t)
                if hit is None:
                    return None
                t += hit[0]
                if hit[2].dot(-nn) < -0.3 and not _framing(hit[3]):
                    return far - t
                if hit[2].dot(-nn) > 0.3 and _framing(hit[3]):
                    return far - t           # the back of a trim: it sits on the wall face right there
                t += 0.001
            return None

        for sx in (-1, 1):
            q = p + u * sx * (w / 2 + 0.03) + Vector((0, 0, zt))
            di, do = face_dist(q, n_in), face_dist(q, -n_in)
            if di is not None and do is not None and di > -0.05 and do > -0.05:
                reveal.append((di, do))
        face = {}
        if reveal:
            fi, fo = max(r[0] for r in reveal), max(r[1] for r in reveal)
            face = {"in": [fi], "out": [fo]}
            mid = (fi - fo) / 2
            if abs(mid) > TOL:
                out.append(f"{lab}: leaf {mid * 100:+.0f} cm off the wall's middle plane (reveal {fi + fo:.2f} m)")
            R0 = 2.5
            for side, nn, f0 in (("inside", n_in, fi), ("outside", -n_in, fo)) if not posts else ():
                proud = []
                for q in (p + u * (w / 2 + 0.045) + Vector((0, 0, zt)), p - u * (w / 2 + 0.045) + Vector((0, 0, zt)),
                          p + Vector((0, 0, h + 0.045))):
                    hit = G.ray("all", q + nn * R0, -nn, R0)
                    proud.append(hit is not None and (R0 - hit[0]) - f0 > 0.008)
                if not all(proud):
                    which = [n for n, ok in zip(("right jamb", "left jamb", "head"), proud) if not ok]
                    out.append(f"{lab}: no architrave on the {side} face ({', '.join(which)})")
        # ---- scale
        lw = w / 2 if pr["double"] else w
        lo, hi = (0.7, 1.3) if pr["double"] else (0.8, 1.3)
        # monumental entrance doors (portals, gates) may be wider per leaf when tall in proportion
        grand = h >= 2.6 and 1.7 <= h / lw <= 3.2 and lw <= 2.6
        if not lo <= lw <= hi + 1e-6 and not grand:
            out.append(f"{lab}: leaf {lw:.2f} m wide is out of proportion ({lo}-{hi} m per leaf)")
        if not 2.0 <= h <= 5.0:
            out.append(f"{lab}: {h:.2f} m high is not person sized")
        # the leaf's swing area on each side (beyond the frame) must be clear up to the leaf's head
        lw_ = w / 2 if pr["double"] else w
        if pr["mode"] == "swing":
            for side, nn, key in (("inside", n_in, "in"), ("outside", -n_in, "out")):
                f0 = face.get(key, [0.15])[0]
                low = None
                for dn in (f0 + 0.3, f0 + 0.3 + (lw_ - 0.3) * 0.5, max(f0 + 0.3, lw_ * 0.9)):
                    for du in (-w / 2 + lw_ * 0.5, w / 2 - lw_ * 0.5):
                        q = p + nn * dn + u * du + Vector((0, 0, 0.6))
                        cz = G.ray("arch", q, Vector((0, 0, 1)), 30.0)
                        if cz and cz[0] + 0.6 < h + 0.03 and (low is None or cz[0] < low[0]):
                            low = cz
                if low:
                    out.append(f"{lab}: {low[3]} {low[0] + 0.6:.2f} m above the floor in the leaf's swing {side} "
                               f"(lower than the {h:.2f} m leaf)")
        # ---- swing
        if pr["mode"] == "swing":
            sides = {"auto": (1, -1), "in": (1,), "out": (-1,)}[pr["swing"]]
            leaves = [(-w / 2, 1)] + ([(w / 2, -1)] if pr["double"] else [])
            for sgn in sides:
                bad = None
                for hx, dirx in leaves:
                    hinge = p + u * hx
                    for deg in range(8, 88, 8):
                        t = math.radians(deg)
                        d = u * dirx * math.cos(t) + n_in * sgn * math.sin(t)
                        for zz in (0.08, 0.5, 1.0, 1.6, h - 0.12):
                            hit = G.ray("all", hinge + d * 0.03 + Vector((0, 0, zz)), d, lw - 0.05)
                            if hit:
                                bad = (hit[3], deg, hit[1])
                                break
                        if bad:
                            break
                    if bad:
                        break
                if bad:
                    q = bad[2]
                    out.append(f"{lab}: {bad[0]} in the leaf's swing ({'into the room' if sgn > 0 else 'outwards'}, "
                               f"{bad[1]} deg, at ({q.x:.2f}, {q.y:.2f}, {q.z:.2f}))")
    return out


# --------------------------------------------------------------------------- walk grid
def _clear_at(G, c):
    """The walk-grid node test at an arbitrary floor point c: nothing within RADIUS at the probe heights."""
    for zz in PROBE_Z:
        q = c + Vector((0, 0, zz))
        for k in range(8):
            d = Vector((math.cos(k * math.pi / 4), math.sin(k * math.pi / 4), 0))
            if G.all.ray_cast(q, d, RADIUS)[0] is not None:
                return False
    return True


def _spiral_clear(G, cx, cy, z0, z1, r, a0, sweep):
    """A person (RADIUS, HEADROOM) walking a spiral stair along radius r from its foot (a0, z0) to the top."""
    z = z0
    for k in range(0, int(sweep) + 3, 3):
        a = math.radians(a0 + k)
        c = Vector((cx + math.cos(a) * r, cy + math.sin(a) * r, z + 0.45))
        h = G.all.ray_cast(c, Vector((0, 0, -1)), 1.0)
        if h[0] is None:
            return False
        z = h[0].z
        if not _clear_at(G, Vector((c.x, c.y, z))) or \
                G.all.ray_cast(Vector((c.x, c.y, z + 0.05)), Vector((0, 0, 1)), HEADROOM - 0.05)[0] is not None:
            return False
    return z >= z1 - 0.05


class Grid:
    def __init__(self, G, bounds, log):
        t = time.time()
        (x0, y0), (x1, y1) = bounds
        x0, y0 = x0 + 0.0137, y0 + 0.0213      # off the authored round coordinates (edges, risers, joints)
        self.x0, self.y0 = x0, y0
        self.nx, self.ny = int((x1 - x0) / GRID) + 1, int((y1 - y0) / GRID) + 1
        self.nodes = []                # (i, j, z)
        self.at = collections.defaultdict(list)      # (i, j) -> node ids
        self.block = {}                # node id -> what is in the way (invalid nodes are not added)
        down = Vector((0, 0, -1))
        for i in range(self.nx):
            x = x0 + i * GRID
            for j in range(self.ny):
                y = y0 + j * GRID
                zs, above, up_last = [], 60.0, False
                o = Vector((x, y, 60.0))
                left = 70.0
                for _ in range(120):          # (five storeys of slabs, ceiling grids, rugs and planks)
                    h = G.all.ray_cast(o, down, left)
                    if h[0] is None:
                        break
                    z = h[0].z
                    if h[1].z > 0.6 and above - z >= HEADROOM:
                        zs.append(z)
                    if abs(h[1].z) > 0.1:      # (a ray grazing a vertical face - a riser - is no ceiling)
                        above, up_last = z, h[1].z > 0.0
                    left -= (o.z - z) + 0.005
                    o = Vector((x, y, z - 0.005))
                    if left <= 0:
                        break
                # (not under a single-sided floor slab: its top face is the lowest thing the ray met)
                if above >= HEADROOM and not (up_last and above < 8.0) and not any(abs(z) < 0.05 for z in zs):
                    zs.append(0.0)               # outdoors: the levelled pad the building stands on (terrain)
                for z in zs:
                    self.at[(i, j)].append(len(self.nodes))
                    self.nodes.append((i, j, z))
        self.clear = np.zeros(len(self.nodes), bool)
        dirs = [Vector((math.cos(k * math.pi / 4), math.sin(k * math.pi / 4), 0)) for k in range(8)]
        for nid, (i, j, z) in enumerate(self.nodes):
            c = Vector((x0 + i * GRID, y0 + j * GRID, z))
            why = None
            for zz in PROBE_Z:
                q = c + Vector((0, 0, zz))
                for d in dirs:
                    h = G.all.ray_cast(q, d, RADIUS)
                    if h[0] is not None:
                        why = G.all_mats[h[2]]
                        break
                if why:
                    break
            if not why:                        # inside a solid (a tier block without a bottom face, a
                back = 0                       # counter): most long rays leave through back faces
                q = c + Vector((0, 0, 1.0))
                for d in dirs:
                    h = G.all.ray_cast(q, d, 6.0)
                    back += h[0] is not None and h[1].dot(d) > 0.3
                if back >= 6:
                    why = "inside a solid"
            if why:
                self.block[nid] = why
            else:
                self.clear[nid] = True
        log(f"  walk grid: {self.nx} x {self.ny} cells, {len(self.nodes)} floor nodes, "
            f"{int(self.clear.sum())} clear ({time.time() - t:.1f} s)")

    def pos(self, nid):
        i, j, z = self.nodes[nid]
        return Vector((self.x0 + i * GRID, self.y0 + j * GRID, z))

    def flood(self, seeds):
        seen = np.zeros(len(self.nodes), bool)
        q = collections.deque()
        for s in seeds:
            if s is not None and self.clear[s] and not seen[s]:
                seen[s] = True
                q.append(s)
        while q:
            nid = q.popleft()
            i, j, z = self.nodes[nid]
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for m in self.at.get((i + di, j + dj), ()):
                    if not seen[m] and self.clear[m] and abs(self.nodes[m][2] - z) <= STEP:
                        seen[m] = True
                        q.append(m)
        return seen

    def near(self, p, r=0.45, dz=0.35, clear_only=True):
        """Node ids within r (horizontal) of p on its floor."""
        out = []
        ci, cj = int(round((p.x - self.x0) / GRID)), int(round((p.y - self.y0) / GRID))
        k = int(r / GRID) + 1
        for i in range(ci - k, ci + k + 1):
            for j in range(cj - k, cj + k + 1):
                for m in self.at.get((i, j), ()):
                    q = self.pos(m)
                    if (q.xy - p.xy).length <= r and abs(q.z - p.z) <= dz and (self.clear[m] or not clear_only):
                        out.append(m)
        return out


def check_paths(aset, G, log, region=None):
    xs = [v.x for mb in aset.meshes.values() for v in mb.verts]
    ys = [v.y for mb in aset.meshes.values() for v in mb.verts]
    (cx0, cy0), (cx1, cy1) = LOC["clamp"]
    bounds = ((max(min(xs), cx0), max(min(ys), cy0)), (min(max(xs), cx1), min(max(ys), cy1)))
    if region:
        bounds = ((region[0], region[1]), (region[2], region[3]))
    grid = Grid(G, bounds, log)
    seeds = []
    for s in aset.sockets:                   # the fast-travel arrivals (lobby, arena, shop, wings, annex)
        if s["type"] == "travel":
            seeds += grid.near(Vector(s["pos"]), r=1.0)
    for sp in LOC["seeds"]:
        seeds += grid.near(Vector(sp), r=LOC["seed_r"], dz=2.5)
    if region:                                     # a focused run: flood from wherever the region starts
        seeds += grid.near(Vector((region[4], region[5], region[6])), r=1.0)
    seen = grid.flood(seeds)
    # doorways narrower than the grid can resolve (a 0.8 m WC door leaves the 0.34 m person 6 cm a side): an
    # exact test along the door's normal through its centre; when it passes, flood on from the far side
    for _ in range(4):
        more = []
        for s in aset.sockets:
            if s["type"] != "door":
                continue
            p = Vector(s["pos"])
            a = math.radians(s["yaw"])
            n_in = Vector((-math.sin(a), math.cos(a), 0.0))
            sides = [grid.near(p + n_in * sg * 0.75, 0.45) for sg in (1, -1)]
            got = [any(seen[m] for m in ids) for ids in sides]
            if got[0] == got[1] or not all(sides):
                continue
            far = sides[1] if got[0] else sides[0]
            z_far = grid.pos(far[0]).z
            if all(_clear_at(G, p + n_in * t + Vector((0, 0, max(p.z, z_far) - p.z)))
                   for t in [k * 0.1 - 0.7 for k in range(15)]):
                more += far
        # spiral stairs tighter than the grid resolves (a 0.32 m walking band between the post and the rail):
        # an exact walk along the middle of the treads; when it passes, flood on from the top
        for (cx, cy, z0, z1, r_in, r_out, a0, step) in SPIRALS:
            rm = (r_in + r_out) / 2.0
            n = max(4, int(round((z1 - z0) / 0.19)))
            ends = []
            for (ang, zz) in ((a0 - 25.0, z0), (a0 + step * n + 25.0, z1)):
                q = Vector((cx + math.cos(math.radians(ang)) * (r_out + 0.3),
                            cy + math.sin(math.radians(ang)) * (r_out + 0.3), zz))
                ends.append(grid.near(q, 0.6))
            got = [any(seen[m] for m in ids) for ids in ends]
            if not all(ends) or got[0] == got[1] or not _spiral_clear(G, cx, cy, z0, z1, rm, a0, step * n):
                continue
            more += ends[1] if got[0] else ends[0]
        if not more:
            break
        seen |= grid.flood(more + list(np.flatnonzero(seen)))
    log(f"  reachable from the entrances: {int(seen.sum())} of {int(grid.clear.sum())} clear nodes "
        f"({len(seeds)} seed nodes)")
    out = []

    def status(p, r=0.45):
        ids = grid.near(p, r, clear_only=False)
        if not ids:
            return "no floor"
        if any(seen[m] for m in ids):
            return None
        clear = [m for m in ids if grid.clear[m]]
        if not clear:
            whats = collections.Counter(grid.block.get(m, "?") for m in ids)
            return "blocked by " + ", ".join(w for w, _ in whats.most_common(2))
        return "not reachable from the entrance"

    inside = (lambda p: True) if not region else (
        lambda p: region[0] + 1 < p.x < region[2] - 1 and region[1] + 1 < p.y < region[3] - 1)
    for s in aset.sockets:
        if s["type"] != "door" or not inside(Vector(s["pos"])):
            continue
        p = Vector(s["pos"])
        a = math.radians(s["yaw"])
        n_in = Vector((-math.sin(a), math.cos(a), 0.0))
        pr = s["props"]
        lab = f"door {pr['style']} {pr['width']:.2f}x{pr['height']:.2f} @ ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})"
        res = {}
        for side, sg in (("inside", 1), ("outside", -1)):
            res[side] = status(p + n_in * sg * 0.75)
        # the doorway itself: a person fits through
        mid = status(p, r=min(0.45, pr["width"] / 2))
        bad = {k: v for k, v in res.items() if v}
        if bad:
            out.append(f"{lab}: " + "; ".join(f"{k} {v}" for k, v in bad.items()))
        elif mid and mid != "no floor" and not any(res.values()):
            out.append(f"{lab}: doorway {mid}")
    for s in aset.sockets:
        if not inside(Vector(s["pos"])):
            continue
        if s["type"] in ("npc", "travel"):
            p = Vector(s["pos"])
            why = status(p, 0.5)
            if why:
                what = f"npc {s['props'].get('dorm', '')}" if s["type"] == "npc" else f"travel {s['props']['id']}"
                out.append(f"{what} at ({p.x:.2f}, {p.y:.2f}, {p.z:.2f}): {why}")
        elif s["type"] == "camera" and s["props"].get("label"):
            c = Vector(s["pos"])
            h = G.arch.ray_cast(c, Vector((0, 0, -1)), 6.0)
            if h[0] is None:
                continue
            f = Vector((c.x, c.y, h[0].z))
            ids = grid.near(f, 2.5, dz=0.6, clear_only=False)
            if ids and not any(seen[m] for m in ids):
                out.append(f"room {s['props']['label']}: no reachable floor round the camera")
    # big clear areas nobody can reach (an enclosed room / a corner cut off by furniture)
    lost = grid.clear & ~seen
    comp = np.full(len(grid.nodes), -1)
    sizes = []
    for nid in np.flatnonzero(lost):
        if comp[nid] >= 0:
            continue
        cid = len(sizes)
        q = collections.deque([nid])
        comp[nid] = cid
        members = []
        while q:
            m = q.popleft()
            members.append(m)
            i, j, z = grid.nodes[m]
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for k in grid.at.get((i + di, j + dj), ()):
                    if lost[k] and comp[k] < 0 and abs(grid.nodes[k][2] - z) <= STEP:
                        comp[k] = cid
                        q.append(k)
        sizes.append(members)
    for members in sizes:
        area = len(members) * GRID * GRID
        if area < 2.0:
            continue
        zs = [grid.nodes[m][2] for m in members]
        ps = [grid.pos(m) for m in members]
        sample = ps[:: max(1, len(ps) // 40)]
        covered = sum(1 for q in sample if G.arch.ray_cast(q + Vector((0, 0, 0.3)), Vector((0, 0, 1)), 12.0)[0])
        if covered < len(sample) / 2:
            continue                     # a roof / terrace top under the open sky: not a room nobody can reach
        cx, cy = sum(p.x for p in ps) / len(ps), sum(p.y for p in ps) / len(ps)
        zmed = sorted(zs)[len(zs) // 2]
        # furniture tops (desks, counters, beds, a kotatsu over its table) are floor-like surfaces of their own:
        # skip what is clearly above the room floor - the lowest upward face within 1.5 m below
        o, low = Vector((cx, cy, zmed - 0.02)), None
        for _ in range(12):
            h = G.arch.ray_cast(o, Vector((0, 0, -1)), 1.5 - (zmed - 0.02 - o.z))
            if h[0] is None:
                break
            if h[1].z > 0.6:
                low = h[0].z
            o = Vector((cx, cy, h[0].z - 0.002))
        if low is not None and zmed - low > STEP and area < 12.0:
            continue
        out.append(f"unreachable floor {area:.1f} m2 round ({cx:.1f}, {cy:.1f}, {zmed:.2f})")
    return out, grid, seen


# --------------------------------------------------------------------------- npcs
def check_npcs(aset, log):
    ck = placement.asset_checker(aset, log=lambda m: None)
    doors = placement._door_zones(aset)
    out = []
    n = 0
    for s in aset.sockets:
        if s["type"] != "npc":
            continue
        n += 1
        p = Vector(s["pos"])
        why = ck.capsule(p, r=placement.NPC_R)
        if why is None and any((p.xy - d.xy).length < r and abs(p.z - d.z) < 1.5 for d, r in doors):
            why = "in a doorway"
        if why is None and s["props"].get("wander", 0) >= 1.0:
            if not ck.wander_points(p, s["props"]["wander"], 3):
                why = f"no clear wander spot within {s['props']['wander']:.1f} m"
        if why and why != "no floor under the feet":
            out.append(f"npc {s['props'].get('dorm', '')} at ({p.x:.2f}, {p.y:.2f}, {p.z:.2f}): {why}")
    log(f"  {n} NPC spots")
    return out


# --------------------------------------------------------------------------- walls
def _in_opening(p0, d, L, ops):
    """Does the segment p0 -> p0 + d * L pass through one of the openings (door / window rectangles)?"""
    for o in ops:
        a = math.radians(o["yaw"])
        n = Vector((-math.sin(a), math.cos(a), 0.0))
        u = Vector((math.cos(a), math.sin(a), 0.0))
        c = Vector(o["pos"])
        den = d.dot(n)
        if abs(den) < 1e-6:
            continue
        t = (c - p0).dot(n) / den
        if not 0.0 <= t <= L:
            continue
        q = p0 + d * t
        if abs((q - c).dot(u)) <= o["w"] / 2 + 0.05 and c.z - 0.05 <= q.z <= c.z + o["h"] + 0.05:
            return True
    return False


def check_walls(aset, G, grid, seen, log):
    out = []
    ops = list(OPENINGS) + [dict(pos=s["pos"], yaw=s["yaw"], w=s["props"]["width"], h=s["props"]["height"])
                            for s in aset.sockets if s["type"] == "door"]
    up = Vector((0, 0, 1))
    leaks = {}
    backs = {}
    nd = 96
    dirs = [Vector((math.cos(2 * math.pi * k / nd), math.sin(2 * math.pi * k / nd), 0)) for k in range(nd)]
    sample = [nid for nid in np.flatnonzero(seen) if grid.nodes[nid][0] % 5 == 0 and grid.nodes[nid][1] % 5 == 0
              and grid.nodes[nid][2] > LOC["leak_z"]]        # the building's floors (not the ground round it)
    holes = [(Vector(o["pos"]), o["w"] / 2 + 0.6) for o in ops]
    for nid in sample:
        c = grid.pos(nid)
        hu = G.arch.ray_cast(c + Vector((0, 0, 0.3)), up, 60.0)
        if hu[0] is None:
            continue                       # outdoors
        if any((c.xy - q.xy).length < r and abs(c.z - q.z) < 1.0 for q, r in holes):
            continue                       # standing in / at a doorway: its rays leave through it
        # a spot under a canopy / eave / walkway roof sees the open air over a wide fan, or straight along a
        # compass line (over a railing, down an open stair) at standing height: it is outdoors, not in a room
        # with a gap (a gap in a room wall is a narrow fan of escaping rays)
        o = c + Vector((0, 0, 1.2))
        free = [_open_air(G, o, d) and not _in_opening(o, d, 120.0, ops) for d in dirs]
        if sum(free) > nd // 4 or (sum(free[k] for k in range(0, nd, nd // 8)) and sum(free) >= 3):
            continue
        for zz in (1.2, 2.3):
            if zz > hu[3] + 0.3 - 0.1:
                continue                   # (not above the room's ceiling)
            o = c + Vector((0, 0, zz))
            for d in dirs:
                h = G.all.ray_cast(o, d, 120.0)
                if h[0] is None:
                    if _in_opening(o, d, 120.0, ops):
                        continue
                    # where does it leave the building? first sample point with no roof over it
                    for k in range(1, 480):
                        q = o + d * (k * 0.25)
                        if G.arch.ray_cast(q, up, 60.0)[0] is None:
                            key = (round(q.x), round(q.y), round(q.z))
                            leaks.setdefault(key, (q, c))
                            break
                    continue
                if h[1].dot(d) > 0.3 and h[3] < 40.0 and "Glass" not in G.all_mats[h[2]] \
                        and not G.all_mats[h[2]].startswith("PROP:") \
                        and "Trim" not in G.all_mats[h[2]] and "Frame" not in G.all_mats[h[2]] \
                        and _back_confirmed(G, o, d, h):
                    # (window linings / frames: open-ended boxes whose ends are coplanar with the wall cut)
                    m = G.all_mats[h[2]]
                    key = (round(h[0].x * 2) / 2, round(h[0].y * 2) / 2, round(h[0].z), m)
                    backs.setdefault(key, (h[0], c, m))
    for key, (q, c) in sorted(leaks.items()):
        out.append(f"leak: a ray from ({c.x:.1f}, {c.y:.1f}, {c.z:.2f}) escapes at ({q.x:.1f}, {q.y:.1f}, {q.z:.1f}) "
                   f"without passing a doorway or window")
    for key, (q, c, m) in sorted(backs.items()):
        out.append(f"back face: {m} at ({q.x:.2f}, {q.y:.2f}, {q.z:.2f}) seen from inside "
                   f"({c.x:.1f}, {c.y:.1f}, {c.z:.2f})")
    out += _coplanar(aset, G)
    return out


OUTDOOR_PROPS = ("Tree", "Palm", "Bush", "Hedge", "Flower", "LampPost", "Flagpole", "Umbrella")


def _back_confirmed(G, o, d, h):
    """A back-face hit that rays 1 cm beside it repeat (a missing face). A ray that grazes the exact edge
    where two faces meet (a cheek's bottom edge, a case's front corner) can report either face; the rays beside
    it then hit the front face."""
    side = Vector((-d.y, d.x, 0.0)) * 0.01
    n = 0
    for off in (Vector((0, 0, 0.01)), Vector((0, 0, -0.01)), side, -side):
        g = G.all.ray_cast(o + off, d, 120.0)
        n += g[0] is not None and g[1].dot(d) > 0.3 and abs(g[3] - h[3]) < 0.1
    return n >= 3


def _open_air(G, o, d):
    """A horizontal ray that meets nothing, or only a tree / bush (whose prop box is not a wall) in front of
    no architecture."""
    h = G.all.ray_cast(o, d, 120.0)
    if h[0] is None:
        return True
    m = G.all_mats[h[2]]
    return m.startswith("PROP:") and any(k in m for k in OUTDOOR_PROPS) and G.arch.ray_cast(o, d, 120.0)[0] is None


def _faces(aset):
    """Axis-aligned planar faces: (axis, sign, plane, (a0, b0, a1, b1), material, mesh, area)."""
    out = []
    for name, mb in aset.meshes.items():
        if not mb.faces:
            continue
        V = np.array([(v.x, v.y, v.z) for v in mb.verts])
        for f, m in zip(mb.faces, mb.face_mats):
            if len(f) < 3 or _soft(m) or m in ("M_IntGlassClear", "M_GlassClear", "M_Glass"):
                continue
            P = V[list(f)]
            mn, mx = P.min(0), P.max(0)
            ext = mx - mn
            ax = int(np.argmin(ext))
            if ext[ax] > 1e-4:
                continue
            o = [k for k in range(3) if k != ax]
            if len(f) != 4:
                continue           # rectangles only (boxes): the area test below assumes them
            if not all(min(abs(P[k][i] - mn[i]), abs(P[k][i] - mx[i])) < 1e-4 for k in range(4) for i in o):
                continue           # (a parallelogram - the side of a sloped beam - is not its bounding rectangle)
            nrm = np.cross(P[1] - P[0], P[2] - P[0])
            sg = 1 if nrm[ax] > 0 else -1
            area = ext[o[0]] * ext[o[1]]
            if area < 1e-4:
                continue
            out.append((ax, sg, round(float(mn[ax]), 4), (mn[o[0]], mn[o[1]], mx[o[0]], mx[o[1]]), m, name, area))
    return out


def _coplanar(aset, G=None, min_area=0.02):
    faces = _faces(aset)
    groups = collections.defaultdict(list)
    for f in faces:
        groups[(f[0], f[1], round(f[2], 3))].append(f)
    zf = {}
    for key, lst in groups.items():
        if len(lst) < 2:
            continue
        lst.sort(key=lambda f: f[3][0])
        for i, f in enumerate(lst):
            a0, b0, a1, b1 = f[3]
            for g in lst[i + 1:]:
                c0, d0, c1, d1 = g[3]
                if c0 >= a1 - 1e-4:
                    break
                if g[4] == f[4]:
                    continue
                ov = (min(a1, c1) - max(a0, c0)) * (min(b1, d1) - max(b0, d0))
                if ov <= 1e-4 or min(a1, c1) - max(a0, c0) < 0.01 or min(b1, d1) - max(b0, d0) < 0.01:
                    continue
                ax = key[0]
                cx, cy = (max(a0, c0) + min(a1, c1)) / 2, (max(b0, d0) + min(b1, d1)) / 2
                pt = [0, 0, 0]
                pt[ax] = key[2]
                o = [k for k in range(3) if k != ax]
                pt[o[0]], pt[o[1]] = cx, cy
                if G is not None:
                    # only what can be seen: from 0.5 m in front of the overlap, the ray reaches the face
                    nrm = [0.0, 0.0, 0.0]
                    nrm[ax] = float(key[1])
                    c = Vector(pt)
                    n = Vector(nrm)
                    o = c + n * 0.5
                    h = G.all.ray_cast(o, -n, 0.6)
                    if h[0] is None or (h[0] - c).length > 0.004 or h[1].dot(-n) > 0.0:
                        continue                         # covered, or only reached from behind
                    hb = G.all.ray_cast(o, n, 3.0)       # the eye must not be inside a solid (a wall)
                    if hb[0] is not None and hb[1].dot(n) > 0.3:
                        continue
                k2 = (tuple(round(v) for v in pt), tuple(sorted((f[4], g[4]))))
                zf[k2] = zf.get(k2, 0.0) + ov
    out = []
    for (pt, mats), area in sorted(zf.items()):
        if area >= min_area:
            out.append(f"z-fighting: {mats[0]} / {mats[1]} coplanar over {area:.2f} m2 near {pt}")
    # wall-face steps: large vertical faces on near-identical planes that meet edge to edge
    big = [f for f in faces if f[0] in (0, 1) and f[6] >= 0.5 and (f[3][3] - f[3][1]) >= 1.0]
    byax = collections.defaultdict(list)
    for f in big:
        byax[(f[0], f[1])].append(f)
    steps = {}
    for key, lst in byax.items():
        lst.sort(key=lambda f: f[2])
        planes = np.array([f[2] for f in lst])
        for i, f in enumerate(lst):
            j = i + 1
            while j < len(lst) and planes[j] - planes[i] <= 0.04:
                g = lst[j]
                j += 1
                dpl = g[2] - f[2]
                if dpl < 0.003 or not all(("Wall" in m or "Plaster" in m) for m in (f[4], g[4])):
                    continue                     # (trims, linings and wainscots stand proud on purpose)
                a0, b0, a1, b1 = f[3]
                c0, d0, c1, d1 = g[3]
                zov = min(b1, d1) - max(b0, d0)
                if zov < 0.5:
                    continue
                touch = min(abs(a1 - c0), abs(c1 - a0))
                if touch > 0.01 or (min(a1, c1) - max(a0, c0)) > 0.01:
                    continue
                u = a1 if abs(a1 - c0) < abs(c1 - a0) else a0
                pt = [0.0, 0.0]
                pt[key[0]] = f[2]
                pt[1 - key[0]] = u
                k2 = (round(pt[0], 1), round(pt[1], 1))
                steps[k2] = (dpl, f[4], g[4], max(b0, d0), min(b1, d1))
    for (x, y), (dpl, m0, m1, z0, z1) in sorted(steps.items()):
        out.append(f"wall step: faces {100 * dpl:.1f} cm apart meet at ({x:.1f}, {y:.1f}) z {z0:.2f}-{z1:.2f} "
                   f"({m0} / {m1})")
    return out


def _cell(cid):
    """A portal room (dai/assets/interiors.py) with its story marks (anchors.json) as NPC spots, flooded from
    the arrival point inside its door."""
    from dai.assets import interiors
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "DuelAcademyIsland", "Content", "Data", "World")
    cells = {c["id"]: c for c in json.load(open(os.path.join(root, "interiors.json")))["cells"]}
    cell = cells[cid]
    aset = interiors.build_cell(cell)
    o = cell["origin_ue"]
    for a in json.load(open(os.path.join(root, "anchors.json")))["anchors"]:
        if a.get("interior_id") == cid and a.get("kind") in ("npc", "player"):
            p = a.get("position_ue")
            aset.npc(((p[0] - o[0]) / 100.0, -(p[1] - o[1]) / 100.0, interiors.FZ), 0.0,
                     dorm=a["id"], wander=0.0)
    w, d, h = interiors._dims(cell)
    arr = cell.get("arrival_ue") or o
    seed = ((arr[0] - o[0]) / 100.0, -(arr[1] - o[1]) / 100.0, interiors.FZ)
    return aset, dict(seeds=[seed, (0.0, d / 2.0 - 0.8, interiors.FZ)], seed_r=0.6, leak_z=-1.0,
                      clamp=((-w / 2 - 1.0, -d / 2 - 1.0), (w / 2 + 1.0, d / 2 + 1.0)))


# --------------------------------------------------------------------------- main
def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--location", default="academy",
                    help=f"{', '.join(sorted(LOCATIONS))} or cell:<interior id> (a portal room of interiors.json)")
    ap.add_argument("--only", default="doors,paths,npcs,walls")
    ap.add_argument("--json", default=None)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--region", default=None, help="x0,y0,x1,y1,sx,sy,sz: walk grid over that box only, "
                    "flooded from (sx, sy, sz) as well (for looking into one spot)")
    args = ap.parse_args(argv)
    only = set(args.only.split(","))
    global LOC
    _record_openings()
    blend.reset_scene()
    t = time.time()
    if args.location.startswith("cell:"):
        aset, LOC = _cell(args.location[5:])
    else:
        import importlib
        LOC = LOCATIONS[args.location]
        A = importlib.import_module("dai.assets." + LOC["module"])
        aset = A.PLACEMENTS[args.location]()
    print(f"  {args.location} built ({time.time() - t:.1f} s): {sum(len(m.faces) for m in aset.meshes.values())} faces, "
          f"{sum(1 for s in aset.sockets if s['type'] == 'door')} doors, {len(OPENINGS)} wall openings")
    res = {}
    if "npcs" in only:
        res["npcs"] = check_npcs(aset, print)
    G = Geo(aset) if only & {"doors", "paths", "walls"} else None
    if "doors" in only:
        res["doors"] = check_doors(aset, G, print)
    grid = seen = None
    if only & {"paths", "walls"}:
        region = [float(v) for v in args.region.split(",")] if args.region else None
        res["paths"], grid, seen = check_paths(aset, G, print, region)
        if "paths" not in only:
            res.pop("paths")
    if "walls" in only:
        res["walls"] = check_walls(aset, G, grid, seen, print)
    total = 0
    for k, lst in res.items():
        total += len(lst)
        print(f"[{k}] {len(lst)}")
        for line in lst[:args.limit]:
            print("   " + line)
        if len(lst) > args.limit:
            print(f"   ... {len(lst) - args.limit} more")
    if args.json:
        with open(args.json, "w") as fp:
            json.dump(res, fp, indent=1)
    print(f"{args.location.upper().replace('CELL:', '')} ISSUES: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
