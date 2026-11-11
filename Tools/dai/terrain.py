"""
Island terrain generator.

Produces (all cached in Tools/.cache and exported to SourceAssets):
  * heightfield (FIELD_RES^2 float32, metres)          -> Heightmap/T_IslandHeight16.png (UE Landscape)
  * splat weights (SPLAT_RES^2, 7 layers + implicit grass) -> Textures/T_TerrainSplatA/B.png
  * colour map (baked albedo, preview + UE macro tint)   -> Textures/T_TerrainColor.png
  * forest density map                                    (used by layout scatter)
  * path profiles (polyline + heights)                    (used by layout for lamps / ribbons)
  * terrain chunk meshes                                  -> Meshes/Terrain/SM_Terrain_XX_YY.fbx

Array convention: field[row, col]; row 0 = north edge (y = +HALF), col 0 = west edge (x = -HALF).
"""

import math
import os

import numpy as np
from scipy import ndimage
from scipy.interpolate import CubicSpline, RectBivariateSpline

from . import atomic, cache
from . import config as C
from . import jsonio, palette

# --------------------------------------------------------------------------- helpers
STAMP_NAME = "terrain_cache.json"


def cache_stamp():
    """Current cache-configuration stamp: shapes / scaling the cached arrays rely on."""
    return {"field_res": int(C.FIELD_RES), "world_size": float(C.WORLD_SIZE)}


def write_cache_stamp():
    """Publish the stamp last, after every array cache, so a stamp proves a complete run."""
    jsonio.write_json(os.path.join(C.CACHE_DIR, STAMP_NAME), cache_stamp(), indent=1, sort_keys=True)


def check_cache(*required, fix="python Tools/build_island.py terrain"):
    """Refuse (StampedCacheError) unless Tools/.cache matches this build's configuration.

    Consumers of the *.npy terrain caches lived off existence checks alone: after a
    FIELD_RES / WORLD_SIZE change or an interrupted run, layout silently mixed
    mismatched resolutions into a finished-looking layout.json.  Runs are stamped
    on write (see write_cache_stamp); reads refuse anything they cannot verify.
    """
    cache.require_stamp(C.CACHE_DIR, STAMP_NAME, cache_stamp(), required,
                        subject="terrain caches", fix=fix)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def grid(res):
    sp = C.WORLD_SIZE / (res - 1)
    xs = -C.HALF + np.arange(res, dtype=np.float64) * sp
    ys = C.HALF - np.arange(res, dtype=np.float64) * sp
    X, Y = np.meshgrid(xs, ys)
    return X.astype(np.float32), Y.astype(np.float32), sp


def fbm(res, feature_m, octaves=5, persistence=0.5, seed=0):
    """Smooth fractal noise, ~unit variance, first octave features of `feature_m` metres."""
    rng = np.random.default_rng(seed)
    out = np.zeros((res, res), np.float32)
    amp, total = 1.0, 0.0
    cells = max(2, int(C.WORLD_SIZE / feature_m))
    u = np.linspace(0, 1, res)
    for _ in range(octaves):
        g = rng.standard_normal((cells + 4, cells + 4))
        k = np.linspace(0, 1, cells + 4)
        spl = RectBivariateSpline(k, k, g, kx=3, ky=3)
        uu = (u * cells + 2) / (cells + 3)
        out += amp * spl(uu, uu).astype(np.float32)
        total += amp * amp
        amp *= persistence
        cells *= 2
        if cells > res:
            break
    return out / math.sqrt(total)


def periodic_spline(points):
    """points: [(deg, value)] covering [0, 360). Returns f(theta_rad_array)."""
    pts = sorted(points)
    xs = [p[0] for p in pts] + [pts[0][0] + 360.0]
    ys = [p[1] for p in pts] + [pts[0][1]]
    cs = CubicSpline(xs, ys, bc_type="periodic")
    def f(theta):
        d = np.degrees(theta) % 360.0
        return cs(d)
    return f


def road_has_ribbon(p):
    """Paved roads get a ribbon mesh (layout.road_ribbon) that lays their stone; the breakwater is a structure
    of its own."""
    return p["surface"] == "paved" and p["id"] != "breakwater"


def polyline_distance(X, Y, pts, max_dist):
    """Distance from grid points to a polyline + arc-length parameter (metres). Returns (dist, s)."""
    dist = np.full(X.shape, np.inf, np.float32)
    s_out = np.zeros(X.shape, np.float32)
    acc = 0.0
    x0g, y0g = X[0, 0], Y[0, 0]
    sp = X[0, 1] - X[0, 0]
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        seg_len = math.hypot(bx - ax, by - ay)
        # bounding box in grid indices
        minx, maxx = min(ax, bx) - max_dist, max(ax, bx) + max_dist
        miny, maxy = min(ay, by) - max_dist, max(ay, by) + max_dist
        c0 = max(0, int((minx - x0g) / sp))
        c1 = min(X.shape[1], int((maxx - x0g) / sp) + 2)
        r0 = max(0, int((y0g - maxy) / sp))
        r1 = min(X.shape[0], int((y0g - miny) / sp) + 2)
        if c1 <= c0 or r1 <= r0:
            acc += seg_len
            continue
        xs = X[r0:r1, c0:c1]
        ys = Y[r0:r1, c0:c1]
        dx, dy = bx - ax, by - ay
        L2 = max(dx * dx + dy * dy, 1e-9)
        t = np.clip(((xs - ax) * dx + (ys - ay) * dy) / L2, 0.0, 1.0)
        px = ax + t * dx
        py = ay + t * dy
        d = np.hypot(xs - px, ys - py)
        sub = dist[r0:r1, c0:c1]
        m = d < sub
        sub[m] = d[m]
        s_sub = s_out[r0:r1, c0:c1]
        s_sub[m] = (acc + t * seg_len)[m]
        acc += seg_len
    return dist, s_out


def resample_polyline(pts, step):
    out = [pts[0]]
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        L = math.hypot(bx - ax, by - ay)
        n = max(1, int(L / step))
        for k in range(1, n + 1):
            t = k / n
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    return out


def solve_profile(raw, ds, grade, z0=None, z1=None, smooth=4, floor=0.6, lower=None):
    """Longitudinal road profile: as close to the ground `raw` (sampled every `ds` m) as the grade limit allows.

    z0 / z1 fix the ends (a pad, a quay or the road this one branches off). The old solver smoothed and
    clamped the profile freely and then blended its last 12 m onto the ground - so a road arriving 10 m below
    its pad ended in a wall (the plaza entrance of the main road was a 120 % ramp). Here the ends are hard
    constraints: the profile stays inside the cone every fixed end allows (z_end +- grade * distance), so the
    climb is spread over the approach as an embankment or a cutting, and no pitch exceeds `grade`.
    `lower`: optional per-sample minimum (bridge decks must clear the water).  Returns (profile, grade used):
    the limit is raised just enough when the two fixed ends are further apart in height than it allows."""
    n = len(raw)
    prof = np.asarray(raw, np.float64).copy()
    s = np.arange(n, dtype=np.float64) * ds
    total = max(s[-1], ds)
    g = float(grade)
    if z0 is not None and z1 is not None:
        g = max(g, abs(z1 - z0) / total * 1.04)
    for _ in range(max(int(smooth), 0)):
        prof = ndimage.uniform_filter1d(prof, size=21, mode="nearest")
    if lower is not None:
        prof = np.maximum(prof, lower)
    prof = np.maximum(prof, floor)
    step = g * ds

    def cone(p):
        if z0 is not None:
            p = np.clip(p, z0 - g * s, z0 + g * s)
        if z1 is not None:
            p = np.clip(p, z1 - g * (total - s), z1 + g * (total - s))
        return p

    def limit(p):
        # Lipschitz envelope: lower every point to what its neighbours can reach, then raise the pits. A cut is
        # preferred over a fill at a crest and the other way round in a dip, which is what a road builder does.
        up = p.copy()
        for i in range(1, n):
            up[i] = min(up[i], up[i - 1] + step)
        for i in range(n - 2, -1, -1):
            up[i] = min(up[i], up[i + 1] + step)
        lo = p.copy()
        for i in range(1, n):
            lo[i] = max(lo[i], lo[i - 1] - step)
        for i in range(n - 2, -1, -1):
            lo[i] = max(lo[i], lo[i + 1] - step)
        return 0.5 * (up + lo)

    for _ in range(6):
        prof = cone(prof)
        prof = limit(prof)
        if lower is not None:
            prof = np.maximum(prof, lower)
    # round the kinks into vertical curves (an average of g-Lipschitz profiles is g-Lipschitz), then the exact
    # pass: back into the cones of the fixed ends and one clamp along the profile
    for _ in range(2):
        prof = ndimage.uniform_filter1d(prof, size=9, mode="nearest")
    prof = cone(np.maximum(prof, floor))
    for i in range(1, n):
        prof[i] = np.clip(prof[i], prof[i - 1] - step, prof[i - 1] + step)
    if lower is not None and (prof < lower - 1e-9).any():
        # a bridge deck must clear the water: raise the profile there and let the approaches climb to it
        prof = np.maximum(prof, lower)
        for i in range(1, n):
            prof[i] = max(prof[i], prof[i - 1] - step)
        for i in range(n - 2, -1, -1):
            prof[i] = max(prof[i], prof[i + 1] - step)
    return prof, g


