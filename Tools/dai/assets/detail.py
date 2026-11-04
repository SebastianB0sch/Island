"""
Detail kit - the small things that make a room read as lived-in and real-world sized.

    from . import detail as DT
    DT.dress_room(aset, mb, nc, x0, y0, x1, y1, z, z_ceil, style="dorm", seed=3)

dress_room() looks up the door sockets on the room's four walls and adds, at real-world heights:
light switches beside every door (latch side, 1.1 m), outlets along the walls (0.3 m, every ~3 m), a smoke
detector, an air-conditioner on a wall without a door, and per style: sprinklers / vents / exit signs
(school, office, service), a thermostat, a calendar, ceiling rose (palace).

The other helpers add clutter on furniture and walls: shelf_fill, desk_set, table_set, floor_clutter,
coat_hooks (dorm jackets), blinds, radiator, trophy, deck_box, card_spread, duel_disk, mug, paper_stack,
book_stack. Small dressing goes into the no-collision mesh `nc`; catalog props (SM_Int_*) are placed as
sockets on `aset`. Room bounds are the INNER faces of the walls. Real sizes throughout (metres).
"""

import math
import random

from .. import palette
from . import interior as K

palette.register({
    "M_DetSwitch":   dict(kind="toon", color=(0.95, 0.94, 0.90), rough=0.5, fill=0.3),
    "M_DetSocket":   dict(kind="toon", color=(0.92, 0.91, 0.87), rough=0.5, fill=0.3),
    "M_DetSlot":     dict(kind="toon", color=(0.12, 0.12, 0.13), rough=0.6, fill=0.2),
    "M_DetExit":     dict(kind="emissive", color=(0.20, 0.90, 0.45), strength=4.0),
    "M_DetLed":      dict(kind="emissive", color=(1.00, 0.25, 0.20), strength=3.0),
    "M_DetGrille":   dict(kind="toon", color=(0.80, 0.81, 0.82), rough=0.4, fill=0.3),
    "M_DetMug1":     dict(kind="toon", color=(0.95, 0.35, 0.30), rough=0.3, fill=0.35),
    "M_DetMug2":     dict(kind="toon", color=(0.30, 0.55, 0.92), rough=0.3, fill=0.35),
    "M_DetMug3":     dict(kind="toon", color=(0.98, 0.85, 0.30), rough=0.3, fill=0.35),
    "M_DetCoffee":   dict(kind="toon", color=(0.30, 0.17, 0.08), rough=0.2, fill=0.2),
    "M_DetBlind":    dict(kind="toon", color=(0.93, 0.92, 0.88), rough=0.6, fill=0.35),
    "M_DetRadiator": dict(kind="toon", color=(0.94, 0.94, 0.92), rough=0.4, fill=0.3),
    "M_DetTrophy":   dict(kind="toon", color=(0.98, 0.78, 0.25), rough=0.25, metallic=0.8, fill=0.35),
    "M_DetSilver":   dict(kind="toon", color=(0.82, 0.84, 0.88), rough=0.25, metallic=0.8, fill=0.35),
    "M_DetJacketRed":    dict(kind="toon", color=(0.78, 0.10, 0.08), rough=0.85, fill=0.35, detail="Fabric", tiling=2.0, detail_strength=0.3),
    "M_DetJacketYellow": dict(kind="toon", color=(0.97, 0.80, 0.18), rough=0.85, fill=0.35, detail="Fabric", tiling=2.0, detail_strength=0.3),
    "M_DetJacketBlue":   dict(kind="toon", color=(0.13, 0.29, 0.72), rough=0.85, fill=0.35, detail="Fabric", tiling=2.0, detail_strength=0.3),
    "M_DetJacketWhite":  dict(kind="toon", color=(0.96, 0.96, 0.95), rough=0.85, fill=0.35, detail="Fabric", tiling=2.0, detail_strength=0.3),
    "M_DetDiskGrey":     dict(kind="toon", color=(0.62, 0.65, 0.70), rough=0.35, metallic=0.6, fill=0.3),
})

JACKETS = {"slifer": "M_DetJacketRed", "ra": "M_DetJacketYellow", "obelisk": "M_DetJacketBlue",
           "white": "M_DetJacketWhite"}
MUGS = ("M_DetMug1", "M_DetMug2", "M_DetMug3", "M_IntTrimWhite")
BOOKS = ("M_IntFabricRed", "M_IntFabricBlue", "M_IntFabricYellow", "M_IntFabricGreen", "M_IntFabricPurple",
         "M_IntFabricNavy", "M_IntFabricOrange", "M_IntWoodDark", "M_IntFabricWhite", "M_IntFabricPink")

