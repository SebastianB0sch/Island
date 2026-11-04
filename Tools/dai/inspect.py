"""
Interior inspection tools: build a location in Blender the way Unreal will show it (meshes, catalog props,
door leaves, light sockets as real lights, a 1.75 m student for scale) and audit it.

Used by Tools/preview_asset.py (--lit, --scale-ref) and Tools/audit_interiors.py.

Audit checks (all in the AssetSet's local metres):
  grounding   floor-standing props whose base floats above / sinks into the surface below them
  ceiling     ceiling fixtures (origin at the top) that do not touch a ceiling
  wall        wall-hung props (paintings, mirrors, clocks ...) that are not on a wall
  clipping    furniture whose footprint pokes through walls
  doors       doorways without floor on both sides at the threshold, or with furniture in the leaf's swing
  rooms       per interior camera: ceiling height, floor-to-ceiling free height, and "detail coverage" -
              the share of the view (ray grid) that hits furniture / decor instead of bare wall, floor or
              ceiling surfaces. Bare rooms score low.
"""

import math

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# props whose origin is at the TOP (hung from the ceiling)
CEILING_PROPS = {"SM_Int_Chandelier", "SM_Int_CeilingLamp", "SM_Int_IndustrialLamp", "SM_Int_CeilingFan"}
# props hung on a wall (back at local +Y)
WALL_PROPS = {"SM_Int_Painting", "SM_Int_Frame", "SM_Int_Mirror", "SM_Int_WallClock", "SM_Int_Lifebuoy"}
# small things that may sit on other furniture (tables, shelves) - grounding is checked against any surface
SMALL_PROPS = {"SM_Int_Books", "SM_Int_TeaSet", "SM_Int_Kettle", "SM_Int_RubberDuck", "SM_Int_DeskLamp",
               "SM_Int_OilLamp", "SM_Int_Candelabra", "SM_Int_Register", "SM_Int_TV", "SM_Int_Radio",
               "SM_Int_Microwave", "SM_Int_Pillows", "SM_Int_Bust", "SM_Int_Basket", "SM_Int_Bucket",
               "SM_Int_PottedPlant", "SM_Int_Box", "SM_Int_Suitcase"}
# materials that count as bare architecture for the detail-coverage metric
BARE_PREFIXES = ("M_IntPlaster", "M_IntWallpaper", "M_IntCeiling", "M_IntWoodFloor", "M_IntTatami",
                 "M_IntTile", "M_IntMarbleFloor", "M_IntCarpet", "M_IntLinoleum", "M_IntConcrete",
                 "M_IntWoodPanel", "M_CreamWall", "M_WhiteWall", "M_Concrete", "M_MarbleFloor", "M_Paving",
                 "M_Terrain")


def _is_bare(mat):
    if mat.startswith(("M_ObInt", "M_Int")) and ("Wallpaper" in mat or "Plaster" in mat or "Floor" in mat
                                                 or "Ceiling" in mat or "Marble" in mat):
        return True
    if mat.endswith(("Wall", "Floor", "Ceiling")):
        return True
    if mat.startswith("M_") and ("Int" in mat[:8]) and any(k in mat for k in ("Wall", "Floor", "Ceil", "Carpet")) \
            and not any(k in mat for k in ("Lamp", "Sconce", "Clock", "Rug")):
        return True             # module-specific wall papers / floors (M_ObIntWallNavy ...) are bare surfaces too
    return mat.startswith(BARE_PREFIXES)


# --------------------------------------------------------------------------- scene building
def build_scene(aset, door_angle=35.0, props=True, doors=True):
    """Blender objects for every mesh + prop socket + door leaf. Returns dict(objs, props=[(socket, obj)])."""
    from .assets import props as P
    from .assets import doors as DR
    objs, placed = [], []
    for n, mb in aset.meshes.items():
        if mb.verts:
            o = mb.build("SM_" + n)
            o["nocol"] = n.endswith("_NoCol")
            objs.append(o)
    if props:
        proto = {}
        for s in aset.sockets:
            if s["type"] != "prop":
                continue
            name = s["props"]["asset"]
            if name not in P.REGISTRY:
                continue
            if name not in proto:
                proto[name] = P.build_object(name, name + "_proto")
                proto[name].hide_render = True
                proto[name].hide_viewport = True
            o = bpy.data.objects.new(name, proto[name].data)
            bpy.context.scene.collection.objects.link(o)
            o.location = s["pos"]
            o.rotation_euler = (0, 0, math.radians(s["yaw"]))
            sc = s["props"].get("scale", 1.0)
            o.scale = (sc, sc, sc)
            placed.append((s, o))
    if doors:
        objs += DR.preview_objects(aset, open_deg=door_angle)
    bpy.context.view_layer.update()
    return dict(objs=objs, props=placed)