def segment_crossings(a_pts, b_pts):
    """Intersections of two 2D polylines: [(i, t, j, u, x, y)] - segment i of a at fraction t meets segment j
    of b at fraction u."""
    out = []
    a = np.asarray(a_pts, np.float64)[:, :2]
    b = np.asarray(b_pts, np.float64)[:, :2]
    for i in range(len(a) - 1):
        p, r = a[i], a[i + 1] - a[i]
        lo, hi = np.minimum(a[i], a[i + 1]), np.maximum(a[i], a[i + 1])
        q, e = b[:-1], b[1:] - b[:-1]
        near = ((np.maximum(q[:, 0], b[1:, 0]) >= lo[0]) & (np.minimum(q[:, 0], b[1:, 0]) <= hi[0])
                & (np.maximum(q[:, 1], b[1:, 1]) >= lo[1]) & (np.minimum(q[:, 1], b[1:, 1]) <= hi[1]))
        for j in np.nonzero(near)[0]:
            den = r[0] * e[j, 1] - r[1] * e[j, 0]
            if abs(den) < 1e-12:
                continue
            w = q[j] - p
            t = (w[0] * e[j, 1] - w[1] * e[j, 0]) / den
            u = (w[0] * r[1] - w[1] * r[0]) / den
            if 0.0 <= t < 1.0 and 0.0 <= u < 1.0:
                out.append((i, float(t), int(j), float(u), float(p[0] + r[0] * t), float(p[1] + r[1] * t)))
    return out


# River cross-section (see Terrain.carve_rivers): a flat bed half a metre wider than the nominal water
# half-width, banks rising from the bed at BANK_SLOPE - so the water's edge lies WATER_MARGIN outside it.
BANK_SLOPE = 0.6
BED_EXTRA = 0.5
BRIDGE_CLEARANCE = {"paved": 2.3, "dirt": 1.8, "boardwalk": 1.8}
# A paved road gets a ribbon mesh laid on the terrain, so its bed is level across the ribbon plus one full
# terrain mesh cell (diagonal) and the reach of the final blur: every triangle under the ribbon then lies in
# the road's plane. Trails are only painted on the ground and keep a narrow bench.
ROAD_FLAT_EXTRA = {"paved": 5.0, "dirt": 1.5, "boardwalk": 1.5}
BRIDGE_ABUTMENT = 4.6      # m a deck runs on beyond the top of the bank (> one mesh cell diagonal)


class Field:
    """Bilinear sampler over a [row, col] array covering the world domain."""

    def __init__(self, arr):
        self.a = arr
        self.res = arr.shape[0]
        self.sp = C.WORLD_SIZE / (self.res - 1)

    def __call__(self, x, y):
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        fc = np.clip((x + C.HALF) / self.sp, 0, self.res - 1.001)
        fr = np.clip((C.HALF - y) / self.sp, 0, self.res - 1.001)
        c0 = np.floor(fc).astype(int)
        r0 = np.floor(fr).astype(int)
        tc = fc - c0
        tr = fr - r0
        a = self.a
        v = (a[r0, c0] * (1 - tc) * (1 - tr) + a[r0, c0 + 1] * tc * (1 - tr)
             + a[r0 + 1, c0] * (1 - tc) * tr + a[r0 + 1, c0 + 1] * tc * tr)
        return v

    def normal(self, x, y, eps=1.5):
        hx = (self(x + eps, y) - self(x - eps, y)) / (2 * eps)
        hy = (self(x, y + eps) - self(x, y - eps)) / (2 * eps)
        n = np.stack([-hx, -hy, np.ones_like(hx)], axis=-1)
        return n / np.linalg.norm(n, axis=-1, keepdims=True)


def mesh_step():
    """Heightfield samples per terrain mesh quad (the mesh is coarser than the field)."""
    return (C.FIELD_RES - 1) // C.MESH_QUADS


def mesh_diagonals(hs):
    """Which way every terrain quad is split: True = north-west -> south-east, False = north-east ->
    south-west. hs[row, col] are the mesh vertex heights (row 0 = north). The diagonal joins the two corners
    closer in height, so a crease (a road edge, a river bank, a pad rim) runs along the triangles instead of
    being sawn into teeth across them. terrain_mesh.build_chunks exports exactly these triangles and
    MeshField samples them, so "the ground" means the same surface everywhere."""
    nw, ne, sw, se = hs[:-1, :-1], hs[:-1, 1:], hs[1:, :-1], hs[1:, 1:]
    return np.abs(nw - se) <= np.abs(ne - sw)


class MeshField:
    """The terrain as it is drawn and walked on: the triangles of the exported mesh, not the finer
    heightfield behind it. Everything that must sit *on the ground* (roads, bridges, props, plinths, people)
    samples this; between mesh vertices the heightfield and the mesh differ by decimetres at any crisp edge.
    `a` is the full-resolution heightfield (maps, statistics)."""

    def __init__(self, h):
        self.a = h
        st = mesh_step()
        self.hs = np.ascontiguousarray(h[::st, ::st]).astype(np.float64)
        self.n = self.hs.shape[0] - 1
        self.sp = C.WORLD_SIZE / self.n
        self.diag = mesh_diagonals(self.hs)

    def __call__(self, x, y):
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        fc = np.clip((x + C.HALF) / self.sp, 0.0, self.n - 1e-9)
        fr = np.clip((C.HALF - y) / self.sp, 0.0, self.n - 1e-9)
        c = np.floor(fc).astype(int)
        r = np.floor(fr).astype(int)
        u, v = fc - c, fr - r                     # u: west -> east, v: north -> south
        hs = self.hs
        nw, ne, sw, se = hs[r, c], hs[r, c + 1], hs[r + 1, c], hs[r + 1, c + 1]
        # diagonal NW-SE: triangles (NW, SW, SE) below it and (NW, SE, NE) above it
        a = np.where(v >= u, nw + (sw - nw) * v + (se - sw) * u, nw + (ne - nw) * u + (se - ne) * v)
        # diagonal NE-SW: triangles (NW, SW, NE) and (SW, SE, NE)
        b = np.where(u + v <= 1.0, nw + (ne - nw) * u + (sw - nw) * v,
                     se + (sw - se) * (1.0 - u) + (ne - se) * (1.0 - v))
        return np.where(self.diag[r, c], a, b)


# --------------------------------------------------------------------------- pads

