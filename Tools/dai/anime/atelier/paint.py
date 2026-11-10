"""
Textures painted in UV space (numpy only - no source images, no Blender).

face()    the face: skin, painted anime eyes (white, layered iris, lashes, crease), blush, nose and lip
          accents, plus the colour swatches the eyelid / brow / mouth decal meshes sample
hair()    hair sheet: strand streaks, root shadow, a zig-zag highlight band and an optional second tone
cloth()   garment atlas regions: flat colour with hem bands, piping, gradients and repeat motifs

The face texture is a front projection of the head: u = 0.5 + x / FACE_W, v = (z + FACE_Z0) / FACE_W with
x, z in metres relative to the head centre (see head.py, which places the decals in the same frame).
"""

import colorsys

import numpy as np

FACE_W = 0.20            # metres covered by the face texture (square)
FACE_Z0 = 0.125          # the texture's bottom edge is this far below the head centre
SWATCH_U = 0.035         # decal swatches sit in the unused left column (u < 0.07)
SWATCH_V = dict(skin=0.95, lash=0.85, brow=0.75, line=0.65, teeth=0.56, inside=0.48, tongue=0.40)


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _aa(d, px):
    """Coverage of a signed distance (positive inside), one pixel wide edge."""
    return np.clip(d / px + 0.5, 0.0, 1.0)


def _over(img, color, alpha):
    img += (np.asarray(color, np.float32) - img) * alpha[..., None].astype(np.float32)


def _mul(img, color, alpha):
    img *= 1.0 + (np.asarray(color, np.float32) - 1.0) * alpha[..., None].astype(np.float32)


def shade(c, v=1.0, s=1.0, h=0.0):
    """Colour with scaled value / saturation and shifted hue."""
    hh, ss, vv = colorsys.rgb_to_hsv(*[min(1.0, max(0.0, x)) for x in c])
    return colorsys.hsv_to_rgb((hh + h) % 1.0, min(1.0, ss * s), min(1.0, vv * v))


# --------------------------------------------------------------------------- eye shape (shared with head.py)
EYE = dict(cx=0.0360, cz=-0.012, hw=0.0205, h=0.0300, upper=0.62, tilt=0.0, inner_drop=0.0, skew=0.12,
           pu=2.3, qu=0.72, pl=2.0, ql=0.85, lash=0.0036, wing=0.28, wing_up=0.55,
           iris_w=0.60, iris_h=0.98, look=0.0)


def eye_spec(spec=None):
    return dict(EYE, **(spec or {}))


def lids(e, t):
    """(upper, lower) lid height (m, relative to the eye centre) at t in [-1 inner .. 1 outer]."""
    t = np.clip(t, -1.0, 1.0)
    base = e["tilt"] * e["hw"] * t - e["inner_drop"] * e["hw"] * (t < 0) * t * t
    ts = np.clip(t - e["skew"] * (1.0 - t * t), -1.0, 1.0)
    up = e["h"] * e["upper"] * (1.0 - np.abs(ts) ** e["pu"]) ** e["qu"]
    lo = e["h"] * (1.0 - e["upper"]) * (1.0 - np.abs(t) ** e["pl"]) ** e["ql"]
    return base + up, base - lo


def lash_width(e, t):
    """Thickness of the painted upper lash over t in [-1 .. 1 + wing]."""
    grow = 0.50 + 0.50 * _smooth((t + 1.0) / 1.7)
    inner = _smooth((t + 1.0) / 0.35)
    wing = 1.0 - _smooth((t - 1.0) / max(e["wing"], 1e-3))
    return e["lash"] * grow * (0.25 + 0.75 * inner) * np.where(t > 1.0, wing, 1.0)


def lash_top(e, t):
    """Upper edge of the painted lash (the wing carries on past the outer corner)."""
    up, _ = lids(e, t)
    over = np.maximum(t - 1.0, 0.0)
    return up + lash_width(e, t) + over * e["hw"] * e["wing_up"]


