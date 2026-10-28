"""
Preview one location module (or one placement) without running the whole pipeline.

    python Tools/preview_asset.py academy                 # every placement in assets/academy.py
    python Tools/preview_asset.py academy --only plaza    # a single placement
    python Tools/preview_asset.py props                   # the shared prop catalog

Renders  Docs/previews/<placement>_*.png  (3/4 front view, rear view, top view)
and prints triangle counts, bounds, sockets and any unknown material names.
Run with the Blender-as-a-module interpreter (pip install bpy, Python 3.13).
"""

import argparse
import importlib
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from dai import blend, config as C  # noqa: E402


def socket_markers(aset):
    """Small coloured markers for sockets so they show up in previews."""
    from dai.geo import MeshBuilder
    mb = MeshBuilder("Sockets")
    colours = {"light": "M_LampGlow", "interact": "M_Hologram", "text": "M_EmblemGlow",
               "emitter": "M_Steam", "npc": "M_Jacket", "prop": "M_Gold"}
    for s in aset.sockets:
        mat = colours.get(s["type"], "M_DuelFieldGlow")
        x, y, z = s["pos"]
        if s["type"] == "prop":
            continue
        mb.box((x, y, z), (0.4, 0.4, 0.4), mat)
    return mb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("module")
    ap.add_argument("--only", default=None)
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--res", default="1100x800")
    ap.add_argument("--views", default="front,back,top")
    ap.add_argument("--no-props", action="store_true")
    args = ap.parse_args()
    res = tuple(int(v) for v in args.res.split("x"))
    out_dir = os.path.join(C.DOCS_DIR, "previews")
    os.makedirs(out_dir, exist_ok=True)

    mod = importlib.import_module(f"dai.assets.{args.module}")
    placements = getattr(mod, "PLACEMENTS", {})
    if args.module == "props":
        placements = {"props": mod.build_catalog_preview}
    for key, fn in placements.items():
        if args.only and key != args.only:
            continue
        blend.reset_scene()
        aset = fn()
        print(f"=== {key}: {len(aset.meshes)} meshes, {len(aset.sockets)} sockets")
        for n, st in aset.stats().items():
            print(f"   SM_{n:32s} tris={st['tris']:7d}  bounds={st['bounds']}")
            print(f"      materials: {', '.join(st['materials'])}")
        bad = aset.unknown_materials()
        if bad:
            print("   !! UNKNOWN MATERIALS:", bad)
        kinds = {}
        for s in aset.sockets:
            kinds[s["type"]] = kinds.get(s["type"], 0) + 1
        print("   sockets:", kinds)
        objs = [mb.build("SM_" + n) for n, mb in aset.meshes.items() if mb.verts]
        if not args.no_props:
            try:
                from dai.assets import props as P
                objs += P.instance_props_for_preview(aset)
            except Exception as e:  # props module may not exist yet
                print("   (props not instanced:", e, ")")
        mk = socket_markers(aset)
        if mk.verts:
            objs.append(mk.build())
        blend.setup_world(sun_elev=40, sun_azim=200)
        views = args.views.split(",")
        if "front" in views:
            blend.preview_asset(objs, os.path.join(out_dir, f"{key}_front.png"), res=res,
                                samples=args.samples, azim=-30, elev=20, dist_mul=0.95)
        if "back" in views:
            for o in list(bpy.data.objects):
                if o.name.startswith(("PreviewCam", "PreviewGround")):
                    bpy.data.objects.remove(o)
            blend.preview_asset(objs, os.path.join(out_dir, f"{key}_back.png"), res=res,
                                samples=args.samples, azim=150, elev=25, dist_mul=0.95)
        if "top" in views:
            for o in list(bpy.data.objects):
                if o.name.startswith(("PreviewCam", "PreviewGround")):
                    bpy.data.objects.remove(o)
            blend.preview_asset(objs, os.path.join(out_dir, f"{key}_top.png"), res=res,
                                samples=max(8, args.samples // 2), azim=0.01, elev=89.0, dist_mul=0.8)
        if "inside" in views:
            # interior views come from sockets: aset.special("camera", pos, target=(x, y, z), lens=18)
            cams = [s for s in aset.sockets if s["type"] == "camera"]
            for i, s in enumerate(cams):
                cam = blend.camera(f"InCam{i}", Vector(s["pos"]), Vector(s["props"]["target"]),
                                   lens=s["props"].get("lens", 18.0))
                blend.setup_render(res, args.samples)
                blend.render(cam, os.path.join(out_dir, f"{key}_inside{i}.png"))
        print(f"   previews -> {out_dir}/{key}_*.png")


if __name__ == "__main__":
    main()