def pad_specs():
    L = C.LOCATIONS
    hx, hy, hhx, hhy = C.HARBOR_RECT
    return {
        "academy": dict(center=L["academy"]["pos"], r=(178.0, 140.0), yaw=0.0, h=34.0, falloff=70.0, shape="ellipse", paving=0.0),
        "plaza": dict(center=L["plaza"]["pos"], r=(100.0, 55.0), yaw=0.0, h=34.0, falloff=40.0, shape="rect", paving=1.0),
        "harbor": dict(center=(hx, hy), r=(hhx, hhy), yaw=0.0, h=3.0, falloff=40.0, shape="rect", land_mask=False, paving=1.0),
        "slifer": dict(center=L["slifer"]["pos"], r=(32.0, 52.0), yaw=0.0, h=None, falloff=22.0, shape="ellipse", dirt=0.7),
        "ra": dict(center=L["ra"]["pos"], r=(70.0, 55.0), yaw=L["ra"]["yaw"], h=None, falloff=45.0, shape="ellipse"),
        "obelisk_boys": dict(center=L["obelisk_boys"]["pos"], r=(105.0, 92.0), yaw=L["obelisk_boys"]["yaw"], h=None, h_add=8.0, falloff=70.0, shape="ellipse"),
        "obelisk_girls": dict(center=L["obelisk_girls"]["pos"], r=(80.0, 65.0), yaw=L["obelisk_girls"]["yaw"], h=33.0, falloff=50.0, shape="ellipse"),
        "abandoned": dict(center=L["abandoned"]["pos"], r=(55.0, 50.0), yaw=L["abandoned"]["yaw"], h=None, falloff=40.0, shape="ellipse", dirt=0.6),
        "gym": dict(center=L["gym"]["pos"], r=(78.0, 66.0), yaw=L["gym"]["yaw"], h=None, falloff=50.0, shape="ellipse", paving=0.5),
        "hotsprings": dict(center=L["hotsprings"]["pos"], r=(46.0, 40.0), yaw=L["hotsprings"]["yaw"], h=None, falloff=30.0, shape="ellipse", dirt=0.5),
        "waterfall": dict(center=L["waterfall"]["pos"], r=(26.0, 22.0), yaw=0.0, h=None, falloff=12.0, shape="ellipse"),
        # the volcano trail's end: a terrace cut into the 45 deg upper slope for the viewpoint deck and the foot
        # of the summit stair (the deck used to be half buried in the hillside)
        "volcano_view": dict(center=C.VOLCANO_VIEW, r=(7.0, 9.0), yaw=C.VOLCANO_VIEW_YAW, h=None, falloff=5.0,
                             shape="rect", dirt=0.6),
        # the villages: a levelled green with trodden ground between the cottages
        # Millbrook's green is level with the forest path that runs through it and with the bridge beside it
        "millbrook": dict(center=L["millbrook"]["pos"], r=L["millbrook"]["pad"], yaw=0.0, h=None, h_add=4.5,
                          falloff=34.0, shape="ellipse", dirt=0.35),
        "willow_pond": dict(center=L["willow_pond"]["pos"], r=L["willow_pond"]["pad"], yaw=0.0, h=None, h_add=5.0,
                            falloff=44.0, shape="ellipse", dirt=0.3),
        "fishers_cove": dict(center=L["fishers_cove"]["pos"], r=L["fishers_cove"]["pad"], yaw=0.0, h=None,
                             falloff=22.0, shape="ellipse", dirt=0.25),
    }


def pad_weight(X, Y, spec):
    cx, cy = spec["center"]
    rx, ry = spec["r"]
    a = math.radians(spec.get("yaw", 0.0))
    dx, dy = X - cx, Y - cy
    lx = dx * math.cos(a) + dy * math.sin(a)
    ly = -dx * math.sin(a) + dy * math.cos(a)
    f = spec["falloff"]
    if spec.get("shape") == "rect":
        ex = np.maximum(np.abs(lx) - rx, 0.0)
        ey = np.maximum(np.abs(ly) - ry, 0.0)
        d = np.hypot(ex, ey)
        core = 1.0 - smoothstep(0.0, f, d)
        inner = (d <= 0).astype(np.float32)
    else:
        q = np.sqrt((lx / rx) ** 2 + (ly / ry) ** 2)
        # convert normalised radius to an approximate metric distance outside the ellipse
        d = np.maximum(q - 1.0, 0.0) * min(rx, ry)
        core = 1.0 - smoothstep(0.0, f, d)
        inner = (q <= 1.0).astype(np.float32)
    return core.astype(np.float32), inner


# --------------------------------------------------------------------------- main build

