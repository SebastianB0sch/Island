"""
The island's fresh water as the later stages see it: the rivers the terrain stage cut (Tools/.cache/
terrain_info.json "rivers" / "bridges") and the water raster (water.npy). Read-only helpers for the layout
stage and the location modules - where is the nearest bank, how far is this spot from the water.

    RIVERS            {id: River}
    clearance(x, y)   metres to the nearest fresh-water edge (river, pond, lake); negative in the water
    nearest(x, y)     (river id, s, distance to the centre line, (px, py), (tx, ty), water level, half width)
    point_at(id, s)   ((x, y), (tx, ty), water level, half width) at arc length s (m, downstream)
    bridges()         bridge records of the terrain stage

Coordinates are world metres, Blender axes (+Y north).
"""

import math
import os

import numpy as np

from . import config as C
from . import jsonio, terrain


class River:
    def __init__(self, rec):
        self.id = rec["id"]
        self.name = rec["name"]
        p = np.asarray(rec["points"], np.float64)
        self.xy = p[:, :2]
        self.level = p[:, 2]
        self.half = p[:, 3]            # half-width of the water surface
        self.depth = p[:, 4]
        self.arc = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1])))])
        self.length = float(self.arc[-1])

    @property
    def pts(self):
        return [(float(x), float(y), float(z), float(hw)) for (x, y), z, hw in zip(self.xy, self.level, self.half)]

    def at(self, s):
        s = float(np.clip(s, 0.0, self.length))
        x = float(np.interp(s, self.arc, self.xy[:, 0]))
        y = float(np.interp(s, self.arc, self.xy[:, 1]))
        i = int(np.clip(np.searchsorted(self.arc, s) - 1, 0, len(self.arc) - 2))
        tx, ty = self.xy[i + 1] - self.xy[i]
        ln = math.hypot(tx, ty) or 1.0
        return (x, y), (tx / ln, ty / ln), float(np.interp(s, self.arc, self.level)), \
            float(np.interp(s, self.arc, self.half))

    def project(self, x, y):
        """(s, distance) of the centre-line point nearest to (x, y)."""
        a, b = self.xy[:-1], self.xy[1:]
        d = b - a
        l2 = np.maximum((d * d).sum(1), 1e-12)
        t = np.clip(((x - a[:, 0]) * d[:, 0] + (y - a[:, 1]) * d[:, 1]) / l2, 0.0, 1.0)
        px, py = a[:, 0] + t * d[:, 0], a[:, 1] + t * d[:, 1]
        dist = np.hypot(px - x, py - y)
        i = int(np.argmin(dist))
        return float(self.arc[i] + t[i] * (self.arc[i + 1] - self.arc[i])), float(dist[i])


class _Lazy(dict):
    """RIVERS: filled from the terrain cache on first use (the module imports without a cache)."""
    _loaded = False

    def _load(self):
        if not self._loaded:
            self._loaded = True
            for rec in _info().get("rivers", []):
                dict.__setitem__(self, rec["id"], River(rec))
        return self

    def __getitem__(self, k):
        return dict.__getitem__(self._load(), k)

    def __iter__(self):
        return dict.__iter__(self._load())

    def __len__(self):
        return dict.__len__(self._load())

    def __contains__(self, k):
        return dict.__contains__(self._load(), k)

    def items(self):
        return dict.items(self._load())

    def values(self):
        return dict.values(self._load())

    def keys(self):
        return dict.keys(self._load())

    def get(self, k, default=None):
        return dict.get(self._load(), k, default)


RIVERS = _Lazy()
_cache = {}


def _info():
    if "info" not in _cache:
        terrain.check_cache("terrain_info.json")
        _cache["info"] = jsonio.read_json(os.path.join(C.CACHE_DIR, "terrain_info.json"))
    return _cache["info"]


def bridges():
    return list(_info().get("bridges", []))


def _edge_field():
    """Signed distance (m) to the fresh-water edge on the heightfield grid: > 0 on land."""
    if "edge" not in _cache:
        from scipy import ndimage
        level = terrain.load_water()
        fresh = np.isfinite(level) & (level > 0.05)
        sp = C.WORLD_SIZE / (level.shape[0] - 1)
        d = ndimage.distance_transform_edt(~fresh) - ndimage.distance_transform_edt(fresh)
        _cache["edge"] = terrain.Field((d * sp).astype(np.float32))
        _cache["level"] = level
    return _cache["edge"]


def clearance(x, y):
    """Metres from (x, y) to the nearest fresh water (rivers, ponds, the lake); negative inside it."""
    return float(_edge_field()(x, y))


def clearances(x, y):
    """clearance() for arrays of points."""
    return np.asarray(_edge_field()(x, y), np.float64)


def water_level(x, y):
    """Water surface height at (x, y), or None on dry ground (sea 0, lake, river)."""
    _edge_field()
    level = _cache["level"]
    sp = C.WORLD_SIZE / (level.shape[0] - 1)
    r = int(np.clip(round((C.HALF - y) / sp), 0, level.shape[0] - 1))
    c = int(np.clip(round((x + C.HALF) / sp), 0, level.shape[1] - 1))
    v = float(level[r, c])
    return v if math.isfinite(v) else None


def nearest(x, y):
    """(river id, s, distance to the centre line, (px, py), (tx, ty), water level, half width) of the river
    whose centre line is closest, or None without rivers."""
    best = None
    for rid, rv in RIVERS.items():
        s, d = rv.project(x, y)
        if best is None or d < best[2]:
            p, t, z, hw = rv.at(s)
            best = (rid, s, d, p, t, z, hw)
    return best


def point_at(river_id, s):
    return RIVERS[river_id].at(s)


def mesh_name(river_id):
    """Static mesh of a river's water surface (Meshes/Water)."""
    return "SM_River_" + "".join(part.capitalize() for part in river_id.split("_"))