STYLES = {
    # outlets, switch, smoke, ac, sprinklers, vents, exit, thermostat, calendar, rose
    "dorm":     dict(outlets=True, ac=True, smoke=True, calendar=True),
    "japanese": dict(outlets=True, ac=True, smoke=True, calendar=True),
    "school":   dict(outlets=True, ac=True, smoke=True, sprinklers=True, vents=True, exit=True, thermostat=True),
    "office":   dict(outlets=True, ac=True, smoke=True, sprinklers=True, vents=True, exit=True, thermostat=True, calendar=True),
    "service":  dict(outlets=True, smoke=True, sprinklers=True, vents=True, exit=True),
    "palace":   dict(outlets=True, smoke=True, rose=True),
    "ruin":     dict(),
}


def _P(x, y, yaw, dx, dy):
    a = math.radians(yaw)
    return (x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a))


# --------------------------------------------------------------------------- fixtures on a wall
def switch(nc, x, y, z, yaw, gang=2):
    """Light switch plate on a wall at (x, y) (wall face), local -Y into the room, centre height z."""
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.005, 0), (0.08 + 0.02 * gang, 0.01, 0.12), "M_DetSwitch")
        for k in range(gang):
            nc.box((-0.012 * (gang - 1) + 0.024 * k, -0.012, 0), (0.018, 0.006, 0.05), "M_DetSocket")


def outlet(nc, x, y, z, yaw):
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.005, 0), (0.08, 0.01, 0.12), "M_DetSocket")
        for dz in (-0.025, 0.025):
            nc.box((-0.012, -0.011, dz), (0.006, 0.003, 0.016), "M_DetSlot")
            nc.box((0.012, -0.011, dz), (0.006, 0.003, 0.016), "M_DetSlot")


def ac_unit(nc, x, y, z, yaw, w=0.85):
    """Wall-mounted split air conditioner (top at z)."""
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.12, -0.15), (w, 0.24, 0.29), "M_DetRadiator")
        nc.box((0, -0.245, -0.25), (w - 0.06, 0.01, 0.05), "M_DetGrille")
        nc.box((w / 2 - 0.08, -0.242, -0.06), (0.03, 0.005, 0.012), "M_DetExit")


def thermostat(nc, x, y, z, yaw):
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.012, 0), (0.09, 0.024, 0.12), "M_DetSwitch")
        nc.box((0, -0.025, 0.015), (0.06, 0.004, 0.04), "M_IntScreen")


def exit_sign(nc, aset, x, y, z, yaw):
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.04, 0), (0.36, 0.08, 0.16), "M_DetSwitch")
        nc.box((0, -0.081, 0), (0.32, 0.004, 0.12), "M_DetExit")
    aset.text("EXIT", K.wall_point(x, y, yaw, 0.09, z - 0.035), yaw, size=0.07, color=(1, 1, 1))


def calendar(nc, x, y, z, yaw, seed=0):
    rnd = random.Random(seed)
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.003, 0.0), (0.3, 0.006, 0.42), "M_IntPaper")
        nc.box((0, -0.007, 0.12), (0.28, 0.003, 0.16), rnd.choice(K.POSTERS))
        for r in range(4):
            for c in range(7):
                nc.box((-0.12 + c * 0.04, -0.0075, -0.03 - r * 0.04), (0.025, 0.002, 0.025),
                       "M_IntFabricRed" if (r * 7 + c) % 9 == 3 else "M_IntTrimWhite")


def ceiling_fixture(nc, x, y, z, kind):
    if kind == "smoke":
        nc.cylinder((x, y, z - 0.035), 0.065, 0.035, "M_DetSwitch", seg=12)
        nc.cylinder((x, y, z - 0.04), 0.012, 0.006, "M_DetLed", seg=6)
    elif kind == "sprinkler":
        nc.cylinder((x, y, z - 0.02), 0.03, 0.02, "M_DetSilver", seg=8)
        nc.cylinder((x, y, z - 0.06), 0.008, 0.04, "M_DetSilver", seg=6)
        nc.cylinder((x, y, z - 0.065), 0.025, 0.006, "M_DetSilver", seg=8)
    elif kind == "vent":
        nc.box((x, y, z - 0.01), (0.6, 0.6, 0.02), "M_DetGrille")
        for k in range(5):
            nc.box((x, y - 0.24 + k * 0.12, z - 0.022), (0.54, 0.02, 0.006), "M_DetSlot")
    elif kind == "rose":
        nc.cylinder((x, y, z - 0.03), 0.42, 0.03, "M_IntTrimWhite", seg=24)
        nc.cylinder((x, y, z - 0.05), 0.3, 0.02, "M_IntTrimGold", seg=24)
        nc.cylinder((x, y, z - 0.07), 0.16, 0.02, "M_IntTrimWhite", seg=16)