class Terrain:
    def __init__(self):
        self.res = C.FIELD_RES
        self.X, self.Y, self.sp = grid(self.res)
        self.h = None
        self.info = {}

    # ------------------------------------------------------------------ base shape
    def build(self, log=print):
        X, Y, sp = self.X, self.Y, self.sp
        res = self.res
        r = np.hypot(X, Y)
        th = np.arctan2(Y, X)

        coast_R = periodic_spline([
            (0, 1250), (12, 1215), (25, 1290), (40, 1420), (55, 1390), (70, 1265), (85, 1195),
            (100, 1180), (115, 1105), (130, 1015), (145, 1075), (160, 1220), (172, 1250), (185, 1125),
            (195, 1130), (205, 1065), (220, 1000), (232, 1085), (245, 1140), (258, 1065), (270, 1030),
            (282, 1050), (295, 1165), (310, 1110), (325, 1060), (340, 1150), (352, 1235)])
        cliff_f = periodic_spline([
            (0, 0.5), (25, 0.75), (55, 0.9), (85, 0.7), (110, 0.55), (130, 0.25), (150, 0.8), (172, 1.0),
            (200, 1.0), (220, 0.9), (240, 0.8), (255, 0.35), (270, 0.15), (285, 0.2), (295, 0.55),
            (310, 0.05), (325, 0.0), (340, 0.05), (352, 0.3)])
        cliff_h = periodic_spline([
            (0, 18), (45, 30), (90, 26), (135, 30), (180, 30), (200, 28), (225, 22), (260, 8),
            (300, 3), (330, 6)])

        log("  coast + base profile")
        n_coast = fbm(res, 260.0, octaves=5, seed=C.SEED + 1) * 48.0 + fbm(res, 60.0, 3, seed=C.SEED + 11) * 12.0
        R = coast_R(th) + n_coast
        land0 = r < R
        # guarantee solid ground around every location so coastline noise never eats a building
        for key, rad in (("slifer", 48.0), ("ra", 80.0), ("gym", 85.0), ("hotsprings", 60.0), ("cliffs", 40.0),
                         ("beach", 20.0), ("abandoned", 70.0)):
            px, py = C.LOCATIONS[key]["pos"]
            land0 |= np.hypot(X - px, Y - py) < rad
        d_in = ndimage.distance_transform_edt(land0).astype(np.float32) * sp
        d_out = ndimage.distance_transform_edt(~land0).astype(np.float32) * sp
        self.d_in, self.d_out = d_in, d_out
        cf = np.clip(cliff_f(th) + fbm(res, 300.0, 3, seed=C.SEED + 2) * 0.12, 0.0, 1.0).astype(np.float32)
        ch = cliff_h(th).astype(np.float32)
        self.cliff_factor = cf

        hills = (fbm(res, 420.0, 4, seed=C.SEED + 3) * 12.0 + fbm(res, 90.0, 3, seed=C.SEED + 4) * 2.8
                 + fbm(res, 22.0, 2, seed=C.SEED + 5) * 0.5)
        plateau = 20.0 + 16.0 * smoothstep(0.0, 650.0, d_in) + hills * smoothstep(0.0, 160.0, d_in)
        plateau_c = lerp(plateau, np.maximum(plateau, ch), cf)
        ramp = lerp(230.0, 16.0, cf)
        s = smoothstep(0.0, ramp, d_in)
        h_land = -0.2 + (plateau_c + 0.2) * s

        L = lerp(170.0, 30.0, cf)
        h_sea = C.SEA_FLOOR * (1.0 - np.exp(-d_out / L)) + fbm(res, 120.0, 3, seed=C.SEED + 6) * 2.5 * smoothstep(0, 80, d_out)
        h = np.where(land0, h_land, h_sea).astype(np.float32)

        # ------------------------------------------------------------------ volcano
        log("  volcano")
        vx, vy = C.VOLCANO_CENTER
        rv = np.hypot(X - vx, Y - vy)
        av = np.arctan2(Y - vy, X - vx)
        t = np.clip(rv / C.VOLCANO_RADIUS, 0.0, 1.0)
        ridges = 1.0 - np.abs(fbm(res, 70.0, 4, seed=C.SEED + 7))
        gully = np.sin(av * 14.0 + fbm(res, 200.0, 2, seed=C.SEED + 8) * 3.0) * 0.5 + 0.5
        hv = C.VOLCANO_PEAK * (1.0 - t) ** 1.7
        hv *= 1.0 + (0.10 * gully + 0.06 * ridges - 0.08) * smoothstep(0.12, 0.3, t)
        signed = d_in - d_out
        hv *= smoothstep(-25.0, 45.0, signed)
        h = h + hv.astype(np.float32)

        # crater
        ring = (rv > C.CRATER_RADIUS - 3) & (rv < C.CRATER_RADIUS + 3)
        rim = float(np.mean(h[ring]))
        floor = rim - C.CRATER_DEPTH
        h_c = floor + (rim - floor) * smoothstep(0.30, 1.0, rv / C.CRATER_RADIUS) ** 1.5
        h = np.where(rv < C.CRATER_RADIUS, np.minimum(h, h_c), h)
        h += 4.0 * np.exp(-((rv - C.CRATER_RADIUS) / 10.0) ** 2)
        lava = floor + 5.0
        self.info["volcano"] = dict(rim=rim + 4.0, floor=floor, lava=lava,
                                    lava_radius=float(C.CRATER_RADIUS * 0.30 + (C.CRATER_RADIUS * 0.70) * ((lava - floor) / (rim - floor)) ** (1 / 3.0)))
        log(f"    rim {rim:.1f}  floor {floor:.1f}  lava {lava:.1f}")

        # ------------------------------------------------------------------ sea stacks
        for (sx, sy, sr, stop) in C.SEA_STACKS:
            ds = np.hypot(X - sx, Y - sy)
            n = fbm(res, 30.0, 2, seed=int(abs(sx))) * 0.25
            prof = stop * (1.0 - smoothstep(0.55, 1.0, ds / sr + n * 0.3))
            base = C.SEA_FLOOR * 0.6 * smoothstep(1.0, 3.0, ds / sr)
            h = np.where(ds < sr * 3.5, np.maximum(h, prof + base * (prof <= 0)), h)

        # ------------------------------------------------------------------ lake
        log("  lake")
        lcx, lcy = C.LAKE_CENTER
        a = math.radians(C.LAKE_ROT)
        dx, dy = X - lcx, Y - lcy
        lx = dx * math.cos(a) + dy * math.sin(a)
        ly = -dx * math.sin(a) + dy * math.cos(a)
        q = np.sqrt((lx / C.LAKE_RADII[0]) ** 2 + (ly / C.LAKE_RADII[1]) ** 2)
        q = q + fbm(res, 150.0, 3, seed=C.SEED + 9) * 0.07
        self.lake_q = q
        bottom = C.LAKE_LEVEL - 0.6 - 7.0 * np.clip(1.0 - q * q, 0, 1) ** 0.6
        shore_target = C.LAKE_LEVEL + 0.4 + (q - 1.0) * 14.0
        w_shore = (1.0 - smoothstep(1.0, 1.55, q)) * (q >= 1.0)
        h = np.where(q < 1.0, np.minimum(h, bottom), lerp(h, shore_target, w_shore))

        # ------------------------------------------------------------------ pads (first pass)
        log("  pads")
        specs = pad_specs()
        heights = {}
        self.pad_masks = {}
        for key, spec in specs.items():
            w, inner = pad_weight(X, Y, spec)
            if spec.get("h") is None:
                sel = inner > 0
                ph = float(np.median(h[sel])) + spec.get("h_add", 0.0)
                ph = round(ph * 2.0) / 2.0
            else:
                ph = spec["h"]
            heights[key] = ph
            if spec.get("land_mask", True):
                w = w * smoothstep(0.0, 25.0, d_in)
            h = lerp(h, ph, w).astype(np.float32)
            self.pad_masks[key] = (w, inner)
        self.pad_heights = heights
        log("    " + ", ".join(f"{k}={v:.1f}" for k, v in heights.items()))

        # ------------------------------------------------------------------ harbor basin & breakwater
        x0, x1, y0, y1 = C.HARBOR_BASIN
        ex = np.maximum(np.maximum(x0 - X, X - x1), 0.0)
        ey = np.maximum(np.maximum(y0 - Y, Y - y1), 0.0)
        wb = 1.0 - smoothstep(0.0, 40.0, np.hypot(ex, ey))
        h = np.where(wb > 0, lerp(h, np.minimum(h, -12.0), wb), h)

        # ------------------------------------------------------------------ rivers (water level from this ground)
        self.river_profiles(h, log)

        # ------------------------------------------------------------------ paths
        log("  paths")
        self.paths = []
        self.bridges = []
        path_paved = np.zeros_like(h)
        path_dirt = np.zeros_like(h)
        path_bed = np.zeros_like(h)          # 1 on a road bed and its verge: the pads must not re-level it
        ds = 2.0
        road_lock = np.zeros_like(h)         # 1 on the carriageway of every road laid so far
        for p in C.PATHS:
            pts = p["pts"]
            hw = p["width"] / 2.0
            flat = hw + p.get("flat", ROAD_FLAT_EXTRA[p["surface"]])
            samples = resample_polyline(pts, ds)
            arr = np.array(samples)
            arc = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(arr[:, 0]), np.diff(arr[:, 1])))])
            crossings = self.path_crossings(p, arr, arc)
            if crossings:
                # a bridge is straight: straighten the road over each crossing (the span and its abutments)
                for cr in crossings:
                    reach = cr["half_span"] + 2.0 * BRIDGE_ABUTMENT + 14.0
                    i0 = int(np.searchsorted(arc, cr["s"] - reach))
                    i1 = int(np.searchsorted(arc, cr["s"] + reach))
                    i0, i1 = max(i0, 0), min(i1, len(arr) - 1)
                    if i1 - i0 >= 2:
                        t = ((arc[i0:i1 + 1] - arc[i0]) / max(arc[i1] - arc[i0], 1e-9))[:, None]
                        arr[i0:i1 + 1] = arr[i0] * (1.0 - t) + arr[i1] * t
                samples = [(float(x), float(y)) for x, y in arr]
                arc = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(arr[:, 0]), np.diff(arr[:, 1])))])
                crossings = self.path_crossings(p, arr, arc)
            hf = Field(h)
            raw = hf(arr[:, 0], arr[:, 1]).astype(np.float64)
            if p.get("fixed_z") is not None:
                prof = np.full(len(raw), float(p["fixed_z"]))
                used = 0.0
            else:
                lower = None
                if crossings:
                    lower = np.full(len(raw), -1e9)
                    for cr in crossings:
                        # over the deck, its abutments and the straight run-out beyond them (see below)
                        near = np.abs(arc - cr["s"]) <= cr["half_span"] + 2.0 * BRIDGE_ABUTMENT + 6.0
                        lower[near] = cr["water"] + cr["clearance"]
                grade = p.get("grade", C.ROAD_GRADE[p["surface"]])
                # Fixed points: both ends (a pad, a quay or the road this one branches off - already in h),
                # every stretch on a pad proper, which stays level whatever the road would like, and every
                # stretch on the carriageway of a road laid earlier (a junction is on the main road's plane).
                # The profile is solved separately for each free stretch between two of them.
                on_pad = Field(road_lock)(arr[:, 0], arr[:, 1]) > 0.5
                tang = np.gradient(arr, axis=0)
                tang /= np.maximum(np.hypot(tang[:, 0], tang[:, 1]), 1e-9)[:, None]
                for off in (0.0, hw + 1.0, -(hw + 1.0)):      # a pad under either edge of the road counts
                    ox, oy = arr[:, 0] - tang[:, 1] * off, arr[:, 1] + tang[:, 0] * off
                    for key, spec in specs.items():
                        pw, _inner = pad_weight(ox.astype(np.float32), oy.astype(np.float32), spec)
                        if spec.get("land_mask", True):
                            pw = pw * smoothstep(0.0, 25.0, Field(d_in)(ox, oy))
                        on_pad |= pw >= 0.995
                on_pad[0] = on_pad[-1] = True
                prof = raw.copy()
                used = grade
                idx = np.nonzero(on_pad)[0]
                for i0, i1 in zip(idx[:-1], idx[1:]):
                    if i1 - i0 < 2:
                        continue
                    seg, g_seg = solve_profile(raw[i0:i1 + 1], ds, grade, z0=raw[i0], z1=raw[i1],
                                               smooth=p.get("smooth", 4), floor=0.6,
                                               lower=None if lower is None else lower[i0:i1 + 1])
                    prof[i0:i1 + 1] = seg
                    used = max(used, g_seg)
                if used > grade + 1e-6:
                    log(f"    {p['id']}: its fixed points need {used * 100:.1f} % (limit {grade * 100:.0f} %)")
                # a deck is a straight line from bank to bank: so is the profile under it (abutments included)
                # ... and for one terrain mesh cell beyond each end, so the change of grade between road and
                # deck is not at the joint (the 3 m mesh rounds a kink off by several centimetres)
                for cr in crossings:
                    s0, s1 = self.bridge_span(cr, arc, prof)
                    c0, c1 = max(s0 - BRIDGE_ABUTMENT, 0.0), min(s1 + BRIDGE_ABUTMENT, float(arc[-1]))
                    inside = (arc >= c0) & (arc <= c1)
                    z0, z1 = float(np.interp(c0, arc, prof)), float(np.interp(c1, arc, prof))
                    prof[inside] = z0 + (z1 - z0) * (arc[inside] - c0) / max(c1 - c0, 1e-9)
                    cr["s0"], cr["s1"] = s0, s1
                    deck = float(np.interp(cr["s"], arc, prof))
                    if deck < cr["water"] + cr["clearance"] - 0.05:
                        log(f"    !! {p['id']}: bridge deck only {deck - cr['water']:.2f} m over the water")
            # level bed per sample: a trail's narrow bench widens to a road's at the abutments of its bridges,
            # so the deck ends on ground that is exactly the path's height across its whole width
            flat_s = np.full(len(prof), flat)
            for cr in crossings:
                near = 1.0 - smoothstep(6.0, 22.0, np.maximum(np.maximum(cr["s0"] - arc, arc - cr["s1"]), 0.0))
                flat_s = np.maximum(flat_s, flat + (hw + ROAD_FLAT_EXTRA["paved"] - flat) * near)
            dev = np.abs(prof - raw)
            dike = bool(p.get("dike"))
            # cut / fill slopes: the shoulder widens with the height of the embankment or the depth of the cutting
            # (a 6 m fill on a 9 m shoulder was a 34 degree wall beside the road)
            shoulder = np.full(len(prof), 30.0) if dike else np.clip(6.0 + 2.6 * ndimage.maximum_filter1d(dev, 9), 9.0, 46.0)
            reach = float(flat_s.max()) + float(shoulder.max()) + 2.0
            dist, sarc = polyline_distance(X, Y, samples, reach)
            sel = np.isfinite(dist)
            ph = np.interp(sarc[sel], arc, prof).astype(np.float32)
            if dike:
                top = ph
                slope_h = top - np.maximum(dist[sel] - hw, 0.0) * 0.7
                h[sel] = np.where(dist[sel] <= hw + 0.5, top, np.maximum(h[sel], slope_h))
            else:
                sh = np.interp(sarc[sel], arc, shoulder).astype(np.float32)
                fl = np.interp(sarc[sel], arc, flat_s).astype(np.float32)
                w = 1.0 - smoothstep(fl, fl + sh, dist[sel])
                # never reshape the carriageway of a road that is already there (a branch's wide shoulder
                # used to drag the main road's bed towards its own profile for tens of metres)
                w = w * (1.0 - road_lock[sel])
                h[sel] = lerp(h[sel], ph, w)
            core = 1.0 - smoothstep(hw - 0.5, hw + 1.5, dist)
            core = np.where(np.isfinite(core), core, 0.0)
            fl_all = np.interp(np.where(np.isfinite(dist), sarc, 0.0), arc, flat_s)
            bed = 1.0 - smoothstep(fl_all + 1.0, fl_all + 6.0, dist)
            path_bed = np.maximum(path_bed, np.where(np.isfinite(bed), bed, 0.0))
            # the whole level bed is the road's from now on: a later road may join it, not reshape it
            lock = 1.0 - smoothstep(fl_all, fl_all + 3.0, dist)
            road_lock = np.maximum(road_lock, np.where(np.isfinite(lock), lock, 0.0))
            if p["surface"] == "paved":
                path_paved = np.maximum(path_paved, core)
            else:
                path_dirt = np.maximum(path_dirt, core)
            for cr in crossings:
                self.add_bridge(p, cr, arr, arc, prof)
            g = np.abs(np.diff(prof)) / ds
            self.paths.append(dict(id=p["id"], width=p["width"], surface=p["surface"], lamps=p.get("lamps", False),
                                   extend=C.path_extension(p["id"]),
                                   grade=float(g.max()) if len(g) else 0.0,
                                   pts=[[float(a), float(b)] for a, b in pts],
                                   samples=[[float(a), float(b), float(c)] for (a, b), c in zip(samples, prof)]))
        self.path_paved_lr = path_paved
        self.path_dirt_lr = path_dirt
        self.path_bed = path_bed
        log("    grades: " + ", ".join(f"{p['id']} {p['grade'] * 100:.0f}%" for p in self.paths))

        # lighthouse platform at the end of the breakwater
        lx_, ly_ = C.LOCATIONS["lighthouse"]["pos"]
        dl = np.hypot(X - lx_, Y - ly_)
        h = np.where(dl < 40, np.maximum(h, 4.0 - np.maximum(dl - 15.0, 0.0) * 0.7), h)
        h = np.where(dl < 15, 4.0, h)

        # ------------------------------------------------------------------ pads (re-flatten cores)
        # A road keeps its graded bed through a pad's apron (the fall-off band): re-levelling it there put the
        # approach ramps back on the old ground - up to 7 m under the road ribbon. The pad proper (w ~ 1) is
        # still flattened everywhere; the road's profile ends on it at pad height.
        def pad_core(w, a, b):
            core = np.clip(w * a - b, 0.0, 1.0)
            return core * (1.0 - path_bed * (1.0 - smoothstep(0.99, 0.999, w)))

        for key, spec in specs.items():
            w, inner = self.pad_masks[key]
            h = lerp(h, heights[key], pad_core(w, 1.6, 0.6)).astype(np.float32)

        # ------------------------------------------------------------------ domain edge + smoothing
        edge = C.HALF - np.maximum(np.abs(X), np.abs(Y))
        we = smoothstep(0.0, 160.0, edge)
        h = lerp(C.SEA_FLOOR, h, we)
        h = ndimage.gaussian_filter(h, 0.7).astype(np.float32)
        # keep pads perfectly flat after blur
        for key in specs:
            w, inner = self.pad_masks[key]
            h = lerp(h, heights[key], pad_core(w, 2.0, 1.0)).astype(np.float32)
        h = np.where(dl < 15, 4.0, h).astype(np.float32)

        # ------------------------------------------------------------------ rivers (cut last: crisp beds)
        h = self.carve_rivers(h, log)

        self.h = h
        self.field = Field(h)
        # slope in degrees
        gy, gx = np.gradient(h, sp)
        self.slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
        self.vol_r = rv.astype(np.float32)
        self.info["pads"] = heights
        self.info["lake_level"] = C.LAKE_LEVEL
        self.info["height_range"] = [float(h.min()), float(h.max())]
        log(f"  height range {h.min():.1f} .. {h.max():.1f}")
        return self

    # ------------------------------------------------------------------ rivers
    def river_profiles(self, h, log=print):
        """Centre line, width and water level of every river in config.RIVERS, from the ground as it is now.

        The water level is the highest profile a river can have: 0.45 m below the (smoothed) ground along its
        centre line and never rising downstream - so it pools on flats, runs down slopes as rapids and only
        cuts a gorge where a ridge is in the way. Samples every 2 m."""
        hf = Field(h)
        self.rivers = []
        for r in C.RIVERS:
            ctrl = np.array(r["pts"], np.float64)
            for _ in range(3):                       # Chaikin: round the corners into bends (ends stay)
                a, b = ctrl[:-1], ctrl[1:]
                mid = np.empty((2 * len(a), ctrl.shape[1]))
                mid[0::2] = a * 0.75 + b * 0.25
                mid[1::2] = a * 0.25 + b * 0.75
                ctrl = np.vstack([ctrl[:1], mid, ctrl[-1:]])
            seg = np.hypot(np.diff(ctrl[:, 0]), np.diff(ctrl[:, 1]))
            arc_c = np.concatenate([[0.0], np.cumsum(seg)])
            arc = np.arange(0.0, arc_c[-1], 2.0)
            x = np.interp(arc, arc_c, ctrl[:, 0])
            y = np.interp(arc, arc_c, ctrl[:, 1])
            hw = np.interp(arc, arc_c, ctrl[:, 2])
            ground = ndimage.uniform_filter1d(hf(x, y).astype(np.float64), size=9, mode="nearest")
            level = ground - 0.45
            lq = Field(self.lake_q)(x, y)
            in_lake = lq < 1.08
            if r.get("source") == "lake":
                level = np.where(in_lake, C.LAKE_LEVEL - 0.03, np.minimum(level, C.LAKE_LEVEL - 0.03))
            level = np.minimum.accumulate(level)
            level = np.minimum(level, ndimage.uniform_filter1d(level, size=15, mode="nearest"))
            level = np.minimum(level, level[0] - 0.0008 * arc)        # it always runs, however slightly
            level = np.maximum(level, C.SEA_LEVEL)
            pond = hw >= C.POND_MIN_HALF_WIDTH
            depth = np.where(pond, 1.25, float(r.get("depth", 1.0)))
            depth = ndimage.uniform_filter1d(depth, size=9, mode="nearest")
            self.rivers.append(dict(id=r["id"], name=r["name"], x=x, y=y, arc=arc, hw=hw, level=level, depth=depth,
                                    in_lake=in_lake, pond=pond))
            fresh = level > 0.05
            log(f"    {r['id']}: {arc[-1]:.0f} m, {level[0]:.1f} m -> sea, deepest cut "
                f"{float((ground - level)[fresh & ~in_lake].max()):.1f} m")

    def path_crossings(self, p, arr, arc):
        """Where a path crosses a river: [(s along the path, river, river sample, water level, ...)]."""
        out = []
        for rv in self.rivers:
            rxy = np.stack([rv["x"], rv["y"]], -1)
            for (i, t, j, u, x, y) in segment_crossings(arr, rxy):
                if rv["in_lake"][j] or rv["level"][j] <= 0.05:
                    continue
                dpx, dpy = arr[i + 1] - arr[i]
                drx, dry = rxy[j + 1] - rxy[j]
                sin_a = abs(dpx * dry - dpy * drx) / (math.hypot(dpx, dpy) * math.hypot(drx, dry) + 1e-9)
                sin_a = max(sin_a, 0.5)
                clearance = BRIDGE_CLEARANCE[p["surface"]]
                bed_half = rv["hw"][j] + BED_EXTRA
                # the banks reach deck height this far from the centre line (measured along the path)
                half_span = (bed_half + (clearance + rv["depth"][j]) / BANK_SLOPE) / sin_a
                out.append(dict(s=float(arc[i] + t * (arc[i + 1] - arc[i])), river=rv["id"], j=int(j), x=x, y=y,
                                water=float(rv["level"][j]), hw=float(rv["hw"][j]), depth=float(rv["depth"][j]),
                                clearance=clearance, half_span=float(half_span), sin=float(sin_a),
                                half_width=p["width"] / 2.0 + 1.0))
        return out

    @staticmethod
    def bridge_span(cr, arc, prof):
        """Arc range (s0, s1) of the deck over a crossing: from where the bank reaches the level of the road
        on one side to the same on the other, plus an abutment that carries it one terrain mesh cell on."""
        deck = float(np.interp(cr["s"], arc, prof))
        # a skew crossing: the bank's top edge runs across the deck at an angle, so one side of the deck
        # reaches it later than the centre line does - by half the deck's width times cot(angle)
        skew = cr["half_width"] * math.sqrt(max(1.0 - cr["sin"] ** 2, 0.0)) / cr["sin"]
        half = ((cr["hw"] + BED_EXTRA + (deck - cr["water"] + cr["depth"]) / BANK_SLOPE) / cr["sin"]
                + skew + BRIDGE_ABUTMENT)
        return max(cr["s"] - half, 0.0), min(cr["s"] + half, float(arc[-1]))

    def add_bridge(self, p, cr, arr, arc, prof):
        """Bridge record for the layout stage: a straight deck between the two abutments of the crossing."""
        s0, s1 = cr.get("s0"), cr.get("s1")
        if s0 is None:
            s0, s1 = self.bridge_span(cr, arc, prof)
        deck = float(np.interp(cr["s"], arc, prof))
        a = [float(np.interp(s0, arc, arr[:, 0])), float(np.interp(s0, arc, arr[:, 1])), float(np.interp(s0, arc, prof))]
        b = [float(np.interp(s1, arc, arr[:, 0])), float(np.interp(s1, arc, arr[:, 1])), float(np.interp(s1, arc, prof))]
        stone = p["surface"] == "paved" or p["id"] in ("to_abandoned",)
        self.bridges.append(dict(path=p["id"], river=cr["river"], kind="stone" if stone else "wood", a=a, b=b,
                                 center=[cr["x"], cr["y"], deck], water=cr["water"], bed=cr["water"] - cr["depth"],
                                 half_water=(cr["hw"] + BED_EXTRA + cr["depth"] / BANK_SLOPE) / cr["sin"],
                                 s0=s0, s1=s1,
                                 width=float(p["width"]), surface=p["surface"]))

    def carve_rivers(self, h, log=print):
        """Cut every river's channel and fill in `self.water` (water surface height per cell, NaN where dry:
        sea, lake, rivers and ponds). Cross-section: a flat bed BED_EXTRA wider than the nominal half-width
        (so the 3 m terrain mesh always has a vertex in it), banks rising at BANK_SLOPE (a little rougher
        with noise), a low levee where the ground beside the channel lies below the water."""
        X, Y = self.X, self.Y
        lake = (self.lake_q < 1.0) & (h < C.LAKE_LEVEL)
        water = np.where(h < C.SEA_LEVEL, C.SEA_LEVEL, np.nan).astype(np.float32)
        water = np.where(lake, C.LAKE_LEVEL, water).astype(np.float32)
        self.river_wet = np.zeros(h.shape, np.float32)
        self.river_bank = np.zeros(h.shape, np.float32)
        rough = np.clip(fbm(self.res, 35.0, 3, seed=C.SEED + 50), -1.5, 1.5)
        for rv in self.rivers:
            pts = list(zip(rv["x"].tolist(), rv["y"].tolist()))
            reach = float(rv["hw"].max()) + 48.0
            dist, sarc = polyline_distance(X, Y, pts, reach)
            sel = np.isfinite(dist)
            d = dist[sel]
            s = sarc[sel]
            w = np.interp(s, rv["arc"], rv["level"]).astype(np.float32)
            hw = np.interp(s, rv["arc"], rv["hw"]).astype(np.float32)
            dep = np.interp(s, rv["arc"], rv["depth"]).astype(np.float32)
            # banks are a little rougher away from the bridges; at a crossing they are exactly BANK_SLOPE, the
            # slope the bridge spans were measured with
            calm = np.ones(d.shape, np.float32)
            for b in self.bridges:
                if b["river"] == rv["id"]:
                    calm = np.minimum(calm, smoothstep(18.0, 40.0, np.hypot(X[sel] - b["center"][0],
                                                                             Y[sel] - b["center"][1])))
            k = BANK_SLOPE * (1.0 + 0.3 * rough[sel] * calm)
            bed_half = hw + BED_EXTRA
            edge = bed_half + dep / k                       # where the bank comes out of the water
            target = (w - dep) + np.maximum(d - bed_half, 0.0) * k
            cur = h[sel]
            fresh = (w > 0.05) & ~lake[sel]
            new = np.where(fresh | (w <= 0.05), np.minimum(cur, target), cur)
            new = np.where(lake[sel], cur, new)
            # levee: ground lower than the water just outside the channel is raised to hold it in
            lev = w + 0.3 * np.clip((d - edge) / 0.8, 0.0, 1.0) - np.clip(d - edge - 3.0, 0.0, None) * 0.35
            hold = fresh & (d >= edge) & (d < edge + 3.9) & (new < lev)
            new = np.where(hold, lev, new)
            h[sel] = new
            wet = fresh & (d <= edge + 0.4) & (new < w - 0.03)
            lvl = water[sel]
            lvl[wet] = w[wet]
            water[sel] = lvl
            rw = self.river_wet[sel]
            rw[wet] = 1.0
            self.river_wet[sel] = rw
            bank = fresh & (cur - new > 0.25) & ~wet
            rb = self.river_bank[sel]
            rb[bank] = 1.0
            rb[fresh & (d <= edge + 4.0) & ~wet] = 1.0
            self.river_bank[sel] = rb
            changed = np.zeros(h.shape, bool)
            changed[sel] = np.abs(new - cur) > 0.05
            for key, (pw, inner) in self.pad_masks.items():
                if (changed & (pw > 0.6)).any():
                    log(f"    !! {rv['id']} cuts into the {key} pad")
        self.water = water
        return h.astype(np.float32)

    # ------------------------------------------------------------------ forest density
    def forest_density(self):
        X, Y, res = self.X, self.Y, self.res
        h = self.h
        n = fbm(res, 160.0, 4, seed=C.SEED + 20)
        dens = smoothstep(-0.1, 0.6, n) * 0.6
        # core forest regions
        regions = [((560.0, 230.0), 330.0, 1.0), ((870.0, 120.0), 220.0, 1.0), ((380.0, 470.0), 180.0, 0.9),
                   ((-330.0, 700.0), 200.0, 0.6), ((-820.0, 120.0), 230.0, 0.55), ((-400.0, -420.0), 200.0, 0.5),
                   ((300.0, -400.0), 230.0, 0.7), ((-850.0, -480.0), 150.0, 0.5), ((1080.0, 0.0), 120.0, 0.7)]
        for (cx, cy), rr, s in regions:
            d = np.hypot(X - cx, Y - cy)
            dens = np.maximum(dens, s * (1.0 - smoothstep(rr * 0.5, rr, d)) * (0.75 + 0.25 * smoothstep(-0.5, 0.5, n)))
        # exclusions
        dens *= smoothstep(1.0, 8.0, h)                       # no trees on beaches / water
        dens *= 1.0 - smoothstep(30.0, 42.0, self.slope)      # no trees on cliffs
        dens *= 1.0 - smoothstep(140.0, 190.0, h)              # volcano upper slopes bare
        dens *= smoothstep(1.03, 1.2, self.lake_q)             # not in the lake
        dens *= 1.0 - np.clip(ndimage.maximum_filter(self.river_wet, size=5), 0, 1)   # nor in the rivers
        for key, (w, inner) in self.pad_masks.items():
            if key in ("abandoned",):
                dens *= 1.0 - inner * 0.85
                continue
            dens *= 1.0 - np.clip(w * 1.3, 0, 1)
        dens *= 1.0 - np.clip((self.path_paved_lr + self.path_dirt_lr) * 1.5, 0, 1)
        self.forest = np.clip(dens, 0.0, 1.0).astype(np.float32)
        return self.forest

    # ------------------------------------------------------------------ splat maps
    def splat(self, res=None, log=print):
        res = res or C.SPLAT_RES
        log(f"  splat {res}x{res}")
        X, Y, sp = grid(res)
        f = self.field
        H = f(X, Y).astype(np.float32)
        z = res / self.res
        slope = ndimage.zoom(self.slope, z, order=1)[:res, :res]
        forest = ndimage.zoom(self.forest, z, order=1)[:res, :res]
        d_in = ndimage.zoom(self.d_in, z, order=1)[:res, :res]
        cf = ndimage.zoom(self.cliff_factor, z, order=1)[:res, :res]
        rv = np.hypot(X - C.VOLCANO_CENTER[0], Y - C.VOLCANO_CENTER[1])
        lake_q = ndimage.zoom(self.lake_q, z, order=1)[:res, :res]
        n1 = fbm(res, 60.0, 4, seed=C.SEED + 30)
        n2 = fbm(res, 15.0, 3, seed=C.SEED + 31)
        n3 = fbm(res, 4.0, 3, seed=C.SEED + 32)

        beach_w = lerp(70.0, 6.0, cf)
        sand = (1.0 - smoothstep(beach_w * 0.6, beach_w * 1.2 + n1 * 10, d_in)) * (1.0 - smoothstep(4.0, 9.0, H))
        sand = np.maximum(sand, (H < -0.5).astype(np.float32) * 0.9)           # sea floor
        sand = np.maximum(sand, (1.0 - smoothstep(0.98, 1.08, lake_q)) * 0.8)  # lake bed / shore
        wet = (1.0 - smoothstep(0.2, 1.4, np.abs(H - 0.3))) * smoothstep(-1, 1, beach_w - 20) * (d_in < beach_w * 1.5)
        rock = smoothstep(31.0 + n2 * 4, 41.0 + n2 * 4, slope)
        rock = np.maximum(rock, (1.0 - smoothstep(0.9, 1.0, lake_q)) * 0.0)
        ash = (1.0 - smoothstep(170.0, 320.0, rv + n1 * 40.0)) * smoothstep(60.0, 120.0, H)
        ash = np.maximum(ash, (1.0 - smoothstep(130.0, 180.0, rv)) * 1.0)
        forest_floor = smoothstep(0.25, 0.7, forest + n2 * 0.1)
        # rivers: a gravelly wet bed, bare earth on the cut banks (rock where they are steep comes from `rock`)
        r_wet = np.clip(ndimage.zoom(self.river_wet, z, order=1)[:res, :res], 0, 1)
        r_bank = np.clip(ndimage.zoom(self.river_bank, z, order=1)[:res, :res], 0, 1)
        wet = np.maximum(wet, r_wet * 0.85)
        rock = np.maximum(rock, r_wet * np.clip(0.35 + n2 * 0.5, 0, 0.7))
        river_dirt = r_bank * (1.0 - r_wet) * np.clip(0.55 + n1 * 0.3, 0.2, 0.8)
        # paths at full resolution
        paved = np.zeros_like(H)
        dirt = np.zeros_like(H)
        road = np.zeros_like(H)                  # stone a road ribbon lays (colour map only, see below)
        cores = {}
        for p in self.paths:
            hw = p["width"] / 2.0
            line = [tuple(q[:2]) for q in p["samples"][::2]] + [tuple(p["samples"][-1][:2])]
            ext = p.get("extend") or {}
            # the last stretch to a door (config.PATH_EXTENSIONS) is painted like the path itself
            line = [tuple(q) for q in ext.get("start", [])] + line + [tuple(q) for q in ext.get("end", [])]
            dist, _ = polyline_distance(X, Y, line, hw + 4.0)
            dist = np.where(np.isfinite(dist), dist, 1e9)
            edge_noise = n2 * 0.7
            core = 1.0 - smoothstep(hw - 0.4 + edge_noise, hw + 0.9 + edge_noise, dist)
            wear = (1.0 - smoothstep(hw, hw + 3.5, dist)) * 0.5
            cores[p["id"]] = core
            if road_has_ribbon(p):
                # The stone of these roads is laid by their ribbon mesh (layout.road_ribbon: the terrain's own
                # Paving layer by vertex colour, with an edge no splat texel could hold). The ground carries
                # the road's bed instead - bare earth under the ribbon and a verge beside it - which is what
                # the ribbon's rim breaks up into and what the grass then grows over: stone -> earth -> grass
                # without a line anywhere.
                ragged = edge_noise + n3 * 0.45          # here the verge is wide, there grass reaches the stones
                bed = 1.0 - smoothstep(hw - 0.1 + ragged, hw + 1.5 + ragged, dist)
                dirt = np.maximum(dirt, np.maximum(bed * 0.92, wear * 0.5))
                road = np.maximum(road, 1.0 - smoothstep(hw - 0.75, hw + 0.75, dist))
            elif p["surface"] == "paved":
                paved = np.maximum(paved, core)
                dirt = np.maximum(dirt, wear * 0.5)
            else:
                dirt = np.maximum(dirt, np.maximum(core, wear))
        # a stone bridge on an earth path: its paving runs out onto the approaches and breaks up there
        for b in getattr(self, "bridges", []):
            if b.get("kind") != "stone" or b.get("surface") == "paved" or b["path"] not in cores:
                continue
            for ex, ey in (b["a"][:2], b["b"][:2]):
                paved = np.maximum(paved, cores[b["path"]] * (1.0 - smoothstep(1.5, 7.0, np.hypot(X - ex, Y - ey))))
        dirt = np.maximum(dirt, river_dirt)
        paved = paved * (1.0 - r_wet)            # a road ends at the water; the bridge carries it over
        self.road_cover = np.clip(road * (1.0 - r_wet), 0, 1)
        # pads
        specs = pad_specs()
        for key, spec in specs.items():
            w, inner = pad_weight(X, Y, spec)
            w = np.clip(w * 1.4 - 0.4, 0, 1)
            if spec.get("paving"):
                paved = np.maximum(paved, w * spec["paving"])
            if spec.get("dirt"):
                dirt = np.maximum(dirt, w * spec["dirt"] * smoothstep(-0.3, 0.3, n1))
        # academy apron: paving around the building footprint only (lawns elsewhere)
        ax_, ay_ = C.LOCATIONS["academy"]["pos"]
        w, inner = pad_weight(X, Y, dict(center=(ax_, ay_ - 10.0), r=(128.0, 92.0), yaw=0.0, falloff=4.0, shape="rect"))
        paved = np.maximum(paved, w)

        # Priority: paving > dirt > rock > ash > sand > wet > forest > grass(implicit)
        layers = {}
        remaining = np.ones_like(H)
        def take(name, w):
            nonlocal remaining
            w = np.clip(w, 0, 1) * remaining
            layers[name] = w
            remaining = remaining - w
        take("Paving", paved)
        take("Dirt", dirt)
        take("Rock", rock)
        take("Ash", ash)
        take("Sand", sand)
        take("WetSand", wet)
        take("ForestFloor", forest_floor * 0.9)
        layers["Grass"] = remaining
        self.splat_layers = layers
        self.splat_res = res
        return layers

    # ------------------------------------------------------------------ outputs
    def colour_map(self, res=None):
        """Baked albedo used for previews / minimap / UE far-distance tint (sRGB float)."""
        layers = self.splat_layers
        res = self.splat_res
        col = np.zeros((res, res, 3), np.float32)
        tints = dict(palette.TERRAIN_LAYERS)
        info_path = os.path.join(C.CACHE_DIR, "terrain_layers.json")
        if os.path.exists(info_path):
            for k, v in jsonio.read_json(info_path).items():
                tints[k] = tuple(v["mean_srgb"])
        rng_n = fbm(res, 25.0, 3, seed=C.SEED + 40)
        for name, w in layers.items():
            c = np.array(tints[name], np.float32)
            col += w[..., None] * c
        # the roads whose stone is a ribbon mesh: on the map (and in the far-distance tint, which the ribbons
        # share with the ground) they are paved like any other
        cover = getattr(self, "road_cover", None)
        if cover is not None:
            col += (cover * (1.0 - layers["Paving"]))[..., None] * (np.array(tints["Paving"], np.float32) - col)
        col *= (1.0 + rng_n[..., None] * 0.06)
        return np.clip(col, 0, 1)

    def save_outputs(self, log=print):
        from PIL import Image
        os.makedirs(C.OUT_TEXTURES, exist_ok=True)
        os.makedirs(C.OUT_HEIGHTMAP, exist_ok=True)
        os.makedirs(C.CACHE_DIR, exist_ok=True)
        os.makedirs(C.OUT_DATA, exist_ok=True)

        def save_npy(path, array):
            # numpy.save appends ".npy" unless the filename already ends with it;
            # the atomic temp path keeps the real suffix for that reason.
            with atomic.atomic_path(path) as temp_path:
                np.save(temp_path, array)

        h = self.h
        # UE Landscape heightmap (16 bit)
        v = np.clip((h - C.HEIGHT_MIN) / (C.HEIGHT_MAX - C.HEIGHT_MIN), 0, 1) * 65535.0
        atomic.save_image(Image.fromarray(v.astype(np.uint16)),
                          os.path.join(C.OUT_HEIGHTMAP, "T_IslandHeight16.png"))
        # splats
        L = self.splat_layers
        def u8(a):
            return (np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)
        A = np.stack([u8(L["Sand"]), u8(L["Rock"]), u8(L["Dirt"]), u8(L["Paving"])], axis=-1)
        B = np.stack([u8(L["Ash"]), u8(L["ForestFloor"]), u8(L["WetSand"]), np.full_like(u8(L["Ash"]), 255)], axis=-1)
        atomic.save_image(Image.fromarray(A, "RGBA"), os.path.join(C.OUT_TEXTURES, "T_TerrainSplatA.png"), optimize=True)
        atomic.save_image(Image.fromarray(B, "RGBA"), os.path.join(C.OUT_TEXTURES, "T_TerrainSplatB.png"), optimize=True)
        col = self.colour_map()
        col_img = Image.fromarray((col * 255).astype(np.uint8), "RGB")
        atomic.save_image(col_img.resize((2048, 2048), Image.LANCZOS),
                          os.path.join(C.OUT_TEXTURES, "T_TerrainColor.png"), optimize=True)
        self.colour = col
        save_npy(os.path.join(C.CACHE_DIR, "height.npy"), h)
        save_npy(os.path.join(C.CACHE_DIR, "forest.npy"), self.forest)
        save_npy(os.path.join(C.CACHE_DIR, "slope.npy"), self.slope)
        occ = np.clip(self.path_paved_lr + self.path_dirt_lr, 0, 1)
        occ = ndimage.maximum_filter(occ, size=3)
        for key, (w, inner) in self.pad_masks.items():
            occ = np.maximum(occ, inner)
        occ = np.maximum(occ, (self.lake_q < 1.04).astype(np.float32))
        occ = np.maximum(occ, ndimage.maximum_filter(self.river_wet, size=5))     # nothing grows in the rivers
        save_npy(os.path.join(C.CACHE_DIR, "occupied.npy"), occ.astype(np.float32))
        save_npy(os.path.join(C.CACHE_DIR, "d_in.npy"), self.d_in.astype(np.float32))
        save_npy(os.path.join(C.CACHE_DIR, "water.npy"), self.water.astype(np.float32))
        # water maps + water.json (wave sets, wave mask, rivers) for the engine
        from . import water as W
        mask = W.save_maps(h, self.water, self.sp, C.OUT_TEXTURES)
        rivers = self.river_records()
        jsonio.write_json(os.path.join(C.OUT_DATA, "water.json"),
                          W.water_json(mask, [(r["id"], r["name"], r["points"][::2]) for r in rivers]),
                          separators=(",", ":"))
        jsonio.write_json(os.path.join(C.CACHE_DIR, "terrain_info.json"),
                          dict(info=self.info, paths=self.paths, rivers=rivers, bridges=self.bridges))
        write_cache_stamp()
        log(f"  saved heightmap, splats, colour map, water maps, caches ({len(rivers)} rivers, "
            f"{len(self.bridges)} bridges)")

    def river_records(self):
        """Rivers as the later stages need them: samples every 2 m from where the water leaves the lake /
        the spring to where it meets the sea: [x, y, water level, half-width of the water, depth]."""
        out = []
        for rv in self.rivers:
            keep = (~rv["in_lake"]) & (rv["level"] > 0.05)
            idx = np.nonzero(keep)[0]
            if len(idx) == 0:
                continue
            i0, i1 = max(int(idx[0]) - 4, 0), min(int(idx[-1]) + 5, len(rv["arc"]))     # overlap lake and sea
            pts = []
            for i in range(i0, i1):
                half = float(rv["hw"][i] + BED_EXTRA + rv["depth"][i] / BANK_SLOPE)
                pts.append([float(rv["x"][i]), float(rv["y"][i]), float(rv["level"][i]), half,
                            float(rv["depth"][i])])
            out.append(dict(id=rv["id"], name=rv["name"], points=pts))
        return out

    def minimap(self, size=2048):
        """Stylised top-down map (no labels; the HUD draws names). Returns float RGB array."""
        h = ndimage.zoom(self.h, size / self.res, order=1)[:size, :size]
        col = ndimage.zoom(self.colour, (size / self.splat_res, size / self.splat_res, 1), order=1)[:size, :size]
        sp = C.WORLD_SIZE / size
        gy, gx = np.gradient(h, sp)
        # hillshade, light from north-west
        lx, ly, lz = -0.6, 0.6, 0.55
        nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
        shade = np.clip((-gx * nz * lx + gy * nz * ly + nz * lz) / math.sqrt(lx * lx + ly * ly + lz * lz), 0, 1)
        img = col * (0.55 + 0.6 * shade[..., None])
        # water
        X, Y, _ = grid(size)
        lake_mask = None
        sea = h < 0.0
        depth = np.clip(-h / 45.0, 0, 1)
        sea_col = np.stack([lerp(0.35, 0.05, depth), lerp(0.75, 0.25, depth), lerp(0.85, 0.50, depth)], -1)
        img = np.where(sea[..., None], sea_col, img)
        lake_q = ndimage.zoom(self.lake_q, size / self.res, order=1)[:size, :size]
        lake = (lake_q < 1.0) & (h < C.LAKE_LEVEL)
        img = np.where(lake[..., None], np.array([0.2, 0.55, 0.65]), img)
        fresh = ndimage.zoom(self.river_wet, size / self.res, order=1)[:size, :size] > 0.3
        img = np.where(fresh[..., None], np.array([0.2, 0.55, 0.65]), img)
        # shoreline outline
        coast = ndimage.binary_dilation(sea, iterations=2) & ~sea
        img = np.where(coast[..., None], img * 0.75 + 0.25, img)
        # contour lines every 25 m
        c = (np.floor(h / 25.0) != np.floor(ndimage.uniform_filter(h, 3) / 25.0)) & (h > 2)
        img = np.where(c[..., None], img * 0.85, img)
        return np.clip(img, 0, 1).astype(np.float32)


