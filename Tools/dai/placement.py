"""
Standing-room checks for people: fast-travel arrival points and NPC spots.

A person is a capsule (radius 0.36-0.38 m, 1.84 m tall) standing with its feet on a floor. A spot is clear when
  * there is a floor under the feet (a building floor, or the terrain outdoors) within FLOOR_TOL,
  * nothing - wall, built-in fixture, procedural furniture (also the no-collision kind NPCs would walk through),
    catalog prop - reaches into the capsule (rays round its axis at five heights, rays up through it),
  * the feet are not inside a solid (most long rays from the chest leave through a back face),
  * outdoors: the ground is above the water and not steeper than the walkable slope.

NPC wander routes are precomputed: spots round the NPC's home that are clear, on the same floor and reachable
along a straight, clear, floored line - the NPC only ever walks home <-> one of them (DAStudentNPC).

Geometry lives in "spaces": BVH trees in their own frame (a location in its local frame, the world prop boxes in
world space). Used by the layout stage (the whole island) and by inspect.audit (one location on its own).
"""

import json
import math
import os

from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import config as C

NPC_R, PLAYER_R, HEIGHT = 0.36, 0.38, 1.84
FLOOR_TOL = 0.15
HEIGHTS = (0.3, 0.65, 1.0, 1.35, 1.7)
WALK_SLOPE = 40.0            # deg; the player's limit is 46, NPCs 40
# materials a person may stand in (water surfaces, light shafts, decals painted on the floor)
SOFT = ("Water", "Lava", "LightShaft", "Smoke", "Steam", "Decal", "Puddle")
# catalog props that are no obstacle (foliage you push through, flat things on the floor)
SOFT_PROPS = {"SM_GrassClump_A", "SM_Fern_A", "SM_FlowerBush_Red", "SM_FlowerBush_Yellow", "SM_FlowerBush_Blue",
              "SM_FlowerBush_White", "SM_Bush_A", "SM_Bush_B", "SM_Pebbles_A"}


# --------------------------------------------------------------------------- prop boxes
def _trunk_spec(name, P):
    """The registry entry of a third-party tree whose collision is its trunk column, else None."""
    if not P.is_thirdparty(name):
        return None
    from . import thirdparty
    spec = thirdparty.registry()["props"][name]
    return spec if spec.get("collision") == "trunk" else None


def prop_bounds(names, log=print):
    """Local AABB (min, max) per catalog prop, cached in .cache/prop_bounds.json (rebuilt when the prop
    sources change). A tree is its trunk, as in the game (its collision is the trunk column): people stand
    and walk under its crown."""
    from .assets import props as P
    src = [os.path.join(C.TOOLS_DIR, "dai", "assets", f) for f in ("props.py", "furniture.py")]
    src.append(os.path.abspath(__file__))
    src += [os.path.join(C.TOOLS_DIR, "thirdparty", "registry", f) for f in os.listdir(
        os.path.join(C.TOOLS_DIR, "thirdparty", "registry")) if f.endswith(".json")]
    stamp = max(os.path.getmtime(p) for p in src if os.path.exists(p))
    path = os.path.join(C.CACHE_DIR, "prop_bounds.json")
    cache = {}
    if os.path.exists(path):
        with open(path) as fp:
            d = json.load(fp)
        if d.get("stamp") == stamp:
            cache = d["bounds"]
    todo = [n for n in sorted(set(names)) if n not in cache and n in P.REGISTRY]
    if todo:
        import bpy
        for n in todo:
            o = P.build_object(n, "_bounds_" + n)
            vs = [v.co for v in o.data.vertices] if o.type == "MESH" else []
            for ch in o.children_recursive:
                if ch.type == "MESH":
                    vs += [ch.matrix_parent_inverse @ v.co for v in ch.data.vertices]
            if vs:
                cache[n] = [[min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]]
                spec = _trunk_spec(n, P)
                if spec is not None:
                    r, z0, z1 = spec.get("trunk_radius", 0.3), cache[n][0][2], cache[n][1][2]
                    cache[n] = [[-r, -r, z0], [r, r, z0 + spec.get("trunk_height", (z1 - z0) * 0.55)]]
            me = o.data if o.type == "MESH" else None
            bpy.data.objects.remove(o, do_unlink=True)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        os.makedirs(C.CACHE_DIR, exist_ok=True)
        with open(path, "w") as fp:
            json.dump(dict(stamp=stamp, bounds=cache), fp)
        log(f"  placement: measured {len(todo)} prop boxes")
    return cache


