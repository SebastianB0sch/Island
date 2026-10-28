"""
MeshBuilder - a small procedural modelling kit on top of bpy.

All dimensions are metres. Primitives are appended in *local* space and
transformed by the current transform stack (see `MeshBuilder.at`). Every face
carries a palette material name; `build()` turns the accumulated data into a
Blender mesh object with box-projected UVs (1 UV unit = 1 metre) and material
slots named exactly like the palette entries, which is what the Unreal import
keys on.

Faces are never welded between primitives, so flat-shaded boxes stay crisp and
smooth surfaces (lathe/cylinder sides) smooth only among themselves.
"""

import math
from contextlib import contextmanager

import bpy
from mathutils import Matrix, Vector

from . import blend

TAU = math.pi * 2.0


def _v(p):
    return Vector((float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0))


class MeshBuilder:
    def __init__(self, name="Mesh"):
        self.name = name
        self.verts = []        # list[Vector]
        self.faces = []        # list[tuple[int]]
        self.face_mats = []    # list[str]
        self.face_smooth = []  # list[bool]
        self._stack = [Matrix.Identity(4)]

    # ------------------------------------------------------------------ transforms
    @property
    def matrix(self):
        return self._stack[-1]

    @contextmanager
    def at(self, offset=(0, 0, 0), rot=0.0, scale=1.0, rot_x=0.0, rot_y=0.0):
        """Push a local transform: translate, then rotate (degrees about Z, Y, X), then scale."""
        if isinstance(scale, (int, float)):
            scale = (scale, scale, scale)
        m = (Matrix.Translation(_v(offset))
             @ Matrix.Rotation(math.radians(rot), 4, "Z")
             @ Matrix.Rotation(math.radians(rot_y), 4, "Y")
             @ Matrix.Rotation(math.radians(rot_x), 4, "X")
             @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0)))
        self._stack.append(self.matrix @ m)
        try:
            yield self
        finally:
            self._stack.pop()

    def _add_vert(self, p):
        self.verts.append(self.matrix @ _v(p))
        return len(self.verts) - 1

    # ------------------------------------------------------------------ low level
    def poly(self, pts, mat, smooth=False, flip=False):
        """Add a single n-gon from local points (counter-clockwise seen from the front)."""
        if flip:
            pts = list(reversed(pts))
        idx = [self._add_vert(p) for p in pts]
        self.faces.append(tuple(idx))
        self.face_mats.append(mat)
        self.face_smooth.append(smooth)

    def quad(self, a, b, c, d, mat, smooth=False):
        self.poly([a, b, c, d], mat, smooth)

    def grid_faces(self, rows, mat, smooth=True, closed_u=False, flip=False):
        """rows: list of rows of points (v-major). Builds quads between consecutive rows."""
        nv = len(rows)
        nu = len(rows[0])
        base = len(self.verts)
        for row in rows:
            for p in row:
                self._add_vert(p)
        ucount = nu if closed_u else nu - 1
        for j in range(nv - 1):
            for i in range(ucount):
                i2 = (i + 1) % nu
                a = base + j * nu + i
                b = base + j * nu + i2
                c = base + (j + 1) * nu + i2
                d = base + (j + 1) * nu + i
                f = (a, b, c, d) if not flip else (d, c, b, a)
                self.faces.append(f)
                self.face_mats.append(mat)
                self.face_smooth.append(smooth)

    # ------------------------------------------------------------------ boxes
    def box(self, center, size, mat, skip=(), mats=None):
        """Axis aligned (in local space) box. skip: subset of {'+x','-x','+y','-y','+z','-z'}.
        mats: optional dict side->material overriding `mat`."""
        cx, cy, cz = center
        sx, sy, sz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
        x0, x1, y0, y1, z0, z1 = cx - sx, cx + sx, cy - sy, cy + sy, cz - sz, cz + sz
        sides = {
            "+z": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
            "-z": [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
            "-y": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            "+y": [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)],
            "+x": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
            "-x": [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)],
        }
        for k, pts in sides.items():
            if k in skip:
                continue
            m = mats.get(k, mat) if mats else mat
            self.poly(pts, m)

    def box_mm(self, mn, mx, mat, skip=(), mats=None):
        c = ((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2)
        s = (mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2])
        self.box(c, s, mat, skip, mats)

    def beam(self, p0, p1, w, h, mat):
        """Box of cross-section w x h stretched between two points (any direction)."""
        p0, p1 = _v(p0), _v(p1)
        d = p1 - p0
        length = d.length
        if length < 1e-6:
            return
        yaw = math.degrees(math.atan2(d.y, d.x))
        pitch = -math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
        with self.at(p0, rot=yaw, rot_y=pitch):
            self.box((length / 2, 0, 0), (length, w, h), mat)

    # ------------------------------------------------------------------ revolved shapes
    def lathe(self, profile, mat, seg=24, cap_top=True, cap_bottom=True, center=(0, 0, 0),
              smooth=True, angle0=0.0, cap_mat=None, sx=1.0, sy=1.0):
        """Revolve [(radius, z), ...] (bottom to top) around the local Z axis."""
        cx, cy, cz = center
        rows = []
        for r, z in profile:
            row = []
            for i in range(seg):
                a = angle0 + TAU * i / seg
                row.append((cx + math.cos(a) * r * sx, cy + math.sin(a) * r * sy, cz + z))
            rows.append(row)
        self.grid_faces(rows, mat, smooth=smooth, closed_u=True)
        cm = cap_mat or mat
        if cap_bottom and profile[0][0] > 1e-4:
            self.poly(list(reversed(rows[0])), cm)
        if cap_top and profile[-1][0] > 1e-4:
            self.poly(rows[-1], cm)

    def cylinder(self, base, radius, height, mat, seg=16, radius_top=None, cap_top=True,
                 cap_bottom=True, smooth=True, cap_mat=None, angle0=0.0):
        rt = radius if radius_top is None else radius_top
        self.lathe([(radius, 0.0), (rt, height)], mat, seg, cap_top, cap_bottom, base, smooth,
                   angle0=angle0, cap_mat=cap_mat)

    def cone(self, base, radius, height, mat, seg=16, smooth=True, cap_bottom=True):
        cx, cy, cz = base
        ring = [(cx + math.cos(TAU * i / seg) * radius, cy + math.sin(TAU * i / seg) * radius, cz)
                for i in range(seg)]
        apex = (cx, cy, cz + height)
        for i in range(seg):
            self.poly([ring[i], ring[(i + 1) % seg], apex], mat, smooth)
        if cap_bottom:
            self.poly(list(reversed(ring)), mat)

    def sphere(self, center, radius, mat, seg=16, rings=10, hemi=False, scale=(1, 1, 1), smooth=True):
        prof = []
        lo = 0 if hemi else -rings // 2
        n = rings // 2 if hemi else rings // 2
        for j in range(lo, n + 1):
            phi = (math.pi / 2) * j / (rings // 2)
            prof.append((math.cos(phi) * radius, math.sin(phi) * radius))
        # avoid zero radius rows for clean quads: nudge poles slightly
        prof = [(max(r, radius * 0.001), z) for r, z in prof]
        cx, cy, cz = center
        rows = []
        for r, z in prof:
            rows.append([(cx + math.cos(TAU * i / seg) * r * scale[0],
                          cy + math.sin(TAU * i / seg) * r * scale[1],
                          cz + z * scale[2]) for i in range(seg)])
        self.grid_faces(rows, mat, smooth=smooth, closed_u=True)
        if hemi:
            self.poly(list(reversed(rows[0])), mat)

    def torus(self, center, major, minor, mat, seg=24, tube_seg=8):
        cx, cy, cz = center
        rows = []
        for j in range(tube_seg + 1):
            b = TAU * j / tube_seg
            r = major + math.cos(b) * minor
            z = math.sin(b) * minor
            rows.append([(cx + math.cos(TAU * i / seg) * r, cy + math.sin(TAU * i / seg) * r, cz + z)
                         for i in range(seg)])
        self.grid_faces(rows, mat, smooth=True, closed_u=True)

    # ------------------------------------------------------------------ extrusions
    def prism(self, poly2d, z0, z1, mat, cap_top=True, cap_bottom=True, top_mat=None, smooth=False):
        """Vertical extrusion of a CCW 2D polygon."""
        n = len(poly2d)
        for i in range(n):
            a = poly2d[i]
            b = poly2d[(i + 1) % n]
            self.poly([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], mat, smooth)
        if cap_top:
            self.poly([(p[0], p[1], z1) for p in poly2d], top_mat or mat)
        if cap_bottom:
            self.poly([(p[0], p[1], z0) for p in reversed(poly2d)], mat)

    def slab_ring(self, outer, inner, z0, z1, mat):
        """Annular slab between two concentric CCW polygons with the same vertex count."""
        n = len(outer)
        for i in range(n):
            j = (i + 1) % n
            o0, o1, i0, i1 = outer[i], outer[j], inner[i], inner[j]
            self.quad((o0[0], o0[1], z1), (o1[0], o1[1], z1), (i1[0], i1[1], z1), (i0[0], i0[1], z1), mat)
            self.quad((i0[0], i0[1], z0), (i1[0], i1[1], z0), (o1[0], o1[1], z0), (o0[0], o0[1], z0), mat)
            self.quad((o0[0], o0[1], z0), (o1[0], o1[1], z0), (o1[0], o1[1], z1), (o0[0], o0[1], z1), mat)
            self.quad((i1[0], i1[1], z0), (i0[0], i0[1], z0), (i0[0], i0[1], z1), (i1[0], i1[1], z1), mat)

    # ------------------------------------------------------------------ roofs
    def gable_roof(self, center, w, d, h, mat, overhang=0.6, thick=0.25, gable_mat=None, ridge_axis="x"):
        """Pitched roof over a w (x) by d (y) rectangle; ridge along x by default.
        `center` is the eave-level centre. gable_mat fills the triangular end walls."""
        cx, cy, cz = center
        if ridge_axis == "y":
            with self.at((cx, cy, cz), rot=90):
                self.gable_roof((0, 0, 0), d, w, h, mat, overhang, thick, gable_mat, "x")
            return
        hw, hd = w / 2 + overhang, d / 2 + overhang
        slope_drop = h * overhang / (d / 2) if d > 0 else 0
        z_e = cz - slope_drop
        top = cz + h
        # two roof planes (with thickness)
        for s in (-1, 1):
            a = (cx - hw, cy + s * hd, z_e)
            b = (cx + hw, cy + s * hd, z_e)
            r1 = (cx + hw, cy, top)
            r0 = (cx - hw, cy, top)
            if s < 0:
                self.quad(a, b, r1, r0, mat)
                self.quad((a[0], a[1], a[2] - thick), (r0[0], r0[1], r0[2] - thick),
                          (r1[0], r1[1], r1[2] - thick), (b[0], b[1], b[2] - thick), mat)
            else:
                self.quad(b, a, r0, r1, mat)
                self.quad((b[0], b[1], b[2] - thick), (r1[0], r1[1], r1[2] - thick),
                          (r0[0], r0[1], r0[2] - thick), (a[0], a[1], a[2] - thick), mat)
            # eave edge
            self.quad((a[0], a[1], a[2] - thick), (b[0], b[1], b[2] - thick), b, a, mat) if s < 0 else \
                self.quad((b[0], b[1], b[2] - thick), (a[0], a[1], a[2] - thick), a, b, mat)
        # verge (gable edges)
        for sx in (-1, 1):
            x = cx + sx * hw
            pts = [(x, cy - hd, z_e), (x, cy, top), (x, cy + hd, z_e)]
            low = [(p[0], p[1], p[2] - thick) for p in pts]
            if sx > 0:
                self.quad(low[0], low[1], pts[1], pts[0], mat)
                self.quad(low[1], low[2], pts[2], pts[1], mat)
            else:
                self.quad(pts[0], pts[1], low[1], low[0], mat)
                self.quad(pts[1], pts[2], low[2], low[1], mat)
        # gable walls (triangles at the actual wall line)
        if gable_mat:
            for sx in (-1, 1):
                x = cx + sx * w / 2
                tri = [(x, cy - d / 2, cz), (x, cy + d / 2, cz), (x, cy, cz + h - thick)]
                self.poly(tri if sx > 0 else list(reversed(tri)), gable_mat)

    def hip_roof(self, center, w, d, h, mat, overhang=0.6, ridge_frac=None, thick=0.25):
        """Hipped roof. ridge_frac: ridge length as fraction of (w-d); 0 -> pyramid."""
        cx, cy, cz = center
        if d > w:
            # keep the ridge along the long side
            with self.at((cx, cy, cz), rot=90):
                self.hip_roof((0, 0, 0), d, w, h, mat, overhang, ridge_frac, thick)
            return
        hw, hd = w / 2 + overhang, d / 2 + overhang
        if ridge_frac is None:
            ridge = max(0.0, (w - d) / 2)
        else:
            ridge = max(0.0, (w - d) / 2 * ridge_frac)
        drop = h * overhang / max(min(w, d) / 2, 0.1)
        ze = cz - drop
        top = cz + h
        a, b, c, e = (cx - hw, cy - hd, ze), (cx + hw, cy - hd, ze), (cx + hw, cy + hd, ze), (cx - hw, cy + hd, ze)
        r0, r1 = (cx - ridge, cy, top), (cx + ridge, cy, top)
        if ridge > 1e-3:
            self.poly([a, b, r1, r0], mat)
            self.poly([c, e, r0, r1], mat)
        else:
            self.poly([a, b, r1], mat)
            self.poly([c, e, r0], mat)
        self.poly([b, c, r1], mat)
        self.poly([e, a, r0], mat)
        # underside + fascia
        lo = lambda p: (p[0], p[1], p[2] - thick)
        self.poly([lo(a), lo(e), lo(c), lo(b)], mat)
        for p, q in ((a, b), (b, c), (c, e), (e, a)):
            self.quad(lo(p), lo(q), q, p, mat)

    def pyramid(self, center, w, d, h, mat, base=True):
        cx, cy, cz = center
        a, b, c, e = (cx - w / 2, cy - d / 2, cz), (cx + w / 2, cy - d / 2, cz), (cx + w / 2, cy + d / 2, cz), (cx - w / 2, cy + d / 2, cz)
        t = (cx, cy, cz + h)
        for p, q in ((a, b), (b, c), (c, e), (e, a)):
            self.poly([p, q, t], mat)
        if base:
            self.poly([e, c, b, a], mat)

    def stepped_pyramid(self, center, w, d, steps, step_h, inset, mat):
        cx, cy, cz = center
        for i in range(steps):
            ww, dd = w - 2 * inset * i, d - 2 * inset * i
            if ww <= 0 or dd <= 0:
                break
            self.box((cx, cy, cz + step_h * (i + 0.5)), (ww, dd, step_h), mat)

    # ------------------------------------------------------------------ walls
    def wall(self, p0, p1, z0, height, thick, mat, openings=(), inner_mat=None, cap_mat=None):
        """Straight wall from p0 to p1 (2D) with rectangular openings.
        openings: iterable of dict(u=centre distance from p0, w=width, z0=bottom (rel), z1=top (rel),
                  glass=material or None, frame=material or None)
        The wall's outward side is to the RIGHT of p0->p1 (i.e. walls listed CCW face outwards)."""
        p0, p1 = _v(p0), _v(p1)
        d = p1 - p0
        length = d.length
        if length < 1e-4:
            return
        yaw = math.degrees(math.atan2(d.y, d.x))
        ops = sorted([dict(o) for o in openings], key=lambda o: o["u"])
        with self.at((p0.x, p0.y, z0), rot=yaw):
            # local: x along wall, y: +y inside (left), -y outside (right), z up
            t = thick
            def piece(u0, u1, v0, v1):
                if u1 - u0 < 1e-4 or v1 - v0 < 1e-4:
                    return
                self.box(((u0 + u1) / 2, t / 2, (v0 + v1) / 2), (u1 - u0, t, v1 - v0), mat,
                         mats={"+y": inner_mat} if inner_mat else None)
            u = 0.0
            for o in ops:
                ou0, ou1 = o["u"] - o["w"] / 2, o["u"] + o["w"] / 2
                ou0, ou1 = max(ou0, 0.0), min(ou1, length)
                piece(u, ou0, 0.0, height)                 # solid part before opening
                piece(ou0, ou1, 0.0, o.get("z0", 0.0))      # below opening
                piece(ou0, ou1, o["z1"], height)            # above opening
                fr = o.get("frame")
                if fr:
                    fw = 0.08
                    z0o, z1o = o.get("z0", 0.0), o["z1"]
                    self.box((ou0 - fw / 2, -0.03, (z0o + z1o) / 2), (fw, 0.12, z1o - z0o + fw), fr)
                    self.box((ou1 + fw / 2, -0.03, (z0o + z1o) / 2), (fw, 0.12, z1o - z0o + fw), fr)
                    self.box(((ou0 + ou1) / 2, -0.03, z1o + fw / 2), (ou1 - ou0 + 2 * fw, 0.12, fw), fr)
                    if z0o > 0.01:
                        self.box(((ou0 + ou1) / 2, -0.06, z0o - fw / 2), (ou1 - ou0 + 2 * fw, 0.2, fw), fr)
                gl = o.get("glass")
                if gl:
                    self.box(((ou0 + ou1) / 2, t / 2, (o.get("z0", 0.0) + o["z1"]) / 2),
                             (ou1 - ou0, 0.04, o["z1"] - o.get("z0", 0.0)), gl)
                u = ou1
            piece(u, length, 0.0, height)
            if cap_mat:
                self.box((length / 2, t / 2, height + 0.05), (length + 0.1, t + 0.1, 0.1), cap_mat)

    def room(self, poly2d, z0, height, thick, mat, openings=None, floor_mat=None, ceil_mat=None,
             inner_mat=None):
        """Closed walls along a CCW footprint (walls are placed INSIDE the footprint line).
        openings: dict edge_index -> list of opening dicts (see wall())."""
        n = len(poly2d)
        openings = openings or {}
        for i in range(n):
            a, b = poly2d[i], poly2d[(i + 1) % n]
            # walls go CCW, outward side is right of a->b for a CW polygon; our footprint is CCW so
            # the outside is to the right when walking CW. We therefore walk b->a? No - for a CCW
            # footprint the interior is on the LEFT of a->b, which matches wall() (+y inside).
            self.wall(a, b, z0, height, thick, mat, openings.get(i, ()), inner_mat=inner_mat)
        if floor_mat:
            self.poly([(p[0], p[1], z0 + 0.02) for p in poly2d], floor_mat)
        if ceil_mat:
            self.poly([(p[0], p[1], z0 + height) for p in reversed(poly2d)], ceil_mat)

    def facade_windows(self, p0, p1, rows_z, count, w, h, glass="M_Glass", frame="M_WindowFrame",
                       margin=None, sill=True, depth=0.06):
        """Decorative windows on the outside face of a solid block whose face runs p0->p1
        (outside is to the RIGHT of p0->p1, same as wall())."""
        p0, p1 = _v(p0), _v(p1)
        d = p1 - p0
        length = d.length
        if count <= 0 or length < 1e-3:
            return
        yaw = math.degrees(math.atan2(d.y, d.x))
        margin = (length / count - w) / 2 if margin is None else margin
        step = (length - 2 * margin) / count
        with self.at((p0.x, p0.y, 0.0), rot=yaw):
            for z in rows_z:
                for i in range(count):
                    u = margin + step * (i + 0.5)
                    self.box((u, -depth / 2, z + h / 2), (w, depth, h), glass, skip=("+y",))
                    fw = 0.1
                    self.box((u - w / 2 - fw / 2, -depth, z + h / 2), (fw, depth * 2, h + 2 * fw), frame, skip=("+y",))
                    self.box((u + w / 2 + fw / 2, -depth, z + h / 2), (fw, depth * 2, h + 2 * fw), frame, skip=("+y",))
                    self.box((u, -depth, z + h + fw / 2), (w, depth * 2, fw), frame, skip=("+y",))
                    if sill:
                        self.box((u, -depth * 2, z - fw / 2), (w + 0.3, depth * 4, fw), frame, skip=("+y",))

    # ------------------------------------------------------------------ circulation
    def stairs(self, origin, yaw, width, steps, rise, run, mat, solid=True):
        """Straight stairs going up along local +x from origin (bottom front edge centre)."""
        with self.at(origin, rot=yaw):
            for i in range(steps):
                z1 = rise * (i + 1)
                if solid:
                    self.box((run * (i + 0.5), 0, z1 / 2), (run, width, z1), mat)
                else:
                    self.box((run * (i + 0.5), 0, z1 - 0.04), (run, width, 0.08), mat)

    def ramp(self, p0, p1, width, mat, thick=0.3):
        """Sloped slab from p0 to p1 (3D points on the walking surface centre line)."""
        p0, p1 = _v(p0), _v(p1)
        d = p1 - p0
        side = Vector((-d.y, d.x, 0.0))
        if side.length < 1e-6:
            return
        side.normalize()
        side *= width / 2
        a, b, c, e = p0 - side, p1 - side, p1 + side, p0 + side
        dn = Vector((0, 0, thick))
        self.quad(a, b, c, e, mat)
        self.quad(e - dn, c - dn, b - dn, a - dn, mat)
        self.quad(a - dn, b - dn, b, a, mat)
        self.quad(c - dn, e - dn, e, c, mat)
        self.quad(e - dn, a - dn, a, e, mat)
        self.quad(b - dn, c - dn, c, b, mat)

    def railing(self, pts, height, mat, post_spacing=1.5, post_size=0.08, rail_size=0.06, mid_rail=True):
        pts = [_v(p) for p in pts]
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            seg = (b - a)
            n = max(1, int(seg.length / post_spacing))
            for k in range(n + (1 if i == len(pts) - 2 else 0)):
                p = a + seg * (k / n)
                self.box((p.x, p.y, p.z + height / 2), (post_size, post_size, height), mat)
            self.beam(a + Vector((0, 0, height)), b + Vector((0, 0, height)), rail_size, rail_size, mat)
            if mid_rail:
                self.beam(a + Vector((0, 0, height * 0.5)), b + Vector((0, 0, height * 0.5)),
                          rail_size * 0.7, rail_size * 0.7, mat)

    def column(self, base, radius, height, mat, seg=12, cap_mat=None, fluted=False):
        cm = cap_mat or mat
        x, y, z = base
        self.box((x, y, z + 0.15), (radius * 2.6, radius * 2.6, 0.3), cm)
        self.lathe([(radius * 1.15, 0.3), (radius, 0.45), (radius * 0.9, height - 0.5), (radius * 1.1, height - 0.35)],
                   mat, seg, False, False, (x, y, z))
        self.box((x, y, z + height - 0.15), (radius * 2.6, radius * 2.6, 0.3), cm)

    def arch(self, center, width, height, depth, thick, mat, seg=10):
        """Semicircular arch frame (opening in the local XZ plane, facing -y). center=(x,y,z_base)."""
        cx, cy, cz = center
        r_in = width / 2
        r_out = r_in + thick
        spring = cz + height - r_in
        # jambs
        self.box((cx - r_in - thick / 2, cy, (cz + spring) / 2), (thick, depth, spring - cz), mat)
        self.box((cx + r_in + thick / 2, cy, (cz + spring) / 2), (thick, depth, spring - cz), mat)
        for i in range(seg):
            a0 = math.pi * i / seg
            a1 = math.pi * (i + 1) / seg
            pts_o = [(cx + math.cos(a) * r_out, spring + math.sin(a) * r_out) for a in (a0, a1)]
            pts_i = [(cx + math.cos(a) * r_in, spring + math.sin(a) * r_in) for a in (a0, a1)]
            y0, y1 = cy - depth / 2, cy + depth / 2
            # front & back
            self.quad((pts_i[0][0], y0, pts_i[0][1]), (pts_o[0][0], y0, pts_o[0][1]),
                      (pts_o[1][0], y0, pts_o[1][1]), (pts_i[1][0], y0, pts_i[1][1]), mat)
            self.quad((pts_i[1][0], y1, pts_i[1][1]), (pts_o[1][0], y1, pts_o[1][1]),
                      (pts_o[0][0], y1, pts_o[0][1]), (pts_i[0][0], y1, pts_i[0][1]), mat)
            # outer & inner
            self.quad((pts_o[0][0], y0, pts_o[0][1]), (pts_o[0][0], y1, pts_o[0][1]),
                      (pts_o[1][0], y1, pts_o[1][1]), (pts_o[1][0], y0, pts_o[1][1]), mat, smooth=True)
            self.quad((pts_i[1][0], y0, pts_i[1][1]), (pts_i[1][0], y1, pts_i[1][1]),
                      (pts_i[0][0], y1, pts_i[0][1]), (pts_i[0][0], y0, pts_i[0][1]), mat, smooth=True)

    def sign_board(self, center, w, h, mat_board, mat_frame, thick=0.12, posts=True, post_mat=None):
        cx, cy, cz = center
        self.box((cx, cy, cz), (w, thick, h), mat_board)
        self.box((cx, cy, cz + h / 2 + 0.05), (w + 0.2, thick + 0.06, 0.1), mat_frame)
        self.box((cx, cy, cz - h / 2 - 0.05), (w + 0.2, thick + 0.06, 0.1), mat_frame)
        if posts:
            pm = post_mat or mat_frame
            for sx in (-1, 1):
                self.box((cx + sx * (w / 2 + 0.05), cy, (cz + h / 2) / 2), (0.12, 0.12, cz + h / 2), pm)

    # ------------------------------------------------------------------ merge / build
    def extend(self, other, offset=(0, 0, 0), rot=0.0, scale=1.0):
        with self.at(offset, rot=rot, scale=scale):
            base = len(self.verts)
            for v in other.verts:
                self.verts.append(self.matrix @ v)
            for f in other.faces:
                self.faces.append(tuple(i + base for i in f))
            self.face_mats.extend(other.face_mats)
            self.face_smooth.extend(other.face_smooth)

    def bounds(self):
        xs = [v.x for v in self.verts]
        ys = [v.y for v in self.verts]
        zs = [v.z for v in self.verts]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def build(self, name=None, collection=None, uv_scale=1.0):
        name = name or self.name
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([tuple(v) for v in self.verts], [], self.faces)
        # material slots in first-use order
        order = []
        index = {}
        for m in self.face_mats:
            if m not in index:
                index[m] = len(order)
                order.append(m)
        for m in order:
            mesh.materials.append(blend.material(m))
        mesh.polygons.foreach_set("material_index", [index[m] for m in self.face_mats])
        mesh.polygons.foreach_set("use_smooth", self.face_smooth)
        blend.box_uv(mesh, uv_scale)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        (collection or bpy.context.scene.collection).objects.link(obj)
        return obj
