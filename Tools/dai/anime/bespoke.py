"""
Bespoke characters: the template every hand-authored design is written in.

A preset look (looks.py) picks a hair recipe and a garment preset. A bespoke design is authored piece by piece
as plain data (see hero.py for the protagonists) and this module turns it into a cast entry:

  hair     every lock placed by hand (comb()), on top of optional recipe sections; double geometric
           resolution, a highlight ring, short spring chains on short locks, an accent under-layer
  face     the base face's sheets repainted while they are packed into the face-parts atlas (repaint()):
           a layered iris, catch-lights, an inked lash line, brows in the hair colour; jaw / chin, resting
           expression, earrings
  outfit   a wear list in the atelier vocabulary (atelier/outfit.GARMENTS), fitted by looks._fit

A design is a dict:

  key, base, female, height, tint            mesh name (SK_Anime_<key>), VRoid base, body table, cm, runtime tints
  hair = dict(
      color, tip, accent, accent_tip, tie, sheen_color, sheen, ombre, seed, res, min_chain, cap,
      sections   recipe sections combed first (fringe / sides / back / spikes / tails / braids / buns / ahoge -
                 atelier/hair.py), in the clump-hair vocabulary
      locks      [dict(az, s0, s1, free, sweep, width, ..., mirror, accent, over_eye)] placed one by one
                 (atelier.hair.Hair.lock keywords; az in degrees, + = the character's left; mirror=True places
                 the lock on both sides, `asym` scales the right one's length)
  )
  face = dict(iris, lash, brows, expression, face_shape, earrings, grow)
  colors = dict(jacket, pants, skirt, shoes, sole)
  wear = [(garment, params)]

LEARNINGS - what made the difference on the protagonists, checked by check():

  * Lock widths are ~2x what reads "right" on paper: a recipe fringe lock is ~0.07 design-m wide. Below 0.045
    (strands excepted) the hair turns stringy, with gaps and a heavy outline per lock.
  * `sweep` moves a lock's azimuth along the scalp: the end sits at az + sweep. A fringe lock that ends below
    the brows (s1 > 0.44) with its end over an eye (12..34 deg off centre) hides that eye - only allowed when
    the design says so (over_eye=True).
  * res=2 (twice the path samples and lens columns) removes the faceted look in close-ups; min_chain 0.045
    gives the short side / back locks spring chains (physics) instead of only the long ones.
  * Dark hair needs its own highlight colour (sheen_color, a cool tone) at ~0.55 opacity to read at all.
  * The base iris is a flat disc: paint it in layers (lid shadow, gradient, fibres, collarette, reflection,
    limbal ring) and put two catch-lights on the highlight layer. The base's lash line is soft and brown;
    thicken and ink it for a sharper face.
  * Silhouette beats surface: a cut-away hem (top(hem_front=...)), one sleeve (sleeve_sides), straps with
    buckles, a belt stack and one statement piece (bracer) did more than any texture.
  * Patterned borders: motif with an explicit `h` (half height in v) - without it the pattern smears into
    stripes over the whole garment.
  * Preview a runtime-tinted jacket in a dorm colour (it is near white in the build). Preview renders write
    the textures into SourceAssets: restore them (git checkout) or rebuild before committing.
  * Budget: a bespoke character is ~130-180k triangles and 11-13 materials (the regular cast ~50-80k, 9).
"""

import numpy as np

from .atelier.paint import shade

# hair.Hair.lock keywords a design's lock may set (az / sweep in degrees / radians as noted)
LOCK_KEYS = ("s0", "s1", "free", "sweep", "loft", "width", "thick", "gravity", "flare", "curl", "wave", "lift",
             "direction", "blunt", "kind", "forward", "up", "n_scalp")
MIN_WIDTH = 0.045                    # below this a lock is a "strand" (kind / strand=True) or it looks stringy
EYE_BAND = (12.0, 34.0)              # degrees off centre where a fringe end covers an eye
EYE_RING = 0.44                      # ring below which a fringe end reaches the eyes


def _rad(d):
    return float(np.radians(d))


# --------------------------------------------------------------------------- hair
def comb(hr, design):
    """Place a design's hand-authored locks on a clump-hair `hr` (after its recipe sections)."""
    hair = design["hair"]
    for spec in hair.get("locks", ()):
        sides = (1.0, -1.0) if spec.get("mirror") else (1.0,)
        for sx in sides:
            kw = {k: spec[k] for k in LOCK_KEYS if k in spec}
            if "sweep" in kw:
                kw["sweep"] = kw["sweep"] * sx
            if sx < 0 and "asym" in spec and "free" in kw:
                kw["free"] = kw["free"] * spec["asym"]
            az = _rad(spec["az"]) * sx
            lk = hr.lock(az, kw.pop("s0", 0.05), kw.pop("s1"), sector=az, **kw)
            lk.accent = bool(spec.get("accent", False))