# trees: only the trunk is in the way (the crown is overhead) - trunk half-width at scale 1
TRUNKS = {"SM_PalmTree_A": 0.3, "SM_PalmTree_B": 0.25, "SM_BroadTree_A": 0.4, "SM_BroadTree_B": 0.45,
          "SM_BroadTree_C": 0.3, "SM_PineTree_A": 0.4, "SM_DeadTree_A": 0.3}


def box_tris(items, bounds, verts, polys, tags, tag_fn=None):
    """Append oriented boxes [(asset, (x, y, z), yaw_deg, scale)] to a polygon soup."""
    for (asset, p, yaw, sc) in items:
        b = bounds.get(asset)
        if asset in TRUNKS and sc >= 0.9:          # a small (potted / indoor) tree's crown is at head height
            r = TRUNKS[asset]
            b = [[-r, -r, -0.5], [r, r, 3.0]]
        if not b:
            continue
        (x0, y0, z0), (x1, y1, z1) = b
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        base = len(verts)
        for (x, y, z) in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                          (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)):
            x, y, z = x * sc, y * sc, z * sc
            verts.append(Vector((p[0] + x * c - y * s, p[1] + x * s + y * c, p[2] + z)))
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            polys.append([base + i for i in f])
            tags.append(tag_fn(asset) if tag_fn else asset)


# --------------------------------------------------------------------------- spaces
class Space:
    """A BVH in its own frame: world point = R(yaw) * local + offset."""

    def __init__(self, bvh, tags, x=0.0, y=0.0, z=0.0, yaw=0.0, name="", bounds=None):
        self.bvh, self.tags, self.name = bvh, tags, name
        self.o = Vector((x, y, z))
        self.c, self.s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        self.bounds = bounds          # world-space (min, max) or None (everywhere)

    def to_local(self, p, d=None):
        q = p - self.o
        lp = Vector((q.x * self.c + q.y * self.s, -q.x * self.s + q.y * self.c, q.z))
        if d is None:
            return lp
        return lp, Vector((d.x * self.c + d.y * self.s, -d.x * self.s + d.y * self.c, d.z))

    def near(self, p, margin):
        if self.bounds is None:
            return True
        mn, mx = self.bounds
        return all(mn[i] - margin <= p[i] <= mx[i] + margin for i in range(3))

    def ray(self, p, d, dist):
        lp, ld = self.to_local(p, d)
        loc, nrm, idx, t = self.bvh.ray_cast(lp, ld, dist)
        if loc is None:
            return None
        nw = Vector((nrm.x * self.c - nrm.y * self.s, nrm.x * self.s + nrm.y * self.c, nrm.z))
        return t, nw, self.tags[idx]


def mesh_space(meshes, x=0.0, y=0.0, z=0.0, yaw=0.0, name="", extra=()):
    """Space from MeshBuilders (all of them: collision and _NoCol) plus extra (verts, polys, tags) soups."""
    verts, polys, tags = [], [], []
    for mb in meshes:
        base = len(verts)
        verts.extend(mb.verts)
        for f, m in zip(mb.faces, mb.face_mats):
            if len(f) >= 3:
                polys.append([base + i for i in f])
                tags.append(m)
    for (ev, ep, et) in extra:
        base = len(verts)
        verts.extend(ev)
        polys.extend([[base + i for i in f] for f in ep])
        tags.extend(et)
    if not polys:
        return None
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    wx = [x + v.x * c - v.y * s for v in verts]
    wy = [y + v.x * s + v.y * c for v in verts]
    wz = [z + v.z for v in verts]
    bounds = ((min(wx), min(wy), min(wz)), (max(wx), max(wy), max(wz)))
    return Space(BVHTree.FromPolygons(verts, polys, all_triangles=False), tags, x, y, z, yaw, name, bounds)