def radiator(mb, x, y, z, yaw, w=1.0, h=0.6):
    """Panel radiator under a window: (x, y) on the wall face, local -Y into the room."""
    with mb.at((x, y, z), rot=yaw):
        n = max(4, int(w / 0.07))
        for k in range(n):
            mb.box((-w / 2 + w * (k + 0.5) / n, -0.06, 0.15 + h / 2), (w / n * 0.7, 0.07, h), "M_DetRadiator")
        mb.box((0, -0.06, 0.15 + 0.03), (w, 0.08, 0.04), "M_DetRadiator")
        mb.box((0, -0.06, 0.15 + h - 0.03), (w, 0.08, 0.04), "M_DetRadiator")
        for s in (-1, 1):
            mb.box((s * (w / 2 - 0.05), -0.03, 0.08), (0.03, 0.03, 0.16), "M_DetSilver")


def blinds(nc, x, y, z0, z1, yaw, w, slats_open=0.55):
    """Venetian blinds hanging inside a window (x, y on the inner wall face), local -Y into the room."""
    h = z1 - z0
    drop = h * slats_open
    with nc.at((x, y, z1), rot=yaw):
        nc.box((0, -0.05, -0.03), (w + 0.06, 0.06, 0.06), "M_DetBlind")
        n = int(drop / 0.035)
        for k in range(n):
            nc.box((0, -0.05, -0.08 - k * 0.035), (w, 0.05, 0.005), "M_DetBlind")
        nc.box((0, -0.05, -0.08 - n * 0.035 - 0.01), (w + 0.02, 0.055, 0.02), "M_DetBlind")


# --------------------------------------------------------------------------- automatic room dressing
def _doors_on(aset, x0, y0, x1, y1, z, tol=0.45):
    """Door sockets whose plane lies on one of the room's walls (inner face within `tol`)."""
    out = []
    for s in aset.sockets:
        if s["type"] != "door":
            continue
        px, py, pz = s["pos"]
        if abs(pz - z) > 0.35:
            continue
        on = None
        if abs(py - y0) < tol and x0 - 0.1 < px < x1 + 0.1:
            on = "s"
        elif abs(py - y1) < tol and x0 - 0.1 < px < x1 + 0.1:
            on = "n"
        elif abs(px - x0) < tol and y0 - 0.1 < py < y1 + 0.1:
            on = "w"
        elif abs(px - x1) < tol and y0 - 0.1 < py < y1 + 0.1:
            on = "e"
        if on:
            out.append((on, px, py, s["props"]["width"]))
    return out


