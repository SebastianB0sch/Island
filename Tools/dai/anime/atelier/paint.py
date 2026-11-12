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
EYE = dict(cx=0.0385, cz=-0.012, hw=0.0240, h=0.0345, upper=0.62, tilt=0.0, inner_drop=0.0, skew=0.12,
           pu=2.3, qu=0.72, pl=2.0, ql=0.85, lash=0.0040, wing=0.26, wing_up=0.55,
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
         mouth_z=-0.0635, female=True):
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
        d = ((X - sx * 0.054) / 0.020) ** 2 + ((Z + 0.042) / 0.010) ** 2
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
         length=1.0, seed=3, accent=None, accent2=None, contrast=1.0, sheen=0.44):
    """Hair sheet: u across a lock, v = distance from the crown / `length` metres (hair.py UVs).
    color2: second tone the hair fades into below ombre[0] (metres) over ombre[1].
    accent: colour of a second sheet painted to the right of the first (hair.Hair.split: streaks, inner
    layers; accent2: its ombre tone). contrast scales the painted shading (runtime-tinted hair is painted
    near white and wants a little more of it); sheen: opacity of the highlight band."""
    from PIL import Image
    rng = np.random.default_rng(seed)
    img = _hair_sheet(color, color2, highlight, band, ombre, size, length, rng, contrast, sheen)
    if accent is not None:
        img = np.concatenate([img, _hair_sheet(accent, accent2, None, band, ombre, size, length, rng, contrast)],
                             axis=1)
    out = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    _save(Image.fromarray(out, "RGB"), path)


HAIR_TOP_U = 0.80        # hair.TOP_U: u below it is a lock's lit face, above it the underside strip


def _hair_sheet(color, color2, highlight, band, ombre, size, length, rng, contrast=1.0, sheen=0.44):
    """One hair sheet. u: across a lock - the lit face in u < HAIR_TOP_U, the lock's underside (the darker
    inner tone that gives the mass its depth) beyond it; v: metres from the crown."""
    w, h = size
    u = (np.arange(w, dtype=np.float32) + 0.5) / w
    d = (np.arange(h, dtype=np.float32) + 0.5) / h * length          # row 0 = crown
    U, D = np.meshgrid(u, d)
    T = np.clip(U / HAIR_TOP_U, 0.0, 1.0)                             # 0..1 across the lit face
    under = _aa((U - (HAIR_TOP_U + 0.012)) * w, 1.0)
    img = np.empty((h, w, 3), np.float32)
    img[:] = np.asarray(color, np.float32)
    if color2 is not None:
        _over(img, color2, _smooth((D - ombre[0]) / max(ombre[1], 1e-3)))
    base = img.copy()
    # a few broad soft tones across the lock (no fine strand lines: they stripe the whole head from behind)
    tone = np.zeros(w, np.float32)
    for k, amp in ((1, 0.020), (2, 0.012)):
        tone += amp * np.sin(u / HAIR_TOP_U * k * 2 * np.pi + rng.uniform(0, 6.28))
    img *= (1.0 + tone * contrast)[None, :, None]
    # one soft inner-lock groove a little off centre, and a gentle darkening towards both edges
    groove = np.exp(-((T - 0.68) / 0.035) ** 2) * (0.5 + 0.5 * _smooth((D - 0.05) / 0.10))
    _mul(img, shade(color, v=0.80, s=1.12), groove * 0.40 * contrast)
    _mul(img, shade(color, v=0.76, s=1.15), (np.abs(T - 0.5) * 2.0) ** 6 * 0.26 * contrast)
    # root shadow
    _mul(img, shade(color, v=0.72, s=1.2), 1.0 - _smooth(D / 0.035))
    # painted highlight: a soft band round the head whose edges break into teeth that follow the lock
    hl = highlight or shade(color, v=1.50, s=0.55, h=0.03)
    lo, hi = band
    n = 3.0
    f = (T * n + 0.5) % 1.0
    k = np.floor(T * n + 0.5)
    jit = 0.5 + 0.5 * np.sin(k * 2.399 + 0.7)                          # per-tooth length, repeatable
    tooth = 1.0 - np.abs(f - 0.5) * 2.0                                 # 0 at a tooth's sides .. 1 at its middle
    lower = hi - (hi - lo) * (0.15 + 0.55 * jit) * (1.0 - tooth ** 0.7)
    upper = lo + (hi - lo) * (0.10 + 0.30 * (1.0 - jit)) * (1.0 - tooth ** 0.9)
    a = _smooth((D - upper) / 0.006) * (1.0 - _smooth((D - lower) / 0.003))
    a *= (1.0 - (np.abs(T - 0.5) * 2.0) ** 4) * (0.70 + 0.30 * tooth)
    _over(img, hl, a * sheen * (1.0 - under))
    # the underside strip: the hair's shadow tone, flat
    und = base * np.array([0.70, 0.68, 0.78], np.float32)
    img += (und - img) * under[..., None]
    return img