def soft(tag):
    return any(k in tag for k in SOFT)


# --------------------------------------------------------------------------- the checker
class Checker:
    def __init__(self, spaces, ground=None, water=None, slope=None, ground_fallback=False):
        """ground(x, y) -> terrain z (None indoors-only), water(x, y) -> water surface z or None,
        slope(x, y) -> ground slope in degrees. ground_fallback: the ground only counts where no built floor
        is found (a location checked on its own: its pad plane, which sunken floors lie below)."""
        self.spaces = [s for s in spaces if s is not None]
        self.ground, self.water, self.slope = ground, water, slope
        self.ground_fallback = ground_fallback

    def _hit(self, p, d, dist, spaces, through_props=False):
        """First solid hit along the ray (soft materials are passed through; catalog props too when
        through_props - nobody stands on a kettle or a bench)."""
        start, left = Vector(p), dist
        for _ in range(12):
            best = None
            for sp in spaces:
                h = sp.ray(start, d, left)
                if h and (best is None or h[0] < best[0]):
                    best = h
            if best is None:
                return None
            if not soft(best[2]) and not (through_props and best[2].startswith("SM_")):
                return (dist - left + best[0], best[1], best[2])
            step = best[0] + 0.002
            start, left = start + d * step, left - step
            if left <= 0:
                return None
        return None

    def spaces_at(self, p, margin=12.0):
        return [s for s in self.spaces if s.near(p, margin)]

    def floor(self, p, spaces=None, above=0.6, below=1.2):
        """Height of the walking surface under p (building floor or terrain), with what it is."""
        spaces = self.spaces_at(p) if spaces is None else spaces
        zf = None              # five probes under the feet (boards have gaps, gratings have holes)
        for (ox, oy) in ((0.0, 0.0), (0.15, 0.0), (-0.15, 0.0), (0.0, 0.15), (0.0, -0.15)):
            top = Vector((p.x + ox, p.y + oy, p.z + above))
            h = self._hit(top, Vector((0, 0, -1)), above + below, spaces, through_props=True)
            if h and (zf is None or top.z - h[0] > zf[0]):
                zf = (top.z - h[0], h[2])
        top = Vector((p.x, p.y, p.z + above))
        if self.ground is not None and not (self.ground_fallback and zf is not None):
            g = self.ground(p.x, p.y)
            if g <= top.z and (zf is None or g > zf[0]):
                zf = (g, "terrain")
        return zf

    def capsule(self, p, r=NPC_R, h=HEIGHT, spaces=None):
        """None when a person fits at feet position p, else the reason."""
        p = Vector(p)
        spaces = self.spaces_at(p) if spaces is None else spaces
        f = self.floor(p, spaces)
        if f is None:
            return "no floor under the feet"
        if abs(f[0] - p.z) > FLOOR_TOL:
            return f"feet {p.z - f[0]:+.2f} m off the floor ({f[1]})"
        if f[1] == "terrain":
            if self.water is not None:
                w = self.water(p.x, p.y)
                if w is not None and w > p.z - 0.05:
                    return "standing in water"
            if self.slope is not None and self.slope(p.x, p.y) > WALK_SLOPE:
                return f"ground too steep ({self.slope(p.x, p.y):.0f} deg)"
        n = 16
        for z in HEIGHTS:
            if z > h:
                continue
            c = Vector((p.x, p.y, p.z + z))
            for k in range(n):
                a = 2 * math.pi * k / n
                d = Vector((math.cos(a), math.sin(a), 0.0))
                hit = self._hit(c, d, r, spaces)
                if hit:
                    return f"{hit[2]} {hit[0]:.2f} m from the axis at {z:.2f} m"
        for k in range(9):        # up through the body (table tops, low beams, shelves)
            a = 2 * math.pi * k / 8
            rr = 0.0 if k == 8 else r * 0.8
            c = Vector((p.x + math.cos(a) * rr, p.y + math.sin(a) * rr, p.z + 0.12))
            hit = self._hit(c, Vector((0, 0, 1)), h - 0.12, spaces)
            if hit:
                return f"{hit[2]} {hit[0] + 0.12:.2f} m above the feet"
        # inside a solid: most long rays from the chest leave through a back face
        back = 0
        c = Vector((p.x, p.y, p.z + 1.0))
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            d = Vector((math.cos(a), math.sin(a), 0.0))
            hit = self._hit(c, d, 1.5, spaces)       # a piece of furniture, not a room with outward-facing panes
            if hit and hit[1].dot(d) > 0.2 and "Glass" not in hit[2]:
                back += 1
        if back >= 6:
            return "inside a solid"
        return None

    def path(self, p0, p1, r=NPC_R, spaces=None, step=0.4):
        """None when a person can walk the straight line p0 -> p1 (both feet positions) on one floor."""
        p0, p1 = Vector(p0), Vector(p1)
        spaces = self.spaces_at(p0, 20.0) if spaces is None else spaces
        d = p1 - p0
        d.z = 0.0
        L = d.length
        if L < 1e-3:
            return None
        d.normalize()
        side = Vector((-d.y, d.x, 0.0))
        for z in (0.3, 0.9, 1.5):
            for o in (-r * 0.9, 0.0, r * 0.9):
                c = p0 + side * o + Vector((0, 0, z))
                hit = self._hit(c, d, L, spaces)
                if hit:
                    return f"{hit[2]} across the way"
        n = max(1, int(L / step))
        for i in range(1, n + 1):
            q = p0 + (p1 - p0) * (i / n)
            f = self.floor(Vector((q.x, q.y, p0.z)), spaces, above=0.5, below=0.6)
            if f is None or abs(f[0] - p0.z) > 0.35:
                return "the floor drops away"
            if f[1] == "terrain":
                if self.water is not None:
                    w = self.water(q.x, q.y)
                    if w is not None and w > f[0] - 0.2:
                        return "water"
                if self.slope is not None and self.slope(q.x, q.y) > WALK_SLOPE - 8.0:
                    return "steep ground"
        return None

    def wander_points(self, home, radius, max_points=6):
        """Clear spots round home reachable in a straight line (feet positions)."""
        home = Vector(home)
        if radius < 1.0:
            return []
        spaces = self.spaces_at(home, radius + 12.0)
        rings = sorted({max(1.0, radius * f) for f in (0.3, 0.55, 0.8, 1.0)})
        cands = []
        for ri, rr in enumerate(rings):
            for k in range(12):
                a = 2 * math.pi * (k + 0.5 * (ri % 2)) / 12
                q = Vector((home.x + math.cos(a) * rr, home.y + math.sin(a) * rr, home.z))
                f = self.floor(q, spaces, above=0.4, below=0.5)
                if f is None or abs(f[0] - home.z) > 0.3:
                    continue
                q.z = f[0]
                if self.capsule(q, spaces=spaces) or self.path(home, q, spaces=spaces):
                    continue
                cands.append(q)
        out = []
        while cands and len(out) < max_points:      # spread out: farthest from the chosen ones (and home)
            best = max(cands, key=lambda c: min([(c - home).length] + [(c - o).length for o in out]))
            out.append(best)
            cands.remove(best)
        return out


