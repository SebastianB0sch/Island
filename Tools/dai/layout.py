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

from . import atomic
from . import config as C
from . import jsonio, palette, terrain, waterways
from .assets import load_placements
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


def emitter_ring(pr, yaw):
    """Extra layout.json fields of a ring emitter (AssetSet.emitter ring / points): ring radius in cm and,
    for a ring of spots, their count, the first spot's angle and the frame yaw (both UE degrees) - the
    spots are placed in the emitter actor's local frame. Empty for ordinary emitters."""
    if float(pr.get("ring", 0.0)) <= 0.0:
        return {}
    out = dict(ring=round(float(pr["ring"]) * 100.0, 1))
    if int(pr.get("points", 0)) > 0:
        out.update(points=int(pr["points"]), angle0=ue_yaw(pr.get("angle0", 0.0)), yaw=ue_yaw(yaw))
    return out


def emitter_jet(pr, yaw, z0):
    """Extra layout.json fields of a jet emitter (AssetSet.jet): initial velocity in cm/s (UE axes, the set's
    yaw applied), the world height of the water it falls into and the spread of the stream. Empty otherwise."""
    if "vel" not in pr:
        return {}
    vx, vy = rot2(float(pr["vel"][0]), float(pr["vel"][1]), yaw)
    return dict(vel=[round(vx * 100.0, 1), round(vy * 100.0 * Y_SIGN, 1), round(float(pr["vel"][2]) * 100.0, 1)],
                floor=round((z0 + float(pr.get("floor", 0.0))) * 100.0, 1), spread=float(pr.get("spread", 2.5)))


NANITE_MIN_TRIS = 40000
# Nanite can't draw these (translucent / special shading)
NANITE_BLOCKERS = {"glass", "water", "pool", "river", "smoke", "beam", "hologram", "waterfall", "flow", "lava"}


