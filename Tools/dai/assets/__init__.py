"""
Asset framework.

Every location module exposes  PLACEMENTS = {"<location_key>": build_fn, ...}
where build_fn() -> AssetSet. The layout stage places each AssetSet at
config.LOCATIONS[key] (position, yaw, pad height) - so everything inside an
AssetSet is modelled in LOCAL metres: origin = centre of the footprint at
finished ground level, front of the building facing -Y.

An AssetSet contains
  * meshes  : name -> MeshBuilder   (exported as SM_<name>.fbx, complex collision)
              names ending in "_NoCol" get no collision (water, glow, leaves...)
  * sockets : gameplay / dressing markers converted to UE actors:
      prop      asset=<catalog mesh>, scale
      light     color, intensity (lumens-ish UE units), radius (m), night_only, spot dir...
      text      text, size (m), color   -> TextRender actor (signs, building names)
      interact  kind = duel_field | card_shop | sign | info, text/title
      emitter   kind = smoke | steam | mist | sparks, scale
      audio     sound = A_Ocean | A_Wind | A_Forest | A_Volcano | A_Waterfall | A_HotSpring | A_Crowd, radius
      npc       dorm = slifer | ra | obelisk | white, wander radius
      spawn     player start candidates
      door      automatic door in a doorway (style, width, height, double, mode, swing) -> ADADoor
      lighthouse_beam / floating (boats bob) / waterfall etc. special kinds
"""

import importlib
import math

from ..geo import MeshBuilder
from .. import palette


class AssetSet:
    def __init__(self, name):
        self.name = name
        self.meshes = {}
        self.sockets = []

    # ------------------------------------------------------------------ meshes
    def mesh(self, name):
        """Get/create a MeshBuilder. The exported asset is called SM_<name>."""
        if name not in self.meshes:
            self.meshes[name] = MeshBuilder(name)
        return self.meshes[name]

    # ------------------------------------------------------------------ sockets
    def socket(self, type, pos, yaw=0.0, **props):
        self.sockets.append(dict(type=type, pos=[float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 0.0],
                                 yaw=float(yaw), props=props))

    def prop(self, asset, pos, yaw=0.0, scale=1.0):
        self.socket("prop", pos, yaw, asset=asset, scale=scale)

    def light(self, pos, color=(1.0, 0.85, 0.6), intensity=5000.0, radius=12.0, night_only=False,
              spot_pitch=None, cone=None, shadows=False, yaw=0.0):
        """Point light (or spot light when spot_pitch is given: aimed along local yaw, pitched down)."""
        self.socket("light", pos, yaw, color=list(color), intensity=intensity, radius=radius,
                    night_only=night_only, spot_pitch=spot_pitch, cone=cone, shadows=shadows)

    def text(self, text, pos, yaw=0.0, size=1.0, color=(1, 1, 1), emissive=False):
        """World text facing local -Y rotated by yaw (readable from the front)."""
        self.socket("text", pos, yaw, text=text, size=size, color=list(color), emissive=emissive)

    def interact(self, kind, pos, yaw=0.0, title="", text="", radius=3.0):
        self.socket("interact", pos, yaw, kind=kind, title=title, text=text, radius=radius)

    def emitter(self, kind, pos, scale=1.0, rate=1.0):
        self.socket("emitter", pos, 0.0, kind=kind, scale=scale, rate=rate)

    def audio(self, sound, pos, radius=40.0, volume=1.0):
        self.socket("audio", pos, 0.0, sound=sound, radius=radius, volume=volume)

    def npc(self, pos, yaw=0.0, dorm="slifer", wander=8.0):
        self.socket("npc", pos, yaw, dorm=dorm, wander=wander)

    def door(self, pos, yaw=0.0, width=0.9, height=2.1, style="wood", double=False, mode=None, swing="auto"):
        """Automatic door (see assets/doors.py). pos = bottom centre of the opening on the wall's middle
        plane, yaw = wall frame with local -Y outside. The leaves are separate meshes (Meshes/Doors)."""
        from .doors import default_mode
        assert swing in ("auto", "in", "out"), swing
        self.socket("door", pos, yaw, width=float(width), height=float(height), style=style, double=bool(double),
                    mode=mode or default_mode(style), swing=swing)

    def arrival(self, spot, yaw):
        """Where fast travel to this location puts the player (feet position, facing yaw; local frame)."""
        self.socket("arrival", spot, yaw)

    def travel(self, id, name, spot, yaw, box=None, subtitle="", desc="", face_open=True):
        """Fast-travel point inside (or at) this location: arrival feet position `spot` facing `yaw` (local
        frame), listed on the island map under the location. box = (x0, y0, z0, x1, y1, z1) local zone box
        (the banner names the room while the player is in it); None = the room measured round the spot."""
        self.socket("travel", spot, yaw, id=id, name=name, subtitle=subtitle, desc=desc,
                    box=list(box) if box else None, face_open=face_open)

    def travel_at(self, camera, id, name, desc="", step=1.5, subtitle="", face_open=True):
        """Fast-travel point in the room of the interior camera `camera` (its label): a step into the room
        along the view, on the floor below the camera, facing the way the camera looks."""
        import math
        cams = [s for s in self.sockets if s["type"] == "camera" and s["props"].get("label") == camera]
        assert cams, f"{self.name}: no camera '{camera}' for fast travel point {id}"
        c = cams[0]
        (x, y, z), (tx, ty, _) = c["pos"], c["props"]["target"]
        yaw = math.degrees(math.atan2(ty - y, tx - x))
        d = math.hypot(tx - x, ty - y) or 1.0
        self.travel(id, name, (x + (tx - x) / d * step, y + (ty - y) / d * step, z - 1.6), yaw,
                    subtitle=subtitle, desc=desc, face_open=face_open)

    def special(self, kind, pos, yaw=0.0, **props):
        self.socket(kind, pos, yaw, **props)

    # ------------------------------------------------------------------ stats
    def stats(self):
        out = {}
        for n, mb in self.meshes.items():
            tris = sum(len(f) - 2 for f in mb.faces)
            out[n] = dict(tris=tris, verts=len(mb.verts),
                          materials=sorted(set(mb.face_mats)),
                          bounds=[list(map(float, b)) for b in mb.bounds()] if mb.verts else None)
        return out

    def unknown_materials(self):
        bad = set()
        for mb in self.meshes.values():
            for m in mb.face_mats:
                if m not in palette.MATERIALS:
                    bad.add(m)
        return sorted(bad)