# --------------------------------------------------------------------------- cloth detail
# Tailoring painted over a garment rectangle (Atlas.paint): what a texture artist adds on top of the flat
# colours - seams, pockets, plackets, lapels, pleat and fold shading, soft ambient darkening. Positions are
# in the part's UVs (u round the part, v along it); sizes are in metres, converted with style["dims"] =
# (metres round the part, metres along it). wrap: u is periodic (closed shells).
_DETAIL_KEYS = ("blocks", "lapel", "pleats", "shade", "creases", "seams", "lines", "stitch", "pockets", "dots", "ribs")
SHADOW_TINT = (0.70, 0.72, 0.86)          # painted cloth shadow: darker and a touch cooler


def _tone(img, alpha, amount=1.0, tint=SHADOW_TINT):
    """Darken towards the shadow tint; cloth that is already near black is lifted instead (a crease or a seam
    on a black coat reads as a lighter line)."""
    a = np.clip(alpha, 0.0, 1.0).astype(np.float32) * amount
    lum = img @ np.array([0.299, 0.587, 0.114], np.float32)
    dark = _smooth((0.20 - lum) / 0.10)
    t = np.asarray(tint, np.float32)
    img *= 1.0 + (t - 1.0) * (a * (1.0 - dark))[..., None]
    img += (np.array([0.115, 0.115, 0.15], np.float32) * (a * dark)[..., None])


def _lift(img, alpha, amount=0.5):
    a = (np.clip(alpha, 0.0, 1.0) * amount).astype(np.float32)[..., None]
    img += (np.minimum(img * 1.25 + 0.10, 1.0) - img) * a