# --------------------------------------------------------------------------- one location on its own
def asset_checker(aset, log=print):
    """Checker for an AssetSet in its local frame (no terrain: spots without a building floor are outdoors
    and only checked for obstacles)."""
    floating = {}
    for s in aset.sockets:
        if s["type"] == "floating":
            floating[s["props"].get("mesh")] = s
    spaces = []
    fixed = [mb for n, mb in aset.meshes.items() if mb.verts and n not in floating]
    props = [(s["props"]["asset"], s["pos"], s["yaw"], s["props"].get("scale", 1.0))
             for s in aset.sockets if s["type"] == "prop" and s["props"]["asset"] not in SOFT_PROPS]
    bounds = prop_bounds({a for a, *_ in props}, log)
    pv, pp, pt = [], [], []
    box_tris(props, bounds, pv, pp, pt)
    from . import collision as COL
    blk = [b for bs in COL.asset_blockers(aset).values() for b in bs]
    spaces.append(mesh_space(fixed, name=aset.name, extra=[(pv, pp, pt), COL.box_soup(blk)]))
    for n, s in floating.items():
        mb = aset.meshes.get(n)
        if mb is not None and mb.verts:
            spaces.append(mesh_space([mb], *s["pos"], yaw=s["yaw"], name=n))
    for sp in spaces:
        if sp is not None:
            sp.local_bounds, sp.bounds = sp.bounds, None
    # buildings stand on a levelled pad: outdoors the ground is the local z = 0 plane
    return Checker(spaces, ground=None if getattr(aset, "absolute", False) else (lambda x, y: 0.0),
                   ground_fallback=True)


