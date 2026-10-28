"""
Procedural, tileable textures (numpy + Pillow).

  T_<Name>_D.png   grayscale detail (mean ~0.5; the UE master material multiplies
                   the palette tint by 2*D, so 0.5 = unchanged colour)
  T_<Name>_N.png   tangent-space normal map, DirectX (green-down) convention
  T_WaterNormal, T_Noise, T_Lava, T_CardBack     special purpose textures

Everything is periodic so it tiles seamlessly.
"""

import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config as C

rng = np.random.default_rng(C.SEED)


# --------------------------------------------------------------------------- noise
def spectral(n, beta=2.0, seed=0, aniso=(1.0, 1.0)):
    """Periodic 1/f^beta noise in [-1, 1] approx (tileable by construction)."""
    r = np.random.default_rng(seed)
    w = r.standard_normal((n, n))
    F = np.fft.fft2(w)
    fy = np.fft.fftfreq(n)[:, None] * aniso[1]
    fx = np.fft.fftfreq(n)[None, :] * aniso[0]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    F = F / (f ** (beta / 2.0))
    F[0, 0] = 0.0
    out = np.real(np.fft.ifft2(F))
    out /= (np.abs(out).max() + 1e-9)
    return out.astype(np.float32)


def band(n, lo, hi, seed=0):
    """Band-limited periodic noise (features between n/hi and n/lo pixels)."""
    r = np.random.default_rng(seed)
    w = r.standard_normal((n, n))
    F = np.fft.fft2(w)
    fy = np.fft.fftfreq(n)[:, None] * n
    fx = np.fft.fftfreq(n)[None, :] * n
    f = np.sqrt(fx * fx + fy * fy)
    F[(f < lo) | (f > hi)] = 0
    out = np.real(np.fft.ifft2(F))
    out /= (np.abs(out).max() + 1e-9)
    return out.astype(np.float32)


def uv(n):
    v, u = np.mgrid[0:n, 0:n].astype(np.float32) / n
    return u, v


def normal_from_height(h, strength=4.0):
    """DirectX normal map from a periodic height field (0..1)."""
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    n = h.shape[0]
    s = strength * n / 256.0
    nx = -dx * s
    ny = -dy * s          # DirectX: green = -dh/drow
    nz = np.ones_like(h)
    L = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([nx / L, ny / L, nz / L], -1) * 0.5 + 0.5
    return rgb


def save_gray(a, path):
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "L").save(path, optimize=True)


def save_rgb(a, path):
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(path, optimize=True)


def norm01(a):
    a = a - a.min()
    return a / (a.max() + 1e-9)


def detail_from(h, mean=0.5, contrast=0.25):
    """Map a height-ish field to a detail texture with the given mean / spread."""
    a = (h - h.mean()) / (h.std() + 1e-9)
    return np.clip(mean + a * contrast * 0.5, 0, 1)


# --------------------------------------------------------------------------- patterns
def tiles(n, cols, rows, grout=0.03, offset_rows=False, bevel=0.06, seed=0):
    """Rectangular tile/brick pattern. Returns (height 0..1, per-tile random 0..1)."""
    u, v = uv(n)
    gv = v * rows
    row = np.floor(gv)
    gu = u * cols + (0.5 * (row % 2) if offset_rows else 0.0)
    col = np.floor(gu)
    fu = gu - col
    fv = gv - row
    du = np.minimum(fu, 1 - fu) / cols * n / n
    dv = np.minimum(fv, 1 - fv) / rows
    d = np.minimum(np.minimum(fu, 1 - fu) * (1.0 / cols), np.minimum(fv, 1 - fv) * (1.0 / rows))
    h = np.clip((d - grout * 0.5) / bevel, 0, 1)
    r = np.random.default_rng(seed)
    table = r.random((rows + 2, cols * 2 + 4))
    rid = table[(row % rows).astype(int), (col % (cols * 2)).astype(int)]
    return h.astype(np.float32), rid.astype(np.float32)