def build_terrain(log=print):
    t = Terrain()
    t.build(log)
    t.forest_density()
    t.splat(log=log)
    t.save_outputs(log)
    return t


def load_cached():
    """Lightweight access for later stages (layout) without regenerating.

    Raises cache.StampedCacheError when the caches are missing / partial / were
    written with a different FIELD_RES / WORLD_SIZE (see check_cache).
    """
    check_cache("height.npy", "forest.npy", "slope.npy", "terrain_info.json")
    h = np.load(os.path.join(C.CACHE_DIR, "height.npy"))
    forest = np.load(os.path.join(C.CACHE_DIR, "forest.npy"))
    slope = np.load(os.path.join(C.CACHE_DIR, "slope.npy"))
    meta = jsonio.read_json(os.path.join(C.CACHE_DIR, "terrain_info.json"))
    # the height sampler is the drawn mesh (MeshField): whatever the later stages put "on the ground" stands
    # on the triangles the player sees
    return MeshField(h), Field(forest), Field(slope), meta


def load_water():
    """Water surface height per heightfield cell (NaN where dry) as a [row, col] array."""
    check_cache("water.npy")
    return np.load(os.path.join(C.CACHE_DIR, "water.npy"))


def load_extra():
    check_cache("occupied.npy", "d_in.npy")
    occ = np.load(os.path.join(C.CACHE_DIR, "occupied.npy"))
    d_in = np.load(os.path.join(C.CACHE_DIR, "d_in.npy"))
    return Field(occ), Field(d_in)