def _detail(img, U, V, style):
    h, w = img.shape[:2]
    W, H = style.get("dims", (1.0, 1.0))
    wrap = bool(style.get("wrap", False))
    mu, mv = W / w, H / h                                 # metres per pixel
    px = max(mu, mv)
    line_w = max(0.0016, 1.3 * px)                        # seam width (m)

    def du(u0):
        d = U - u0
        return ((d + 0.5) % 1.0 - 0.5) if wrap else d

    def seg(u0, v0, u1, v1):
        """Distance (m) to a segment."""
        ax, ay = du(u0) * W, (V - v0) * H
        bx, by = (((u1 - u0 + 0.5) % 1.0 - 0.5) if wrap else (u1 - u0)) * W, (v1 - v0) * H
        t = np.clip((ax * bx + ay * by) / max(bx * bx + by * by, 1e-12), 0.0, 1.0)
        return np.hypot(ax - t * bx, ay - t * by)

    for u0, u1, v0, v1, col in style.get("blocks", ()):
        uc, uh = 0.5 * (u0 + u1), 0.5 * abs(u1 - u0)
        a = _aa((uh - np.abs(du(uc))) * W, px) * _aa((V - v0) * H, px) * _aa((v1 - V) * H, px)
        _over(img, col, a)
    lp = style.get("lapel")
    if lp:
        # open fronts: a turned-back lapel along both front edges above the button point, with a notch
        e = np.minimum(U, 1.0 - U) * W
        v0 = lp.get("v0", 0.55)
        t = np.clip((V - v0) / max(1.0 - v0, 1e-3), 0.0, 1.0)
        wd = lp.get("w", 0.05) * np.sin(np.clip(t * 1.25, 0.0, 1.0) * np.pi * 0.5) ** 0.8
        cut = np.clip(1.0 - np.abs(V - lp.get("notch", 0.80)) * H / 0.012, 0.0, 1.0) * 0.45
        wd = wd * (1.0 - cut)                               # the notch bites into the lapel
        on = (t > 0.02) * (wd > 0.004)
        _over(img, lp.get("color", shade(style["_color"], v=1.12)), _aa(wd - e, px) * on)
        _tone(img, _aa(line_w * 0.5 - np.abs(e - wd), px) * on, 0.75)
        _tone(img, np.exp(-np.maximum(e - wd, 0.0) / 0.012) * (e > wd) * on, 0.30)
    pl = style.get("pleats")
    if pl:
        f = (U * pl["n"] + pl.get("phase", 0.0)) % 1.0
        fall = 0.30 + 0.70 * (1.0 - V) ** 0.8             # the pleats open towards the hem
        dep = pl.get("depth", 0.5)
        _tone(img, _smooth((f - 0.42) / 0.50) * fall, dep)
        _tone(img, _aa(line_w * 0.6 - (1.0 - f) * W / pl["n"], px) * (0.5 + 0.5 * fall), 0.9)
        _lift(img, _smooth((0.10 - f) / 0.08) * (f < 0.12) * fall, 0.44 * dep)
    rb = style.get("ribs")
    if rb:
        f = np.abs(((U * rb["n"]) % 1.0) - 0.5) * 2.0
        band = ((V <= rb.get("v1", 2.0)) & (V >= rb.get("v0", -1.0))).astype(np.float32)
        _tone(img, _smooth((f - 0.45) / 0.4) * band, rb.get("depth", 0.35))
    sh = style.get("shade")
    if sh:
        if sh.get("top"):
            d, s = sh["top"]
            _tone(img, (1.0 - _smooth((1.0 - V) * H / d)) ** 1.5, s)
        if sh.get("bottom"):
            d, s = sh["bottom"]
            _tone(img, (1.0 - _smooth(V * H / d)) ** 1.3, s)
        for u0, v0, ru, rv, s in sh.get("spots", ()):
            q = (du(u0) * W / ru) ** 2 + ((V - v0) * H / rv) ** 2
            _tone(img, np.exp(-q * 1.2), s)
        for v0, d, s in sh.get("under", ()):              # cast shade below a line (belts, collars, flaps)
            y = (v0 - V) * H
            _tone(img, (y > 0) * np.exp(-np.maximum(y, 0.0) / d), s)
    for fd in style.get("creases", ()):
        n = fd.get("n", 3)
        L = fd.get("len", 0.06)
        t0 = fd.get("thick", 0.0032)
        x = du(fd["u"]) * W
        s = fd.get("s", 0.8)
        for k in range(n):
            o = k - (n - 1) / 2.0
            Lk = L * (1.0 - 0.28 * ((k * 5 + 1) % 3) / 2.0)
            xs = x - fd.get("shift", 0.0) * o
            y = (V - fd["v"]) * H - o * fd.get("gap", 0.014) - fd.get("tilt", 0.0) * xs \
                - (fd.get("curve", 0.0) + fd.get("fan", 0.0) * o) * xs * xs / max(L, 1e-3)
            lens = t0 * np.clip(1.0 - (2.0 * xs / Lk) ** 2, 0.0, 1.0) ** 0.8
            _tone(img, _aa(lens - np.abs(y), px) * (lens > 0), s)
            _tone(img, np.exp(-np.maximum(-y, 0.0) / (t0 * 2.5)) * (y < 0) * (lens > t0 * 0.15), s * 0.28)
    for axis, pos, a0, a1 in style.get("seams", ()):
        if axis == "u":
            d = np.abs(du(pos)) * W
            m = _aa((V - a0) * H, px) * _aa((a1 - V) * H, px)
        else:
            d = np.abs(V - pos) * H
            m = 1.0 if a0 is None else _aa((U - a0) * W, px) * _aa((a1 - U) * W, px)
        _tone(img, _aa(line_w * 0.5 - d, px) * m, 0.62)
    for u0, v0, u1, v1 in style.get("lines", ()):
        _tone(img, _aa(line_w * 0.5 - seg(u0, v0, u1, v1), px), 0.70)
    for axis, pos, a0, a1 in style.get("stitch", ()):
        if axis == "u":
            d, along = np.abs(du(pos)) * W, V * H
            m = _aa((V - a0) * H, px) * _aa((a1 - V) * H, px)
        else:
            d, along = np.abs(V - pos) * H, U * W
            m = 1.0 if a0 is None else _aa((U - a0) * W, px) * _aa((a1 - U) * W, px)
        _lift(img, _aa(line_w * 0.4 - d, px) * m * (((along / 0.009) % 1.0) < 0.62), 0.55)
    for pk in style.get("pockets", ()):
        x = du(pk["u"]) * W                                 # from the pocket centre
        y = (V - pk["v"]) * H - pk.get("tilt", 0.0) * x
        hw, hh = pk.get("w", 0.09) / 2, pk.get("h", 0.10) / 2
        kind = pk.get("kind", "patch")
        if kind == "welt":
            inx = _aa(hw - np.abs(x), px)
            _tone(img, _aa(0.0030 - np.abs(y), px) * inx, 0.95)
            _lift(img, _aa(0.0016 - np.abs(y + 0.0050), px) * inx, 0.35)
            _tone(img, (y < 0) * np.exp(-np.maximum(-y, 0.0) / 0.012) * inx, 0.22)
            continue
        r = min(hw, hh) * 0.35                              # rounded lower corners
        qx, qy = np.abs(x) - (hw - r), np.maximum(-y, 0.0) - (hh - r)
        sd = np.where(y < 0, np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0)) + np.minimum(np.maximum(qx, qy), 0.0) - r,
                      np.maximum(np.abs(x) - hw, y - hh))
        _tone(img, _aa(line_w * 0.5 - np.abs(sd), px), 0.70)
        _lift(img, _aa(line_w * 0.35 - np.abs(sd + 0.0045), px) * (((x + y) / 0.009) % 1.0 < 0.6), 0.40)
        _tone(img, (sd > 0) * (y < hh * 0.6) * np.exp(-np.maximum(sd, 0.0) / 0.006), 0.22)
        if kind == "flap":
            fy = hh - pk.get("flap", 0.36) * 2 * hh * (1.0 - 0.22 * (np.abs(x) / hw) ** 2)
            _tone(img, _aa(y - fy, px) * (sd < 0), 0.16)
            _tone(img, _aa(line_w * 0.5 - np.abs(y - fy), px) * (sd < 0), 0.75)
            _tone(img, (y < fy) * np.exp(-np.maximum(fy - y, 0.0) / 0.008) * (sd < 0), 0.30)
            if pk.get("button") is not None:
                d = np.hypot(x, y - (fy + 0.011))
                _over(img, shade(pk["button"], v=0.55), _aa(0.0062 - d, px))
                _over(img, pk["button"], _aa(0.0046 - d, px))
    for u0, v0, r, col in style.get("dots", ()):
        x, y = du(u0) * W, (V - v0) * H
        d = np.hypot(x, y)
        _tone(img, np.exp(-np.hypot(x - 0.002, y + 0.003) / (r * 0.9)) * (d > r), 0.35)
        _over(img, shade(col, v=0.5, s=1.1), _aa(r * 1.28 - d, px))
        _over(img, col, _aa(r - d, px))
        _over(img, shade(col, v=1.35, s=0.6), _aa(r * 0.36 - np.hypot(x + r * 0.3, y - r * 0.3), px) * 0.8)


