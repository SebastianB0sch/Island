"""
Anime head: an oval cranium, soft cheeks tapering to a small pointed chin, small ears. The whole head uses the character's face material (face.py texture, planar-projected
from the front by skin._face_uvs), so the eyes, brows and mouth are painted, like the sprites and
portraits of the GX games.
"""

import math

from mathutils import Vector

from ..geo import MeshBuilder, TAU
from . import skeleton as S


def head_point(az, el, shape=None):
    """Head surface point for azimuth az (0 = front/-Y, +90 = character's left/+X) and elevation el
    (degrees), before the jaw shaping. Used by hair.py to root locks on the scalp."""
    shape = shape or {}
    cx, cy, cz = S.HEAD_CENTER
    R = S.HEAD_RADIUS
    a, e = math.radians(az), math.radians(el)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    return Vector((cx + d.x * R * shape.get("width", 1.0), cy + d.y * R * shape.get("depth", 1.0),
                   cz + d.z * R * shape.get("height", 1.12))), d


def _shape(d, shape):
    """Unit direction -> head surface point (jaw taper, chin, flattened back of the skull)."""
    cx, cy, cz = S.HEAD_CENTER
    R = S.HEAD_RADIUS
    width = shape.get("width", 0.92)
    depth = shape.get("depth", 1.02)
    jaw = shape.get("jaw", 0.52)            # how much the lower face narrows
    chin = shape.get("chin", 0.20)          # chin drop (in R)
    x, y, z = d.x * width, d.y * depth, d.z * shape.get("height", 1.12)
    if d.z < 0:
        t = (-d.z) ** 1.25
        front = max(0.0, -d.y)
        x *= 1.0 - jaw * t * (0.55 + 0.45 * front)
        y *= 1.0 - 0.28 * t * (1.0 - front)
        # chin: the lowest front part reaches a little further down and forward
        c = max(0.0, (-d.z - 0.55) / 0.45) * front ** 2
        z -= chin * c
        y -= 0.05 * c
        # cheeks: slight fullness at mid height
        x *= 1.0 + 0.05 * math.sin(math.pi * min(1.0, -d.z * 1.6))
    if d.y > 0:                              # back of the skull a touch flatter
        y *= 0.96
    return Vector((cx + x * R, cy + y * R, cz + z * R))


def head(face_mat, skin_mat, shape=None, seg=28, rings=18):
    shape = shape or {}
    mb = MeshBuilder("Head")
    rows = []
    for j in range(1, rings):
        phi = -math.pi / 2 + math.pi * j / rings
        row = []
        for i in range(seg):
            th = TAU * i / seg + math.pi / 2       # start at the back (+Y) so the seam is hidden by hair
            d = Vector((math.cos(phi) * math.cos(th), math.cos(phi) * math.sin(th), math.sin(phi)))
            row.append(tuple(_shape(d, shape)))
        rows.append(row)
    mb.grid_faces(rows, face_mat, smooth=True, closed_u=True)
    bottom = tuple(_shape(Vector((0, 0, -1)), shape))
    top = tuple(_shape(Vector((0, 0, 1)), shape))
    for i in range(seg):
        i2 = (i + 1) % seg
        mb.poly([rows[0][i2], rows[0][i], bottom], face_mat, smooth=True)
        mb.poly([rows[-1][i], rows[-1][i2], top], face_mat, smooth=True)
    # ears (small, mostly under the hair)
    cx, cy, cz = S.HEAD_CENTER
    R = S.HEAD_RADIUS
    for s in (-1, 1):
        mb.sphere((cx + s * R * shape.get("width", 0.92) * 0.9, cy + R * 0.06, cz - R * 0.12), R * 0.16, skin_mat,
                  seg=8, rings=6, scale=(0.45, 0.75, 1.25))
    return mb


def neck(skin_mat):
    mb = MeshBuilder("Neck")
    mb.cylinder((0, 0.008, S.SHOULDER - 0.03), 0.044, S.HEAD + 0.04 - (S.SHOULDER - 0.03), skin_mat, seg=12,
                radius_top=0.036, cap_top=False, cap_bottom=False)
    return mb


def face_surface(fx, fz, shape=None, lift=0.004):
    """Point on the face for face-texture coordinates (fx, fz), pushed `lift` metres outwards
    (glasses, etc. sit on it)."""
    shape = shape or {}
    cx, cy, cz = S.HEAD_CENTER
    R = S.HEAD_RADIUS
    # search the front hemisphere direction whose projection matches (fx, fz)
    best, bp = 1e9, None
    for j in range(41):
        for i in range(41):
            az = -80 + 160 * i / 40
            el = -80 + 160 * j / 40
            a, e = math.radians(az), math.radians(el)
            d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
            p = _shape(d, shape)
            err = ((p.x - cx) / R - fx) ** 2 + ((p.z - cz) / R - fz) ** 2
            if err < best:
                best, bp = err, p
    n = (bp - Vector(S.HEAD_CENTER)).normalized()
    return bp + n * lift