def dress_room(aset, mb, nc, x0, y0, x1, y1, z, z_ceil, style="dorm", seed=0, skip_walls=(), ac=None,
               outlet_spacing=3.2, keep_clear=()):
    """Fixtures every real room has (see module doc). Walls: 's' (y0), 'n' (y1), 'w' (x0), 'e' (x1).
    keep_clear: [(xa, ya, xb, yb)] wall spans where nothing may be mounted (built-ins, windows to the floor)."""
    st = STYLES.get(style, STYLES["dorm"])
    rnd = random.Random(seed)
    doors = _doors_on(aset, x0, y0, x1, y1, z)
    walls = {   # name: (start, end, yaw facing into the room, fixed coordinate)
        "s": ((x0, y0), (x1, y0), 180.0), "n": ((x1, y1), (x0, y1), 0.0),
        "w": ((x0, y1), (x0, y0), 90.0), "e": ((x1, y0), (x1, y1), -90.0),
    }

    def blocked(px, py, r=0.35):
        for on, dx, dy, w in doors:
            if math.hypot(px - dx, py - dy) < w / 2 + r:
                return True
        for xa, ya, xb, yb in keep_clear:
            if min(xa, xb) - r < px < max(xa, xb) + r and min(ya, yb) - r < py < max(ya, yb) + r:
                return True
        return False

    # switches on the latch side of each door (inside face)
    if st:
        for on, dx, dy, w in doors:
            (a, b, yaw) = walls[on]
            ux, uy = (b[0] - a[0]), (b[1] - a[1])
            L = math.hypot(ux, uy) or 1.0
            ux, uy = ux / L, uy / L
            for side in (1, -1):
                sx, sy = dx + ux * side * (w / 2 + 0.2), dy + uy * side * (w / 2 + 0.2)
                if x0 + 0.1 < sx < x1 - 0.1 or y0 + 0.1 < sy < y1 - 0.1:
                    px = min(max(sx, x0), x1) if on in "sn" else x0 if on == "w" else x1
                    py = (y0 if on == "s" else y1) if on in "sn" else min(max(sy, y0), y1)
                    if x0 + 0.15 <= px <= x1 - 0.15 or y0 + 0.15 <= py <= y1 - 0.15:
                        switch(nc, px, py, z + 1.15, yaw)
                        if st.get("thermostat") and side == 1:
                            thermostat(nc, *(_P(px, py, yaw, -0.25 * side, 0)), z + 1.45, yaw)
                        break
    # outlets
    if st.get("outlets"):
        for name, (a, b, yaw) in walls.items():
            if name in skip_walls:
                continue
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            n = max(1, int(L / outlet_spacing))
            for k in range(n):
                t = (k + 0.5) / n
                px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                if not blocked(px, py, 0.4):
                    outlet(nc, px, py, z + 0.3, yaw)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if st.get("smoke"):
        ceiling_fixture(nc, cx + 0.6, cy + 0.4, z_ceil, "smoke")
    if st.get("rose"):
        ceiling_fixture(nc, cx, cy, z_ceil, "rose")
    if st.get("sprinklers"):
        nx = max(1, int((x1 - x0) / 3.0))
        ny = max(1, int((y1 - y0) / 3.0))
        for i in range(nx):
            for j in range(ny):
                ceiling_fixture(nc, x0 + (x1 - x0) * (i + 0.5) / nx, y0 + (y1 - y0) * (j + 0.5) / ny, z_ceil, "sprinkler")
    if st.get("vents"):
        ceiling_fixture(nc, x0 + (x1 - x0) * 0.25, y0 + (y1 - y0) * 0.7, z_ceil, "vent")
        if (x1 - x0) * (y1 - y0) > 40:
            ceiling_fixture(nc, x0 + (x1 - x0) * 0.75, y0 + (y1 - y0) * 0.3, z_ceil, "vent")
    want_ac = st.get("ac") if ac is None else ac
    if want_ac:
        # the longest wall without a door
        cands = sorted(((math.hypot(b[0] - a[0], b[1] - a[1]), n) for n, (a, b, yaw) in walls.items()
                        if n not in skip_walls and not any(d[0] == n for d in doors)), reverse=True)
        if cands:
            n = cands[0][1]
            a, b, yaw = walls[n]
            px, py = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            if not blocked(px, py, 0.6):
                top = min(z_ceil - 0.12, z + 2.75)
                ac_unit(nc, px, py, top, yaw)
    if st.get("exit") and doors:
        on, dx, dy, w = doors[0]
        a, b, yaw = walls[on]
        ex = dx if on in "sn" else (x0 if on == "w" else x1)
        ey = dy if on in "ew" else (y0 if on == "s" else y1)
        exit_sign(nc, aset, ex, ey, min(z_ceil - 0.15, z + 2.45), yaw)
    if st.get("calendar") and any(n not in skip_walls for n in walls):
        names = [n for n in walls if n not in skip_walls]
        n = rnd.choice(names)
        a, b, yaw = walls[n]
        t = rnd.uniform(0.25, 0.75)
        px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        if not blocked(px, py, 0.5):
            calendar(nc, px, py, z + 1.55, yaw, seed)


# --------------------------------------------------------------------------- clutter (procedural, no collision)
def mug(nc, x, y, z, seed=0, coffee=True):
    rnd = random.Random(seed)
    m = rnd.choice(MUGS)
    nc.cylinder((x, y, z), 0.042, 0.095, m, seg=12, cap_top=not coffee)
    if coffee:
        nc.cylinder((x, y, z + 0.075), 0.038, 0.004, "M_DetCoffee", seg=12)
    nc.box((x + 0.05, y, z + 0.05), (0.02, 0.012, 0.05), m)


def paper_stack(nc, x, y, z, yaw=0.0, n=6, seed=0):
    rnd = random.Random(seed)
    for k in range(n):
        with nc.at((x + rnd.uniform(-0.01, 0.01), y + rnd.uniform(-0.01, 0.01), z + 0.002 + k * 0.004),
                   rot=yaw + rnd.uniform(-6, 6)):
            nc.box((0, 0, 0), (0.21, 0.297, 0.003), "M_IntPaper")