# --------------------------------------------------------------------------- face
def face(path, skin, eyes=None, iris=(0.30, 0.55, 0.85), iris2=None, lash=(0.12, 0.09, 0.10),
         brow=(0.25, 0.18, 0.16), blush=0.28, lips=None, bang_shadow=0.0, mole=None, size=2048,
         mouth_z=-0.0665, female=True):
    """Paint the face texture and save it to `path`. Colours are sRGB 0..1. Returns the eye spec used."""
    from PIL import Image
    e = eye_spec(eyes)
    px = FACE_W / size
    xs = (np.arange(size, dtype=np.float32) + 0.5) / size * FACE_W - FACE_W / 2
    zs = (size - (np.arange(size, dtype=np.float32) + 0.5)) / size * FACE_W - FACE_Z0
    X, Z = np.meshgrid(xs, zs)
    img = np.empty((size, size, 3), np.float32)
    img[:] = np.asarray(skin, np.float32)
    skin_sh = shade(skin, v=0.86, s=1.55, h=-0.012)       # warm, saturated skin shadow
    if bang_shadow > 0:                                    # soft cast shadow of the fringe on the forehead
        edge = 0.040 + 0.004 * np.sin(X * 210.0) + 0.002 * np.sin(X * 530.0 + 1.3)
        _over(img, skin_sh, _smooth((Z - edge) / 0.004) * bang_shadow)
    # blush, eyelid warmth
    for sx in (-1.0, 1.0):
        d = ((X - sx * 0.050) / 0.020) ** 2 + ((Z + 0.040) / 0.010) ** 2
        _over(img, (1.0, 0.52, 0.50), np.exp(-d * 1.6) * blush)
        d = ((X - sx * e["cx"]) / 0.022) ** 2 + ((Z - e["cz"] - e["h"] * 0.55) / 0.008) ** 2
        _over(img, skin_sh, np.exp(-d * 1.5) * 0.30)
    # nose: a small shadow tick on one side and a highlight dot
    d = np.hypot((X - 0.0020) / 0.0011, (Z + 0.0468) / 0.0019)
    _over(img, shade(skin, v=0.80, s=1.8, h=-0.02), _smooth((1.0 - d) / 0.5) * 0.55)
    # lower lip: soft tint under the mouth line
    lip = lips or shade(skin, v=0.93, s=1.9, h=-0.02)
    d = ((X) / 0.0085) ** 2 + ((Z - mouth_z + 0.0042) / 0.0016) ** 2
    _over(img, lip, np.exp(-d * 1.4) * (0.55 if female else 0.30))
    if lips:                                               # lipstick: upper lip too
        d = ((X) / 0.0100) ** 2 + ((Z - mouth_z - 0.0012) / 0.0013) ** 2
        _over(img, lip, np.exp(-d * 1.4) * 0.6)
    if mole:
        d = np.hypot(X - mole[0], Z - mole[1])
        _over(img, (0.28, 0.17, 0.15), _aa(0.0008 - d, px))
    iris2 = iris2 or shade(iris, v=1.25, s=0.75, h=0.06)
    for sx in (-1.0, 1.0):
        _eye(img, X, Z, px, e, sx, iris, iris2, lash, skin, skin_sh)
    # decal swatches (left column)
    sw = dict(skin=skin, lash=lash, brow=brow, line=shade(skin, v=0.42, s=1.9, h=-0.02), teeth=(0.98, 0.97, 0.95),
              inside=(0.52, 0.16, 0.18), tongue=(0.93, 0.50, 0.50))
    w = int(size * 0.07)
    for name, v in SWATCH_V.items():
        r0, r1 = int(size * (1 - v - 0.04)), int(size * (1 - v + 0.04))
        img[r0:r1, :w] = np.asarray(sw[name], np.float32)
    out = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    _save(Image.fromarray(out, "RGB"), path)
    return e


