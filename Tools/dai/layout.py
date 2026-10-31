"""
Layout stage: turns AssetSets + terrain into the data Unreal needs.

Outputs (SourceAssets/):
  Meshes/Locations/<key>/SM_*.fbx    location meshes (local space, placed by actors)
  Meshes/Roads/SM_Road_*.fbx          paved road ribbons (world space)
  Meshes/Props/SM_*.fbx               shared props + vegetation (with UCX collision)
  Meshes/Characters/SM_Avatar_*.fbx   avatar parts
  Data/layout.json                     every actor / instance / light / zone, in UE units (cm, left-handed)
  Data/materials.json                  palette (linear colours)
  Data/assets.json                     import manifest (collision / nanite flags per mesh)
  Textures/T_IslandMap.png             minimap with building footprints
"""

import json
import math
import os
import random

import numpy as np

from . import config as C
from . import palette, terrain
from .assets import AssetSet, load_placements
from .assets import props as P
from .assets import avatar as AV

# --------------------------------------------------------------------------- coordinate helpers
Y_SIGN = -1.0   # Blender +Y (north) -> UE -Y


def ue_loc(p):
    return [round(float(p[0]) * 100.0, 1), round(float(p[1]) * 100.0 * Y_SIGN, 1), round(float(p[2]) * 100.0, 1)]


def ue_yaw(yaw):
    return round(float(yaw) * (-1.0 if Y_SIGN < 0 else 1.0), 2)


def rot2(x, y, yaw_deg):
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    return x * c - y * s, x * s + y * c


class Xform:
    def __init__(self, x, y, z, yaw):
        self.x, self.y, self.z, self.yaw = x, y, z, yaw

    def point(self, p):
        lx, ly = rot2(p[0], p[1], self.yaw)
        return (self.x + lx, self.y + ly, self.z + (p[2] if len(p) > 2 else 0.0))


