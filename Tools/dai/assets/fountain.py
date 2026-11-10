"""
Fountain water shapes shared by the plaza and the Obelisk dorm fountains.

All of them go into a no-collision mesh with the flow materials (palette kind "flow", master
M_DA_WaterFlow). That master is world-aligned, so no UVs are needed: vertical faces stream along world Z
(falling sheets down, rising jets up - the sign of the material's FlowSpeed), horizontal faces churn.

  overflow_sheet  water spilling over a round lip: a ballistic (parabolic) curtain, not a straight drum
  jet_arc         round tapered jet on a real projectile path; the rising half uses the rising material,
                  the falling half the falling one, so the streaks run the way the water does
  foam_ring       churning white water where a sheet lands (flat annulus just above the pool surface)
  foam_patch      the same for one jet landing point
  jet_droplets    the droplet emitter of one jet (same projectile path as jet_arc)
"""

import math

G = 9.81
TAU = 2.0 * math.pi

WATER = "M_FountainWater"   # pools (single layer water, small fast ripples)
FALL = "M_FountainFall"     # falling sheets and the falling half of every jet
JET = "M_FountainJet"       # rising half of every jet
FOAM = "M_FountainFoam"     # churned water where it lands


def sheet_radius(r_lip, drop, v0):
    """Horizontal distance from the axis after falling `drop` m off a lip at r_lip with outward speed v0."""
    return r_lip + v0 * math.sqrt(2.0 * max(drop, 0.0) / G)


def overflow_sheet(mb, center, r_lip, z_lip, z_land, mat=FALL, seg=48, v0=0.55, rows=9):
    """Sheet of water rolling over a round lip at (r_lip, z_lip) and falling to z_land.
    Returns the radius where it lands (put the foam ring / spray there)."""
    cx, cy, cz = (tuple(center) + (0.0,))[:3]
    drop = z_lip - z_land
    prof = []
    for k in range(rows + 1):
        d = drop * (k / rows) ** 1.6        # denser rows near the lip, where the sheet bends most
        prof.append((sheet_radius(r_lip, d, v0), z_lip - d))
    prof.insert(0, (r_lip - 0.07, z_lip + 0.035))   # the water rolling over the lip
    prof.reverse()                                     # lathe profiles run bottom -> top
    mb.lathe(prof, mat, seg, cap_top=False, cap_bottom=False, center=(cx, cy, cz))
    return prof[0][0]


def _frame(d):
    """Two unit vectors perpendicular to direction d (side is horizontal unless d is vertical)."""
    dx, dy, dz = d
    sx, sy, sz = -dy, dx, 0.0
    n = math.sqrt(sx * sx + sy * sy)
    if n < 1e-6:
        sx, sy, sz, n = 1.0, 0.0, 0.0, 1.0
    sx, sy = sx / n, sy / n
    ux, uy, uz = sy * dz - sz * dy, sz * dx - sx * dz, sx * dy - sy * dx
    return (sx, sy, sz), (ux, uy, uz)


def jet_path(p0, p1, apex, n=14):
    """Points of a projectile path from p0 to p1 peaking `apex` m above p0, and the index of the apex
    (time-uniform sampling, so the samples crowd where the water slows down at the top)."""
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    vz = math.sqrt(2.0 * G * apex)
    t_up = vz / G
    za = z0 + apex
    t = t_up + math.sqrt(2.0 * max(za - z1, 0.0) / G)
    pts, ia = [], 0
    for k in range(n + 1):
        tk = t * k / n
        f = tk / t
        pts.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, z0 + vz * tk - 0.5 * G * tk * tk))
        if tk <= t_up + 1e-9:
            ia = k
    return pts, ia


def jet_arc(mb, p0, p1, apex, r0=0.06, r1=0.035, rise=JET, fall=FALL, n=14, sides=6):
    """Round water jet from nozzle p0 landing at p1 (apex m above p0), thinning from r0 to r1."""
    pts, ia = jet_path(p0, p1, apex, n)
    rows = []
    for k, p in enumerate(pts):
        a, b = pts[max(k - 1, 0)], pts[min(k + 1, n)]
        d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ln = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1.0
        s, u = _frame((d[0] / ln, d[1] / ln, d[2] / ln))
        r = r0 + (r1 - r0) * k / n
        rows.append([(p[0] + r * (math.cos(TAU * i / sides) * s[0] + math.sin(TAU * i / sides) * u[0]),
                      p[1] + r * (math.cos(TAU * i / sides) * s[1] + math.sin(TAU * i / sides) * u[1]),
                      p[2] + r * (math.cos(TAU * i / sides) * s[2] + math.sin(TAU * i / sides) * u[2]))
                     for i in range(sides)])
    ia = min(max(ia, 1), n - 1)
    mb.grid_faces(rows[:ia + 1], rise, smooth=True, closed_u=True)
    mb.grid_faces(rows[ia:], fall, smooth=True, closed_u=True)
    return pts[-1]


def foam_ring(mb, center, r_in, r_out, z, mat=FOAM, seg=48):
    """Flat annulus of churned water at height z (a few mm above the pool surface)."""
    cx, cy = center[0], center[1]
    mb.lathe([(r_out, z), (r_in, z)], mat, seg, cap_top=False, cap_bottom=False, center=(cx, cy, 0.0))


def foam_patch(mb, p, r, mat=FOAM, seg=12):
    mb.poly([(p[0] + math.cos(TAU * i / seg) * r, p[1] + math.sin(TAU * i / seg) * r, p[2]) for i in range(seg)], mat)


def jet_velocity(p0, p1, apex):
    """Initial velocity (m/s) of the projectile that leaves p0, peaks `apex` m above it and lands at p1 -
    the same path jet_arc models, for the droplet emitter that rides along it."""
    vz = math.sqrt(2.0 * G * apex)
    t = vz / G + math.sqrt(2.0 * max(p0[2] + apex - p1[2], 0.0) / G)
    return ((p1[0] - p0[0]) / t, (p1[1] - p0[1]) / t, vz)


def jet_droplets(aset, p0, p1, apex, scale=1.0, rate=1.0):
    """Droplets breaking away from one jet (ADAEmitter Jet): the solid arc is the coherent core of the stream,
    these are what it frays into on the way down."""
    aset.jet(p0, jet_velocity(p0, p1, apex), floor=p1[2], spread=2.5, scale=scale, rate=rate)