def _eye(img, X, Z, px, e, sx, iris, iris2, lash, skin, skin_sh):
    hw, H = e["hw"], e["h"]
    t = (np.abs(X) - e["cx"]) / hw                       # -1 inner .. 1 outer
    side = (X * sx) > 0
    z = Z - e["cz"]
    up, lo = lids(e, t)
    near = side & (t > -1.25) & (t < 1.0 + e["wing"] + 0.3) & (np.abs(z) < H * 1.4)
    if not near.any():
        return
    inside_t = _aa((1.0 - np.abs(t)) * hw, px)
    eye = np.minimum(_aa(up - z, px), _aa(z - lo, px)) * inside_t * near
    # eye white with a cool shadow under the upper lid
    _over(img, (0.985, 0.975, 0.965), eye)
    sh = _smooth((z - (up - 0.42 * (up - lo))) / np.maximum(0.42 * (up - lo), 1e-6))
    _over(img, (0.74, 0.76, 0.90), eye * sh * 0.85)
    # iris
    ix = e["look"] * hw
    rx, rz = e["iris_w"] * hw, e["iris_h"] * H * 0.5
    icz = (lids(e, np.array(0.0))[0] + lids(e, np.array(0.0))[1]) * 0.5 + 0.03 * H
    dx, dz = (np.abs(X) - e["cx"] - ix), (z - icz)
    d = np.hypot(dx / rx, dz / rz)
    ir = _aa((1.0 - d) * min(rx, rz), px) * eye
    g = _smooth((dz / rz + 1.0) * 0.5 * 1.05)
    dark = np.asarray(shade(iris, v=0.42, s=1.15), np.float32)
    mid = np.asarray(iris, np.float32)
    lite = np.asarray(iris2, np.float32)
    col = np.where(g[..., None] < 0.5, lite + (mid - lite) * (g[..., None] * 2.0),
                   mid + (dark - mid) * ((g[..., None] - 0.5) * 2.0))
    ang = np.arctan2(dz, dx + 1e-9)
    col = col * (1.0 + 0.05 * np.sin(ang * 23.0)[..., None] * _smooth((d - 0.35) / 0.3)[..., None])
    img += (col - img) * ir[..., None]
    _over(img, shade(iris, v=0.20, s=1.1), ir * _smooth((d - 0.80) / 0.10))                 # limbal ring
    dp = np.hypot(dx / (0.37 * rx), (dz - 0.04 * rz) / (0.43 * rz))
    _over(img, shade(iris, v=0.12, s=1.0), ir * _smooth((1.0 - dp) / 0.18))                  # pupil
    glow = _smooth((-dz / rz - 0.18) / 0.5) * _smooth((d - 0.30) / 0.2) * (1.0 - _smooth((d - 0.72) / 0.12))
    _over(img, shade(iris2, v=1.25, s=0.55), ir * glow * 0.80)                                # lower glow
    lsh = 1.0 - _smooth((up - z) / (0.30 * H))
    _over(img, shade(iris, v=0.10, s=1.0), ir * lsh * 0.70)                                   # lash shadow
    # highlights (the key light sits to the same side for both eyes)
    for hx, hz, hr, ha in ((-0.36, 0.40, 0.27, 1.0), (0.42, -0.46, 0.12, 0.92)):
        dh = np.hypot((dx * sx - hx * rx) / (hr * rx), (dz - hz * rz) / (hr * 0.8 * rz))
        _over(img, (1.0, 1.0, 1.0), _aa((1.0 - dh) * hr * rx, px) * eye * ha)
    # upper lash (with wing), crease, lower lash
    tw = (np.abs(X) - e["cx"]) / hw
    upw = lids(e, tw)[0] + np.maximum(tw - 1.0, 0.0) * hw * e["wing_up"]
    top = lash_top(e, tw)
    in_t = _aa((tw + 1.04) * hw, px) * _aa((1.0 + e["wing"] - tw) * hw, px)
    band = np.minimum(_aa(top - z, px), _aa(z - (upw - 0.0004), px)) * in_t * near
    _over(img, lash, band)
    _over(img, shade(lash, v=2.6, s=1.4), band * _smooth((tw - 0.2) / 0.9) * _aa((upw + 0.0007) - z, px) * 0.35)
    cz_ = top + 0.0017 + 0.0010 * (1.0 - tw * tw)
    crease = np.minimum(_aa(cz_ + 0.00045 - z, px), _aa(z - cz_, px)) * _smooth((tw + 0.75) / 0.3) * \
        (1.0 - _smooth((tw - 0.55) / 0.35)) * near
    _over(img, skin_sh if False else shade(skin, v=0.62, s=1.9, h=-0.02), crease * 0.85)
    lw = 0.00035 + 0.00055 * _smooth((tw - 0.0) / 1.0)
    low = np.minimum(_aa(lo + 0.0002 - z, px), _aa(z - (lo - lw), px)) * _smooth((tw + 0.25) / 0.5) * \
        _aa((1.0 - tw) * hw, px) * near
    _over(img, lash, low * 0.85)