def book_stack(nc, x, y, z, yaw=0.0, n=4, seed=0):
    rnd = random.Random(seed)
    h = z
    for k in range(n):
        t = rnd.uniform(0.025, 0.05)
        with nc.at((x, y, h + t / 2), rot=yaw + rnd.uniform(-12, 12)):
            nc.box((0, 0, 0), (rnd.uniform(0.16, 0.24), rnd.uniform(0.22, 0.3), t), rnd.choice(BOOKS))
        h += t
    return h


def book_row(nc, x0, x1, y, z, depth=0.2, yaw=0.0, max_h=0.3, seed=0, gaps=0.12, lean=True):
    """Books standing on a shelf between x0..x1 (local to a frame at yaw about (x0, y))."""
    rnd = random.Random(seed)
    with nc.at((x0, y, z), rot=yaw):
        u, L = 0.0, x1 - x0
        while u < L - 0.03:
            if rnd.random() < gaps:
                u += rnd.uniform(0.04, 0.12)
                continue
            bw = rnd.uniform(0.022, 0.05)
            bh = min(max_h, rnd.uniform(0.17, 0.3))
            nc.box((u + bw / 2, 0, bh / 2), (bw, depth * rnd.uniform(0.75, 0.95), bh), rnd.choice(BOOKS))
            u += bw + 0.003
        if lean and L > 0.4:
            with nc.at((u + 0.02, 0, 0), rot_y=-18):
                nc.box((0.0, 0, 0.12), (0.03, depth * 0.85, 0.24), rnd.choice(BOOKS))


def shelf_fill(nc, aset, x, y, z_levels, yaw, width, depth, kind="books", seed=0):
    """Fill shelf boards (heights z_levels) of a unit centred at (x, y), back at local +Y, with real-size
    things: books, binders, boxes, jars, plants, trophies (kind: books | office | kitchen | decor | store)."""
    rnd = random.Random(seed)
    for i, z in enumerate(z_levels):
        x0l = -width / 2 + 0.03
        u = x0l
        while u < width / 2 - 0.08:
            pick = rnd.random()
            gx, gy = _P(x, y, yaw, u, 0.0)
            if kind in ("books", "office") and pick < 0.6:
                seg = rnd.uniform(0.25, 0.55)
                book_row(nc, *(_P(x, y, yaw, u, 0.0)), z, depth * 0.8, yaw, seed=seed * 31 + i * 7 + int(u * 100))
                u += seg
            elif kind == "kitchen" and pick < 0.5:
                for k in range(rnd.randint(2, 4)):
                    px, py = _P(x, y, yaw, u + 0.05 + k * 0.1, 0.0)
                    nc.cylinder((px, py, z), 0.045, rnd.uniform(0.1, 0.18), rnd.choice(MUGS + ("M_IntGlassClear",)), seg=10)
                u += 0.45
            elif kind == "store" and pick < 0.7:
                bw = rnd.uniform(0.3, 0.5)
                bh = rnd.uniform(0.2, 0.35)
                px, py = _P(x, y, yaw, u + bw / 2, 0.0)
                with nc.at((px, py, z + bh / 2), rot=yaw + rnd.uniform(-4, 4)):
                    nc.box((0, 0, 0), (bw, depth * 0.85, bh), "M_ShopShelf")
                    nc.box((0, -depth * 0.43, bh * 0.1), (bw * 0.5, 0.004, bh * 0.25), "M_IntPaper")
                u += bw + 0.03
            elif pick < 0.75:
                px, py = _P(x, y, yaw, u + 0.1, 0.0)
                aset.prop(rnd.choice(("SM_Int_VaseB", "SM_Int_PhotoFrame", "SM_Int_PottedPlant", "SM_Int_Candlestick",
                                      "SM_Int_HorseStatue", "SM_Int_AlarmClock") if kind != "kitchen" else
                                     ("SM_Int_Jug", "SM_Int_Pot", "SM_Int_Bowl", "SM_Int_EnamelPot")),
                          (px, py, z), yaw + rnd.uniform(-20, 20))
                u += 0.32
            elif kind == "office" and pick < 0.9:
                px, py = _P(x, y, yaw, u + 0.15, 0.0)
                for k in range(rnd.randint(3, 6)):
                    qx, qy = _P(x, y, yaw, u + 0.02 + k * 0.06, 0.0)
                    nc.box((qx, qy, z + 0.16), (0.05, depth * 0.85, 0.32), rnd.choice(("M_IntFabricBlue", "M_IntFabricRed",
                                                                                      "M_IntTrimWhite", "M_IntFabricYellow")))
                u += 0.42
            else:
                px, py = _P(x, y, yaw, u + 0.12, 0.0)
                book_stack(nc, px, py, z, yaw, rnd.randint(2, 5), seed + i * 13 + int(u * 77))
                u += 0.3