def add_socket_lights(aset, scale=0.02):
    """Point / spot lights for the AssetSet's light sockets and the lights that come with fixture props
    (PROP_LIGHTS), so previews are lit like the Unreal level. UE unitless intensity -> Blender W * scale."""
    from .assets import props as P
    n = 0
    for s in aset.sockets:
        L = None
        pos = Vector(s["pos"])
        if s["type"] == "light":
            L = s["props"]
        elif s["type"] == "prop" and s["props"]["asset"] in P.PROP_LIGHTS:
            L = P.PROP_LIGHTS[s["props"]["asset"]]
            off = Vector(L["offset"])
            a = math.radians(s["yaw"])
            pos = pos + Vector((off.x * math.cos(a) - off.y * math.sin(a), off.x * math.sin(a) + off.y * math.cos(a),
                                off.z * s["props"].get("scale", 1.0)))
        if not L:
            continue
        spot = L.get("spot_pitch") is not None
        ld = bpy.data.lights.new(f"L{n}", "SPOT" if spot else "POINT")
        ld.energy = float(L.get("intensity", 3000.0)) * scale
        ld.color = tuple(L.get("color", (1, 0.9, 0.7)))[:3]
        ld.shadow_soft_size = 0.08
        try:
            ld.use_custom_distance = True
            ld.cutoff_distance = float(L.get("radius", 10.0))
        except Exception:  # noqa: BLE001
            pass
        lo = bpy.data.objects.new(f"L{n}", ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.location = pos
        if spot:
            ld.spot_size = math.radians(float(L.get("cone") or 40.0))
            pitch = math.radians(float(L["spot_pitch"]))
            yaw = math.radians(s["yaw"])
            d = Vector((math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), -math.sin(pitch)))
            lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        n += 1
    return n


def scale_figure(pos, yaw=0.0, name="ScaleRef"):
    """The procedural student (1.75 m, Duel Academy jacket) standing at pos, for judging scale."""
    from .assets import avatar as AV
    a = AV.build_preview()
    o = a.meshes["Avatar_Assembled"].build(name)
    o.location = pos
    o.rotation_euler = (0, 0, math.radians(yaw))
    return o


# --------------------------------------------------------------------------- ray casting helpers
def _bvh(objs, include_nocol=True):
    verts, polys, mats = [], [], []
    for o in objs:
        if o.type != "MESH" or (not include_nocol and o.get("nocol")):
            continue
        me = o.data
        mw = o.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in me.vertices)
        names = [m.name if m else "" for m in me.materials]
        for p in me.polygons:
            polys.append([base + i for i in p.vertices])
            mats.append(names[p.material_index] if p.material_index < len(names) else "")
    if not polys:
        return None, []
    return BVHTree.FromPolygons(verts, polys, all_triangles=False), mats


def _prop_box(o):
    """World-space AABB (min, max) of a placed prop object."""
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))),
            Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb))))


