"""
Interior showcase: renders a pick of interior cameras (aset.special("camera", ..., label=...)) from several
locations with Cycles and assembles them into Docs/renders/interiors.jpg (the README image).

    python Tools/preview_interiors.py                      # the default picks below
    python Tools/preview_interiors.py slifer:room101 ra:   # module:label-substring (empty = first camera)

Run with the Blender-as-a-module interpreter (pip install bpy, Python 3.13).
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,F401  (provides mathutils)
from mathutils import Vector  # noqa: E402

from dai import blend, config as C  # noqa: E402

PICKS = [
    ("slifer", "slifer", "room101"),
    ("ra", "ra", "attic_obs"),
    ("obelisk", "obelisk_boys", "4f_cupola"),
    ("academy", "academy", "pavE_3f_physics_lab"),
    ("obelisk", "obelisk_girls", "tea_room"),
    ("harbor", "lighthouse", "lh_g3_lookout"),
    ("hotsprings", "hotsprings", "wash_men"),
    ("abandoned", "abandoned", "clockwork"),
    ("harbor", "harbor", "ferry_lower_cabin"),
]
TILE = (640, 400)


def render_pick(module, placement, label, out, samples):
    from dai.assets import doors as DR
    from dai.assets import props as P
    mod = importlib.import_module(f"dai.assets.{module}")
    fn = mod.PLACEMENTS[placement]
    blend.reset_scene()
    aset = fn()
    cams = [s for s in aset.sockets if s["type"] == "camera" and label in str(s["props"].get("label", ""))
            and (label or s["props"].get("label"))]
    if not cams:
        print(f"  !! {placement}: no interior camera matching '{label}'")
        return None
    for n, mb in aset.meshes.items():
        if mb.verts:
            mb.build("SM_" + n)
    P.instance_props_for_preview(aset)
    DR.preview_objects(aset, open_deg=55.0)
    blend.setup_world(sun_elev=38, sun_azim=210)
    from dai import inspect
    inspect.add_socket_lights(aset)          # lit like the Unreal level (light sockets + fixtures)
    s = cams[0]
    cam = blend.camera("InCam", Vector(s["pos"]), Vector(s["props"]["target"]), lens=s["props"].get("lens", 18.0))
    blend.setup_render(TILE, samples)
    blend.render(cam, out)
    return out


def main(argv):
    picks = PICKS
    if argv:
        picks = []
        for a in argv:
            mod, _, lab = a.partition(":")
            picks.append((mod, mod, lab))
    tmp = os.path.join(C.DOCS_DIR, "previews", "interiors")
    os.makedirs(tmp, exist_ok=True)
    tiles = []
    for module, placement, label in picks:
        out = os.path.join(tmp, f"{placement}_{label or 'first'}.png")
        if render_pick(module, placement, label, out, samples=24):
            tiles.append(out)
    if not tiles:
        return
    from PIL import Image
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * TILE[0], rows * TILE[1]), (20, 20, 24))
    for i, t in enumerate(tiles):
        sheet.paste(Image.open(t).convert("RGB").resize(TILE), ((i % cols) * TILE[0], (i // cols) * TILE[1]))
    dest = os.path.join(C.DOCS_DIR, "renders", "interiors.jpg")
    sheet.save(dest, quality=88)
    print("->", dest)


if __name__ == "__main__":
    main(sys.argv[1:])