def make_detail_set(n=512):
    """Returns dict name -> (detail, height) arrays."""
    out = {}
    u, v = uv(n)

    # Plaster: soft mottling
    h = spectral(n, 2.2, 1) * 0.6 + band(n, 30, 90, 2) * 0.4
    out["Plaster"] = (detail_from(h, 0.5, 0.12), norm01(h) * 0.3)

    # Marble: veins
    t = spectral(n, 2.4, 3)
    veins = np.abs(np.sin((u * 2 + v * 3) * math.pi * 2 + t * 6.0))
    veins = 1 - np.clip(1 - veins, 0, 1) ** 12
    d = 0.55 + spectral(n, 2.0, 4) * 0.05 - (1 - veins) * 0.25
    out["Marble"] = (np.clip(d, 0, 1), veins * 0.1)

    # Floor tiles: 4x4 large tiles
    h, rid = tiles(n, 4, 4, grout=0.012, bevel=0.01, seed=5)
    d = 0.5 + (rid - 0.5) * 0.08 + spectral(n, 2.0, 6) * 0.04
    d = d * (0.6 + 0.4 * h)
    out["FloorTiles"] = (np.clip(d, 0, 1), h)

    # Concrete: speckle + blotches + faint form seams
    h = spectral(n, 1.6, 7) * 0.5 + band(n, 60, 200, 8) * 0.5
    seams = (np.abs((v * 2) % 1.0 - 0.5) > 0.495).astype(np.float32)
    d = detail_from(h, 0.5, 0.18) - seams * 0.12
    out["Concrete"] = (np.clip(d, 0, 1), norm01(h) * 0.4 - seams * 0.2)

    # Paving: offset stone blocks
    h, rid = tiles(n, 6, 8, grout=0.02, offset_rows=True, bevel=0.012, seed=9)
    rough = spectral(n, 2.0, 10)
    d = (0.48 + (rid - 0.5) * 0.25 + rough * 0.06) * (0.55 + 0.45 * h)
    out["Paving"] = (np.clip(d, 0, 1), h * 0.8 + rough * 0.1)

    # Grunge
    h = spectral(n, 1.8, 11)
    stains = np.clip(band(n, 2, 12, 12) * 1.5, 0, 1)
    out["Grunge"] = (np.clip(0.55 + h * 0.15 - stains * 0.2, 0, 1), norm01(h) * 0.2)

    # Planks: horizontal boards along U with grain
    rows = 8
    gv = v * rows
    row = np.floor(gv)
    fv = gv - row
    seam = np.clip(np.minimum(fv, 1 - fv) / 0.04, 0, 1)
    rr = np.random.default_rng(13).random(rows + 1)[(row % rows).astype(int)]
    grain = spectral(n, 2.0, 14, aniso=(0.08, 1.0))
    # board ends
    shift = np.random.default_rng(15).random(rows + 1)[(row % rows).astype(int)]
    gu = (u * 2 + shift) % 1.0
    end = np.clip(np.minimum(gu, 1 - gu) / 0.01, 0, 1)
    d = (0.48 + (rr - 0.5) * 0.18 + grain * 0.12) * (0.55 + 0.45 * seam * end)
    out["Planks"] = (np.clip(d, 0, 1), seam * end * 0.8 + grain * 0.1)

    # Siding (clapboard): sawtooth profile rows
    rows = 10
    fv = (v * rows) % 1.0
    profile = fv  # sloped boards
    grain = spectral(n, 2.0, 16, aniso=(0.1, 1.0))
    d = 0.5 + grain * 0.08 - (fv < 0.06) * 0.2
    out["Siding"] = (np.clip(d, 0, 1), profile * 0.8)

    # Corrugated: ridges varying along U
    ridges = 0.5 + 0.5 * np.sin(u * 2 * math.pi * 16)
    d = 0.5 + spectral(n, 1.8, 17) * 0.1 + (ridges - 0.5) * 0.1
    rust = np.clip(band(n, 3, 20, 18) * 2 - 0.6, 0, 1)
    d = d - rust * 0.15
    out["Corrugated"] = (np.clip(d, 0, 1), ridges)

    # Roof tiles: overlapping rows with rounded lower edges
    rows, cols = 8, 6
    gv = v * rows
    row = np.floor(gv)
    gu = u * cols + 0.5 * (row % 2)
    fu = gu % 1.0
    fv = gv - row
    arc = np.sqrt(np.clip(1 - (2 * fu - 1) ** 2, 0, 1)) * 0.25
    hgt = np.clip(fv - (0.0 + arc * 0.0), 0, 1)
    edge = np.clip((fv - arc * 0.3) / 0.05, 0, 1)
    rid = np.random.default_rng(19).random((rows + 1, cols * 2 + 2))[(row % rows).astype(int), (np.floor(gu) % (cols * 2)).astype(int)]
    side = np.clip(np.minimum(fu, 1 - fu) / 0.05, 0, 1)
    h = (1 - fv) * 0.7 * side + arc * side
    d = (0.5 + (rid - 0.5) * 0.15) * (0.6 + 0.4 * edge * side)
    out["RoofTiles"] = (np.clip(d, 0, 1), norm01(h))

    # Bricks
    h, rid = tiles(n, 4, 12, grout=0.025, offset_rows=True, bevel=0.01, seed=21)
    rough = spectral(n, 1.8, 22)
    d = (0.5 + (rid - 0.5) * 0.2 + rough * 0.06) * (0.5 + 0.5 * h)
    out["Bricks"] = (np.clip(d, 0, 1), h * 0.9 + rough * 0.1)

    # Rock: ridged multi-scale + cracks
    a = spectral(n, 2.0, 23)
    b = 1 - np.abs(band(n, 4, 40, 24))
    cr = np.clip(1 - np.abs(band(n, 6, 30, 25)) * 18, 0, 1)
    h = a * 0.5 + b * 0.5 - cr * 0.3
    out["Rock"] = (detail_from(h, 0.5, 0.35), norm01(h))

    # Bark: vertical fibres
    a = spectral(n, 2.0, 26, aniso=(1.0, 0.06))
    b = band(n, 8, 60, 27)
    h = a * 0.8 + b * 0.2
    out["Bark"] = (detail_from(h, 0.5, 0.4), norm01(h))

    # Leaves (hedge): clumpy blobs
    a = band(n, 20, 80, 28)
    h = np.clip(a * 1.5, -1, 1)
    out["Leaves"] = (detail_from(h, 0.5, 0.35), norm01(h))

    # Sand: fine grain + ripples
    rip = np.sin((v * 22 + spectral(n, 2.2, 29) * 1.5) * 2 * math.pi) * 0.5 + 0.5
    grain = band(n, 120, 256, 30)
    h = rip * 0.4 + grain * 0.3
    out["Sand"] = (detail_from(h, 0.5, 0.12), norm01(h))

    # Dirt: lumps + pebbles
    a = spectral(n, 1.9, 31)
    peb = np.clip(band(n, 40, 90, 32) * 3 - 1.5, 0, 1)
    h = a * 0.6 + peb * 0.6
    out["Dirt"] = (detail_from(h, 0.5, 0.3), norm01(h))

    # Fabric: weave
    w = (np.sin(u * 2 * math.pi * 64) * np.sin(v * 2 * math.pi * 64)) * 0.5 + 0.5
    h = w * 0.5 + spectral(n, 2.0, 33) * 0.2
    out["Fabric"] = (detail_from(h, 0.5, 0.15), norm01(h) * 0.3)

    # Grass (terrain): streaky blades + clumps
    a = spectral(n, 1.6, 34, aniso=(1.0, 0.35))
    b = band(n, 10, 40, 35)
    h = a * 0.7 + b * 0.3
    out["Grass"] = (detail_from(h, 0.5, 0.35), norm01(h) * 0.5)
    return out