# Location modules (each provides PLACEMENTS)
LOCATION_MODULES = [
    "academy", "slifer", "ra", "obelisk", "harbor", "abandoned", "gym", "hotsprings", "features",
]


def load_placements(log=print):
    import os
    placements = {}
    mods = os.environ.get("DAI_MODULES")
    mods = [m.strip() for m in mods.split(",")] if mods else LOCATION_MODULES
    for modname in mods:
        try:
            mod = importlib.import_module(f"{__name__}.{modname}")
        except ModuleNotFoundError as e:
            if e.name and e.name.endswith(modname):
                log(f"  (module {modname} not present yet)")
                continue
            raise
        for key, fn in getattr(mod, "PLACEMENTS", {}).items():
            placements[key] = fn
    return placements


def with_travel(build, points):
    """A location builder that also adds its interior fast-travel points:
    points = [(camera label, id, name, description[, dict(step=, face_open=)])] (see AssetSet.travel_at),
    or (None, id, name, description, dict(spot=(x, y, z), yaw=, face_open=)) for a hand-placed point."""
    def wrapped():
        aset = build()
        for pt in points:
            cam, id_, name, desc = pt[:4]
            opts = dict(pt[4]) if len(pt) > 4 else {}
            if "spot" in opts:              # placed by hand (cam is then None)
                aset.travel(id_, name, opts["spot"], opts["yaw"], desc=desc, face_open=opts.get("face_open", True))
            else:
                aset.travel_at(cam, id_, name, desc, **opts)
        return aset
    wrapped.__name__ = getattr(build, "__name__", "build")
    return wrapped
