"""
Anime face textures for the cast (big GX-style eyes, brows, mouth, blush).

The head mesh projects this texture planar from the front (see head.py): face
coordinates fx, fz in [-1, 1] are the head-local x / (z - centre) divided by the
head radius, so (0, 0) is the middle of the head seen from the front. Everything
outside the drawn features is plain skin, which is what the sides and back of
the head (mapped to the rim of the texture) show.

Drawn at 4x and downsampled for clean, anti-aliased lines.
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 512
SS = 4  # supersampling


def _rgb(c, a=255):
    return tuple(int(round(max(0.0, min(1.0, v)) * 255)) for v in c[:3]) + (a,)


def _mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


class _Canvas:
    def __init__(self, skin):
        self.n = SIZE * SS
        self.img = Image.new("RGBA", (self.n, self.n), _rgb(skin))

    def px(self, fx, fz):
        return ((fx + 1.0) * 0.5 * self.n, (1.0 - (fz + 1.0) * 0.5) * self.n)

    def pts(self, pts):
        return [self.px(x, z) for x, z in pts]

    def layer(self):
        return Image.new("RGBA", (self.n, self.n), (0, 0, 0, 0))

    def over(self, layer, mask=None):
        if mask is not None:
            a = np.array(layer.split()[3], np.float32) * (np.array(mask, np.float32) / 255.0)
            layer.putalpha(Image.fromarray(a.astype(np.uint8)))
        self.img = Image.alpha_composite(self.img, layer)

    def width(self, w):
        return max(1, int(round(w * self.n / 2.0)))


def _eye_outline(cx, cz, w, h, side, shape, tilt):
    """Eye opening polygon (face coords). side=-1 left (viewer's right), +1 right. Outer corner = side * +x."""
    top, bot = [], []
    n = 28
    for i in range(n + 1):
        t = i / n                      # 0 = inner corner, 1 = outer corner
        x = (t - 0.5) * w
        s = math.sin(math.pi * t)
        if shape == "sharp":
            up = h * (0.62 * s ** 0.55 + 0.38 * t * s ** 0.3)
            down = -h * 0.30 * s ** 1.2
        elif shape == "sleepy":
            up = h * 0.55 * s ** 0.7
            down = -h * 0.40 * s ** 0.9
        else:  # round
            up = h * 0.66 * s ** 0.62
            down = -h * 0.42 * s ** 0.85
        # outer corner sits a little higher (anime eyes lift towards the temples)
        lift = h * 0.10 * (t - 0.5) + tilt * (t - 0.5) * w
        top.append((x, up + lift))
        bot.append((x, down + lift))
    poly = top + list(reversed(bot))
    return [(cx + side * x, cz + z) for x, z in poly], [(cx + side * x, cz + z) for x, z in top]


def _thick_curve(draw, canvas, pts, w0, w1, color):
    """Polyline with a tapered width (w0 at the start, w1 at the end), as one polygon."""
    P = [np.array(canvas.px(*p)) for p in pts]
    left, right = [], []
    for i, p in enumerate(P):
        a = P[max(i - 1, 0)]
        b = P[min(i + 1, len(P) - 1)]
        t = b - a
        t = t / (np.linalg.norm(t) + 1e-9)
        nrm = np.array([-t[1], t[0]])
        w = canvas.width(w0 + (w1 - w0) * i / max(1, len(P) - 1)) * 0.5
        left.append(tuple(p + nrm * w))
        right.append(tuple(p - nrm * w))
    draw.polygon(left + list(reversed(right)), fill=color)


def _eye(canvas, spec, side):
    e = spec["eyes"]
    cx = side * e.get("spacing", 0.38)
    cz = e.get("z", -0.12)
    w = e.get("w", 0.30)
    h = e.get("h", 0.40)
    shape = e.get("shape", "round")
    poly, top = _eye_outline(cx, cz, w, h, side, shape, e.get("tilt", 0.0))
    iris = e.get("iris", (0.45, 0.25, 0.10))
    lash = e.get("lash_color", (0.10, 0.06, 0.05))

    # opening mask
    mask = Image.new("L", (canvas.n, canvas.n), 0)
    ImageDraw.Draw(mask).polygon(canvas.pts(poly), fill=255)

    # sclera (very light blue-white, a soft shadow under the lash)
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    d.polygon(canvas.pts(poly), fill=_rgb((0.98, 0.99, 1.0)))
    shadow = [(x, z - h * 0.18) for x, z in top]
    _thick_curve(d, canvas, shadow, h * 0.30, h * 0.30, _rgb((0.78, 0.82, 0.92), 255))
    canvas.over(lay, mask)

    # iris: tall ellipse, vertical gradient, darker rim, pupil, highlights
    ix = cx + side * w * e.get("look", 0.06)
    iz = cz + h * 0.06
    iw = w * e.get("iris_w", 0.62) / 2
    ih = h * e.get("iris_h", 0.98) / 2
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    steps = 24
    dark = _mix(iris, (0.0, 0.0, 0.0), 0.55)
    light = _mix(iris, (1.0, 1.0, 1.0), 0.35)
    x0, y0 = canvas.px(ix - iw, iz + ih)
    x1, y1 = canvas.px(ix + iw, iz - ih)
    d.ellipse([x0, y0, x1, y1], fill=_rgb(dark))
    for k in range(steps):
        t = k / (steps - 1)
        c = _mix(_mix(dark, iris, min(1.0, t * 1.6)), light, max(0.0, t - 0.55) * 1.4)
        shrink = 0.86
        yy0 = y0 + (y1 - y0) * (0.12 + 0.88 * t) * 0.0
        d.ellipse([x0 + (x1 - x0) * (1 - shrink) / 2, yy0 + (y1 - y0) * (0.18 + 0.5 * t) * 0.6,
                   x1 - (x1 - x0) * (1 - shrink) / 2, y1 - (y1 - y0) * (1 - shrink) / 2], fill=_rgb(c))
    # pupil
    pw, ph = iw * 0.42, ih * 0.46
    px0, py0 = canvas.px(ix - pw, iz + ph * 0.9)
    px1, py1 = canvas.px(ix + pw, iz - ph * 1.1)
    d.ellipse([px0, py0, px1, py1], fill=_rgb(_mix(dark, (0, 0, 0), 0.6)))
    # highlights: big one up and to the side, a small one low on the other side
    for (ox, oz, r) in ((-0.38, 0.42, 0.34), (0.36, -0.46, 0.15)):
        hx = ix + side * ox * iw * -1.0
        hz = iz + oz * ih
        rr = r * iw
        a0, b0 = canvas.px(hx - rr, hz + rr * 1.15)
        a1, b1 = canvas.px(hx + rr, hz - rr * 1.15)
        d.ellipse([a0, b0, a1, b1], fill=_rgb((1, 1, 1)))
    canvas.over(lay, mask)

    # lashes: thick upper line (wing for girls), thin lower line
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    thick = h * e.get("lash", 0.16)
    _thick_curve(d, canvas, top, thick * 0.55, thick * 1.25, _rgb(lash))
    if e.get("female"):
        ox, oz = top[-1]
        wing = [(ox, oz), (ox + side * w * 0.12, oz + h * 0.10), (ox + side * w * 0.20, oz + h * 0.16)]
        _thick_curve(d, canvas, wing, thick * 1.1, thick * 0.2, _rgb(lash))
        for k in (0.62, 0.8):
            i = int(k * (len(top) - 1))
            bx, bz = top[i]
            _thick_curve(d, canvas, [(bx, bz), (bx + side * w * 0.07, bz + h * 0.14)], thick * 0.5, 0.004, _rgb(lash))
    low = [(x, z) for x, z in poly[len(top):]]
    low = low[int(len(low) * 0.08):int(len(low) * 0.45)]
    if low:
        _thick_curve(d, canvas, low, thick * 0.12, thick * 0.32, _rgb(_mix(lash, (0.6, 0.35, 0.3), 0.35)))
    canvas.over(lay)


def _brows(canvas, spec, side):
    e = spec["eyes"]
    b = spec.get("brows", {})
    cx = side * e.get("spacing", 0.38)
    cz = e.get("z", -0.12) + e.get("h", 0.40) * 0.62 + b.get("lift", 0.10)
    w = e.get("w", 0.30) * b.get("len", 0.95)
    ang = math.radians(b.get("angle", 6.0))     # + = inner end lower (determined / angry)
    pts = []
    for i in range(10):
        t = i / 9
        x = (t - 0.5) * w
        z = math.sin(math.pi * t) * w * 0.12 * b.get("arch", 1.0) - (t - 0.5) * w * math.tan(-ang)
        pts.append((cx + side * x, cz + z))
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    _thick_curve(d, canvas, pts, b.get("thick", 0.035), b.get("thick", 0.035) * 0.45, _rgb(b.get("color", (0.25, 0.14, 0.08))))
    canvas.over(lay)


def _mouth(canvas, spec):
    m = spec.get("mouth", {})
    kind = m.get("kind", "smile")
    z = m.get("z", -0.80)
    w = m.get("w", 0.13)
    line = _rgb(m.get("color", (0.45, 0.15, 0.12)))
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    if kind == "grin":
        poly = [(-w, z + 0.01), (w, z + 0.01)] + [(math.cos(math.pi * t) * w * 0.95, z - math.sin(math.pi * t) * w * 0.85)
                                                 for t in np.linspace(0.0, 1.0, 16)]
        d.polygon(canvas.pts(poly), fill=_rgb((0.55, 0.12, 0.12)))
        teeth = [(-w * 0.92, z + 0.005), (w * 0.92, z + 0.005), (w * 0.8, z - w * 0.22), (-w * 0.8, z - w * 0.22)]
        d.polygon(canvas.pts(teeth), fill=_rgb((1, 1, 1)))
        tongue = [(math.cos(math.pi * t) * w * 0.5, z - w * 0.6 - math.sin(math.pi * t) * w * 0.22) for t in np.linspace(0, 1, 10)]
        d.polygon(canvas.pts(tongue), fill=_rgb((0.9, 0.42, 0.42)))
    elif kind == "smirk":
        pts = [(-w * 0.8, z), (0.0, z - 0.012), (w * 0.9, z + 0.035)]
        _thick_curve(d, canvas, pts, 0.016, 0.02, line)
    elif kind == "flat":
        _thick_curve(d, canvas, [(-w * 0.6, z), (w * 0.6, z)], 0.014, 0.014, line)
    elif kind == "lips":
        up = [(math.cos(math.pi * t) * w, z + math.sin(math.pi * t) * 0.03 - 0.004) for t in np.linspace(0, 1, 12)]
        lo = [(math.cos(math.pi * t) * w, z - math.sin(math.pi * t) * 0.035) for t in np.linspace(1, 0, 12)]
        d.polygon(canvas.pts(up + lo), fill=_rgb(m.get("lip_color", (0.75, 0.15, 0.35))))
    elif kind == "open":
        x0, y0 = canvas.px(-w * 0.45, z + 0.02)
        x1, y1 = canvas.px(w * 0.45, z - 0.07)
        d.ellipse([x0, y0, x1, y1], fill=_rgb((0.55, 0.12, 0.12)))
    else:  # smile
        pts = [(math.cos(math.pi * t) * w, z - math.sin(math.pi * t) * w * 0.28) for t in np.linspace(0.0, 1.0, 14)]
        _thick_curve(d, canvas, pts, 0.012, 0.012, line)
    canvas.over(lay)


def _blush(canvas, spec):
    b = spec.get("blush")
    if not b:
        return
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    e = spec["eyes"]
    for side in (-1, 1):
        cx = side * (e.get("spacing", 0.38) + 0.04)
        cz = e.get("z", -0.12) - e.get("h", 0.40) * 0.62
        x0, y0 = canvas.px(cx - 0.11, cz + 0.045)
        x1, y1 = canvas.px(cx + 0.11, cz - 0.045)
        d.ellipse([x0, y0, x1, y1], fill=_rgb((0.98, 0.55, 0.55), int(255 * b)))
    lay = lay.filter(ImageFilter.GaussianBlur(canvas.n * 0.012))
    canvas.over(lay)


def _extras(canvas, spec):
    for ex in spec.get("face_extras", ()):
        lay = canvas.layer()
        d = ImageDraw.Draw(lay)
        if ex == "eyeshadow":
            e = spec["eyes"]
            for side in (-1, 1):
                cx = side * e.get("spacing", 0.38)
                cz = e.get("z", -0.12) + e.get("h", 0.40) * 0.35
                x0, y0 = canvas.px(cx - e.get("w", 0.3) * 0.62, cz + 0.11)
                x1, y1 = canvas.px(cx + e.get("w", 0.3) * 0.62, cz - 0.05)
                d.ellipse([x0, y0, x1, y1], fill=_rgb((0.55, 0.35, 0.65), 150))
            lay = lay.filter(ImageFilter.GaussianBlur(canvas.n * 0.01))
        elif ex == "nose":
            _thick_curve(d, canvas, [(0.0, -0.46), (0.025, -0.54)], 0.014, 0.006, _rgb((0.84, 0.60, 0.52)))
        canvas.over(lay)


def paint(spec, path):
    """spec: the cast entry's face section (+ skin colour). Writes an sRGB PNG and returns the path."""
    skin = spec.get("skin", (1.0, 0.86, 0.74))
    c = _Canvas(skin)
    extras = list(spec.get("face_extras", ()))
    if "nose" not in extras:            # every face gets the small anime nose stroke
        extras.append("nose")
    _blush(c, spec)
    _extras(c, dict(spec, face_extras=extras))
    for side in (-1, 1):
        if not spec.get("eyes_closed"):
            _eye(c, spec, side)
        _brows(c, spec, side)
    _mouth(c, spec)
    img = c.img.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    return path