# --------------------------------------------------------------------------- special
def water_normal(n=1024):
    u, v = uv(n)
    h = np.zeros((n, n), np.float32)
    r = np.random.default_rng(40)
    for i in range(14):
        kx, ky = r.integers(-9, 10), r.integers(-9, 10)
        if kx == 0 and ky == 0:
            continue
        amp = 1.0 / math.hypot(kx, ky)
        h += amp * np.sin(2 * math.pi * (kx * u + ky * v) + r.uniform(0, 6.28))
    h += spectral(n, 2.6, 41) * 0.8
    return normal_from_height(norm01(h), strength=3.0)


def lava(n=512):
    u, v = uv(n)
    cells = 1 - np.abs(band(n, 3, 14, 42)) * 2.5
    cr = np.clip(1 - np.abs(band(n, 4, 18, 43)) * 10, 0, 1)
    heat = np.clip(cr * 0.9 + np.clip(spectral(n, 2.0, 44), 0, 1) * 0.4, 0, 1)
    crust = np.clip(cells, 0, 1)
    col = np.stack([0.15 + heat * 1.0, 0.05 + heat ** 1.6 * 0.6, 0.03 + heat ** 3 * 0.25], -1)
    return np.clip(col, 0, 1)


def noise_tex(n=512):
    return norm01(spectral(n, 1.8, 45) * 0.6 + band(n, 8, 40, 46) * 0.4)