def check_people(aset, log=print, settle=True):
    """Issue lines for NPC and fast-travel sockets of one location (after settling the NPCs, as the layout
    stage does)."""
    ck = asset_checker(aset, log)
    if settle:
        settle_npcs(aset, ck, log)
        face_open_view(aset, ck, log)
    doors = _door_zones(aset)
    out = []
    for s in aset.sockets:
        if s["type"] not in ("npc", "travel"):
            continue
        p = Vector(s["pos"])
        why = ck.capsule(p, r=NPC_R if s["type"] == "npc" else PLAYER_R)
        if why is None and any((Vector((p.x, p.y, 0)) - Vector((d.x, d.y, 0))).length < r and abs(p.z - d.z) < 1.5
                               for d, r in doors):
            why = "in a doorway"
        if why and why != "no floor under the feet":
            what = f"npc {s['props'].get('dorm', '')}" if s["type"] == "npc" else f"travel {s['props']['id']}"
            out.append(f"{what} at ({p.x:.2f}, {p.y:.2f}, {p.z:.2f}): {why}")
    return out


def _door_zones(aset):
    out = []
    for s in aset.sockets:
        if s["type"] == "door":
            out.append((Vector(s["pos"]), max(1.0, s["props"]["width"] / 2 + 0.6)))
    return out


