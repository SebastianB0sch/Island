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