def card_back(w=512, h=744):
    """Original card-back design (deliberately not the official one)."""
    img = Image.new("RGB", (w, h), (70, 38, 18))
    px = np.zeros((h, w, 3), np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    ang = np.arctan2(yy - cy, xx - cx)
    rad = np.hypot((xx - cx) / w, (yy - cy) / h)
    swirl = 0.5 + 0.5 * np.sin(ang * 3 + rad * 40.0)
    base = np.array([0.42, 0.22, 0.09])
    hi = np.array([0.78, 0.45, 0.16])
    px = base[None, None, :] * (1 - swirl[..., None]) + hi[None, None, :] * swirl[..., None]
    img = Image.fromarray((px * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    # frame
    d.rectangle([8, 8, w - 9, h - 9], outline=(30, 16, 8), width=14)
    d.rectangle([24, 24, w - 25, h - 25], outline=(205, 150, 60), width=4)
    # central oval
    ow, oh = w * 0.62, h * 0.42
    box = [cx - ow / 2, cy - oh / 2, cx + ow / 2, cy + oh / 2]
    d.ellipse(box, fill=(18, 10, 6), outline=(225, 170, 70), width=8)
    inner = [box[0] + 26, box[1] + 26, box[2] - 26, box[3] - 26]
    d.ellipse(inner, outline=(160, 80, 30), width=4)
    # three-point star of the three dorm colours
    for k, col in enumerate([(200, 30, 25), (240, 200, 40), (40, 90, 220)]):
        a = -math.pi / 2 + k * 2 * math.pi / 3
        tip = (cx + math.cos(a) * oh * 0.32, cy + math.sin(a) * oh * 0.32)
        l = (cx + math.cos(a + 2.5) * oh * 0.08, cy + math.sin(a + 2.5) * oh * 0.08)
        r = (cx + math.cos(a - 2.5) * oh * 0.08, cy + math.sin(a - 2.5) * oh * 0.08)
        d.polygon([tip, l, (cx, cy), r], fill=col)
    d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=(240, 190, 80))
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 34)
    except Exception:
        f = ImageFont.load_default()
    d.text((cx, h - 70), "DUEL ACADEMY", fill=(230, 180, 80), font=f, anchor="mm")
    return np.asarray(img).astype(np.float32) / 255.0


# --------------------------------------------------------------------------- export
TERRAIN_HIRES = {"Grass", "Sand", "Rock", "Dirt", "Paving"}


def build_textures(log=print):
    os.makedirs(C.OUT_TEXTURES, exist_ok=True)
    sets_lo = make_detail_set(512)
    sets_hi = make_detail_set(1024)
    for name in sets_lo:
        d, h = (sets_hi if name in TERRAIN_HIRES else sets_lo)[name]
        save_gray(d, os.path.join(C.OUT_TEXTURES, f"T_{name}_D.png"))
        save_rgb(normal_from_height(norm01(h), 3.0), os.path.join(C.OUT_TEXTURES, f"T_{name}_N.png"))
    save_rgb(water_normal(), os.path.join(C.OUT_TEXTURES, "T_WaterNormal.png"))
    save_rgb(lava(), os.path.join(C.OUT_TEXTURES, "T_Lava.png"))
    save_gray(noise_tex(), os.path.join(C.OUT_TEXTURES, "T_Noise.png"))
    save_rgb(card_back(), os.path.join(C.OUT_TEXTURES, "T_CardBack.png"))
    # neutral defaults for the PBR masters (one per sampler type)
    save_rgb(np.ones((8, 8, 3), np.float32), os.path.join(C.OUT_TEXTURES, "T_White.png"))
    save_rgb(np.tile(np.array([0.5, 0.5, 1.0], np.float32), (8, 8, 1)), os.path.join(C.OUT_TEXTURES, "T_FlatNormal.png"))
    save_rgb(np.tile(np.array([1.0, 1.0, 0.0], np.float32), (8, 8, 1)), os.path.join(C.OUT_TEXTURES, "T_DefaultMask.png"))
    log(f"  textures: {len(sets_lo) * 2 + 4} written")
    os.makedirs(C.OUT_DATA, exist_ok=True)
    build_photo_textures(log)
    return sorted(sets_lo)


# =========================================================================== third-party photo texture sets
# Registry sections (Tools/thirdparty/registry/*.json):
#   "textures": {"<DetailName>": {"albedo": "...", "normal": "...", "normal_gl": true, "rough": "..."}}
#       replaces T_<DetailName>_D (luminance detail of the photo) and T_<DetailName>_N
#   "terrain":  {"<Layer>": {"albedo": ..., "normal": ..., "normal_gl": ..., "rough": ..., "tile_m": 4.0,
#                            "tint": [1, 1, 1]}}
#       -> T_Terrain_<Layer>_BC / _N / _R  (full colour layers for M_DA_Terrain)
TERRAIN_LAYER_NAMES = ["Grass", "ForestFloor", "Sand", "WetSand", "Ash", "Rock", "Dirt", "Paving"]
TERRAIN_FALLBACK_DETAIL = {"Grass": "Grass", "ForestFloor": "Leaves", "Sand": "Sand", "WetSand": "Sand",
                           "Ash": "Rock", "Rock": "Rock", "Dirt": "Dirt", "Paving": "Paving"}
TERRAIN_DEFAULT_TILE_M = {"Grass": 4.0, "ForestFloor": 4.0, "Sand": 4.0, "WetSand": 4.0, "Ash": 6.0,
                          "Rock": 8.0, "Dirt": 4.0, "Paving": 3.0}


def _tp():
    from . import thirdparty
    return thirdparty


def _load_img(rel, size, mode="RGB"):
    path = _tp().tp_path(rel)
    img = Image.open(path)
    if img.mode in ("I;16", "I", "F") and mode != "L":
        arr = np.asarray(img, dtype=np.float32)
        arr = arr / max(arr.max(), 1.0)
        img = Image.fromarray((arr * 255).astype(np.uint8))
    img = img.convert(mode)
    if size and img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS)
    return np.asarray(img).astype(np.float32) / 255.0