# --------------------------------------------------------------------------- cloth atlas
class Atlas:
    """Garment texture atlas: every garment part gets a rectangle; part UVs (0..1) are remapped into it and
    the rectangle is painted with that part's pattern."""

    def __init__(self, size=2048, cell=256):
        self.size, self.cell = size, cell
        self.img = np.full((size, size, 3), 0.5, np.float32)
        self.sky = None
        self.swatches = {}
        self.swatch_cell = None
        self.swatch_n = 0

    def alloc(self, w=1, h=1):
        """A free w x h block of cells (skyline packing: garments mix 1-, 2- and 4-cell tall parts)."""
        n = self.size // self.cell
        if self.sky is None:
            self.sky = [0] * n
        best = None
        for x in range(n - w + 1):
            y = max(self.sky[x:x + w])
            if best is None or y < best[1]:
                best = (x, y)
        if best is None or best[1] + h > n:
            raise ValueError("garment atlas is full")
        x, y = best
        self.sky[x:x + w] = [y + h] * w
        return (x * self.cell, y * self.cell, w * self.cell, h * self.cell)

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
        end) towards v = 0, motif dict(kind, n, v, size, color, h), crest dict(u, v, size, color), fold (0..1 soft vertical fold shading);
        plus the tailoring keys of _detail() above (seams, pockets, lapel, pleats, shade, folds, ...)."""
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
            cv = (V - m["v"]) / m.get("h", m["size"] * w / h * m["n"])     # h: explicit half height in v
            if m["kind"] == "diamond":
                a = (np.abs(cu) / m["size"] + np.abs(cv) < 1.0)
            elif m["kind"] == "dot":
                a = (np.hypot(cu / m["size"], cv) < 1.0)
            else:                                     # chevron
                a = (np.abs(np.abs(cu) / m["size"] + cv) < 0.35) & (np.abs(cu) < m["size"])
            _over(img, m["color"], a.astype(np.float32))
        cr = style.get("crest")
        if cr:
            # a large emblem painted on the garment (e.g. the back of a coat): diamond outline, inner diamond,
            # side wings; u, v: centre, size: half height in v
            du, dv = (U - cr["u"]) * w, (V - cr["v"]) * h
            sz = cr["size"] * h
            m = (np.abs(du) + np.abs(dv)) / sz
            a = ((m > 0.80) & (m < 1.0)) | (m < 0.40)
            a |= (np.abs(dv) < 0.05 * sz) & (np.abs(du) > 1.15 * sz) & (np.abs(du) < 2.1 * sz - np.abs(dv) * 4)
            a |= (np.abs(du) < 0.05 * sz) & (np.abs(dv) > 1.15 * sz) & (np.abs(dv) < 1.6 * sz)
            _over(img, cr["color"], a.astype(np.float32) * cr.get("alpha", 1.0))
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
        if any(k in style for k in _DETAIL_KEYS):
            _detail(img, U, V, dict(style, _color=color))
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
