"""Strips laid on the terrain: footpaths and other narrow surfaces drawn with the road material.

A strip is a ribbon draped over the ground as it is drawn (terrain.MeshField): its middle lies a few
centimetres above the highest ground under it and carries a coverage of 1, its two outer edges lie a hair
*under* the ground with coverage 0 - so, drawn with M_DA_Road (the terrain's own surface + a layer laid on by
vertex colour), the strip thins out into whatever the ground is and has no edge to see. The road ribbons
(layout.Layout.ribbon_sections) follow the same recipe; this module is the small general version.
"""

import math

LIFT = 0.03          # m the covered middle lies above the ground under it
RIM_LIFT = -0.015    # m at the outer edges (under the ground)


def resample(pts, step):
    """Points every `step` metres (or less) along a polyline, both ends kept."""
    out = [tuple(pts[0])]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        d = math.hypot(bx - ax, by - ay)
        n = max(1, int(math.ceil(d / step)))
        out += [(ax + (bx - ax) * k / n, ay + (by - ay) * k / n) for k in range(1, n + 1)]
    return out


def smooth(pts, rounds=2):
    """Chaikin corner cutting; the two ends stay where they are."""
    for _ in range(rounds):
        if len(pts) < 3:
            break
        out = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            out.append((ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25))
            out.append((ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75))
        out.append(pts[-1])
        pts = out
    return pts


def drape(ground, pts, width, rim=0.36, step=0.75, lift=LIFT, rim_lift=RIM_LIFT, tolerance=0.008, close_end=True):
    """Cross-sections of a strip along the polyline `pts`: [[(x, y, z, cover) x 5, left -> right], ...].

    ground: fn(x, y) -> height. The outer two vertices of a section are the rim (cover 0, rim_lift under
    the ground), the inner three are covered and stand `lift` above the highest ground within 20 cm. More
    sections go in wherever the ground bends away from an edge between two of them by more than
    `tolerance`. The start is open (covered across: it lies under a doorstep or a slab); the end is closed
    with the same rim - the last section is all rim, so the strip comes down into the ground it arrives on
    (a lane, a road's verge, another strip) - unless close_end is off."""
    line = resample(pts, step)
    n = len(line)
    hw = width / 2.0
    inner = max(hw - rim, hw * 0.4)
    arc = [0.0]
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        arc.append(arc[-1] + math.hypot(bx - ax, by - ay))

    def frame(s):
        i = 1
        while i < n - 1 and arc[i] < s:
            i += 1
        t = (s - arc[i - 1]) / max(arc[i] - arc[i - 1], 1e-9)
        x = line[i - 1][0] + (line[i][0] - line[i - 1][0]) * t
        y = line[i - 1][1] + (line[i][1] - line[i - 1][1]) * t
        j0, j1 = max(i - 2, 0), min(i + 1, n - 1)                 # tangent over a few points (smooth edges)
        tx, ty = line[j1][0] - line[j0][0], line[j1][1] - line[j0][1]
        d = math.hypot(tx, ty) or 1.0
        return x, y, -ty / d, tx / d

    def top(x, y):
        return max(ground(x + dx, y + dy) for dx, dy in ((0.0, 0.0), (0.2, 0.0), (-0.2, 0.0), (0.0, 0.2), (0.0, -0.2)))

    def section(s, rim_all=False):
        x, y, nx, ny = frame(s)
        row = []
        for f in (hw, inner, 0.0, -inner, -hw):
            px, py = x + nx * f, y + ny * f
            if abs(f) == hw or rim_all:
                row.append((px, py, ground(px, py) + rim_lift, 0.0))
            else:
                row.append((px, py, top(px, py) + lift, 1.0))
        return row

    def edge_error(ra, rb):
        worst = 0.0
        for c in (0, 4):
            for t in (0.25, 0.5, 0.75):
                x, y, z = (ra[c][k] + (rb[c][k] - ra[c][k]) * t for k in range(3))
                worst = max(worst, abs(z - ground(x, y) - rim_lift))
        return worst

    stations = list(arc)
    closed = close_end and arc[-1] > 3.0 * rim
    if closed:                                    # the last full section stands one rim width before the end
        stations = [s for s in stations if s < arc[-1] - rim - 0.2] + [arc[-1] - rim, arc[-1]]
    rows = [(s, section(s)) for s in stations]
    if closed:
        rows[-1] = (arc[-1], section(arc[-1], rim_all=True))
    for _ in range(3):
        fine, changed = [rows[0]], False
        for (sa, ra), (sb, rb) in zip(rows, rows[1:]):
            if sb - sa > 0.2 and edge_error(ra, rb) > tolerance:
                fine.append((0.5 * (sa + sb), section(0.5 * (sa + sb))))
                changed = True
            fine.append((sb, rb))
        rows = fine
        if not changed:
            break
    return [row for _s, row in rows]


def build(mb, rows, mat, color):
    """Add a draped strip to a MeshBuilder. color: fn(cover) -> (r, g, b, a) vertex colour."""
    for r0, r1 in zip(rows, rows[1:]):
        for c in range(len(r0) - 1):
            quad = (r0[c + 1], r1[c + 1], r1[c], r0[c])              # left -> right across: this faces up
            mb.cquad([q[:3] for q in quad], [color(q[3]) for q in quad], mat, smooth=True)