# --------------------------------------------------------------------------- main
class Layout:
    def __init__(self, log=print):
        self.log = log
        self.hf, self.ff, self.sf, self.meta = terrain.load_cached()
        self.occ, self.din = terrain.load_extra()
        from scipy import ndimage
        # "near built-up area" mask: paths/pads/lake dilated by ~30 m (keeps cliff boulders off quays and dikes)
        self.near = terrain.Field(ndimage.maximum_filter(self.occ.a, size=21))
        self.info = self.meta["info"]
        self.static = []
        self.floating = []
        self.instances = {}
        self.lights = []
        self.texts = []
        self.interacts = []
        self.emitters = []
        self.audio = []
        self.npcs = []
        self.specials = []
        self.clearings = []      # (x, y, r) world metres
        self.footprints = []     # (key, [(x,y)...]) for the minimap
        self.manifest = []
        self.rng = random.Random(C.SEED)

    # ------------------------------------------------------------------ helpers
    def ground(self, x, y):
        return float(self.hf(x, y))

    def add_instance(self, asset, x, y, z, yaw, scale):
        g = self.instances.setdefault(asset, [])
        g.append([round(x * 100, 1), round(y * 100 * Y_SIGN, 1), round(z * 100, 1), ue_yaw(yaw), round(scale, 3)])

    def add_light(self, p, props, yaw=0.0):
        d = dict(loc=ue_loc(p), color=props.get("color", [1, 0.85, 0.6]), intensity=props.get("intensity", 5000.0),
                 radius=props.get("radius", 12.0) * 100.0, night_only=bool(props.get("night_only", False)),
                 shadows=bool(props.get("shadows", False)))
        if props.get("spot_pitch") is not None:
            d["spot"] = dict(yaw=ue_yaw(yaw), pitch=-float(props["spot_pitch"]), cone=float(props.get("cone") or 40.0))
        self.lights.append(d)

    def export_mesh(self, mb, name, folder, collision):
        from . import blend
        rel = os.path.join("Meshes", folder, f"SM_{name}.fbx")
        path = os.path.join(C.OUT_DIR, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        obj = mb.build("SM_" + name)
        blend.export_fbx([obj], path)
        blend.delete([obj])
        self.manifest.append(dict(file=rel.replace(os.sep, "/"), name=f"SM_{name}", folder=folder.replace(os.sep, "/"),
                                  collision=collision, nanite=False, category="location"))

    # ------------------------------------------------------------------ locations
    def place_locations(self, export=True):
        placements = load_placements(self.log)
        for key, fn in placements.items():
            if key not in C.LOCATIONS:
                continue
            aset = fn()
            loc = C.LOCATIONS[key]
            absolute = getattr(aset, "absolute", False)
            x0, y0 = loc["pos"]
            if absolute:
                xf = Xform(x0, y0, 0.0, 0.0)
            else:
                z0 = self.info["pads"].get(key)
                if z0 is None:
                    z0 = 4.0 if key == "lighthouse" else self.ground(x0, y0)
                xf = Xform(x0, y0, z0, loc["yaw"])
            floating_meshes = {s["props"].get("mesh") for s in aset.sockets if s["type"] == "floating"}
            n_mesh = 0
            for name, mb in aset.meshes.items():
                if not mb.verts:
                    continue
                collision = "none" if name.endswith("_NoCol") else "complex"
                folder = os.path.join("Locations", key)
                if export:
                    self.export_mesh(mb, name, folder, collision)
                n_mesh += 1
                if name in floating_meshes:
                    continue
                self.static.append(dict(mesh=f"SM_{name}", folder=f"Locations/{key}", loc=ue_loc((xf.x, xf.y, xf.z)),
                                        yaw=ue_yaw(xf.yaw), collision=collision, group=key, label=f"{key}_{name}"))
                if collision != "none":
                    (mn, mx) = mb.bounds()
                    corners = [(mn[0], mn[1]), (mx[0], mn[1]), (mx[0], mx[1]), (mn[0], mx[1])]
                    if mx[2] - max(mn[2], 0) > 2.5 and (mx[0] - mn[0]) * (mx[1] - mn[1]) > 30:
                        self.footprints.append((key, [xf.point((c[0], c[1], 0))[:2] for c in corners]))
            self.place_sockets(aset, xf, key)
            self.log(f"  {key:14s} {n_mesh} meshes, {len(aset.sockets)} sockets")

    # ------------------------------------------------------------------ interiors
    def place_interiors(self, export=True):
        """Build/export the portal-cell interiors listed in Content/Data/World/interiors.json.

        Cells are authored in local metres by `dai.assets.interiors`; this method
        places each AssetSet at its UE origin and appends its lights/text/interacts
        to the same layout arrays the existing island uses.  It does not touch any
        existing location placement.
        """
        from .assets import interiors as I

        path = os.path.join(C.UE_PROJECT_DIR, "Content", "Data", "World", "interiors.json")
        if not os.path.exists(path):
            self.log(f"  interiors: {path} not found, skipping")
            return
        with open(path, "r", encoding="utf-8") as fp:
            doc = json.load(fp)

        cells = doc.get("cells", [])
        for cell in cells:
            cid = str(cell.get("id", "cell"))
            origin = [float(v) for v in cell.get("origin_ue", [0, 0, 0])]
            aset = I.build_cell(cell)
            folder = "Locations/interiors"
            for name, mb in aset.meshes.items():
                if not mb.verts:
                    continue
                collision = "none" if name.endswith("_NoCol") else "complex"
                if export:
                    self.export_mesh(mb, name, folder, collision)
                self.static.append(dict(mesh=f"SM_{name}", folder=folder, loc=origin, yaw=0.0,
                                        collision=collision, group="interiors", label=name))
            self._place_interior_sockets(aset, origin, cid)
            self.log(f"  interior {cid:24s} {len(aset.meshes)} meshes, {len(aset.sockets)} sockets")

        self.log(f"  interiors: {len(cells)} cells")

    def _place_interior_sockets(self, aset, origin, cid):
        """Convert local socket positions to UE world and append them to layout arrays."""
        ox, oy, oz = origin

        def upoint(p):
            return [round(ox + float(p[0]) * 100.0, 1),
                    round(oy - float(p[1]) * 100.0, 1),
                    round(oz + (float(p[2]) if len(p) > 2 else 0.0) * 100.0, 1)]

        for s in aset.sockets:
            t, p, pr = s["type"], s["pos"], s["props"]
            loc = upoint(p)
            yaw = ue_yaw(s["yaw"])
            if t == "light":
                L = dict(loc=loc, color=pr.get("color", [1, 0.85, 0.6]),
                         intensity=pr.get("intensity", 5000.0),
                         radius=float(pr.get("radius", 12.0)) * 100.0,
                         night_only=bool(pr.get("night_only", False)),
                         shadows=bool(pr.get("shadows", False)))
                if pr.get("spot_pitch") is not None:
                    L["spot"] = dict(yaw=yaw, pitch=-float(pr["spot_pitch"]), cone=float(pr.get("cone") or 40.0))
                self.lights.append(L)
            elif t == "text":
                self.texts.append(dict(loc=loc, yaw=yaw, text=pr.get("text", ""),
                                       size=float(pr.get("size", 1.0)) * 100.0,
                                       color=pr.get("color", [1, 1, 1]),
                                       emissive=bool(pr.get("emissive", False))))
            elif t == "interact":
                self.interacts.append(dict(kind=pr.get("kind", "sign"), loc=loc, yaw=yaw,
                                           title=pr.get("title", ""), text=pr.get("text", ""),
                                           radius=float(pr.get("radius", 3.0)) * 100.0,
                                           group=cid))
            elif t == "audio":
                self.audio.append(dict(sound=pr.get("sound", "A_Wind"), loc=loc,
                                       radius=float(pr.get("radius", 40.0)) * 100.0,
                                       volume=float(pr.get("volume", 1.0))))
            elif t == "emitter":
                self.emitters.append(dict(kind=pr.get("kind", "steam"), loc=loc,
                                          scale=float(pr.get("scale", 1.0)),
                                          rate=float(pr.get("rate", 1.0))))

    def place_sockets(self, aset, xf, key):
        for s in aset.sockets:
            p = xf.point(s["pos"])
            yaw = xf.yaw + s["yaw"]
            t, pr = s["type"], s["props"]
            if t == "prop":
                asset = pr["asset"]
                if asset not in P.REGISTRY:
                    self.log(f"   !! {key}: unknown prop {asset}")
                    continue
                if asset in P.FLOATING_PROPS:
                    self.floating.append(dict(mesh=asset, folder="Props", loc=ue_loc(p), yaw=ue_yaw(yaw),
                                              scale=pr.get("scale", 1.0), amplitude=8.0, period=4.0 + self.rng.random() * 2,
                                              sway=2.0))
                else:
                    self.add_instance(asset, p[0], p[1], p[2], yaw, pr.get("scale", 1.0))
                if asset in P.PROP_LIGHTS:
                    L = P.PROP_LIGHTS[asset]
                    ox, oy = rot2(L["offset"][0], L["offset"][1], yaw)
                    sc = pr.get("scale", 1.0)
                    self.add_light((p[0] + ox, p[1] + oy, p[2] + L["offset"][2] * sc), L)
                self.clearings.append((p[0], p[1], 2.5))
            elif t == "light":
                self.add_light(p, pr, yaw)
            elif t == "text":
                self.texts.append(dict(loc=ue_loc(p), yaw=ue_yaw(yaw), text=pr["text"], size=pr.get("size", 1.0) * 100.0,
                                       color=pr.get("color", [1, 1, 1]), emissive=pr.get("emissive", False)))
            elif t == "interact":
                self.interacts.append(dict(kind=pr["kind"], loc=ue_loc(p), yaw=ue_yaw(yaw), title=pr.get("title", ""),
                                           text=pr.get("text", ""), radius=pr.get("radius", 3.0) * 100.0, group=key))
                self.clearings.append((p[0], p[1], 3.0))
            elif t == "emitter":
                self.emitters.append(dict(kind=pr["kind"], loc=ue_loc(p), scale=pr.get("scale", 1.0), rate=pr.get("rate", 1.0)))
            elif t == "audio":
                self.audio.append(dict(sound=pr["sound"], loc=ue_loc(p), radius=pr.get("radius", 40.0) * 100.0,
                                       volume=pr.get("volume", 1.0)))
            elif t == "npc":
                self.npcs.append(dict(loc=ue_loc((p[0], p[1], p[2] + 0.95)), yaw=ue_yaw(yaw), dorm=pr.get("dorm", "slifer"),
                                      wander=pr.get("wander", 8.0) * 100.0, group=key))
            elif t == "clearing":
                self.clearings.append((p[0], p[1], pr.get("radius", 5.0)))
            elif t == "floating":
                self.floating.append(dict(mesh=f"SM_{pr['mesh']}", folder=f"Locations/{key}", loc=ue_loc(p), yaw=ue_yaw(yaw),
                                          scale=1.0, amplitude=pr.get("amplitude", 0.15) * 100.0, period=pr.get("period", 6.0),
                                          sway=pr.get("sway", 0.4)))
            elif t == "camera":
                continue
            else:
                extra = {}
                for k, v in pr.items():
                    if k in ("lip",) and isinstance(v, (list, tuple)) and len(v) == 3:
                        extra[k] = ue_loc(xf.point(v))
                    elif k in ("beam_length", "height", "length", "radius"):
                        extra[k] = float(v) * 100.0
                    else:
                        extra[k] = v
                self.specials.append(dict(kind=t, loc=ue_loc(p), yaw=ue_yaw(yaw), props=extra, group=key))

    # ------------------------------------------------------------------ paths: lamps, signposts, roads
    DEST = {
        "main_road": "Harbor  /  Duel Academy", "to_slifer": "Slifer Red Dorm", "to_ra": "Ra Yellow Dorm",
        "to_obelisk": "Obelisk Blue Dorm", "to_girls": "Girls' Dorm & Lake", "lake_walk": "Volcano Falls",
        "to_abandoned": "Abandoned Dorm  (Off Limits!)", "to_gym": "Duel Gym & Beach", "to_springs": "Hot Springs",
        "volcano_trail": "Volcano Crater", "forest_trail": "Forest Trail / Lake", "breakwater": "Lighthouse",
        "to_heliport": "Heliport", "to_cliffs": "Sunset Point",
    }

    def in_any_pad(self, x, y, margin=0.0):
        for key, spec in terrain.pad_specs().items():
            w, inner = terrain.pad_weight(np.array([[x]], np.float32), np.array([[y]], np.float32),
                                          dict(spec, r=(spec["r"][0] + margin, spec["r"][1] + margin)))
            if inner[0, 0] > 0:
                return key
        return None

    def place_path_dressing(self, export=True):
        from .geo import MeshBuilder
        lamps = 0
        for p in self.meta["paths"]:
            samples = p["samples"]
            hw = p["width"] / 2.0
            arc = [0.0]
            for i in range(1, len(samples)):
                arc.append(arc[-1] + math.hypot(samples[i][0] - samples[i - 1][0], samples[i][1] - samples[i - 1][1]))
            # lamps
            if p.get("lamps"):
                spacing = 34.0
                side = 1
                s = spacing * 0.5
                while s < arc[-1] - 5:
                    i = int(np.searchsorted(arc, s))
                    i = min(max(i, 1), len(samples) - 1)
                    ax, ay, _ = samples[i - 1]
                    bx, by, _ = samples[i]
                    d = math.hypot(bx - ax, by - ay) or 1.0
                    nx, ny = -(by - ay) / d, (bx - ax) / d
                    px, py = bx + nx * (hw + 1.2) * side, by + ny * (hw + 1.2) * side
                    if self.in_any_pad(px, py, 4.0) is None and self.ground(px, py) > 1.0:
                        z = self.ground(px, py)
                        yaw = math.degrees(math.atan2(-ny * side, -nx * side)) + 90.0
                        self.add_instance("SM_LampPost", px, py, z - 0.05, yaw, 1.0)
                        self.add_light((px, py, z + 4.2), P.PROP_LIGHTS["SM_LampPost"])
                        self.clearings.append((px, py, 2.0))
                        lamps += 1
                    side = -side
                    s += spacing
            # signpost at the path start (if not inside a pad)
            sx, sy, _ = samples[0]
            bx, by, _ = samples[min(4, len(samples) - 1)]
            d = math.hypot(bx - sx, by - sy) or 1.0
            nx, ny = -(by - sy) / d, (bx - sx) / d
            px, py = sx + nx * (hw + 2.0) + (bx - sx) / d * 3.0, sy + ny * (hw + 2.0) + (by - sy) / d * 3.0
            if self.in_any_pad(px, py, 0.0) is None and p["id"] not in ("breakwater",):
                z = self.ground(px, py)
                yaw = math.degrees(math.atan2(by - sy, bx - sx)) - 90.0
                self.add_instance("SM_Signpost", px, py, z, yaw, 1.0)
                self.interacts.append(dict(kind="sign", loc=ue_loc((px, py, z + 1.6)), yaw=ue_yaw(yaw),
                                           title="Signpost", text="This way: " + self.DEST.get(p["id"], p["id"]),
                                           radius=300.0, group="paths"))
                self.clearings.append((px, py, 2.0))
            # paved road ribbons (crisp edges + kerbs on top of the splat paving)
            if export and p["surface"] == "paved" and p["id"] != "breakwater":
                mb = MeshBuilder(f"Road_{p['id']}")
                pts = samples
                left, right = [], []
                for i in range(len(pts)):
                    a = pts[max(i - 1, 0)]
                    b = pts[min(i + 1, len(pts) - 1)]
                    d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
                    nx, ny = -(b[1] - a[1]) / d, (b[0] - a[0]) / d
                    x, y, z = pts[i]
                    zl = max(z, self.ground(x + nx * hw, y + ny * hw)) + 0.10
                    zr = max(z, self.ground(x - nx * hw, y - ny * hw)) + 0.10
                    zc = max(z, self.ground(x, y)) + 0.10
                    zz = max(zl, zr, zc)
                    left.append((x + nx * hw, y + ny * hw, zz))
                    right.append((x - nx * hw, y - ny * hw, zz))
                for i in range(len(pts) - 1):
                    l0, l1, r0, r1 = left[i], left[i + 1], right[i], right[i + 1]
                    mb.quad(r0, r1, l1, l0, "M_Paving")
                    # side skirts down into the ground + kerb tops
                    for (e0, e1, sgn) in ((l0, l1, 1), (r0, r1, -1)):
                        lo0 = (e0[0], e0[1], e0[2] - 0.8)
                        lo1 = (e1[0], e1[1], e1[2] - 0.8)
                        if sgn > 0:
                            mb.quad(lo1, lo0, e0, e1, "M_Concrete")
                        else:
                            mb.quad(lo0, lo1, e1, e0, "M_Concrete")
                self.export_mesh(mb, f"Road_{p['id']}", "Roads", "complex")
                self.static.append(dict(mesh=f"SM_Road_{p['id']}", folder="Roads", loc=[0, 0, 0], yaw=0.0,
                                        collision="complex", group="roads", label=f"Road_{p['id']}"))
        self.log(f"  path dressing: {lamps} lamps")

    # ------------------------------------------------------------------ vegetation scatter
    def scatter(self):
        rng = np.random.default_rng(C.SEED + 100)
        clear = np.array(self.clearings, dtype=np.float64) if self.clearings else np.zeros((0, 3))

        def jitter_grid(cell, extent=1450.0):
            n = int(2 * extent / cell)
            gx, gy = np.meshgrid(np.arange(n), np.arange(n))
            x = -extent + (gx.ravel() + rng.random(gx.size)) * cell
            y = -extent + (gy.ravel() + rng.random(gy.size)) * cell
            return x, y

        def free(x, y, radius):
            ok = np.ones(x.shape, bool)
            if len(clear):
                for (cx, cy, r) in clear:
                    m = (np.abs(x - cx) < r + radius) & (np.abs(y - cy) < r + radius)
                    if m.any():
                        d = np.hypot(x[m] - cx, y[m] - cy)
                        sub = ok[m]
                        sub &= d > (r + radius)
                        ok[m] = sub
            return ok

        h_all = None
        counts = {}

        def emit(asset, x, y, z, scale_lo, scale_hi, sink=0.15):
            for i in range(len(x)):
                self.add_instance(asset, x[i], y[i], z[i] - sink, rng.uniform(0, 360), rng.uniform(scale_lo, scale_hi))
            counts[asset] = counts.get(asset, 0) + len(x)

        vx, vy = C.VOLCANO_CENTER
        # ---------------- forest trees
        x, y = jitter_grid(8.5)
        dens = self.ff(x, y)
        keep = rng.random(x.size) < dens * 0.95
        x, y = x[keep], y[keep]
        h = self.hf(x, y)
        occ = self.occ(x, y)
        din = self.din(x, y)
        ok = (occ < 0.2) & (h > 2.0) & free(x, y, 4.0)
        x, y, h, din = x[ok], y[ok], h[ok], din[ok]
        rv = np.hypot(x - vx, y - vy)
        r = rng.random(x.size)
        coastal = (din < 90) & (h < 18)
        high = (h > 95) | (rv < 380)
        sel_palm = coastal & (r < 0.75)
        sel_pine = ~sel_palm & (high | (r < 0.08))
        sel_b = ~sel_palm & ~sel_pine & (r < 0.38)
        sel_a = ~sel_palm & ~sel_pine & ~sel_b
        emit("SM_PalmTree_A", x[sel_palm & (r < 0.4)], y[sel_palm & (r < 0.4)], h[sel_palm & (r < 0.4)], 0.85, 1.2)
        emit("SM_PalmTree_B", x[sel_palm & (r >= 0.4)], y[sel_palm & (r >= 0.4)], h[sel_palm & (r >= 0.4)], 0.85, 1.25)
        emit("SM_PineTree_A", x[sel_pine], y[sel_pine], h[sel_pine], 0.75, 1.25)
        emit("SM_BroadTree_B", x[sel_b], y[sel_b], h[sel_b], 0.8, 1.2)
        emit("SM_BroadTree_A", x[sel_a], y[sel_a], h[sel_a], 0.8, 1.3)

        # ---------------- coastal palms on beaches / harbor edges
        x, y = jitter_grid(16.0)
        h = self.hf(x, y)
        din = self.din(x, y)
        sl = self.sf(x, y)
        ok = (din > 8) & (din < 75) & (h > 1.3) & (h < 12) & (sl < 18) & (self.occ(x, y) < 0.2)
        ok &= rng.random(x.size) < 0.45
        ok &= free(x, y, 4.0)
        emit("SM_PalmTree_A", x[ok], y[ok], self.hf(x[ok], y[ok]), 0.8, 1.25)

        # ---------------- meadow trees + bushes
        x, y = jitter_grid(28.0)
        h = self.hf(x, y)
        ok = (self.ff(x, y) < 0.25) & (h > 6) & (h < 120) & (self.sf(x, y) < 22) & (self.occ(x, y) < 0.1)
        ok &= (rng.random(x.size) < 0.18) & free(x, y, 5.0)
        emit("SM_BroadTree_C", x[ok], y[ok], h[ok], 0.9, 1.5)

        x, y = jitter_grid(6.5)
        h = self.hf(x, y)
        f = self.ff(x, y)
        ok = (h > 2.5) & (h < 150) & (self.sf(x, y) < 28) & (self.occ(x, y) < 0.1)
        ok &= rng.random(x.size) < (0.04 + 0.4 * f * (1 - f) * 4 * 0.5)
        ok &= free(x, y, 1.5)
        r = rng.random(ok.sum())
        xs, ys, hs = x[ok], y[ok], h[ok]
        emit("SM_Bush_A", xs[r < 0.5], ys[r < 0.5], hs[r < 0.5], 0.7, 1.4, sink=0.2)
        emit("SM_Bush_B", xs[r >= 0.5], ys[r >= 0.5], hs[r >= 0.5], 0.8, 1.5, sink=0.2)

        # ferns under forest
        x, y = jitter_grid(4.5)
        f = self.ff(x, y)
        ok = (rng.random(x.size) < f * 0.45) & (self.occ(x, y) < 0.1) & (self.hf(x, y) > 2.5)
        ok &= free(x, y, 1.0)
        emit("SM_Fern_A", x[ok], y[ok], self.hf(x[ok], y[ok]), 0.8, 1.6, sink=0.05)

        # flowers near paths/meadows
        x, y = jitter_grid(18.0)
        h = self.hf(x, y)
        ok = (self.ff(x, y) < 0.3) & (h > 4) & (h < 90) & (self.sf(x, y) < 18) & (self.occ(x, y) < 0.1)
        ok &= (rng.random(x.size) < 0.22) & free(x, y, 1.5)
        cols = ["SM_FlowerBush_Red", "SM_FlowerBush_Yellow", "SM_FlowerBush_Blue", "SM_FlowerBush_White"]
        pick = rng.integers(0, 4, ok.sum())
        xs, ys, hs = x[ok], y[ok], h[ok]
        for k, nm in enumerate(cols):
            m = pick == k
            emit(nm, xs[m], ys[m], hs[m], 0.7, 1.2, sink=0.1)

        # grass clumps on open grass
        x, y = jitter_grid(5.0)
        h = self.hf(x, y)
        ok = (h > 3.0) & (h < 140) & (self.sf(x, y) < 25) & (self.occ(x, y) < 0.05) & (self.din(x, y) > 25)
        ok &= rng.random(x.size) < 0.33
        ok &= free(x, y, 0.8)
        emit("SM_GrassClump_A", x[ok], y[ok], h[ok], 0.8, 1.6, sink=0.02)

        # ---------------- rocks
        x, y = jitter_grid(11.0)
        h = self.hf(x, y)
        sl = self.sf(x, y)
        ok = (sl > 30) & (h > -2) & (self.occ(x, y) < 0.2) & (rng.random(x.size) < 0.55)
        ok &= free(x, y, 3.0)
        r = rng.random(ok.sum())
        xs, ys, hs = x[ok], y[ok], h[ok]
        emit("SM_Rock_A", xs[r < 0.35], ys[r < 0.35], hs[r < 0.35], 0.8, 2.0, sink=0.6)
        emit("SM_Rock_C", xs[(r >= 0.35) & (r < 0.65)], ys[(r >= 0.35) & (r < 0.65)], hs[(r >= 0.35) & (r < 0.65)], 0.8, 1.8, sink=0.8)
        emit("SM_Rock_D", xs[r >= 0.65], ys[r >= 0.65], hs[r >= 0.65], 0.7, 1.6, sink=0.6)
        # cliff boulders at the waterline
        x, y = jitter_grid(24.0)
        h = self.hf(x, y)
        din = self.din(x, y)
        ok = (h > -4) & (h < 6) & (self.sf(x, y) > 22) & (rng.random(x.size) < 0.6) & (self.near(x, y) < 0.1)
        for key in ("harbor", "lighthouse"):
            px, py = C.LOCATIONS[key]["pos"]
            ok &= np.hypot(x - px, y - py) > (420.0 if key == "harbor" else 120.0)
        emit("SM_CliffRock_A", x[ok], y[ok], h[ok], 0.6, 1.4, sink=2.0)
        # volcanic rocks
        x, y = jitter_grid(14.0)
        h = self.hf(x, y)
        rv = np.hypot(x - vx, y - vy)
        ok = (rv < 520) & (rv > 105) & (h > 70) & (rng.random(x.size) < 0.3) & (self.occ(x, y) < 0.2)
        ok &= free(x, y, 3.0)
        emit("SM_VolcanicRock_A", x[ok], y[ok], h[ok], 0.6, 2.2, sink=0.5)
        # beach rocks
        x, y = jitter_grid(30.0)
        h = self.hf(x, y)
        ok = (h > -1.5) & (h < 2.5) & (rng.random(x.size) < 0.12) & free(x, y, 6.0)
        emit("SM_Rock_B", x[ok], y[ok], h[ok], 0.6, 1.5, sink=0.3)

        # driftwood + pebbles on the beaches, stumps and fallen trunks in the forest
        x, y = jitter_grid(26.0)
        h = self.hf(x, y)
        ok = (h > 0.4) & (h < 3.0) & (self.sf(x, y) < 12) & (self.occ(x, y) < 0.05) & (rng.random(x.size) < 0.18)
        ok &= free(x, y, 4.0)
        emit("SM_Driftwood_A", x[ok], y[ok], h[ok], 0.7, 1.2, sink=0.1)
        x, y = jitter_grid(17.0)
        h = self.hf(x, y)
        ok = (h > -0.5) & (h < 4.0) & (self.occ(x, y) < 0.05) & (rng.random(x.size) < 0.2) & free(x, y, 2.0)
        emit("SM_Pebbles_A", x[ok], y[ok], h[ok], 0.7, 1.5, sink=0.03)
        x, y = jitter_grid(15.0)
        f = self.ff(x, y)
        ok = (rng.random(x.size) < f * 0.12) & (self.occ(x, y) < 0.1) & (self.hf(x, y) > 3.0) & free(x, y, 2.5)
        r = rng.random(ok.sum())
        xs, ys = x[ok], y[ok]
        emit("SM_Stump_A", xs[r < 0.6], ys[r < 0.6], self.hf(xs[r < 0.6], ys[r < 0.6]), 0.7, 1.3, sink=0.1)
        emit("SM_Driftwood_A", xs[r >= 0.6], ys[r >= 0.6], self.hf(xs[r >= 0.6], ys[r >= 0.6]), 0.8, 1.3, sink=0.15)

        # ---------------- dead trees around the abandoned dorm
        ax, ay = C.LOCATIONS["abandoned"]["pos"]
        n = 26
        ang = rng.uniform(0, 2 * math.pi, n)
        rad = rng.uniform(42, 95, n)
        x, y = ax + np.cos(ang) * rad, ay + np.sin(ang) * rad
        ok = free(x, y, 3.0) & (self.occ(x, y) < 0.2)
        emit("SM_DeadTree_A", x[ok], y[ok], self.hf(x[ok], y[ok]), 0.8, 1.4)

        total = sum(counts.values())
        self.log(f"  scatter: {total} instances " + ", ".join(f"{k.replace('SM_', '')}={v}" for k, v in sorted(counts.items())))

    # ------------------------------------------------------------------ terrain + water actors
    def place_world(self):
        for cj in range(C.CHUNKS):
            for ci in range(C.CHUNKS):
                self.static.append(dict(mesh=f"SM_Terrain_{ci:02d}_{cj:02d}", folder="Terrain", loc=[0, 0, 0], yaw=0.0,
                                        collision="complex", group="terrain", label=f"Terrain_{ci:02d}_{cj:02d}"))
        for n in ("SM_Ocean", "SM_SeaFloor", "SM_LakeSurface"):
            self.static.append(dict(mesh=n, folder="Water", loc=[0, 0, 0], yaw=0.0, collision="none", group="water",
                                    label=n.replace("SM_", "")))

    # ------------------------------------------------------------------ zones
    def zones(self):
        out = []
        for key, L in C.LOCATIONS.items():
            x, y = L["pos"]
            z = self.info["pads"].get(key)
            if z is None:
                z = self.ground(x, y)
            ex, ey, ez = L["zone"]
            sx, sy, _ = L["spawn"]
            sz = self.ground(sx, sy)
            if key == "harbor":
                sz = max(sz, 3.0)
            # face the location; arriving at the harbor you look inland towards the academy
            tx, ty = (0.0, 0.0) if key == "harbor" else (x, y)
            face = math.degrees(math.atan2(ty - sy, tx - sx))
            out.append(dict(id=key, name=L["name"], subtitle=L["subtitle"], desc=L["desc"], color=list(L["color"]),
                            center=ue_loc((x, y, z)), extent=[ex * 100.0, ey * 100.0, ez * 100.0],
                            spawn=dict(loc=ue_loc((sx, sy, sz + 1.2)), yaw=ue_yaw(face))))
        return out

    # ------------------------------------------------------------------ minimap
    def minimap(self, size=2048):
        from PIL import Image, ImageDraw
        from .terrain import Terrain
        # recompute the base map from cached height + colour map
        h = self.hf.a
        col = np.asarray(Image.open(os.path.join(C.OUT_TEXTURES, "T_TerrainColor.png")).convert("RGB")).astype(np.float32) / 255.0
        from scipy import ndimage
        hz = ndimage.zoom(h, size / h.shape[0], order=1)[:size, :size]
        cz = ndimage.zoom(col, (size / col.shape[0], size / col.shape[1], 1), order=1)[:size, :size]
        sp = C.WORLD_SIZE / size
        gy, gx = np.gradient(hz, sp)
        nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
        shade = np.clip((-gx * nz * -0.6 + gy * nz * 0.6 + nz * 0.55) / 1.0, 0, 1)
        img = cz * (0.55 + 0.55 * shade[..., None])
        sea = hz < 0.0
        depth = np.clip(-hz / 45.0, 0, 1)
        sea_col = np.stack([0.35 - 0.3 * depth, 0.72 - 0.47 * depth, 0.85 - 0.35 * depth], -1)
        img = np.where(sea[..., None], sea_col, img)
        X, Y = np.meshgrid(-C.HALF + np.arange(size) * sp, C.HALF - np.arange(size) * sp)
        a = math.radians(C.LAKE_ROT)
        dx, dy = X - C.LAKE_CENTER[0], Y - C.LAKE_CENTER[1]
        q = np.sqrt(((dx * math.cos(a) + dy * math.sin(a)) / C.LAKE_RADII[0]) ** 2 +
                    ((-dx * math.sin(a) + dy * math.cos(a)) / C.LAKE_RADII[1]) ** 2)
        lake = (hz < C.LAKE_LEVEL) & (q < 1.1)
        img = np.where(lake[..., None], np.array([0.25, 0.6, 0.72]), img)
        coast = ndimage.binary_dilation(sea, iterations=2) & ~sea
        img = np.where(coast[..., None], img * 0.6 + 0.4, img)
        pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB")
        d = ImageDraw.Draw(pil)

        def px(p):
            return ((p[0] + C.HALF) / C.WORLD_SIZE * size, (C.HALF - p[1]) / C.WORLD_SIZE * size)

        for key, poly in self.footprints:
            colr = tuple(int(c * 255) for c in C.LOCATIONS.get(key, {}).get("color", (0.8, 0.8, 0.8)))
            fill = tuple(int(0.55 * c + 0.45 * 235) for c in colr)
            d.polygon([px(p) for p in poly], fill=fill, outline=(60, 60, 70))
        pil.save(os.path.join(C.OUT_TEXTURES, "T_IslandMap.png"), optimize=True)
        self.log("  minimap: T_IslandMap.png")

    # ------------------------------------------------------------------ write
    def write(self):
        os.makedirs(C.OUT_DATA, exist_ok=True)
        from .anime import cast as anime_cast
        anime_cast.assign_npcs(self.npcs)          # who stands where (named cast + generic looks)
        hx = C.HALF
        cull = {
            "SM_GrassClump_A": [3000, 6000], "SM_Fern_A": [4000, 8000], "SM_Bush_A": [12000, 20000],
            "SM_Bush_B": [12000, 20000], "SM_FlowerBush_Red": [8000, 14000], "SM_FlowerBush_Yellow": [8000, 14000],
            "SM_FlowerBush_Blue": [8000, 14000], "SM_FlowerBush_White": [8000, 14000],
            "SM_Pebbles_A": [4000, 7000], "SM_Stump_A": [9000, 15000],
        }
        nocol = {"SM_GrassClump_A", "SM_Fern_A", "SM_FlowerBush_Red", "SM_FlowerBush_Yellow", "SM_FlowerBush_Blue",
                 "SM_FlowerBush_White", "SM_Bush_A", "SM_Bush_B", "SM_Pebbles_A"}
        inst = {}
        for k, v in sorted(self.instances.items()):
            inst[k] = dict(folder="Props", collision=k not in nocol, cull=cull.get(k, [0, 0]),
                           shadow=k not in ("SM_GrassClump_A", "SM_Fern_A"), items=v)
        start = [z for z in self.zones() if z["id"] == "harbor"][0]["spawn"]
        layout = dict(
            version=1, units="cm", generator="Tools/build_island.py",
            axis_check=dict(mesh="SM_Terrain_00_00", expected_center_y=round((C.HALF - C.WORLD_SIZE / C.CHUNKS / 2) * 100 * Y_SIGN, 1)),
            world=dict(size=C.WORLD_SIZE * 100, sea_level=0.0, lake_level=C.LAKE_LEVEL * 100,
                       lake=dict(center=ue_loc((*C.LAKE_CENTER, C.LAKE_LEVEL)), radii=[C.LAKE_RADII[0] * 100, C.LAKE_RADII[1] * 100],
                                 rot=ue_yaw(C.LAKE_ROT)),
                       volcano=dict(center=ue_loc((*C.VOLCANO_CENTER, self.info["volcano"]["lava"])),
                                    rim=self.info["volcano"]["rim"] * 100, lava=self.info["volcano"]["lava"] * 100),
                       map=dict(texture="T_IslandMap", min=[-hx * 100, -hx * 100], max=[hx * 100, hx * 100]),
                       terrain_chunks=C.CHUNKS),
            environment=dict(start_hour=16.25, day_minutes=24.0),
            player_start=start,
            static=self.static, floating=self.floating, instances=inst, lights=self.lights, texts=self.texts,
            interacts=self.interacts, emitters=self.emitters, audio=self.audio, npcs=self.npcs,
            specials=self.specials, zones=self.zones(),
        )
        with open(os.path.join(C.OUT_DATA, "layout.json"), "w") as fp:
            json.dump(layout, fp, separators=(",", ":"))
        with open(os.path.join(C.OUT_DATA, "materials.json"), "w") as fp:
            json.dump(palette.material_json(), fp, indent=1)
        with open(os.path.join(C.OUT_DATA, "assets.json"), "w") as fp:
            json.dump(self.manifest, fp, indent=1)
        n_inst = sum(len(v["items"]) for v in inst.values())
        self.log(f"  layout.json: {len(self.static)} static, {len(self.floating)} floating, {n_inst} instances, "
                 f"{len(self.lights)} lights, {len(self.texts)} texts, {len(self.interacts)} interactables, "
                 f"{len(self.emitters)} emitters, {len(self.audio)} sounds, {len(self.npcs)} npcs, "
                 f"{len(self.specials)} specials")


# --------------------------------------------------------------------------- shared asset exports
def export_props(manifest, log=print):
    out = os.path.join(C.OUT_MESHES, "Props")
    P.export_all(out, log)
    nanite = {n for n in P.REGISTRY if any(t in n for t in ("Tree", "Palm", "Bush", "Rock", "Fern", "Grass", "Driftwood", "Stump", "Pebbles"))}
    for n in P.REGISTRY:
        manifest.append(dict(file=f"Meshes/Props/{n}.fbx", name=n, folder="Props", collision="simple",
                             nanite=n in nanite, category="prop"))


def export_avatar(manifest, log=print):
    from . import blend
    out = os.path.join(C.OUT_MESHES, "Characters")
    os.makedirs(out, exist_ok=True)
    for name, fn in AV.PARTS.items():
        o = fn().build("SM_" + name)
        blend.export_fbx([o], os.path.join(out, f"SM_{name}.fbx"))
        blend.delete([o])
        manifest.append(dict(file=f"Meshes/Characters/SM_{name}.fbx", name=f"SM_{name}", folder="Characters",
                             collision="none", nanite=False, category="character"))
    log(f"  avatar: {len(AV.PARTS)} parts")


def terrain_manifest(manifest):
    for cj in range(C.CHUNKS):
        for ci in range(C.CHUNKS):
            n = f"SM_Terrain_{ci:02d}_{cj:02d}"
            manifest.append(dict(file=f"Meshes/Terrain/{n}.fbx", name=n, folder="Terrain", collision="complex",
                                 nanite=False, category="terrain"))
    for n, col in (("SM_Ocean", "none"), ("SM_SeaFloor", "none"), ("SM_LakeSurface", "none")):
        manifest.append(dict(file=f"Meshes/Water/{n}.fbx", name=n, folder="Water", collision=col, nanite=False,
                             category="water"))