def desk_set(nc, aset, x, y, z, yaw, kind="student", seed=0, w=1.1, d=0.6):
    """Things on a desk top at height z, desk centred at (x, y), user side local -Y.
    kind: student | office | teacher | vanity | reception | gamer."""
    rnd = random.Random(seed)

    def P(dx, dy):
        return _P(x, y, yaw, dx, dy)
    if kind in ("student", "teacher", "office", "reception"):
        if rnd.random() < 0.55 or kind == "office":
            px, py = P(0.0, 0.05)
            aset.prop("SM_Int_Laptop", (px, py, z), yaw + 180 + rnd.uniform(-8, 8))
        else:
            px, py = P(-0.05, -0.05)
            aset.prop("SM_Int_Binder", (px, py, z), yaw + rnd.uniform(-10, 10))
        px, py = P(w / 2 - 0.15, d / 2 - 0.12)
        aset.prop("SM_Int_Stationery", (px, py, z), yaw + 180)
        px, py = P(-w / 2 + 0.2, d / 2 - 0.15)
        aset.prop("SM_Int_DeskLamp", (px, py, z), yaw + 160)
        px, py = P(w / 2 - 0.25, -d / 2 + 0.18)
        mug(nc, px, py, z, seed)
        px, py = P(-w / 2 + 0.25, -d / 2 + 0.2)
        paper_stack(nc, px, py, z, yaw, rnd.randint(3, 8), seed)
        if kind == "student":
            px, py = P(0.25, -0.1)
            deck_box(nc, px, py, z, yaw + rnd.uniform(-30, 30), rnd.choice(("M_IntFabricRed", "M_IntFabricBlue",
                                                                            "M_IntFabricYellow", "M_IntWoodDark")))
            px, py = P(-0.3, 0.15)
            book_stack(nc, px, py, z, yaw, 3, seed + 1)
        if kind in ("teacher", "office", "reception"):
            px, py = P(-0.35, 0.1)
            aset.prop("SM_Int_Clipboard", (px, py, z), yaw + rnd.uniform(-15, 15))
            px, py = P(0.4, 0.02)
            aset.prop("SM_Int_Stapler", (px, py, z), yaw + 200)
        if kind == "reception":
            px, py = P(-0.45, -0.15)
            aset.prop("SM_Int_Notepads", (px, py, z), yaw)
    elif kind == "vanity":
        for k in range(5):
            px, py = P(-0.3 + k * 0.12, d / 2 - 0.12)
            nc.cylinder((px, py, z), 0.025, rnd.uniform(0.06, 0.14), rnd.choice(("M_IntFabricPink", "M_IntGlassClear",
                                                                                "M_IntTrimGold", "M_IntFabricPurple")), seg=8)
        px, py = P(0.3, -0.05)
        aset.prop("SM_Int_VaseB", (px, py, z), yaw)
    elif kind == "gamer":
        px, py = P(0.0, 0.1)
        aset.prop("SM_Int_TVB", (px, py, z), yaw + 180)
        px, py = P(0.25, -0.2)
        aset.prop("SM_Int_Gamepad", (px, py, z), yaw + rnd.uniform(-20, 20))
        px, py = P(-0.3, -0.15)
        mug(nc, px, py, z, seed + 2)


