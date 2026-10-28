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

import json
import math
import os

import numpy as np
from scipy import ndimage
from scipy.interpolate import CubicSpline, RectBivariateSpline

from . import config as C
from . import palette

# --------------------------------------------------------------------------- helpers

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

        # ------------------------------------------------------------------ paths
        log("  paths")
        self.paths = []
        path_paved = np.zeros_like(h)
        path_dirt = np.zeros_like(h)
        for p in C.PATHS:
            pts = p["pts"]
            hw = p["width"] / 2.0
            samples = resample_polyline(pts, 2.0)
            arr = np.array(samples)
            hf = Field(h)
            prof = hf(arr[:, 0], arr[:, 1]).astype(np.float64)
            if p.get("fixed_z") is not None:
                prof[:] = p["fixed_z"]
            else:
                raw = prof.copy()
                for _ in range(4):
                    prof = ndimage.uniform_filter1d(prof, size=21, mode="nearest")
                # grade limit 13 %
                g = 0.13 * 2.0
                for _ in range(3):
                    for i in range(1, len(prof)):
                        prof[i] = np.clip(prof[i], prof[i - 1] - g, prof[i - 1] + g)
                    for i in range(len(prof) - 2, -1, -1):
                        prof[i] = np.clip(prof[i], prof[i + 1] - g, prof[i + 1] + g)
                # pin ends to the raw terrain (pads)
                for k in range(min(6, len(prof))):
                    wk = 1.0 - k / 6.0
                    prof[k] = lerp(prof[k], raw[k], wk)
                    prof[-1 - k] = lerp(prof[-1 - k], raw[-1 - k], wk)
                prof = np.maximum(prof, 0.6)
            shoulder = 9.0 if p.get("dike") is None else 30.0
            dist, sarc = polyline_distance(X, Y, pts, hw + shoulder + 2)
            sel = np.isfinite(dist)
            arc = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(arr[:, 0]), np.diff(arr[:, 1])))])
            ph = np.interp(sarc[sel], arc, prof).astype(np.float32)
            if p.get("dike"):
                top = ph
                slope_h = top - np.maximum(dist[sel] - hw, 0.0) * 0.7
                h[sel] = np.where(dist[sel] <= hw + 0.5, top, np.maximum(h[sel], slope_h))
            else:
                w = 1.0 - smoothstep(hw + 0.5, hw + 0.5 + shoulder, dist[sel])
                h[sel] = lerp(h[sel], ph, w)
            core = 1.0 - smoothstep(hw - 0.5, hw + 1.5, dist)
            core = np.where(np.isfinite(core), core, 0.0)
            if p["surface"] == "paved":
                path_paved = np.maximum(path_paved, core)
            else:
                path_dirt = np.maximum(path_dirt, core)
            self.paths.append(dict(id=p["id"], width=p["width"], surface=p["surface"], lamps=p.get("lamps", False),
                                   pts=[[float(a), float(b)] for a, b in pts],
                                   samples=[[float(a), float(b), float(c)] for (a, b), c in zip(samples, prof)]))
        self.path_paved_lr = path_paved
        self.path_dirt_lr = path_dirt

        # lighthouse platform at the end of the breakwater
        lx_, ly_ = C.LOCATIONS["lighthouse"]["pos"]
        dl = np.hypot(X - lx_, Y - ly_)
        h = np.where(dl < 40, np.maximum(h, 4.0 - np.maximum(dl - 15.0, 0.0) * 0.7), h)
        h = np.where(dl < 15, 4.0, h)

        # ------------------------------------------------------------------ pads (re-flatten cores)
        for key, spec in specs.items():
            w, inner = self.pad_masks[key]
            core = np.clip(w * 1.6 - 0.6, 0.0, 1.0)
            h = lerp(h, heights[key], core).astype(np.float32)

        # ------------------------------------------------------------------ domain edge + smoothing
        edge = C.HALF - np.maximum(np.abs(X), np.abs(Y))
        we = smoothstep(0.0, 160.0, edge)
        h = lerp(C.SEA_FLOOR, h, we)
        h = ndimage.gaussian_filter(h, 0.7).astype(np.float32)
        # keep pads perfectly flat after blur
        for key in specs:
            w, inner = self.pad_masks[key]
            core = np.clip(w * 2.0 - 1.0, 0.0, 1.0)
            h = lerp(h, heights[key], core).astype(np.float32)
        h = np.where(dl < 15, 4.0, h).astype(np.float32)

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
        # paths at full resolution
        paved = np.zeros_like(H)
        dirt = np.zeros_like(H)
        for p in self.paths:
            hw = p["width"] / 2.0
            dist, _ = polyline_distance(X, Y, p["pts"], hw + 4.0)
            dist = np.where(np.isfinite(dist), dist, 1e9)
            edge_noise = n2 * 0.7
            core = 1.0 - smoothstep(hw - 0.4 + edge_noise, hw + 0.9 + edge_noise, dist)
            wear = (1.0 - smoothstep(hw, hw + 3.5, dist)) * 0.5
            if p["surface"] == "paved":
                paved = np.maximum(paved, core)
                dirt = np.maximum(dirt, wear * 0.5)
            else:
                dirt = np.maximum(dirt, np.maximum(core, wear))
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
        rng_n = fbm(res, 25.0, 3, seed=C.SEED + 40)
        for name, w in layers.items():
            c = np.array(tints[name], np.float32)
            col += w[..., None] * c
        col *= (1.0 + rng_n[..., None] * 0.06)
        return np.clip(col, 0, 1)

    def save_outputs(self, log=print):
        from PIL import Image
        os.makedirs(C.OUT_TEXTURES, exist_ok=True)
        os.makedirs(C.OUT_HEIGHTMAP, exist_ok=True)
        os.makedirs(C.CACHE_DIR, exist_ok=True)
        os.makedirs(C.OUT_DATA, exist_ok=True)
        h = self.h
        # UE Landscape heightmap (16 bit)
        v = np.clip((h - C.HEIGHT_MIN) / (C.HEIGHT_MAX - C.HEIGHT_MIN), 0, 1) * 65535.0
        Image.fromarray(v.astype(np.uint16)).save(os.path.join(C.OUT_HEIGHTMAP, "T_IslandHeight16.png"))
        # splats
        L = self.splat_layers
        def u8(a):
            return (np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)
        A = np.stack([u8(L["Sand"]), u8(L["Rock"]), u8(L["Dirt"]), u8(L["Paving"])], axis=-1)
        B = np.stack([u8(L["Ash"]), u8(L["ForestFloor"]), u8(L["WetSand"]), np.full_like(u8(L["Ash"]), 255)], axis=-1)
        Image.fromarray(A, "RGBA").save(os.path.join(C.OUT_TEXTURES, "T_TerrainSplatA.png"), optimize=True)
        Image.fromarray(B, "RGBA").save(os.path.join(C.OUT_TEXTURES, "T_TerrainSplatB.png"), optimize=True)
        col = self.colour_map()
        col_img = Image.fromarray((col * 255).astype(np.uint8), "RGB")
        col_img.resize((2048, 2048), Image.LANCZOS).save(os.path.join(C.OUT_TEXTURES, "T_TerrainColor.png"), optimize=True)
        self.colour = col
        np.save(os.path.join(C.CACHE_DIR, "height.npy"), h)
        np.save(os.path.join(C.CACHE_DIR, "forest.npy"), self.forest)
        np.save(os.path.join(C.CACHE_DIR, "slope.npy"), self.slope)
        occ = np.clip(self.path_paved_lr + self.path_dirt_lr, 0, 1)
        occ = ndimage.maximum_filter(occ, size=3)
        for key, (w, inner) in self.pad_masks.items():
            occ = np.maximum(occ, inner)
        occ = np.maximum(occ, (self.lake_q < 1.04).astype(np.float32))
        np.save(os.path.join(C.CACHE_DIR, "occupied.npy"), occ.astype(np.float32))
        np.save(os.path.join(C.CACHE_DIR, "d_in.npy"), self.d_in.astype(np.float32))
        with open(os.path.join(C.CACHE_DIR, "terrain_info.json"), "w") as fp:
            json.dump(dict(info=self.info, paths=self.paths), fp)
        log("  saved heightmap, splats, colour map, caches")

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
    """Lightweight access for later stages (layout) without regenerating."""
    h = np.load(os.path.join(C.CACHE_DIR, "height.npy"))
    forest = np.load(os.path.join(C.CACHE_DIR, "forest.npy"))
    slope = np.load(os.path.join(C.CACHE_DIR, "slope.npy"))
    with open(os.path.join(C.CACHE_DIR, "terrain_info.json")) as fp:
        meta = json.load(fp)
    return Field(h), Field(forest), Field(slope), meta


def load_extra():
    occ = np.load(os.path.join(C.CACHE_DIR, "occupied.npy"))
    d_in = np.load(os.path.join(C.CACHE_DIR, "d_in.npy"))
    return Field(occ), Field(d_in)