def _box_mesh(boxes, name="PropBoxes"):
    """One mesh of axis-aligned boxes (props as solid blocks for ray tests), material 'PROP'."""
    import bmesh
    bm = bmesh.new()
    for mn, mx in boxes:
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co = Vector(((mn.x + mx.x) / 2 + v.co.x * (mx.x - mn.x), (mn.y + mx.y) / 2 + v.co.y * (mx.y - mn.y),
                           (mn.z + mx.z) / 2 + v.co.z * (mx.z - mn.z)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    mat = bpy.data.materials.get("PROP") or bpy.data.materials.new("PROP")
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.hide_render = True
    return o


# --------------------------------------------------------------------------- audit
def audit(aset, scene=None, log=print, coverage_rays=(48, 30)):
    """Run every check; returns a dict of issue lists + per-camera room metrics."""
    scene = scene or build_scene(aset, door_angle=0.0)
    solid = [o for o in scene["objs"] if not o.get("nocol")]
    arch, arch_mats = _bvh(solid)
    issues = dict(grounding=[], ceiling=[], wall=[], clipping=[], doors=[], rooms=[])
    if arch is None:
        return issues
    boxes = {id(o): _prop_box(o) for _, o in scene["props"]}
    big = [(s, o) for s, o in scene["props"] if s["props"]["asset"] not in CEILING_PROPS | WALL_PROPS | SMALL_PROPS]
    other_boxes = _box_mesh([boxes[id(o)] for _, o in big]) if big else None
    furn, _ = _bvh([other_boxes]) if other_boxes else (None, [])

    def down(p, start=0.6, through_props=False):
        o = Vector((p.x, p.y, p.z + start))
        h = arch.ray_cast(o, Vector((0, 0, -1)), 4.0)
        z = h[0].z if h[0] else None
        if through_props and furn:
            hf = furn.ray_cast(o, Vector((0, 0, -1)), 4.0)
            if hf[0] and (z is None or hf[0].z > z):
                z = hf[0].z
        return z

    def indoors(p):
        h = arch.ray_cast(Vector((p.x, p.y, p.z + 0.3)), Vector((0, 0, 1)), 12.0)
        return h[0] is not None

    for s, o in scene["props"]:
        name = s["props"]["asset"]
        p = Vector(s["pos"])
        label = f"{name} @ ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})"
        if name not in CEILING_PROPS and not indoors(p):
            continue                       # outdoor dressing stands on the terrain, which is not part of the set
        if name in CEILING_PROPS:
            h = arch.ray_cast(p - Vector((0, 0, 0.05)), Vector((0, 0, 1)), 1.0)
            if not h[0] or h[0].z - p.z > 0.08:
                issues["ceiling"].append(f"{label}: no ceiling within 8 cm above the fixture")
            continue
        if name in WALL_PROPS:
            a = math.radians(s["yaw"])
            back = Vector((-math.sin(a), math.cos(a), 0.0))    # local +Y
            mn, mx = boxes[id(o)]
            c = Vector((p.x, p.y, (mn.z + mx.z) / 2))
            h = arch.ray_cast(c - back * 0.05, back, 0.35)
            if not h[0]:
                issues["wall"].append(f"{label}: no wall behind it (within 30 cm)")
            continue
        # grounding: the base should rest on the surface below (small items may rest on furniture)
        mn, mx = boxes[id(o)]
        z = down(p, start=0.05, through_props=name in SMALL_PROPS)
        zs = down(p, start=max(0.1, (mx.z - mn.z) * 0.5), through_props=name in SMALL_PROPS)
        if zs is not None and zs > p.z + 0.04:
            issues["grounding"].append(f"{label}: sunk {100 * (zs - p.z):.0f} cm into the surface")
        elif z is None:
            if p.z > 0.06:                 # at ground level it stands on the terrain (not part of the set)
                issues["grounding"].append(f"{label}: nothing below it")
        elif p.z - z > 0.04:
            issues["grounding"].append(f"{label}: floats {100 * (p.z - z):.0f} cm above the surface")
        # clipping: rays from the centre to the footprint corners at 40 % height
        if name not in SMALL_PROPS:
            mn, mx = boxes[id(o)]
            zc = mn.z + (mx.z - mn.z) * 0.4
            c = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, zc))
            worst = 0.0
            for cx, cy in ((mn.x, mn.y), (mx.x, mn.y), (mx.x, mx.y), (mn.x, mx.y)):
                t = Vector((cx, cy, zc)) - c
                L = t.length
                if L < 1e-3:
                    continue
                h = arch.ray_cast(c, t.normalized(), L)
                if h[0]:
                    worst = max(worst, L - (h[0] - c).length)
            if worst > 0.12:
                issues["clipping"].append(f"{label}: pokes {100 * worst:.0f} cm into a wall")

    # doors: floor on both sides at the threshold, swing space free of furniture
    for s in aset.sockets:
        if s["type"] != "door":
            continue
        p = Vector(s["pos"])
        pr = s["props"]
        a = math.radians(s["yaw"])
        n_out = Vector((math.sin(a), -math.cos(a), 0.0))      # local -Y = outside
        label = f"door {pr['style']} {pr['width']:.2f}x{pr['height']:.2f} @ ({p.x:.2f}, {p.y:.2f}, {p.z:.2f})"
        for side, sgn in (("outside", 1), ("inside", -1)):
            q = p + n_out * sgn * 0.7
            z = down(q, start=0.5)
            if z is None or abs(z - p.z) > 0.21:
                issues["doors"].append(f"{label}: no floor at threshold height {side} "
                                       f"({'none' if z is None else f'{100 * (z - p.z):+.0f} cm'})")
        if pr["mode"] == "swing" and furn:
            lw = pr["width"] / (2 if pr["double"] else 1)
            for sgn in (1, -1):
                q = p + n_out * sgn * (lw * 0.55) + Vector((0, 0, 1.0))
                for dx in (-pr["width"] / 2 + lw * 0.5, pr["width"] / 2 - lw * 0.5):
                    t = Vector((math.cos(a), math.sin(a), 0.0)) * dx
                    hit = furn.find_nearest(q + t, lw * 0.45)
                    if hit[0]:
                        issues["doors"].append(f"{label}: furniture inside the leaf's swing "
                                               f"({'outside' if sgn > 0 else 'inside'})")
                        break
        if pr["height"] < 2.0 or pr["width"] < 0.75:
            issues["doors"].append(f"{label}: smaller than a person-sized doorway")

    # rooms: per camera
    every = solid + [o for o in scene["objs"] if o.get("nocol")] + ([other_boxes] if other_boxes else [])
    small_boxes = [boxes[id(o)] for s, o in scene["props"] if s["props"]["asset"] in CEILING_PROPS | WALL_PROPS | SMALL_PROPS]
    if small_boxes:
        every.append(_box_mesh(small_boxes, "SmallBoxes"))
    allv, all_mats = _bvh(every)
    for s in aset.sockets:
        if s["type"] != "camera" or not s["props"].get("label"):
            continue
        cam = Vector(s["pos"])
        tgt = Vector(s["props"]["target"])
        hu = arch.ray_cast(cam, Vector((0, 0, 1)), 30.0)
        hd = arch.ray_cast(cam, Vector((0, 0, -1)), 30.0)
        ceil_h = (hu[0].z - hd[0].z) if (hu[0] and hd[0]) else None
        fwd = (tgt - cam).normalized()
        right = fwd.cross(Vector((0, 0, 1))).normalized()
        up = right.cross(fwd).normalized()
        lens = s["props"].get("lens", 18.0)
        half_w = 18.0 / lens          # 36 mm sensor
        nx, ny = coverage_rays
        hits = detail = 0
        for i in range(nx):
            for j in range(ny):
                u = (i + 0.5) / nx * 2 - 1
                v = (j + 0.5) / ny * 2 - 1
                d = (fwd + right * u * half_w + up * v * half_w * ny / nx).normalized()
                h = allv.ray_cast(cam, d, 60.0)
                if h[0] is None:
                    continue
                hits += 1
                if not _is_bare(all_mats[h[2]]):
                    detail += 1
        cov = detail / hits if hits else 0.0
        issues["rooms"].append(dict(label=s["props"]["label"], ceiling=ceil_h, coverage=round(cov, 3)))
    return issues


def report(name, issues, log=print, limit=12):
    total = 0
    for k in ("grounding", "ceiling", "wall", "clipping", "doors"):
        lst = issues.get(k, [])
        total += len(lst)
        if lst:
            log(f"  [{k}] {len(lst)}")
            for line in lst[:limit]:
                log("     " + line)
            if len(lst) > limit:
                log(f"     ... {len(lst) - limit} more")
    rooms = issues.get("rooms", [])
    if rooms:
        log("  [rooms] label, ceiling height, detail coverage of the view")
        for r in sorted(rooms, key=lambda r: r["coverage"]):
            ch = f"{r['ceiling']:.2f} m" if r["ceiling"] else "  -   "
            flag = "  <-- bare" if r["coverage"] < 0.35 else ""
            log(f"     {r['label']:28s} {ch}  {100 * r['coverage']:4.0f} %{flag}")
    log(f"  {name}: {total} issues, {len(rooms)} rooms")
    return total