def hair_style(design, cid):
    """The clump-hair options (clumphair.build reads them) of a design."""
    h = design["hair"]
    return dict(style=dict(h.get("sections", {})), author=cid, accent=h.get("accent"), accent2=h.get("accent_tip"),
                tie=h.get("tie"), ombre=h.get("ombre", (0.17, 0.12)), highlight=h.get("sheen_color"),
                sheen=h.get("sheen", 0.55), seed=h.get("seed", 11), res=h.get("res", 2),
                min_chain=h.get("min_chain", 0.045), cap=h.get("cap", (0.27, 0.52, 0.72)))


# --------------------------------------------------------------------------- face paint
def _blobs(alpha):
    """(centre x, centre y, radius x, radius y) of the two iris discs (left / right halves of the sheet)."""
    h, w = alpha.shape
    out = []
    for x0, x1 in ((0, w // 2), (w // 2, w)):
        a = alpha[:, x0:x1].astype(np.float64)
        m = a > 24
        if m.sum() < 16:
            continue
        ys, xs = np.nonzero(m)
        wgt = a[m]
        cx, cy = float((xs * wgt).sum() / wgt.sum()) + x0, float((ys * wgt).sum() / wgt.sum())
        out.append((cx, cy, 0.5 * float(np.ptp(xs) + 1), 0.5 * float(np.ptp(ys) + 1)))
    return out


def _sm(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def paint_iris(tex, color, grow=1.10, ring=None):
    """Layered anime iris over the base sheet's discs: dark top under the lid shadow, the body colour, a bright
    crescent at the bottom, fine radial fibres, a collarette round the pupil, a soft inner reflection and an
    ink limbal ring. ring: optional second colour for the outer band (two-tone eyes)."""
    rgb = tex[..., :3].astype(np.float32) / 255.0
    alpha = tex[..., 3]
    h, w = alpha.shape
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    c = np.asarray(color, np.float32)
    deep = np.asarray(shade(color, v=0.30, s=1.25, h=-0.03), np.float32)
    mid = np.asarray(shade(color, v=0.72, s=1.15, h=-0.015), np.float32)
    bright = np.asarray(shade(color, v=1.30, s=0.80, h=0.02), np.float32)
    ink = np.asarray(shade(color, v=0.16, s=1.2, h=-0.05), np.float32)
    new_alpha = np.zeros((h, w), np.float32)
    for cx, cy, rx, ry in _blobs(alpha):
        rx, ry = rx * grow, ry * grow
        dx, dy = (X - cx) / rx, (Y - cy) / ry                # -1..1 over the disc, y down
        r = np.sqrt(dx * dx + dy * dy)
        new_alpha = np.maximum(new_alpha, _sm((1.0 - r) / 0.04 + 0.5))
        inside = r < 1.05
        ang = np.arctan2(dy, dx)
        t = _sm((dy + 0.85) / 1.6)
        col = deep[None, None] * (1 - _sm(t / 0.45))[..., None] + mid[None, None] * _sm(t / 0.45)[..., None]
        col = col * (1 - _sm((t - 0.45) / 0.35))[..., None] + c[None, None] * _sm((t - 0.45) / 0.35)[..., None]
        col = col + (bright - col) * (_sm((dy - 0.25) / 0.55) * _sm((0.98 - r) / 0.25))[..., None] * 0.85
        if ring is not None:
            col = col + (np.asarray(ring, np.float32) - col) * (_sm((r - 0.62) / 0.14) * 0.75)[..., None]
        fib = 0.5 + 0.5 * np.sin(ang * 34.0 + 1.3 * np.sin(ang * 7.0))
        fib = fib ** 6 * _sm((r - 0.34) / 0.15) * _sm((0.92 - r) / 0.18) * (0.35 + 0.65 * _sm((dy + 0.1) / 0.6))
        col = col + (bright - col) * fib[..., None] * 0.30
        coll = np.exp(-((r - 0.40) / 0.06) ** 2) * (0.4 + 0.6 * _sm((dy + 0.2) / 0.6))
        col = col + (bright - col) * coll[..., None] * 0.35
        rp = np.sqrt(dx * dx + (dy * 0.86) ** 2)
        col = col + (ink - col) * _sm((0.30 - rp) / 0.04)[..., None]
        refl = _sm((0.18 - np.abs(np.sqrt((dx + 0.18) ** 2 + (dy - 0.42) ** 2) - 0.30)) / 0.12) * _sm((dy - 0.20) / 0.25)
        col = col + (np.float32(1.0) - col) * refl[..., None] * 0.22
        col = col * (1.0 - 0.55 * _sm((-dy - 0.30) / 0.45))[..., None]
        col = col + (ink - col) * _sm((r - 0.84) / 0.12)[..., None]
        rgb = np.where(inside[..., None], col, rgb)
    out = tex.copy()
    out[..., :3] = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    out[..., 3] = (np.clip(new_alpha, 0, 1) * 255 + 0.5).astype(np.uint8)
    return out


def paint_highlight(tex, iris_tex, sparkle=False):
    """Catch-lights (a large soft one up and out, a small one low and in; sparkle: a third tiny one) on the
    highlight layer (it shares the iris sheet's layout)."""
    h, w = tex.shape[:2]
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.zeros((h, w), np.float32)
    for i, (cx, cy, rx, ry) in enumerate(_blobs(iris_tex[..., 3])):
        out_dir = -1.0 if i == 0 else 1.0                   # towards the outer corner of each eye
        lights = [(0.34 * out_dir, -0.38, 0.22, 0.17, 1.0), (-0.26 * out_dir, 0.36, 0.09, 0.08, 0.85)]
        if sparkle:
            lights.append((0.05 * out_dir, -0.55, 0.05, 0.05, 0.9))
        for ox, oy, sx, sy, k in lights:
            d = np.sqrt(((X - (cx + ox * rx)) / (sx * rx)) ** 2 + ((Y - (cy + oy * ry)) / (sy * ry)) ** 2)
            a = np.maximum(a, _sm((1.0 - d) / 0.25) * k)
    out = np.zeros_like(tex)
    out[..., :3] = 255
    out[..., 3] = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    return out


def paint_lash(tex, ink, weight=1.0):
    """Heavier, inked upper lash line (weight 0: the base's own)."""
    if weight <= 0:
        return tex
    from scipy import ndimage
    out = tex.copy()
    a = tex[..., 3].astype(np.float32)
    k = 1 + 2 * int(round(2 * weight))
    thick = ndimage.grey_dilation(a, size=(k, max(1, k // 2 + 1)))
    out[..., 3] = np.clip(np.maximum(a, thick * 0.92), 0, 255).astype(np.uint8)
    out[..., :3] = (np.asarray(ink, np.float32) * 255).astype(np.uint8)
    return out


def repaint_for(design):
    """models.merge_face_parts hook for a design: its own versions of the base face's sheets."""
    face = design.get("face", {})
    hair = design["hair"]

    def repaint(source, tex, sheets):
        s = source.lower()
        if "eyeiris" in s:
            return paint_iris(tex, face["iris"], grow=face.get("grow", 1.10), ring=face.get("iris_ring"))
        if "eyehighlight" in s:
            iris = next((v for k, v in sheets.items() if "eyeiris" in k.lower()), None)
            return paint_highlight(tex, iris, face.get("sparkle", False)) if iris is not None else tex
        if "faceeyeline" in s:
            return paint_lash(tex, face.get("lash_ink", shade(hair["color"], v=0.55, s=0.8)), face.get("lash", 1.0))
        if "facebrow" in s:
            out = tex.copy()
            out[..., :3] = (np.asarray(face.get("brows", shade(hair["color"], v=0.9)), np.float32) * 255).astype(np.uint8)
            return out
        return tex
    return repaint


# --------------------------------------------------------------------------- the cast entry
def look(design, cid):
    """A design -> look entry (models.build_model vocabulary)."""
    from . import looks as L
    h, f = design["hair"], design.get("face", {})
    kw = dict(hair_style=hair_style(design, cid), tint=tuple(design.get("tint", ("jacket",))),
              colors=dict(design.get("colors", {})), expression=dict(f.get("expression", {})),
              face_shape=dict(f.get("face_shape", {})), outline=design.get("outline", 0.0024))
    if f.get("earrings"):
        kw["accessories"] = dict(earrings=tuple(f["earrings"]))
    out = L.look(design["base"], (h["color"], h.get("tip")), f["iris"], female=design.get("female"), **kw)
    out["wear"] = L._fit(list(design["wear"]))
    out["bespoke"] = cid
    return out


def check(design):
    """The learnings above as rules: [problem, ...] (empty: the design follows them)."""
    out = []
    h = design["hair"]
    for i, lk in enumerate(h.get("locks", ())):
        w = lk.get("width", 0.030)
        if w < MIN_WIDTH and not lk.get("strand"):
            out.append(f"lock {i}: width {w} < {MIN_WIDTH} (stringy) - widen it or mark strand=True")
        if lk.get("kind") == "fringe" and lk.get("s1", 0.0) > EYE_RING and not lk.get("over_eye"):
            end = abs(lk["az"] + np.degrees(lk.get("sweep", 0.0)))
            if EYE_BAND[0] <= end <= EYE_BAND[1]:
                out.append(f"lock {i}: fringe ends over an eye (az {end:.0f} deg, ring {lk['s1']}) - "
                           f"shorten / move it or mark over_eye=True")
    if h.get("res", 2) < 2:
        out.append("hair res < 2: faceted in close-ups")
    if h.get("color") and sum(h["color"]) < 0.6 and not h.get("sheen_color"):
        out.append("dark hair without a sheen_color: the highlight ring will not read")
    for kind, p in design.get("wear", ()):
        for key in ("motif",):
            for st in (p.get("style") or {}, p.get("sleeve_style") or {}):
                m = st.get(key)
                if m and "h" not in m:
                    out.append(f"{kind}: motif without h smears into stripes")
    if "iris" not in design.get("face", {}):
        out.append("face: no iris colour")
    return out