# --------------------------------------------------------------------------- hair
def hair(path, color, color2=None, highlight=None, band=(0.100, 0.150), ombre=(0.45, 0.30), size=(512, 1024),
         length=1.0, seed=3):
    """Hair sheet: u across a lock, v = distance from the crown / `length` metres (hair.py UVs).
    color2: second tone the hair fades into below ombre[0] (metres) over ombre[1]."""
    from PIL import Image
    w, h = size
    rng = np.random.default_rng(seed)
    u = (np.arange(w, dtype=np.float32) + 0.5) / w
    d = (np.arange(h, dtype=np.float32) + 0.5) / h * length          # row 0 = crown
    U, D = np.meshgrid(u, d)
    img = np.empty((h, w, 3), np.float32)
    img[:] = np.asarray(color, np.float32)
    if color2 is not None:
        _over(img, color2, _smooth((D - ombre[0]) / max(ombre[1], 1e-3)))
    # strand streaks: a few broad soft tones and fine lines
    tone = np.zeros(w, np.float32)
    for k, amp in ((1, 0.025), (2, 0.018), (5, 0.008)):
        tone += amp * np.sin(u * k * 2 * np.pi + rng.uniform(0, 6.28))
    lines = (rng.random(w) > 0.985).astype(np.float32)
    lines = np.convolve(lines, [0.25, 0.5, 0.25], "same")
    img *= (1.0 + tone - 0.06 * lines)[None, :, None]
    # edge darkening across a lock (reads as a soft crease between neighbouring locks)
    _mul(img, shade(color, v=0.72, s=1.15), (np.abs(U - 0.5) * 2.0) ** 5 * 0.45)
    # root shadow
    _mul(img, shade(color, v=0.70, s=1.2), 1.0 - _smooth(D / 0.035))
    # highlight band with a zig-zag lower edge
    hl = highlight or shade(color, v=1.55, s=0.55, h=0.03)
    lo, hi = band
    zig = np.abs(((U * 2.0 + 0.5) % 1.0) - 0.5) * 2.0                 # two teeth per lock
    edge = hi - (hi - lo) * 0.55 * zig
    a = _smooth((D - lo) / 0.014) * (1.0 - _smooth((D - edge) / 0.0025))
    _over(img, hl, a * 0.46)
    out = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    _save(Image.fromarray(out, "RGB"), path)