def split_translucent(meshes, skip=()):
    """Dense meshes that also carry a few translucent faces (window glass, vitrines, water) are split: the
    translucent faces go to <name>_Glass (<name>_Glass_NoCol for no-collision meshes; same collision rule as
    the source, so glass still blocks the way), so the opaque bulk can use Nanite. `skip`: names to keep whole
    (floating meshes - both halves must move together)."""
    from .geo import MeshBuilder
    out = {}
    for name, mb in meshes.items():
        tris = sum(len(f) - 2 for f in mb.faces)
        kinds = [palette.MATERIALS.get(m, {}).get("kind", "opaque") in NANITE_BLOCKERS for m in mb.face_mats]
        if name in skip or tris < NANITE_MIN_TRIS or not any(kinds) or all(kinds):
            out[name] = mb
            continue
        opaque, trans = MeshBuilder(name), MeshBuilder(name + "_Glass")
        for f, m, sm, k in zip(mb.faces, mb.face_mats, mb.face_smooth, kinds):
            dst = trans if k else opaque
            base = len(dst.verts)
            dst.verts.extend(mb.verts[i].copy() for i in f)
            dst.faces.append(tuple(range(base, base + len(f))))
            dst.face_mats.append(m)
            dst.face_smooth.append(sm)
        out[name] = opaque
        out[name[:-len("_NoCol")] + "_Glass_NoCol" if name.endswith("_NoCol") else name + "_Glass"] = trans
    return out


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
        self.doors = []
        self.door_leaves = {}    # mesh name -> (style, leaf width, height)
        self.clearings = []      # (x, y, r) world metres
        self.spaces = []         # placement.Space per location (walls, fixtures, furniture, its props) in the world
        self.road_mbs = []       # road ribbons (world space) for the standing-room checks
        self.inst_raw = []       # (asset, x, y, z, yaw, scale) of every instance not placed by a location
        self.travel = []         # fast-travel points inside locations (zones with a parent)
        self.arrivals = {}       # location key -> (world feet position, yaw) declared by the location itself
        self.assets = {}         # location key -> AssetSet as placed (for world-space audits)
        self.location_xforms = {}  # location key -> Xform used to place it
        self._in_location = False
        self._zones = None
        self.footprints = []     # (key, [(x,y)...]) for the minimap
        self.manifest = []
        self.rng = random.Random(C.SEED)
        self.inst_all = []       # (asset, (x, y, z), yaw, scale, location key or None) of every instance
        self.ribbons = {}        # path id -> [(s, left xyz, right xyz)] per run (alignment audit)
        self.bridge_info = []    # one record per placed bridge (alignment audit)
        # geometry signatures of the meshes as they were last exported (Data/assets.json "sig")
        self._prev_sig = {}
        try:
            for e in jsonio.read_json(os.path.join(C.OUT_DATA, "assets.json")):
                if e.get("sig"):
                    self._prev_sig[e["name"]] = e["sig"]
        except (OSError, ValueError):
            pass
        self.exported = []       # mesh names this run wrote

    # ------------------------------------------------------------------ helpers
    def ground(self, x, y):
        return float(self.hf(x, y))

    def add_instance(self, asset, x, y, z, yaw, scale):
        self.inst_all.append((asset, (x, y, z), yaw, scale, self._in_location or None))
        if not self._in_location:
            self.inst_raw.append((asset, (x, y, z), yaw, scale))
        g = self.instances.setdefault(asset, [])
        g.append([round(x * 100, 1), round(y * 100 * Y_SIGN, 1), round(z * 100, 1), ue_yaw(yaw), round(scale, 3)])

    def add_light(self, p, props, yaw=0.0):
        d = dict(loc=ue_loc(p), color=props.get("color", [1, 0.85, 0.6]), intensity=props.get("intensity", 5000.0),
                 radius=props.get("radius", 12.0) * 100.0, night_only=bool(props.get("night_only", False)),
                 shadows=bool(props.get("shadows", False)))
        if props.get("spot_pitch") is not None:
            d["spot"] = dict(yaw=ue_yaw(yaw), pitch=-float(props["spot_pitch"]), cone=float(props.get("cone") or 40.0))
        self.lights.append(d)

    @staticmethod
    def mesh_signature(mb):
        """Fingerprint of a mesh's geometry (vertices to the millimetre, faces, materials)."""
        import hashlib
        h = hashlib.sha1()
        h.update(np.round(np.asarray([tuple(v) for v in mb.verts], np.float64).reshape(-1, 3) * 1000.0)
                 .astype(np.int64).tobytes())
        h.update(repr([tuple(f) for f in mb.faces]).encode())
        h.update("|".join(mb.face_mats).encode())
        return h.hexdigest()[:16]

    def export_mesh(self, mb, name, folder, collision, nanite=None):
        """Write SM_<name>.fbx and list it in the manifest with its geometry signature.

        With DAI_EXPORT_ONLY set, a mesh the filter does not name is still written when its geometry differs
        from the signature recorded at its last export - a location that samples the terrain (a stair up a
        slope, a house on its plinth) must never be left behind as a stale FBX on moved ground. A file with
        no recorded signature is taken as current the first time."""
        from . import blend
        rel = os.path.join("Meshes", folder, f"SM_{name}.fbx")
        path = os.path.join(C.OUT_DIR, rel)
        sig = self.mesh_signature(mb)
        prev = self._prev_sig.get(f"SM_{name}")
        changed = prev is not None and prev != sig
        if blend.export_wanted(path) or changed:
            obj = mb.build("SM_" + name)
            try:
                blend.export_fbx([obj], path, force=True)
            finally:
                blend.delete([obj])
            self.exported.append(f"SM_{name}")
        self.manifest.append(dict(file=rel.replace(os.sep, "/"), name=f"SM_{name}", folder=folder.replace(os.sep, "/"),
                                  collision=collision, nanite=self.nanite_ok(mb) if nanite is None else nanite,
                                  category="location", sig=sig))

    def split_translucent(self, meshes, skip=()):
        return split_translucent(meshes, skip)

    NANITE_MIN_TRIS = NANITE_MIN_TRIS          # module constants (shared with split_translucent / render.py)
    NANITE_BLOCKERS = NANITE_BLOCKERS

    def nanite_ok(self, mb):
        """Dense, opaque location meshes (furnished interiors run to several 100k triangles) go on Nanite:
        Unreal then streams and culls them per cluster, so the detail costs little. Meshes with translucent
        materials (window glass, water ...) stay classic meshes."""
        tris = sum(len(f) - 2 for f in mb.faces)
        if tris < self.NANITE_MIN_TRIS:
            return False
        kinds = {palette.MATERIALS.get(m, {}).get("kind", "opaque") for m in set(mb.face_mats)}
        return not (kinds & self.NANITE_BLOCKERS)

    # ------------------------------------------------------------------ locations
    def place_locations(self, export=True):
        placements = load_placements(self.log)
        for key, fn in placements.items():
            if key not in C.LOCATIONS:
                continue
            aset = fn()
            self.assets[key] = aset
            loc = C.LOCATIONS[key]
            from . import placement
            ck = placement.asset_checker(aset, log=self.log)
            moved, failed = placement.settle_npcs(aset, ck, log=self.log)
            placement.face_open_view(aset, ck, log=self.log)
            if moved:
                self.log(f"  {key:14s} {len(moved)} NPCs stepped clear of furniture / walls / doorways "
                         f"(furthest {max(m[1] for m in moved):.1f} m)")
            for (sk, why) in failed:
                self.log(f"   !! {key}: NPC at {tuple(round(c, 2) for c in sk['pos'])} has no room: {why}")
            absolute = getattr(aset, "absolute", False)
            x0, y0 = loc["pos"]
            if absolute:
                xf = Xform(x0, y0, 0.0, 0.0)
            else:
                z0 = self.info["pads"].get(key)
                if z0 is None:
                    z0 = 4.0 if key == "lighthouse" else self.ground(x0, y0)
                xf = Xform(x0, y0, z0, loc["yaw"])
            self.location_xforms[key] = xf
            n_mesh = 0
            # meshes an actor of their own moves (boats bob, water wheels turn): exported, not placed as statics
            floating_meshes = {s["props"].get("mesh") for s in aset.sockets if s["type"] in ("floating", "spinner")}
            for name, mb in self.split_translucent(aset.meshes, skip=floating_meshes).items():
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
            # furniture modelled into the no-collision meshes gets invisible collision boxes (dai/collision.py)
            from . import collision as COL
            boxes = [b for bs in COL.asset_blockers(aset).values() for b in bs]
            if boxes:
                from .geo import MeshBuilder
                bm = MeshBuilder(f"{self._loc_prefix(aset)}_Blockers")
                verts, polys, _ = COL.box_soup(boxes)
                bm.verts.extend(verts)
                bm.faces.extend(tuple(f) for f in polys)
                bm.face_mats.extend(["M_Concrete"] * len(polys))
                bm.face_smooth.extend([False] * len(polys))
                if export:
                    self.export_mesh(bm, bm.name, os.path.join("Locations", key), "complex", nanite=False)
                self.static.append(dict(mesh=f"SM_{bm.name}", folder=f"Locations/{key}", loc=ue_loc((xf.x, xf.y, xf.z)),
                                        yaw=ue_yaw(xf.yaw), collision="complex", hidden=True, group=key,
                                        label=f"{key}_{bm.name}"))
                self.log(f"  {key:14s} {len(boxes)} furniture collision boxes ({bm.name})")
            for sp in ck.spaces:
                self.spaces.append(placement.placed(sp, xf.x, xf.y, xf.z, xf.yaw))
            self._in_location = key
            self.place_sockets(aset, xf, key)
            self._in_location = False
            self.log(f"  {key:14s} {n_mesh} meshes, {len(aset.sockets)} sockets")
        if export:
            self.export_door_leaves()

    @staticmethod
    def _loc_prefix(aset):
        """Mesh name prefix of a location (Academy, ObeliskGirls, ...) from its first mesh."""
        names = [n for n in aset.meshes if aset.meshes[n].verts]
        return names[0].split("_")[0] if names else aset.name.title().replace("_", "")

    def export_door_leaves(self):
        from .assets import doors as DR
        for name, (style, lw, h) in sorted(self.door_leaves.items()):
            mb = DR.build_leaf(style, lw, h)
            self.export_mesh(mb, name[3:], "Doors", "complex")
        self.log(f"  doors: {len(self.doors)} doorways, {len(self.door_leaves)} leaf meshes")

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
                                          rate=float(pr.get("rate", 1.0)), **emitter_ring(pr, s["yaw"])))

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
                    sc = pr.get("scale", 1.0)
                    ox, oy = rot2(L["offset"][0] * sc, L["offset"][1] * sc, yaw)
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
                self.emitters.append(dict(kind=pr["kind"], loc=ue_loc(p), scale=pr.get("scale", 1.0), rate=pr.get("rate", 1.0),
                                          **emitter_ring(pr, yaw), **emitter_jet(pr, xf.yaw, xf.z)))
            elif t == "audio":
                self.audio.append(dict(sound=pr["sound"], loc=ue_loc(p), radius=pr.get("radius", 40.0) * 100.0,
                                       volume=pr.get("volume", 1.0)))
            elif t == "spinner":           # a mesh of this location turning at constant speed (ADASpinner)
                self.specials.append(dict(kind="spinner", loc=ue_loc(p), yaw=ue_yaw(yaw), group=key,
                                          props=dict(mesh=f"SM_{pr['mesh']}", folder=f"Locations/{key}",
                                                     axis=pr.get("axis", "y"), rpm=float(pr.get("rpm", 6.0)))))
                self.clearings.append((p[0], p[1], float(pr.get("clear", 4.0))))
            elif t == "npc":
                self.npcs.append(dict(loc=ue_loc((p[0], p[1], p[2] + 0.95)), yaw=ue_yaw(yaw), dorm=pr.get("dorm", "slifer"),
                                      wander=pr.get("wander", 8.0) * 100.0, group=key, _feet=p))
            elif t == "arrival":           # the location's own fast-travel arrival point (overrides config spawn)
                self.arrivals[key] = (p, yaw)
                self.clearings.append((p[0], p[1], 4.0))
            elif t == "travel":
                if pr.get("box"):
                    x0, y0, z0, x1, y1, z1 = pr["box"]
                    center = xf.point(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
                    half = (abs(x1 - x0) / 2, abs(y1 - y0) / 2, abs(z1 - z0) / 2)
                else:
                    center = half = None     # measured round the spot (room_box)
                self.travel.append(dict(id=pr["id"], parent=key, name=pr["name"], subtitle=pr.get("subtitle", ""),
                                        desc=pr.get("desc", ""), spot=p, yaw=yaw, center=center, half=half,
                                        box_yaw=xf.yaw))
                self.clearings.append((p[0], p[1], 3.0))
            elif t == "clearing":
                self.clearings.append((p[0], p[1], pr.get("radius", 5.0)))
            elif t == "floating":
                self.floating.append(dict(mesh=f"SM_{pr['mesh']}", folder=f"Locations/{key}", loc=ue_loc(p), yaw=ue_yaw(yaw),
                                          scale=1.0, amplitude=pr.get("amplitude", 0.15) * 100.0, period=pr.get("period", 6.0),
                                          sway=pr.get("sway", 0.4)))
                # keep scatter (trees, rocks) out of the hull: the ferry is not part of the occupied pad mask
                self.clearings.append((p[0], p[1], float(pr.get("clear", 12.0))))
            elif t == "camera":
                continue
            elif t == "door":
                from .assets import doors as DR
                lw = DR.leaf_width(pr["width"], pr["double"])
                mesh = DR.leaf_name(pr["style"], lw, pr["height"])
                self.door_leaves[mesh] = (pr["style"], lw, pr["height"])
                # UE frame: local +Y is outside (Blender -Y); SwingSide +1 = towards outside
                self.doors.append(dict(mesh=mesh, loc=ue_loc(p), yaw=ue_yaw(yaw), width=round(pr["width"] * 100.0, 1),
                                       height=round(pr["height"] * 100.0, 1), double=pr["double"], mode=pr["mode"],
                                       swing={"auto": 0, "out": 1, "in": -1}[pr["swing"]], group=key))
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
                    if self.in_any_pad(px, py, 4.0) is None and self.ground(px, py) > 1.0 \
                            and waterways.clearance(px, py) > 2.5 and not self.on_bridge(p["id"], s, 2.0):
                        z = self.ground(px, py)
                        yaw = math.degrees(math.atan2(-ny * side, -nx * side)) + 90.0
                        self.add_instance("SM_LampPost", px, py, z - 0.05, yaw, 1.0)
                        self.add_light((px, py, z + P.PROP_LIGHTS["SM_LampPost"]["offset"][2]),
                                       P.PROP_LIGHTS["SM_LampPost"])
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
            if p["surface"] == "paved" and p["id"] != "breakwater":
                mb = self.road_ribbon(p)
                self.road_mbs.append(mb)
                if export:
                    self.export_mesh(mb, f"Road_{p['id']}", "Roads", "complex")
                self.static.append(dict(mesh=f"SM_Road_{p['id']}", folder="Roads", loc=[0, 0, 0], yaw=0.0,
                                        collision="complex", group="roads", label=f"Road_{p['id']}"))
        self.log(f"  path dressing: {lamps} lamps")

    # ------------------------------------------------------------------ road ribbons
    RIBBON_LIFT = 0.06       # m the paving lies above the terrain triangles under it
    RIBBON_SKIRT = 0.8       # m the kerb faces reach down into the ground

    def road_runs(self, p):
        """The stretches of a paved road that get a ribbon: (arc, [(s_start, s_end, start_edges, end_edges)]).
        A ribbon stops exactly at a bridge's abutments (the deck carries the road there) and at the edge of
        the carriageway of a road laid before it (a junction: the main road's ribbon is the surface there).
        *_edges = (s_left, s_right) when that end is cut along the other road's edge - each side of the ribbon
        then ends where it meets that edge, so an oblique junction closes without a wedge - else None."""
        samples = p["samples"]
        hw = p["width"] / 2.0
        xs, ys = [t[0] for t in samples], [t[1] for t in samples]
        arc = np.concatenate([[0.0], np.cumsum([math.hypot(samples[i][0] - samples[i - 1][0],
                                                           samples[i][1] - samples[i - 1][1])
                                                for i in range(1, len(samples))])])
        total = float(arc[-1])

        def point(s_, side):
            x, y = float(np.interp(s_, arc, xs)), float(np.interp(s_, arc, ys))
            i = int(min(max(np.searchsorted(arc, s_), 1), len(samples) - 1))
            j0, j1 = max(i - 2, 0), min(i + 1, len(samples) - 1)
            tx, ty = xs[j1] - xs[j0], ys[j1] - ys[j0]
            d = math.hypot(tx, ty) or 1.0
            return x - ty / d * hw * side, y + tx / d * hw * side

        cuts = [(b["s0"], b["s1"], None, None) for b in self.meta.get("bridges", []) if b["path"] == p["id"]]
        order = [q["id"] for q in self.meta["paths"]]
        for q in self.meta["paths"]:
            if q["surface"] != "paved" or q["id"] == "breakwater" or order.index(q["id"]) >= order.index(p["id"]):
                continue
            line = np.asarray(q["samples"], np.float64)[:, :2]
            seg_a, seg_d = line[:-1], line[1:] - line[:-1]
            seg_l2 = np.maximum((seg_d * seg_d).sum(1), 1e-12)
            hwq = q["width"] / 2.0

            def inside(s_, side):
                x, y = point(s_, side)
                t = np.clip(((x - seg_a[:, 0]) * seg_d[:, 0] + (y - seg_a[:, 1]) * seg_d[:, 1]) / seg_l2, 0.0, 1.0)
                return float(np.hypot(seg_a[:, 0] + t * seg_d[:, 0] - x, seg_a[:, 1] + t * seg_d[:, 1] - y).min()) < hwq

            for end, step in ((0.0, 1.0), (total, -1.0)):
                if not inside(end, 0.0):
                    continue
                exits = []
                for side in (1.0, -1.0):         # left edge, right edge
                    s_out = end
                    while inside(s_out, side) and abs(s_out - end) < min(80.0, total):
                        s_out += step * 0.5
                    lo, hi = s_out - step * 0.5, s_out
                    for _ in range(28):
                        mid = 0.5 * (lo + hi)
                        lo, hi = (mid, hi) if inside(mid, side) else (lo, mid)
                    exits.append(min(max(hi, 0.0), total))
                if step > 0:
                    cuts.append((0.0, max(exits), None, tuple(exits)))        # the next run starts on these
                else:
                    cuts.append((min(exits), total, tuple(exits), None))      # the previous run ends on these
        runs, s, start_edges = [], 0.0, None
        for c0, c1, end_edges, next_edges in sorted(cuts, key=lambda c: (c[0], c[1])):
            if c0 - s > 0.5:
                runs.append((s, c0, start_edges, end_edges))
            if c1 >= s:
                s, start_edges = c1, next_edges
        if total - s > 0.5:
            runs.append((s, total, start_edges, None))
        return arc, runs

    RIBBON_COLUMNS = 5       # vertices across a ribbon: it is draped on the ground, not laid flat over it

    def ribbon_sections(self, p):
        """Cross-sections of a road's ribbon, per run: [[(s, [xyz across, left -> right]), ...], ...].

        The paving is draped: every vertex stands RIBBON_LIFT above the highest terrain within 30 cm
        of it, so the ribbon follows the cross-fall of a junction or a pad's apron instead of bridging it
        (a level cross-section floated up to half a metre there). Sections every 2 m plus one exactly at
        each end of a run; a skewed end has each edge where it meets the other road's edge."""
        samples = p["samples"]
        hw = p["width"] / 2.0
        arc, runs = self.road_runs(p)
        xs, ys = [t[0] for t in samples], [t[1] for t in samples]
        cols = self.RIBBON_COLUMNS

        def frame(s_):
            x, y = float(np.interp(s_, arc, xs)), float(np.interp(s_, arc, ys))
            i = int(min(max(np.searchsorted(arc, s_), 1), len(samples) - 1))
            j0, j1 = max(i - 2, 0), min(i + 1, len(samples) - 1)      # tangent over a few samples (smooth edges)
            tx, ty = xs[j1] - xs[j0], ys[j1] - ys[j0]
            d = math.hypot(tx, ty) or 1.0
            return x, y, -ty / d, tx / d

        def top(x, y):
            return max(self.ground(x + dx, y + dy) for dx, dy in
                       ((0.0, 0.0), (0.3, 0.0), (-0.3, 0.0), (0.0, 0.3), (0.0, -0.3))) + self.RIBBON_LIFT

        def section(s_, edges=None):
            if edges is None:
                x, y, nx, ny = frame(s_)
                left, right = (x + nx * hw, y + ny * hw), (x - nx * hw, y - ny * hw)
            else:
                xl, yl, nxl, nyl = frame(edges[0])
                xr, yr, nxr, nyr = frame(edges[1])
                left, right = (xl + nxl * hw, yl + nyl * hw), (xr - nxr * hw, yr - nyr * hw)
            row = []
            for c in range(cols):
                f = c / (cols - 1)
                x, y = left[0] + (right[0] - left[0]) * f, left[1] + (right[1] - left[1]) * f
                row.append((x, y, top(x, y)))
            return row

        out = []
        for s0, s1, e0, e1 in runs:
            n = max(1, int(math.ceil((s1 - s0) / 2.0)))
            run = [(s0 + (s1 - s0) * k / n, section(s0 + (s1 - s0) * k / n)) for k in range(n + 1)]
            if e0 is not None:
                run[0] = (s0, section(s0, e0))
            if e1 is not None:
                run[-1] = (s1, section(s1, e1))
            out.append(run)
        return out

    def road_ribbon(self, p):
        """Paving of one road: the draped strip of ribbon_sections with kerb faces down into the ground along
        both edges and across every end."""
        from .geo import MeshBuilder
        mb = MeshBuilder(f"Road_{p['id']}")
        sk = self.RIBBON_SKIRT

        def down(q):
            return (q[0], q[1], q[2] - sk)

        sections = self.ribbon_sections(p)
        self.ribbons[p["id"]] = sections
        for run in sections:
            rows = [row for _s, row in run]
            for r0, r1 in zip(rows, rows[1:]):
                for c in range(len(r0) - 1):
                    # left -> right across, so (right0, right1, left1, left0) faces up
                    mb.quad(r0[c + 1], r1[c + 1], r1[c], r0[c], "M_Paving", smooth=True)
                mb.quad(down(r1[0]), down(r0[0]), r0[0], r1[0], "M_Concrete")              # left kerb
                mb.quad(down(r0[-1]), down(r1[-1]), r1[-1], r0[-1], "M_Concrete")          # right kerb
            for row, flip in ((rows[0], False), (rows[-1], True)):                         # end faces
                for c in range(len(row) - 1):
                    a_, b_ = row[c], row[c + 1]
                    if flip:
                        mb.quad(down(b_), down(a_), a_, b_, "M_Concrete")
                    else:
                        mb.quad(down(a_), down(b_), b_, a_, "M_Concrete")
        return mb

    # ------------------------------------------------------------------ bridges
    def place_bridges(self, export=True):
        """One bridge per path / river crossing found by the terrain stage (terrain_info.json "bridges"):
        stone arches under the paved roads (and the forest path at Millbrook), timber trestles on the trails.
        World-space meshes in Meshes/Roads; the deck runs straight from bank to bank on the road's grade."""
        try:
            from .assets import bridges as BR
        except ModuleNotFoundError:
            self.log("  (assets/bridges.py not present: no bridges)")
            return
        from .geo import MeshBuilder
        names = {}
        for b in self.meta.get("bridges", []):
            (ax, ay, az), (bx, by, bz) = b["a"], b["b"]
            run = math.hypot(bx - ax, by - ay)
            length = math.hypot(run, bz - az)
            yaw = math.degrees(math.atan2(by - ay, bx - ax))
            pitch = -math.degrees(math.atan2(bz - az, run))        # MeshBuilder.at: +rot_y tips +X down
            stone = b["kind"] == "stone"
            # flush with the road ribbon (which lies RIBBON_LIFT above the ground) / with the trodden path
            lift = self.RIBBON_LIFT if b["surface"] == "paved" else 0.03
            mid = ((ax + bx) / 2, (ay + by) / 2, (az + bz) / 2 + lift)
            drop = mid[2] - b["bed"]
            width = b["width"] if stone else max(2.6, b["width"] - 1.2)
            base = "Bridge_" + "".join(part.capitalize() for part in b["path"].split("_"))
            names[base] = names.get(base, 0) + 1
            name = base if names[base] == 1 else f"{base}{names[base]}"
            mb, nc = MeshBuilder(name), MeshBuilder(name + "_NoCol")
            with mb.at(mid, rot=yaw, rot_y=pitch), nc.at(mid, rot=yaw, rot_y=pitch):
                info = (BR.stone_arch if stone else BR.wood_trestle)(mb, length, width, drop, b["half_water"],
                                                                     nocol=nc)
            for m, collision in ((mb, "complex"), (nc, "none")):
                if not m.verts:
                    continue
                if export:
                    self.export_mesh(m, m.name, "Roads", collision, nanite=False)
                self.static.append(dict(mesh=f"SM_{m.name}", folder="Roads", loc=[0, 0, 0], yaw=0.0,
                                        collision=collision, group="bridges", label=m.name))
            self.road_mbs.append(mb)
            self.bridge_info.append(dict(name=name, rec=b, mb=mb, nc=nc, mid=mid, yaw=yaw, pitch=pitch,
                                         length=length, width=width, lift=lift, drop=drop))
            cy_, sy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            cp, sp_ = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

            def world(q):
                x, y, z = q
                x, z = x * cp + z * sp_, -x * sp_ + z * cp          # pitch about Y, then yaw about Z
                return (mid[0] + x * cy_ - y * sy_, mid[1] + x * sy_ + y * cy_, mid[2] + z)

            for q in (info or {}).get("lamps", []):
                self.add_light(world(q), dict(color=[1.0, 0.72, 0.42], intensity=900.0, radius=9.0, night_only=True))
            k = max(2, int(length / 4.0))
            for i in range(k + 1):
                q = world((-length / 2 + length * i / k, 0.0, 0.0))
                self.clearings.append((q[0], q[1], width / 2 + 2.5))
            self.log(f"  bridge {name:26s} {b['kind']:5s} {length:5.1f} m long, {width:.1f} m wide, deck "
                     f"{mid[2] - b['water']:.1f} m over the water")

    # ------------------------------------------------------------------ life: waterside, roadside, sea, sky
    def place_life(self, export=True):
        """The dressing that makes the island lived-in rather than built: reeds, boulders and mist along the
        rivers, lily pads on the pond, benches, planters and lanterns along the roads, guard fences on the
        embankments, picnic spots on the banks, buoys and fishing boats at sea, birds in the air, fireflies."""
        rng = random.Random(C.SEED + 7)
        counts = {}

        def put(asset, x, y, z, yaw, scale):
            self.add_instance(asset, x, y, z, yaw, scale)
            counts[asset] = counts.get(asset, 0) + 1

        def floater(asset, x, y, z=0.0, yaw=0.0, scale=1.0, amplitude=8.0):
            self.floating.append(dict(mesh=asset, folder="Props", loc=ue_loc((x, y, z)), yaw=ue_yaw(yaw), scale=scale,
                                      amplitude=amplitude, period=4.0 + rng.random() * 2, sway=2.0))
            counts[asset] = counts.get(asset, 0) + 1
            if asset in P.PROP_LIGHTS:
                L = P.PROP_LIGHTS[asset]
                self.add_light((x, y, z + L["offset"][2] * scale), L)

        def birds(x, y, z, radius, height, count, kind):
            self.specials.append(dict(kind="birds", loc=ue_loc((x, y, z)), yaw=0.0, group="life",
                                      props=dict(radius=radius * 100.0, height=height * 100.0, count=count, kind=kind)))

        def open_ground(x, y, r=1.5, slope=14.0, verge=False):
            """Free, fairly level, dry ground outside the pads; verge = beside a road (the road's own
            occupancy mask reaches a metre or two past its edge, so it is not consulted there)."""
            return ((verge or self.occ(x, y) < 0.15) and self.slope_at(x, y, 1.5) < slope
                    and waterways.clearance(x, y) > r and self.ground(x, y) > 1.5
                    and self.in_any_pad(x, y, 3.0) is None)

        # ---------------- rivers: reeds on the banks, boulders in the rapids, mist + sound at the drops
        lilies = None
        from .geo import MeshBuilder
        for rv in waterways.RIVERS.values():
            n = len(rv.arc)
            slope = np.clip(-np.gradient(rv.level, rv.arc), 0.0, None)
            last_sound = last_fire = -1e9
            drop_base = -1e9
            for i in range(2, n - 2):
                (x, y), (tx, ty), z, half = rv.at(rv.arc[i])
                nx, ny = -ty, tx
                pond = half >= C.POND_MIN_HALF_WIDTH
                on_bridge = any(math.hypot(x - b["center"][0], y - b["center"][1]) < 9.0 for b in self.meta["bridges"])
                if not on_bridge:
                    for side in (-1, 1):                       # reeds / tall grass where the bank is low
                        if rng.random() < (0.5 if not pond else 0.8):
                            d = half + rng.uniform(-0.5, 1.3)
                            px, py = x + nx * d * side + tx * rng.uniform(-1, 1), y + ny * d * side + ty * rng.uniform(-1, 1)
                            g = self.ground(px, py)
                            if z - 0.5 < g < z + 0.9:
                                put("SM_GrassClump_A", px, py, g - 0.05, rng.uniform(0, 360), rng.uniform(1.3, 2.3))
                        if rng.random() < 0.06:
                            d = half + rng.uniform(1.5, 4.0)
                            px, py = x + nx * d * side, y + ny * d * side
                            g = self.ground(px, py)
                            if g < z + 2.0 and open_ground(px, py, 0.8, 30.0):
                                put(rng.choice(["SM_FlowerBush_Yellow", "SM_FlowerBush_White", "SM_FlowerBush_Blue"]),
                                    px, py, g - 0.1, rng.uniform(0, 360), rng.uniform(0.7, 1.2))
                    if slope[i] > 0.05 and rng.random() < 0.55:       # boulders breaking the water in the rapids
                        d = rng.uniform(-0.75, 0.75) * half
                        px, py = x + nx * d, y + ny * d
                        put(rng.choice(["SM_Rock_B", "SM_Rock_D"]), px, py, self.ground(px, py) - 0.25,
                            rng.uniform(0, 360), rng.uniform(0.45, 0.95))
                    elif not pond and rng.random() < 0.03:            # the odd stone in the stream
                        d = rng.uniform(-0.7, 0.7) * half
                        px, py = x + nx * d, y + ny * d
                        put("SM_Rock_B", px, py, self.ground(px, py) - 0.3, rng.uniform(0, 360), rng.uniform(0.4, 0.8))
                # the foot of a drop: mist and the sound of falling water
                if slope[i] < 0.04 <= slope[i - 1] and rv.arc[i] - drop_base > 25.0:
                    j0 = max(0, i - 15)
                    fall = float(rv.level[j0] - rv.level[i])
                    if fall > 1.2:
                        drop_base = rv.arc[i]
                        self.emitters.append(dict(kind="mist", loc=ue_loc((x, y, z + 0.6)),
                                                  scale=round(min(0.9 + fall * 0.22, 2.6), 2), rate=1.1))
                        self.audio.append(dict(sound="A_Waterfall", loc=ue_loc((x, y, z + 1.0)),
                                               radius=round(min(40.0 + fall * 9.0, 110.0), 1) * 100.0,
                                               volume=round(min(0.35 + fall * 0.06, 0.8), 2)))
                        last_sound = rv.arc[i]
                if rv.arc[i] - last_sound > 150.0 and slope[i] > 0.004:     # the stream itself, quietly
                    self.audio.append(dict(sound="A_Waterfall", loc=ue_loc((x, y, z + 0.5)), radius=3200.0, volume=0.22))
                    last_sound = rv.arc[i]
                if rv.arc[i] - last_fire > 110.0 and not on_bridge:
                    side = rng.choice((-1, 1))
                    self.emitters.append(dict(kind="fireflies", scale=1.6, rate=1.0,
                                              loc=ue_loc((x + nx * (half + 2.5) * side, y + ny * (half + 2.5) * side, z + 1.2))))
                    last_fire = rv.arc[i]
                if pond and rng.random() < 0.9:                    # lily pads on still water
                    lilies = lilies or MeshBuilder("Waterside_Lilies_NoCol")
                    for _ in range(3):
                        a, rr = rng.uniform(0, 2 * math.pi), half * math.sqrt(rng.uniform(0.25, 0.9))
                        px, py = x + math.cos(a) * rr, y + math.sin(a) * rr
                        lvl = waterways.water_level(px, py)
                        if lvl is None or abs(lvl - z) > 0.05 or waterways.clearance(px, py) > -1.5:
                            continue
                        r = rng.uniform(0.35, 0.8)
                        a0 = rng.uniform(0, 2 * math.pi)       # a pad is a disc with a notch
                        lilies.poly([(px, py, z + 0.03)] + [(px + math.cos(a0 + 5.6 * t / 8) * r,
                                                             py + math.sin(a0 + 5.6 * t / 8) * r, z + 0.03)
                                                            for t in range(9)], "M_LeavesBush")
                        if rng.random() < 0.22:
                            lilies.sphere((px, py, z + 0.1), 0.11, rng.choice(["M_FlowerWhite", "M_FlowerRed"]),
                                          seg=6, rings=4)
            # picnic spots on a level bank
            for frac in (0.22, 0.47, 0.63, 0.9):
                (x, y), (tx, ty), z, half = rv.at(rv.length * frac)
                for side in (1, -1):
                    done = False
                    for d in (half + 7.0, half + 10.0, half + 14.0):
                        px, py = x - ty * d * side, y + tx * d * side
                        if open_ground(px, py, 3.0, 8.0) and self.ground(px, py) < z + 3.5:
                            yaw = math.degrees(math.atan2(ty, tx))
                            g = self.ground(px, py)
                            put("SM_PicnicTable", px, py, g, yaw, 1.0)
                            bx, by = px + tx * 3.2, py + ty * 3.2
                            put("SM_TrashBin", bx, by, self.ground(bx, by), yaw, 1.0)
                            self.clearings.append((px, py, 4.5))
                            done = True
                            break
                    if done:
                        break
        if lilies is not None and lilies.verts:
            if export:
                self.export_mesh(lilies, lilies.name, "Water", "none", nanite=False)
            self.static.append(dict(mesh=f"SM_{lilies.name}", folder="Water", loc=[0, 0, 0], yaw=0.0,
                                    collision="none", group="waterside", label=lilies.name))

        # ---------------- roads: benches and planters, lanterns on the trails, guard fences on embankments
        for p in self.meta["paths"]:
            if p["id"] in ("breakwater", "volcano_trail"):
                continue
            samples = p["samples"]
            hw = p["width"] / 2.0
            arc = np.concatenate([[0.0], np.cumsum([math.hypot(samples[i][0] - samples[i - 1][0],
                                                               samples[i][1] - samples[i - 1][1])
                                                    for i in range(1, len(samples))])])
            paved = p["surface"] == "paved"

            def frame(s):
                i = int(min(max(np.searchsorted(arc, s), 1), len(samples) - 1))
                (ax, ay, az), (bx, by, bz) = samples[i - 1], samples[i]
                d = math.hypot(bx - ax, by - ay) or 1.0
                return (bx, by, bz), ((bx - ax) / d, (by - ay) / d)

            spacing = 130.0 if paved else 95.0
            s, side = spacing * 0.6, 1
            while s < arc[-1] - 20.0:
                (x, y, z), (tx, ty) = frame(s)
                off = hw + (2.3 if paved else 1.5)
                px, py = x - ty * off * side, y + tx * off * side
                g = self.ground(px, py)
                if open_ground(px, py, 3.0, 10.0, verge=True) and abs(g - z) < 0.8 \
                        and not self.on_bridge(p["id"], s, 8.0):
                    face = math.degrees(math.atan2(-tx * side, ty * side)) + 90.0    # back to the verge
                    if paved:
                        put("SM_Bench", px, py, g, face, 1.0)
                        qx, qy = px + tx * 2.4, py + ty * 2.4
                        if open_ground(qx, qy, 3.0, 12.0, verge=True):
                            put("SM_Planter", qx, qy, self.ground(qx, qy), face, 1.0)
                        if rng.random() < 0.35:
                            qx, qy = px - tx * 2.2, py - ty * 2.2
                            if open_ground(qx, qy, 3.0, 12.0, verge=True):
                                put("SM_TrashBin", qx, qy, self.ground(qx, qy), face, 1.0)
                    else:
                        put("SM_StoneLantern", px, py, g - 0.03, face, 1.0)
                        L = P.PROP_LIGHTS["SM_StoneLantern"]
                        self.add_light((px, py, g + L["offset"][2]), L)
                    self.clearings.append((px, py, 2.5))
                side = -side
                s += spacing
            # guard fence where the verge falls away (embankments, the approach ramps of the bridges)
            for side in (1, -1):
                s = 4.0
                while s < arc[-1] - 4.0:
                    (x, y, z), (tx, ty) = frame(s)
                    ex, ey = x - ty * (hw + 0.8) * side, y + tx * (hw + 0.8) * side
                    fx, fy = x - ty * (hw + 4.5) * side, y + tx * (hw + 4.5) * side
                    if (z - self.ground(fx, fy) > 1.6 and self.in_any_pad(ex, ey, 2.0) is None
                            and not self.on_bridge(p["id"], s, 0.5) and self.ground(ex, ey) > 1.0
                            and waterways.clearance(ex, ey) > 0.5):
                        put("SM_Fence_Wood", ex, ey, self.ground(ex, ey), math.degrees(math.atan2(ty, tx)), 1.0)
                    s += 4.0

        # ---------------- the sea: swim-zone buoys off the beach, channel markers, fishing boats
        for (bx, by) in C.BEACH_SEGMENT:
            ln = math.hypot(bx, by) or 1.0
            ux, uy = bx / ln, by / ln
            for k in range(1, 60):
                x, y = bx + ux * k * 4.0, by + uy * k * 4.0
                if self.ground(x, y) < -2.6:
                    floater("SM_Buoy", x, y, 0.0, rng.uniform(0, 360))
                    break
        hx0, hx1, hy0, hy1 = C.HARBOR_BASIN
        for x, y in ((-40.0, hy0 - 30.0), (150.0, hy0 - 30.0), (-40.0, hy0 - 110.0), (150.0, hy0 - 110.0)):
            if self.ground(x, y) < -3.0:
                floater("SM_Buoy", x, y, 0.0, rng.uniform(0, 360))
        for x, y, yaw in ((1290.0, -700.0, 40.0), (-1400.0, -420.0, 200.0), (120.0, 1400.0, 80.0), (760.0, -1090.0, -20.0)):
            if self.ground(x, y) < -6.0:
                floater("SM_FishingBoat", x, y, 0.0, yaw, amplitude=10.0)

        # ---------------- the air: gulls over the coast, songbirds inland
        hy = C.LOCATIONS["harbor"]["pos"]
        birds(hy[0], hy[1] - 60.0, 14.0, 190.0, 34.0, 14, "gull")
        lx, ly = C.LOCATIONS["lighthouse"]["pos"]
        birds(lx, ly, 22.0, 70.0, 22.0, 8, "gull")
        bx, by = C.LOCATIONS["beach"]["pos"]
        birds(bx + 40.0, by, 10.0, 170.0, 28.0, 10, "gull")
        sx, sy = C.SEA_STACKS[0][:2]
        birds(sx, sy, 30.0, 150.0, 40.0, 12, "gull")
        birds(C.LAKE_CENTER[0], C.LAKE_CENTER[1], C.LAKE_LEVEL + 10.0, 160.0, 26.0, 9, "songbird")
        fx, fy = C.LOCATIONS["forest"]["pos"]
        birds(fx, fy, self.ground(fx, fy) + 22.0, 210.0, 24.0, 12, "songbird")
        px, py = C.LOCATIONS["plaza"]["pos"]
        birds(px, py, self.info["pads"]["plaza"] + 14.0, 90.0, 18.0, 7, "songbird")
        # fireflies on the lake shore
        a0 = math.radians(C.LAKE_ROT)
        for k in range(8):
            th = 2 * math.pi * k / 8 + 0.3
            lx_, ly_ = math.cos(th) * C.LAKE_RADII[0] * 1.06, math.sin(th) * C.LAKE_RADII[1] * 1.06
            x = C.LAKE_CENTER[0] + lx_ * math.cos(a0) - ly_ * math.sin(a0)
            y = C.LAKE_CENTER[1] + lx_ * math.sin(a0) + ly_ * math.cos(a0)
            if self.ground(x, y) > C.LAKE_LEVEL - 0.2:
                self.emitters.append(dict(kind="fireflies", loc=ue_loc((x, y, self.ground(x, y) + 1.2)), scale=1.8, rate=1.0))
        self.log("  life: " + ", ".join(f"{k.replace('SM_', '')}={v}" for k, v in sorted(counts.items())))

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
        self.drop_indoor_scatter()

    def drop_indoor_scatter(self):
        """Remove scattered plants and stones that came up under a roof (a pier shed, a veranda, a pavilion
        over a lawn): the occupancy mask keeps scatter off the pads, not out of every building volume."""
        from mathutils import Vector
        doomed = set()
        for n, (asset, p, _yaw, _scale) in enumerate(self.inst_raw):
            if asset in P.FLOATING_PROPS:
                continue
            q = Vector(p)
            for sp in self.spaces:
                if sp.near(q, 0.8) and sp.ray(q + Vector((0, 0, 0.6)), Vector((0, 0, 1)), 2.0):
                    doomed.add(n)
                    break
        if not doomed:
            return
        gone = {}
        for n in doomed:
            asset, p, yaw, scale = self.inst_raw[n]
            gone.setdefault(asset, []).append([round(p[0] * 100, 1), round(p[1] * 100 * Y_SIGN, 1), round(p[2] * 100, 1)])
        for asset, locs in gone.items():
            keep = [it for it in self.instances[asset] if it[:3] not in locs]
            self.instances[asset] = keep
        dead = {(self.inst_raw[n][0], self.inst_raw[n][1]) for n in doomed}
        self.inst_raw = [it for n, it in enumerate(self.inst_raw) if n not in doomed]
        self.inst_all = [it for it in self.inst_all if it[4] is not None or (it[0], it[1]) not in dead]
        self.log(f"  scatter: {len(doomed)} instances under a roof removed")

    # ------------------------------------------------------------------ terrain + water actors
    def place_world(self):
        for L in C.LOCATIONS.values():          # keep the arrival points free of trees and rocks
            self.clearings.append((L["spawn"][0], L["spawn"][1], 4.0))
        for cj in range(C.CHUNKS):
            for ci in range(C.CHUNKS):
                self.static.append(dict(mesh=f"SM_Terrain_{ci:02d}_{cj:02d}", folder="Terrain", loc=[0, 0, 0], yaw=0.0,
                                        collision="complex", group="terrain", label=f"Terrain_{ci:02d}_{cj:02d}"))
        for n in ["SM_Ocean", "SM_SeaFloor", "SM_LakeSurface"] + self.river_meshes():
            self.static.append(dict(mesh=n, folder="Water", loc=[0, 0, 0], yaw=0.0, collision="none", group="water",
                                    label=n.replace("SM_", "")))

    def river_meshes(self):
        return [waterways.mesh_name(r["id"]) for r in self.meta.get("rivers", [])]

    def on_bridge(self, path_id, s, margin=0.0):
        """Is arc length s of that path on (or within `margin` m of) one of its bridges?"""
        return any(b["path"] == path_id and b["s0"] - margin <= s <= b["s1"] + margin
                   for b in self.meta.get("bridges", []))

    # ------------------------------------------------------------------ zones
    def zones(self):
        """Map / fast-travel zones: every location, then the fast-travel points inside locations (parent set).
        Arrival points stand on the walking surface found by the standing-room checker (check_people)."""
        if self._zones is not None:
            return self._zones
        out = []
        for key, L in C.LOCATIONS.items():
            x, y = L["pos"]
            z = self.info["pads"].get(key)
            if z is None:
                z = self.ground(x, y)
            ex, ey, ez = L["zone"]
            if key in self.arrivals:
                (sx, sy, az), face = self.arrivals[key]
                sz = self.spawn_floor(sx, sy, az)
            else:
                sx, sy = L["spawn"][:2]
                sz = self.spawn_floor(sx, sy)
            if key in self.arrivals:
                pass
            elif "face" in L:
                face = L["face"]
            else:   # face the location; arriving at the harbor you look inland towards the academy
                tx, ty = (0.0, 0.0) if key == "harbor" else (x, y)
                face = math.degrees(math.atan2(ty - sy, tx - sx))
            out.append(dict(id=key, name=L["name"], subtitle=L["subtitle"], desc=L["desc"], color=list(L["color"]),
                            center=ue_loc((x, y, z)), extent=[ex * 100.0, ey * 100.0, ez * 100.0], yaw=0.0, parent="",
                            spawn=dict(loc=ue_loc((sx, sy, sz + 1.0)), yaw=ue_yaw(face)), _feet=(sx, sy, sz),
                            _r=L.get("spawn_r", 0.38)))
        order = list(C.LOCATIONS)
        for t in sorted(self.travel, key=lambda t: order.index(t["parent"])):
            L = C.LOCATIONS[t["parent"]]
            sx, sy, sz = t["spot"]
            sz = self.spawn_floor(sx, sy, sz)
            if t["center"] is None:
                t["center"], t["half"] = self.room_box((sx, sy, sz), t["box_yaw"])
            out.append(dict(id=t["id"], name=t["name"], subtitle=t["subtitle"] or L["name"], desc=t["desc"],
                            color=list(L["color"]), center=ue_loc(t["center"]),
                            extent=[t["half"][0] * 100.0, t["half"][1] * 100.0, t["half"][2] * 100.0],
                            yaw=ue_yaw(t["box_yaw"]), parent=t["parent"],
                            spawn=dict(loc=ue_loc((sx, sy, sz + 1.0)), yaw=ue_yaw(t["yaw"])), _feet=(sx, sy, sz),
                            _r=0.38))
        self._zones = out
        return out

    def spawn_floor(self, x, y, near_z=None):
        """Height of the walking surface at (x, y): the top of whatever stands there (a platform, a quay, a
        road), else the terrain; near_z picks the surface closest below near_z + 1 m (e.g. one storey)."""
        from mathutils import Vector
        g = self.ground(x, y)
        if not hasattr(self, "_ck"):
            return g
        top = (near_z + 1.0) if near_z is not None else max(g, 0.0) + 2.5
        f = self._ck.floor(Vector((x, y, top - 0.6)), above=0.6, below=top - min(g, top) + 0.5)
        return f[0] if f else g

    def room_box(self, feet, yaw, cap=30.0):
        """The room round a feet position, measured along the building's axes (rays at 1.9 m - over the
        furniture - three abreast so a pillar does not cut the room short; up to the ceiling). Returns the
        zone box centre and half extents (world, box axes = building axes)."""
        from mathutils import Vector
        if not hasattr(self, "_ck"):
            return feet, (4.0, 4.0, 2.0)
        sp = [s for s in self.spaces if s.near(Vector(feet), 5.0)]
        c, si = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        ax = [Vector((c, si, 0.0)), Vector((-si, c, 0.0))]
        base = Vector(feet) + Vector((0, 0, 1.9))
        ext = []
        for i, a in enumerate(ax):
            side = ax[1 - i]
            for sgn in (1, -1):
                d = a * sgn
                hits = []
                for o in (-2.0, -1.0, 0.0, 1.0, 2.0):   # median of up to five abreast: a doorway or a pillar
                    if o:                               # is one ray, not the room (only starts in the room)
                        hs = self._ck._hit(base, side * (1 if o > 0 else -1), abs(o), sp)
                        if hs:
                            continue
                    h = self._ck._hit(base + side * o, d, cap, sp)
                    hits.append(h[0] if h else cap)
                e = sorted(hits)[len(hits) // 2]
                k = 1.0                                  # never past the first spot with no roof over it
                while k < e:
                    q = base + d * k
                    if not self._ck._hit(q, Vector((0, 0, 1)), 40.0, sp):
                        e = max(1.0, k - 0.5)
                        break
                    k += 1.0
                ext.append(e)
        hz = self._ck._hit(base, Vector((0, 0, 1)), 30.0, sp)
        top = base.z + (hz[0] if hz else 4.0)
        bot = feet[2] - 0.3
        ux = (ext[0] - ext[1]) / 2
        uy = (ext[2] - ext[3]) / 2
        cx = feet[0] + ax[0].x * ux + ax[1].x * uy
        cy = feet[1] + ax[0].y * ux + ax[1].y * uy
        return (cx, cy, (top + bot) / 2), ((ext[0] + ext[1]) / 2, (ext[2] + ext[3]) / 2, (top - bot) / 2)

    def water_at(self, x, y):
        level = waterways.water_level(x, y)          # rivers and ponds count: nobody is posted in a stream
        if level is not None and level > 0.05:
            return level
        a = math.radians(C.LAKE_ROT)
        dx, dy = x - C.LAKE_CENTER[0], y - C.LAKE_CENTER[1]
        q = math.hypot((dx * math.cos(a) + dy * math.sin(a)) / C.LAKE_RADII[0],
                       (-dx * math.sin(a) + dy * math.cos(a)) / C.LAKE_RADII[1])
        return C.LAKE_LEVEL if q < 1.15 else 0.0

    def slope_at(self, x, y, d=1.0):
        gx = (self.ground(x + d, y) - self.ground(x - d, y)) / (2 * d)
        gy = (self.ground(x, y + d) - self.ground(x, y - d)) / (2 * d)
        return math.degrees(math.atan(math.hypot(gx, gy)))

    def build_checker(self):
        from . import placement
        if hasattr(self, "_ck"):
            return self._ck
        world = [it for it in self.inst_raw if it[0] not in placement.SOFT_PROPS]
        bounds = placement.prop_bounds({it[0] for it in world}, self.log)
        pv, pp, pt = [], [], []
        placement.box_tris(world, bounds, pv, pp, pt)
        sp_props = placement.mesh_space([], name="world props", extra=[(pv, pp, pt)])
        spaces = list(self.spaces)
        if sp_props is not None:
            spaces.append(self._grid(sp_props, pv, pp, pt))
        for mb in self.road_mbs:
            spaces.append(placement.mesh_space([mb], name=mb.name))
        self._ck = placement.Checker(spaces, ground=self.ground, water=self.water_at, slope=self.slope_at)
        return self._ck

    @staticmethod
    def _grid(sp, pv, pp, pt):
        sp.bounds = None          # everywhere (the props are spread over the whole island)
        return sp

    def check_people(self):
        """Arrival points must have room for the player; every NPC gets its wander route (clear straight walks
        from home on the same floor). Returns the list of problems."""
        import time
        from mathutils import Vector
        from . import placement
        t0 = time.time()
        ck = self.build_checker()
        self._zones = None
        problems = []
        for z in self.zones():
            why = ck.capsule(Vector(z["_feet"]), r=z["_r"])
            if why:
                problems.append(f"travel {z['id']} at {tuple(round(c, 1) for c in z['_feet'])}: {why}")
        n_routes = n_still = 0
        for n in self.npcs:
            feet = n["_feet"]
            pts = ck.wander_points(feet, n["wander"] / 100.0) if n["wander"] > 100.0 else []
            if not pts and n["wander"] > 100.0:
                n_still += 1
            n["points"] = [ue_loc((q.x, q.y, q.z + 0.95)) for q in pts]
            n_routes += bool(pts)
            why = ck.capsule(Vector(feet))
            if why:
                problems.append(f"npc {n['group']} at {tuple(round(c, 1) for c in feet)}: {why}")
        self.log(f"  people: {len(self.zones())} arrival points, {len(self.npcs)} NPCs ({n_routes} with wander routes, "
                 f"{n_still} with no room to stroll stay put), {len(problems)} problems ({time.time() - t0:.0f}s)")
        for line in problems:
            self.log("   !! " + line)
        return problems

    # ------------------------------------------------------------------ minimap
    def minimap(self, size=2048):
        from PIL import Image, ImageDraw
        # recompute the base map from cached height + colour map
        h = self.hf.a
        colour_path = os.path.join(C.OUT_TEXTURES, "T_TerrainColor.png")
        if not os.path.exists(colour_path):
            raise FileNotFoundError(f"{colour_path} missing - run the textures and terrain stages first")
        with Image.open(colour_path) as colour:
            col = np.asarray(colour.convert("RGB")).astype(np.float32) / 255.0
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
        level = terrain.load_water()
        fresh = ndimage.zoom((np.isfinite(level) & (level > 0.05)).astype(np.float32), size / level.shape[0],
                             order=1)[:size, :size] > 0.35
        img = np.where(fresh[..., None], np.array([0.25, 0.6, 0.72]), img)
        coast = ndimage.binary_dilation(sea, iterations=2) & ~sea
        img = np.where(coast[..., None], img * 0.6 + 0.4, img)
        pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB")
        d = ImageDraw.Draw(pil)

        def px(p):
            return ((p[0] + C.HALF) / C.WORLD_SIZE * size, (C.HALF - p[1]) / C.WORLD_SIZE * size)

        for b in self.meta.get("bridges", []):
            d.line([px(b["a"]), px(b["b"])], fill=(232, 222, 200), width=max(3, int(b["width"] / sp) + 2))
            d.line([px(b["a"]), px(b["b"])], fill=(120, 96, 70), width=1)
        for key, poly in self.footprints:
            colr = tuple(int(c * 255) for c in C.LOCATIONS.get(key, {}).get("color", (0.8, 0.8, 0.8)))
            fill = tuple(int(0.55 * c + 0.45 * 235) for c in colr)
            d.polygon([px(p) for p in poly], fill=fill, outline=(60, 60, 70))
        atomic.save_image(pil, os.path.join(C.OUT_TEXTURES, "T_IslandMap.png"), optimize=True)
        self.log("  minimap: T_IslandMap.png")

    # ------------------------------------------------------------------ write
    def write(self):
        os.makedirs(C.OUT_DATA, exist_ok=True)
        from .anime import cast as anime_cast
        self.check_people()
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
            if k.startswith("SM_Int_"):      # furniture is only ever seen from inside or through a window
                cull.setdefault(k, [6000, 9000])
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
            interacts=self.interacts, emitters=self.emitters, audio=self.audio,
            npcs=[{k: v for k, v in n.items() if not k.startswith("_")} for n in self.npcs],
            specials=self.specials, doors=self.doors,
            zones=[{k: v for k, v in z.items() if not k.startswith("_")} for z in self.zones()],
        )
        jsonio.write_json(os.path.join(C.OUT_DATA, "layout.json"), layout, separators=(",", ":"))
        jsonio.write_json(os.path.join(C.OUT_DATA, "materials.json"), palette.material_json(), indent=1)
        jsonio.write_json(os.path.join(C.OUT_DATA, "assets.json"), self.manifest, indent=1)
        n_inst = sum(len(v["items"]) for v in inst.values())
        self.log(f"  layout.json: {len(self.static)} static, {len(self.floating)} floating, {n_inst} instances, "
                 f"{len(self.lights)} lights, {len(self.texts)} texts, {len(self.interacts)} interactables, "
                 f"{len(self.emitters)} emitters, {len(self.audio)} sounds, {len(self.npcs)} npcs, "
                 f"{len(self.specials)} specials, {len(self.doors)} doors")


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
        try:
            blend.export_fbx([o], os.path.join(out, f"SM_{name}.fbx"))
        finally:
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
    rivers = [waterways.mesh_name(r["id"]) for r in
              jsonio.read_json(os.path.join(C.CACHE_DIR, "terrain_info.json")).get("rivers", [])]
    for n in ["SM_Ocean", "SM_SeaFloor", "SM_LakeSurface"] + rivers:
        manifest.append(dict(file=f"Meshes/Water/{n}.fbx", name=n, folder="Water", collision="none", nanite=False,
                             category="water"))