def _dx_normal(arr, gl):
    arr = arr.copy()
    if gl:
        arr[..., 1] = 1.0 - arr[..., 1]
    return arr


def _rough(spec, size):
    """Roughness from a plain map ("rough") or the G channel of a packed AO/Rough/Metal map ("arm")."""
    if spec.get("rough"):
        r = _load_img(spec["rough"], size, "L")
    elif spec.get("arm"):
        r = _load_img(spec["arm"], size)[..., 1]
    else:
        return np.full((size, size), 0.85, np.float32)
    return np.clip(r * spec.get("rough_scale", 1.0), 0.0, 1.0)


def photo_detail(spec, size=1024, contrast=0.35):
    """Grayscale detail (mean 0.5) + DX normal from a photo texture set."""
    alb = _load_img(spec["albedo"], size)
    lum = alb[..., 0] * 0.2126 + alb[..., 1] * 0.7152 + alb[..., 2] * 0.0722
    d = detail_from(lum, 0.5, contrast)
    nrm = _dx_normal(_load_img(spec["normal"], size), spec.get("normal_gl", True)) if spec.get("normal") else None
    return d, nrm


def build_photo_textures(log=print):
    """Overrides detail / normal textures with registered photo sets and writes the terrain layer sets."""
    reg = _tp().registry()
    n_detail = 0
    for name, spec in reg.get("textures", {}).items():
        try:
            if name == "WaterNormal":
                arr = _dx_normal(_load_img(spec["normal"], 1024), spec.get("normal_gl", True))
                save_rgb(arr, os.path.join(C.OUT_TEXTURES, "T_WaterNormal.png"))
                n_detail += 1
                continue
            size = spec.get("size", 1024)
            d, nrm = photo_detail(spec, size, spec.get("contrast", 0.35))
            save_gray(d, os.path.join(C.OUT_TEXTURES, f"T_{name}_D.png"))
            if nrm is not None:
                save_rgb(nrm, os.path.join(C.OUT_TEXTURES, f"T_{name}_N.png"))
            n_detail += 1
        except Exception as e:  # noqa: BLE001
            log(f"  !! texture set {name}: {e}")

    from . import palette
    tints = dict(palette.TERRAIN_LAYERS)
    layer_info = {}
    for layer in TERRAIN_LAYER_NAMES:
        spec = reg.get("terrain", {}).get(layer)
        bc_path = os.path.join(C.OUT_TEXTURES, f"T_Terrain_{layer}_BC.jpg")
        n_path = os.path.join(C.OUT_TEXTURES, f"T_Terrain_{layer}_N.png")
        r_path = os.path.join(C.OUT_TEXTURES, f"T_Terrain_{layer}_R.png")
        try:
            if spec:
                size = spec.get("size", 1024)
                bc = _load_img(spec["albedo"], size) * np.array(spec.get("tint", [1, 1, 1]), np.float32)
                nrm = _dx_normal(_load_img(spec["normal"], size), spec.get("normal_gl", True)) if spec.get("normal") \
                    else np.tile(np.array([0.5, 0.5, 1.0], np.float32), (size, size, 1))
                rough = _rough(spec, size)
                source = "photo"
            else:
                raise KeyError("no photo set")
        except Exception:  # noqa: BLE001  - procedural fallback (tint * detail)
            det = TERRAIN_FALLBACK_DETAIL[layer]
            d = np.asarray(Image.open(os.path.join(C.OUT_TEXTURES, f"T_{det}_D.png")).convert("L")).astype(np.float32) / 255.0
            bc = np.clip(np.array(tints[layer], np.float32)[None, None, :] * (d[..., None] * 2.0), 0, 1)
            nrm = np.asarray(Image.open(os.path.join(C.OUT_TEXTURES, f"T_{det}_N.png")).convert("RGB")).astype(np.float32) / 255.0
            rough = np.full(d.shape, 0.9, np.float32)
            source = "procedural"
        Image.fromarray((np.clip(bc, 0, 1) * 255).astype(np.uint8), "RGB").save(bc_path, quality=92)
        save_rgb(nrm, n_path)
        save_gray(rough, r_path)
        mean = bc.reshape(-1, 3).mean(0)
        layer_info[layer] = dict(mean_srgb=[float(x) for x in mean], source=source,
                                 tile_m=float((spec or {}).get("tile_m", TERRAIN_DEFAULT_TILE_M[layer])))
    os.makedirs(C.CACHE_DIR, exist_ok=True)
    with open(os.path.join(C.CACHE_DIR, "terrain_layers.json"), "w") as fp:
        json.dump(layer_info, fp, indent=1)
    with open(os.path.join(C.OUT_DATA, "terrain_layers.json"), "w") as fp:
        json.dump(layer_info, fp, indent=1)
    n_photo = sum(1 for v in layer_info.values() if v["source"] == "photo")
    log(f"  photo textures: {n_detail} detail sets, terrain layers {n_photo}/{len(layer_info)} from photo sets")