def table_set(nc, aset, x, y, z, yaw, kind="tea", seats=4, seed=0, length=1.2):
    """Table-top settings at height z: tea | dining | cafe | kitchen | banquet."""
    rnd = random.Random(seed)

    def P(dx, dy):
        return _P(x, y, yaw, dx, dy)
    if kind == "tea":
        aset.prop("SM_Int_TeaSet", (x, y, z), yaw + rnd.uniform(-15, 15))
        px, py = P(0.25, 0.15)
        aset.prop("SM_Int_Cake", (px, py, z), rnd.uniform(0, 360))
    elif kind in ("dining", "banquet", "cafe"):
        per = max(1, seats // 2)
        for i in range(per):
            dx = -length / 2 + length * (i + 0.5) / per
            for s in (-1, 1):
                px, py = P(dx, s * 0.28)
                nc.cylinder((px, py, z), 0.13, 0.012, "M_IntTrimWhite", seg=16)
                if kind == "banquet":
                    nc.cylinder((px, py, z + 0.012), 0.09, 0.006, "M_IntTrimGold", seg=16)
                    qx, qy = P(dx + 0.17, s * 0.22)
                    nc.cylinder((qx, qy, z), 0.03, 0.16, "M_IntGlassClear", seg=8)
                else:
                    qx, qy = P(dx + 0.16, s * 0.24)
                    mug(nc, qx, qy, z, seed + i * 2 + (s > 0), coffee=kind == "cafe")
                for side in (-1, 1):
                    qx, qy = P(dx + side * 0.17, s * 0.29)
                    nc.box((qx, qy, z + 0.006), (0.015, 0.17, 0.006), "M_DetSilver")
        cx, cy = P(0, 0)
        if kind == "banquet":
            aset.prop("SM_Int_Candelabra", (cx, cy, z), yaw)
            for d in (-length * 0.3, length * 0.3):
                qx, qy = P(d, 0)
                aset.prop("SM_Int_Goblets", (qx, qy, z), yaw)
        else:
            aset.prop(rnd.choice(("SM_Int_VaseB", "SM_Int_Bowl", "SM_Int_Jug")), (cx, cy, z), rnd.uniform(0, 360))
    elif kind == "kitchen":
        aset.prop("SM_Int_CuttingBoard", (x, y, z), yaw + rnd.uniform(-10, 10))
        px, py = P(0.35, 0.1)
        aset.prop("SM_Int_Bowl", (px, py, z), 0)
        for k in range(3):
            qx, qy = P(0.3 + k * 0.06, 0.12)
            aset.prop("SM_Int_Apple", (qx, qy, z + 0.035), rnd.uniform(0, 360))
        px, py = P(-0.4, 0.15)
        aset.prop("SM_Int_Bananas", (px, py, z), yaw + rnd.uniform(-30, 30))


def floor_clutter(nc, aset, x0, y0, x1, y1, z, kind="dorm", n=6, seed=0, clear=()):
    """Things along the walls of a room: bags, shoes, boxes, a guitar, balls ... (keeps `clear` rects free)."""
    rnd = random.Random(seed)
    cands = {"dorm": ("bag", "shoes", "box", "ball", "ukulele", "bat", "laundry"),
             "store": ("box", "box", "crate", "broom"),
             "office": ("box", "bin", "bag"),
             "ruin": ("plank", "box", "papers")}[kind]
    for k in range(n):
        side = rnd.choice("snwe")
        if side in "sn":
            px, py = rnd.uniform(x0 + 0.4, x1 - 0.4), (y0 + 0.25 if side == "s" else y1 - 0.25)
            yaw = 0.0 if side == "s" else 180.0
        else:
            px, py = (x0 + 0.25 if side == "w" else x1 - 0.25), rnd.uniform(y0 + 0.4, y1 - 0.4)
            yaw = 90.0 if side == "w" else -90.0
        if any(a - 0.5 < px < c + 0.5 and b - 0.5 < py < d + 0.5 for a, b, c, d in clear):
            continue
        what = rnd.choice(cands)
        if what == "bag":
            with nc.at((px, py, z), rot=yaw + rnd.uniform(-20, 20)):
                c = rnd.choice(("M_IntFabricNavy", "M_IntFabricRed", "M_IntWoodDark", "M_IntFabricGreen"))
                nc.box((0, 0, 0.17), (0.34, 0.16, 0.34), c)
                nc.box((0, -0.09, 0.12), (0.26, 0.03, 0.16), c)
                nc.box((0, 0, 0.37), (0.12, 0.03, 0.06), c)
        elif what == "shoes":
            with nc.at((px, py, z), rot=yaw + rnd.uniform(-25, 25)):
                c = rnd.choice(("M_IntFabricRed", "M_IntFabricWhite", "M_IntBlack"))
                for s in (-1, 1):
                    nc.box((s * 0.065, 0, 0.04), (0.1, 0.27, 0.08), c)
        elif what == "box":
            aset.prop("SM_Int_Box", (px, py, z), yaw + rnd.uniform(-15, 15))
        elif what == "crate":
            aset.prop("SM_Crate", (px, py, z), yaw + rnd.uniform(-10, 10), 0.6)
        elif what == "ball":
            aset.prop("SM_Int_Ball", (px, py, z), rnd.uniform(0, 360))
        elif what == "ukulele":
            aset.prop("SM_Int_Ukulele", (px, py, z), yaw)
        elif what == "bat":
            aset.prop("SM_Int_BaseballBat", (px, py, z), yaw)
        elif what == "broom":
            aset.prop("SM_Int_Broom", (px, py, z), yaw)
        elif what == "bin":
            nc.cylinder((px, py, z), 0.16, 0.34, "M_IntSteelBlue", seg=12, cap_top=False)
        elif what == "laundry":
            nc.cylinder((px, py, z), 0.22, 0.42, "M_IntWood", seg=10)
            nc.sphere((px, py, z + 0.42), 0.18, rnd.choice(("M_IntFabricWhite", "M_IntFabricBlue")), seg=8, rings=5)
        elif what == "papers":
            paper_stack(nc, px, py, z, rnd.uniform(0, 90), 3, seed + k)
        elif what == "plank":
            with nc.at((px, py, z + 0.03), rot=rnd.uniform(0, 180)):
                nc.box((0, 0, 0), (1.4, 0.16, 0.03), "M_RottenWood")


def coat_hooks(nc, x, y, z, yaw, n=4, dorm="slifer", jackets=None, seed=0):
    """Hook rail on a wall at (x, y), height z, local -Y into the room; some hooks carry a dorm jacket."""
    rnd = random.Random(seed)
    jackets = n // 2 + 1 if jackets is None else jackets
    w = n * 0.25
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.01, 0), (w, 0.02, 0.09), "M_IntWood")
        for k in range(n):
            u = -w / 2 + 0.125 + k * 0.25
            nc.box((u, -0.05, 0.0), (0.02, 0.07, 0.02), "M_DetSilver")
            if k < jackets:
                m = JACKETS.get(dorm, "M_DetJacketRed")
                nc.box((u, -0.07, -0.33), (0.38, 0.07, 0.62), m)
                nc.box((u, -0.075, -0.06), (0.16, 0.06, 0.1), "M_DetJacketWhite")
                for s in (-1, 1):
                    nc.box((u + s * 0.22, -0.07, -0.32), (0.08, 0.06, 0.56), m)