def settle_npcs(aset, ck=None, log=print, reach=3.0):
    """Move every NPC (and fast-travel arrival point) whose spot is blocked (inside furniture, against a wall, in a doorway, off the floor) to
    the nearest clear spot on the same floor that can be seen from the intended one. Returns (moved, failed)
    lists of (socket, distance / reason)."""
    ck = ck or asset_checker(aset, log)
    doors = _door_zones(aset)

    def in_door(q):
        return any((Vector((q.x, q.y, 0)) - Vector((d.x, d.y, 0))).length < r and abs(q.z - d.z) < 1.5
                   for d, r in doors)

    moved, failed = [], []
    from . import collision as COL
    floating = {s["props"].get("mesh") for s in aset.sockets if s["type"] == "floating"}
    solid_floor = COL.floor_fn([mb for n, mb in aset.meshes.items()
                                if mb.verts and not n.endswith("_NoCol") and n not in floating])
    for s in aset.sockets:          # arrival points stand on the building's floor, not on what lies on it
        if s["type"] == "travel" and solid_floor is not None:
            x, y, z = s["pos"]
            fz = solid_floor(x, y, z + 0.5)
            if fz is not None and 0.0 <= z - fz <= 2.0:
                s["pos"] = (x, y, fz)
    taken = [Vector(s["pos"]) for s in aset.sockets if s["type"] in ("npc", "travel")]
    for s in aset.sockets:
        if s["type"] not in ("npc", "travel"):
            continue
        rad = NPC_R if s["type"] == "npc" else PLAYER_R
        p = Vector(s["pos"])
        why = ck.capsule(p, r=rad)
        if why == "no floor under the feet" or (why is None and not in_door(p)):
            continue
        spaces = ck.spaces_at(p, 8.0)
        f0 = ck.floor(p, spaces, above=0.6, below=0.8)
        z0 = f0[0] if f0 and abs(f0[0] - p.z) < 0.6 else p.z
        best = None
        rr = 0.1
        while rr <= reach + 1e-6 and best is None:
            n = max(8, int(2 * math.pi * rr / 0.12))
            for k in range(n):
                a = 2 * math.pi * k / n
                q = Vector((p.x + math.cos(a) * rr, p.y + math.sin(a) * rr, z0))
                f = ck.floor(q, spaces, above=0.4, below=0.5)
                if f is None or abs(f[0] - z0) > 0.35:
                    continue
                q.z = f[0]
                if in_door(q) or any((q - t).length < 0.8 for t in taken if (t - p).length > 1e-3):
                    continue
                if ck.capsule(q, r=rad, spaces=spaces):
                    continue
                eye0, eye1 = Vector((p.x, p.y, z0 + 1.9)), Vector((q.x, q.y, q.z + 1.9))
                d = eye1 - eye0
                if d.length > 1e-3 and ck._hit(eye0, d.normalized(), d.length, spaces):
                    continue
                best = q
                break
            rr += 0.1
        if best is None:
            failed.append((s, why or "in a doorway"))
            continue
        taken = [t for t in taken if (t - p).length > 1e-3] + [best]
        s["pos"] = (best.x, best.y, best.z)
        moved.append((s, (best - p).length, why or "in a doorway"))
    return moved, failed


def placed(sp, x, y, z, yaw):
    """The space sp (in a location's frame) put into the world by the location transform."""
    c, si = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    ox = x + sp.o.x * c - sp.o.y * si
    oy = y + sp.o.x * si + sp.o.y * c
    a = math.degrees(math.atan2(sp.s, sp.c)) + yaw
    (x0, y0, z0), (x1, y1, z1) = sp.local_bounds
    xs, ys = [], []
    for (px, py) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        xs.append(x + px * c - py * si)
        ys.append(y + px * si + py * c)
    w = Space(sp.bvh, sp.tags, ox, oy, z + sp.o.z, a, sp.name, ((min(xs), min(ys), z + z0), (max(xs), max(ys), z + z1)))
    return w


def face_open_view(aset, ck=None, log=print):
    """Fast-travel arrivals look into the room, not at a wall a step away: each travel point turns to the
    direction with the longest clear sightline at eye height (props included), within 90 deg of the intended
    facing and weighted towards it."""
    ck = ck or asset_checker(aset, log)
    for s in aset.sockets:
        if s["type"] != "travel":
            continue
        if not s["props"].get("face_open", True):
            continue
        p = Vector(s["pos"])
        spaces = ck.spaces_at(p, 40.0)
        best = None
        for k in range(-6, 7):
            yaw = s["yaw"] + k * 15.0
            a = math.radians(yaw)
            d = Vector((math.cos(a), math.sin(a), 0.0))
            dist = 30.0
            for h in (1.0, 1.55):                       # chest and eye height (a low screen, a shelf)
                hit = ck._hit(p + Vector((0, 0, h)), d, 30.0, spaces)
                dist = min(dist, hit[0] if hit else 30.0)
            score = min(dist, 12.0) * (0.8 + 0.2 * math.cos(math.radians(k * 15.0)))
            if best is None or score > best[0]:
                best = (score, yaw, dist)
        s["yaw"] = best[1]