# --------------------------------------------------------------------------- cloth atlas
class Atlas:
    """Garment texture atlas: every garment part gets a rectangle; part UVs (0..1) are remapped into it and
    the rectangle is painted with that part's pattern."""

    def __init__(self, size=2048, cell=256):
        self.size, self.cell = size, cell
        self.img = np.full((size, size, 3), 0.5, np.float32)
        self.cursor = [0, 0]
        self.row_h = 0
        self.swatches = {}
        self.swatch_cell = None
        self.swatch_n = 0

    def alloc(self, w=1, h=1):
        cw, ch = w * self.cell, h * self.cell
        if self.cursor[0] + cw > self.size:
            self.cursor = [0, self.cursor[1] + self.row_h]
            self.row_h = 0
        if self.cursor[1] + ch > self.size:
            raise ValueError("garment atlas is full")
        x, y = self.cursor
        self.cursor[0] += cw
        self.row_h = max(self.row_h, ch)
        return (x, y, cw, ch)

    def swatch(self, color, px=32):
        """Small flat-colour block (shared per colour) for parts without a pattern."""
        key = tuple(round(float(c), 3) for c in color)
        if key in self.swatches:
            return self.swatches[key]
        per = self.cell // px
        if self.swatch_cell is None or self.swatch_n >= per * per:
            self.swatch_cell = self.alloc(1, 1)
            self.swatch_n = 0
        x0, y0, _, _ = self.swatch_cell
        x, y = x0 + (self.swatch_n % per) * px, y0 + (self.swatch_n // per) * px
        self.swatch_n += 1
        self.img[y:y + px, x:x + px] = np.asarray(color, np.float32)
        self.swatches[key] = (x, y, px, px)
        return self.swatches[key]

    def paint(self, rect, color, **style):
        """Fill a rectangle. style: hem / top (v-bands at the bottom / top: [(width, colour)]), edge (u-bands
        at both u ends: [(width, colour)]), stripes dict(n, width, color, axis), gradient (colour, start,
        end) towards v = 0, motif dict(kind, n, v, size, color), fold (0..1 soft vertical fold shading)."""
        x, y, w, h = rect
        u = (np.arange(w, dtype=np.float32) + 0.5) / w
        v = 1.0 - (np.arange(h, dtype=np.float32) + 0.5) / h
        U, V = np.meshgrid(u, v)
        img = np.empty((h, w, 3), np.float32)
        img[:] = np.asarray(color, np.float32)
        g = style.get("gradient")
        if g:
            _over(img, g[0], 1.0 - _smooth((V - g[1]) / max(g[2] - g[1], 1e-3)))
        fold = style.get("fold", 0.0)
        if fold:
            n = style.get("folds", 9)
            f = 0.5 + 0.5 * np.cos(U * n * 2 * np.pi)
            _mul(img, shade(color, v=0.80, s=1.15), (f ** 3) * fold * (1.0 - V) ** 0.7)
        st = style.get("stripes")
        if st:
            c = (U if st.get("axis", "u") == "u" else V) * st["n"]
            a = (np.abs((c % 1.0) - 0.5) * 2.0 < st["width"]).astype(np.float32)
            _over(img, st["color"], a * st.get("alpha", 1.0))
        m = style.get("motif")
        if m:
            cu = (U * m["n"]) % 1.0 - 0.5
            cv = (V - m["v"]) / (m["size"] * w / h * m["n"])
            if m["kind"] == "diamond":
                a = (np.abs(cu) / m["size"] + np.abs(cv) < 1.0)
            elif m["kind"] == "dot":
                a = (np.hypot(cu / m["size"], cv) < 1.0)
            else:                                     # chevron
                a = (np.abs(np.abs(cu) / m["size"] + cv) < 0.35) & (np.abs(cu) < m["size"])
            _over(img, m["color"], a.astype(np.float32))
        pos = 0.0
        for width, col in style.get("hem", ()):
            _over(img, col, ((V >= pos) & (V < pos + width)).astype(np.float32))
            pos += width
        pos = 0.0
        for width, col in style.get("top", ()):
            _over(img, col, ((V <= 1.0 - pos) & (V > 1.0 - pos - width)).astype(np.float32))
            pos += width
        pos = 0.0
        for width, col in style.get("edge", ()):
            a = ((U >= pos) & (U < pos + width)) | ((U <= 1.0 - pos) & (U > 1.0 - pos - width))
            _over(img, col, a.astype(np.float32))
            pos += width
        self.img[y:y + h, x:x + w] = img
        # bleed the border texels outwards one pixel so bilinear filtering never picks up the neighbour
        return rect

    def uv(self, rect, uv, inset=3.0):
        """Map part UVs (0..1) into the rectangle (inset by a few texels)."""
        x, y, w, h = rect
        uv = np.clip(np.asarray(uv, np.float64), 0.0, 1.0)
        u = (x + inset + uv[:, 0] * (w - 2 * inset)) / self.size
        v = 1.0 - (y + inset + (1.0 - uv[:, 1]) * (h - 2 * inset)) / self.size
        return np.stack([u, v], axis=1)

    def save(self, path):
        from PIL import Image
        out = (np.clip(self.img, 0, 1) * 255 + 0.5).astype(np.uint8)
        _save(Image.fromarray(out, "RGB"), path)


def _save(image, path):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        from ... import atomic
        atomic.save_image(image, path, optimize=True)
    except ImportError:
        image.save(path, optimize=True)