def trophy(nc, x, y, z, s=1.0, mat="M_DetTrophy"):
    nc.box((x, y, z + 0.03 * s), (0.12 * s, 0.12 * s, 0.06 * s), "M_IntWoodDark")
    nc.cylinder((x, y, z + 0.06 * s), 0.015 * s, 0.12 * s, mat, seg=8)
    nc.lathe([(0.02 * s, 0.0), (0.07 * s, 0.03 * s), (0.08 * s, 0.1 * s), (0.075 * s, 0.13 * s)], mat, seg=12,
             cap_bottom=True, cap_top=False, center=(x, y, z + 0.18 * s))
    for sd in (-1, 1):
        nc.torus((x + sd * 0.085 * s, y, z + 0.26 * s), 0.025 * s, 0.006 * s, mat, seg=10, tube_seg=4)


def deck_box(nc, x, y, z, yaw, mat="M_IntFabricRed"):
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, 0, 0.035), (0.075, 0.095, 0.07), mat)
        nc.box((0, 0, 0.071), (0.077, 0.097, 0.004), "M_IntTrimGold")


def card_spread(nc, x, y, z, yaw, n=5, seed=0):
    rnd = random.Random(seed)
    for k in range(n):
        with nc.at((x + (k - n / 2) * 0.065, y + rnd.uniform(-0.02, 0.02), z + 0.001 + k * 0.0005),
                   rot=yaw + rnd.uniform(-10, 10)):
            nc.box((0, 0, 0), (0.059, 0.086, 0.001), "M_CardBack")


def duel_disk(nc, x, y, z, yaw):
    """A duel disk lying on a surface (blade folded along local x)."""
    with nc.at((x, y, z), rot=yaw):
        nc.cylinder((0, 0, 0), 0.11, 0.06, "M_DetDiskGrey", seg=16)
        nc.cylinder((0, 0, 0.06), 0.06, 0.01, "M_IntScreen", seg=12)
        nc.box((0.3, 0.0, 0.025), (0.42, 0.13, 0.03), "M_DetDiskGrey")
        for k in range(5):
            nc.box((0.13 + k * 0.08, 0.0, 0.042), (0.06, 0.09, 0.004), "M_DetSlot")
