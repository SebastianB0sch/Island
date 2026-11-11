"""
Water model shared by the whole pipeline: the Gerstner wave sets, the island-wide water maps and the
tileable water textures. Pure numpy / scipy / Pillow (no bpy), so the tests and the terrain stage can use it.

  OCEAN_WAVES / LAKE_WAVES    the wave sets (metres, Blender axes); `ue_waves` converts them for water.json
  offset / height_at / normal the reference implementation of the wave formula (Docs/WATER.md); the Unreal
                              material (M_DA_Water) and the C++ sampler (DAWaterWaves.h) implement the same one
  wave_mask                   T_WaveMask   - wave amplitude scale (shallows, sheltered water, domain edge)
  shore_map                   T_WaterShore - depth / distance from the shore / submerged / wet band
  build_textures              T_WaterDetailN, T_WaterFoam, T_Caustics, T_Ripples
  water_json                  Data/water.json (wave sets, the wave mask bytes, the rivers) for the engine

Wave i: unit direction D, wavelength L, amplitude A, choppiness s, phase speed c, phase phi.

    k = 2 pi / L,  omega = k c,  theta = k D.p - omega t + phi
    offset.xy = sum D (s A m) cos(theta)        offset.z = sum A m sin(theta)        (m = wave mask)

Only waves the water meshes can carry are in the sets (wavelength >= 4 grid cells: 5 m cells at sea, 1.5 m on
the lake); everything shorter is in the normal maps, where it belongs.
"""

import base64
import math
import os

import numpy as np

from . import config as C

try:                                    # the maps and textures need scipy; the wave model and water.json do not
    from scipy import ndimage
except ImportError:                     # pragma: no cover - CI runs the wave tests with numpy only
    ndimage = None

G = 9.81
MAX_WAVES = 6          # wave slots of M_DA_Water
OCEAN_CELL = 5.0       # m, inner ocean grid (terrain_mesh.build_water)
LAKE_CELL = 1.5        # m, lake grid


def _wave(direction_deg, wavelength, amplitude, steepness, phase):
    """direction: where the wave travels to, degrees counter-clockwise from +X (east), Blender axes."""
    a = math.radians(direction_deg)
    return dict(dir=(math.cos(a), math.sin(a)), wavelength=float(wavelength), amplitude=float(amplitude),
                steepness=float(steepness), speed=math.sqrt(G * wavelength / (2.0 * math.pi)), phase=float(phase))


# A moderate trade-wind sea running up from the south-south-east onto the harbour and the beach: significant
# wave height ~1.3 m in open water (the wave mask calms it towards the shore and inside the breakwater).
OCEAN_WAVES = [
    _wave(100.0, 78.0, 0.30, 0.70, 0.0),
    _wave(70.0, 55.0, 0.24, 0.75, 1.7),
    _wave(124.0, 41.0, 0.19, 0.80, 3.9),
    _wave(52.0, 33.0, 0.15, 0.85, 0.6),
    _wave(142.0, 27.0, 0.12, 0.85, 5.1),
    _wave(86.0, 24.0, 0.10, 0.85, 2.4),
]
# The lake: a light breeze off the volcano, wavelets a hand high.
LAKE_WAVES = [
    _wave(205.0, 11.0, 0.040, 0.60, 0.0),
    _wave(232.0, 7.6, 0.028, 0.65, 2.2),
    _wave(178.0, 6.2, 0.020, 0.65, 4.4),
]

assert len(OCEAN_WAVES) <= MAX_WAVES and len(LAKE_WAVES) <= MAX_WAVES
assert min(w["wavelength"] for w in OCEAN_WAVES) >= 4.0 * OCEAN_CELL
assert min(w["wavelength"] for w in LAKE_WAVES) >= 4.0 * LAKE_CELL


# --------------------------------------------------------------------------- reference implementation
def _terms(waves, x, y, t):
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    for w in waves:
        k = 2.0 * math.pi / w["wavelength"]
        theta = k * (w["dir"][0] * x + w["dir"][1] * y) - k * w["speed"] * t + w["phase"]
        yield w, k, theta


def offset(waves, x, y, t, m=1.0):
    """Displacement (dx, dy, dz) of the surface point that rests at (x, y)."""
    dx = dy = dz = 0.0
    for w, k, th in _terms(waves, x, y, t):
        b = w["steepness"] * w["amplitude"] * m
        dx = dx + w["dir"][0] * b * np.cos(th)
        dy = dy + w["dir"][1] * b * np.cos(th)
        dz = dz + w["amplitude"] * m * np.sin(th)
    return dx, dy, dz


def height_at(waves, x, y, t, m=1.0, iterations=3):
    """Surface height above the rest level at the fixed position (x, y): the displaced surface inverted by
    fixed-point iteration (q = p - offset.xy(q))."""
    qx, qy = np.asarray(x, np.float64), np.asarray(y, np.float64)
    for _ in range(iterations):
        dx, dy, _dz = offset(waves, qx, qy, t, m)
        qx, qy = x - dx, y - dy
    return offset(waves, qx, qy, t, m)[2]


def normal(waves, x, y, t, m=1.0):
    nx = ny = 0.0
    nz = 1.0
    for w, k, th in _terms(waves, x, y, t):
        a = k * w["amplitude"] * m
        nx = nx - w["dir"][0] * a * np.cos(th)
        ny = ny - w["dir"][1] * a * np.cos(th)
        nz = nz - w["steepness"] * a * np.sin(th)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    return nx / n, ny / n, nz / n


def max_fold(waves):
    """Upper bound of the fold term sum(k s A sin(theta)): crests overlap (loops) above 1."""
    return sum(2.0 * math.pi / w["wavelength"] * w["steepness"] * w["amplitude"] for w in waves)


def ue_waves(waves):
    """Wave set in Unreal units and axes (cm, y mirrored) for water.json."""
    return [dict(dir=[round(w["dir"][0], 6), round(-w["dir"][1], 6)], wavelength=round(w["wavelength"] * 100.0, 2),
                 amplitude=round(w["amplitude"] * 100.0, 3), steepness=round(w["steepness"], 4),
                 speed=round(w["speed"] * 100.0, 2), phase=round(w["phase"], 4)) for w in waves]


# --------------------------------------------------------------------------- island-wide maps
WAVE_MASK_SIZE = 256
SHORE_SIZE = 2048
SHORE_DEPTH_M = 8.0        # T_WaterShore.R = 1 at this depth
SHORE_DIST_M = 40.0        # T_WaterShore.G = 1 this far out from the waterline
WET_BAND_M = 4.0           # T_WaterShore.A falls to 0 this far up the bank / beach
EDGE_FADE_M = 220.0        # waves die away towards the edge of the fine ocean grid (flat, coarse sea beyond)


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _resize(a, size, order=1):
    z = size / a.shape[0]
    out = ndimage.zoom(a, z, order=order)
    if out.shape[0] != size:           # zoom rounds; make the shape exact
        out = np.pad(out, ((0, max(0, size - out.shape[0])), (0, max(0, size - out.shape[1]))), mode="edge")
    return out[:size, :size]


def wave_mask(h, sp):
    """Wave amplitude scale 0..1 on the heightfield grid: deep open water 1, shallows and sheltered water
    (the harbour basin behind the breakwater, coves, between the sea stacks) calm, 0 at the edge of the domain
    so the coarse far sea stays flat and the mesh rings do not crack."""
    sea = (h < 0.0).astype(np.float32)
    depth = np.clip(-h, 0.0, None)
    shoal = _smoothstep(0.4, 9.0, depth)                       # waves feel the bottom
    # openness: how much of the neighbourhood (~130 m) is sea - a straight coast sees half, a basin far less
    openness = ndimage.gaussian_filter(sea, 65.0 / sp, mode="nearest")
    shelter = _smoothstep(0.42, 0.92, openness)
    m = 0.06 + 0.94 * shoal * shelter
    m = ndimage.gaussian_filter(m.astype(np.float32), 9.0 / sp, mode="nearest")
    res = h.shape[0]
    half = sp * (res - 1) / 2.0
    xs = -half + np.arange(res) * sp
    edge = half - np.maximum(np.abs(xs)[None, :], np.abs(xs)[:, None])
    m = m * _smoothstep(12.0, 12.0 + EDGE_FADE_M, edge) * sea
    return ndimage.gaussian_filter(m.astype(np.float32), 4.0 / sp, mode="nearest")


def shore_map(h, level, sp):
    """T_WaterShore channels on the heightfield grid. `level`: water surface height per cell, NaN where dry."""
    wet = np.isfinite(level)
    lv = np.where(wet, level, 0.0)
    depth = np.clip((lv - h) / SHORE_DEPTH_M, 0.0, 1.0) * wet
    d_in = ndimage.distance_transform_edt(wet).astype(np.float32) * sp          # into the water
    d_out, idx = ndimage.distance_transform_edt(~wet, return_indices=True)
    d_out = d_out.astype(np.float32) * sp
    near_level = lv[idx[0], idx[1]]                                              # level of the nearest water
    r = depth.astype(np.float32)
    g = np.clip(d_in / SHORE_DIST_M, 0.0, 1.0)
    b = ndimage.gaussian_filter(wet.astype(np.float32), 0.8)
    a = (1.0 - np.clip(d_out / WET_BAND_M, 0.0, 1.0)) * (1.0 - _smoothstep(0.25, 1.1, h - near_level)) * (~wet)
    a = ndimage.gaussian_filter(a.astype(np.float32), 0.7)
    return r, g, b, a


def save_maps(h, level, sp, out_textures):
    """Writes T_WaveMask.png / T_WaterShore.png and returns the wave mask bytes (row 0 = north)."""
    from PIL import Image
    from . import atomic

    def u8(x):
        return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)

    m = u8(_resize(wave_mask(h, sp), WAVE_MASK_SIZE))
    atomic.save_image(Image.fromarray(np.stack([m, m, m], -1), "RGB"), os.path.join(out_textures, "T_WaveMask.png"),
                      optimize=True)
    chans = [u8(_resize(c, SHORE_SIZE)) for c in shore_map(h, level, sp)]
    atomic.save_image(Image.fromarray(np.stack(chans, -1), "RGBA"), os.path.join(out_textures, "T_WaterShore.png"),
                      optimize=True)
    return m


def sample_mask(mask_u8, x, y):
    """Wave mask at world (x, y) metres (Blender axes): bilinear with clamping, exactly like the GPU."""
    n = mask_u8.shape[0]
    u = (np.asarray(x, np.float64) + C.HALF) / C.WORLD_SIZE * n - 0.5
    v = (C.HALF - np.asarray(y, np.float64)) / C.WORLD_SIZE * n - 0.5
    u0 = np.floor(u)
    v0 = np.floor(v)
    fu, fv = u - u0, v - v0
    c0 = np.clip(u0, 0, n - 1).astype(int)
    c1 = np.clip(u0 + 1, 0, n - 1).astype(int)
    r0 = np.clip(v0, 0, n - 1).astype(int)
    r1 = np.clip(v0 + 1, 0, n - 1).astype(int)
    a = mask_u8.astype(np.float64) / 255.0
    return (a[r0, c0] * (1 - fu) * (1 - fv) + a[r0, c1] * fu * (1 - fv)
            + a[r1, c0] * (1 - fu) * fv + a[r1, c1] * fu * fv)


def water_json(mask_u8, rivers):
    """Data/water.json. rivers: [(id, name, [(x, y, z, half_width)] in metres, Blender axes)]."""
    hx = C.HALF * 100.0
    return dict(
        version=1, sea_level=C.SEA_LEVEL * 100.0,
        ocean=dict(waves=ue_waves(OCEAN_WAVES), max_fold=round(max_fold(OCEAN_WAVES), 5)),
        lake=dict(level=C.LAKE_LEVEL * 100.0, waves=ue_waves(LAKE_WAVES), max_fold=round(max_fold(LAKE_WAVES), 5)),
        wave_mask=dict(texture="T_WaveMask", size=int(mask_u8.shape[0]), min=[-hx, -hx], max=[hx, hx],
                       data=base64.b64encode(np.ascontiguousarray(mask_u8).tobytes()).decode("ascii")),
        rivers=[dict(id=rid, name=name,
                     points=[[round(x * 100.0, 1), round(-y * 100.0, 1), round(z * 100.0, 1), round(hw * 100.0, 1)]
                             for (x, y, z, hw, *_rest) in pts]) for rid, name, pts in rivers])


# --------------------------------------------------------------------------- tileable textures
def _save(arr, path, mode):
    from PIL import Image
    from . import atomic
    atomic.save_image(Image.fromarray((np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), mode), path,
                      optimize=True)


def spectrum_height(n=1024, tile_m=24.0, wind=(1.0, 0.35), wind_speed=5.5, seed=7, k_cut=None):
    """Tileable wind-sea height field from a Phillips spectrum (Tessendorf), unit variance."""
    rng = np.random.default_rng(seed)
    k1 = np.fft.fftfreq(n, d=tile_m / n) * 2.0 * math.pi
    kx, ky = np.meshgrid(k1, k1)
    k = np.hypot(kx, ky)
    k[0, 0] = 1.0
    wl = math.hypot(*wind)
    wx, wy = wind[0] / wl, wind[1] / wl
    big = wind_speed * wind_speed / G                     # largest wave the wind raises
    small = tile_m / n * 2.5                              # damp what the texel grid cannot hold
    align = (kx / k * wx + ky / k * wy)
    ph = np.exp(-1.0 / (k * big) ** 2) / k ** 4 * (0.12 + 0.88 * align * align) * np.exp(-(k * small) ** 2)
    ph[0, 0] = 0.0
    if k_cut is not None:                                 # keep only waves shorter than k_cut metres
        ph = ph * (1.0 - np.exp(-(k * k_cut / (2.0 * math.pi)) ** 4))
    spec = (rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))) * np.sqrt(ph)
    hgt = np.real(np.fft.ifft2(spec))
    return (hgt / (hgt.std() + 1e-12)).astype(np.float32), (kx, ky, spec)


def detail_normal(n=1024):
    """T_WaterDetailN: wind ripples and capillary waves (two crossing wave trains), DirectX normal map."""
    def slopes(tile_m, wind, speed, seed, k_cut):
        _h, (kx, ky, spec) = spectrum_height(n, tile_m, wind, speed, seed, k_cut)
        sx = np.real(np.fft.ifft2(1j * kx * spec))
        sy = np.real(np.fft.ifft2(1j * ky * spec))
        s = math.sqrt(float((sx * sx + sy * sy).mean())) + 1e-12
        return sx / s, sy / s

    ax, ay = slopes(16.0, (1.0, 0.3), 4.5, 7, 5.0)
    bx, by = slopes(6.0, (0.55, 1.0), 3.0, 8, 1.6)
    sx = (ax * 0.75 + bx * 0.55) * 0.34
    sy = (ay * 0.75 + by * 0.55) * 0.34
    nz = 1.0 / np.sqrt(sx * sx + sy * sy + 1.0)
    # image row runs down, so +y of the field is -row: DirectX green = +slope along the row axis
    return np.stack([-sx * nz * 0.5 + 0.5, sy * nz * 0.5 + 0.5, nz * 0.5 + 0.5], -1).astype(np.float32)


def _worley(n, cells, seed, k=2):
    """Distances to the k nearest of `cells`^2 jittered feature points, periodic, in cell units."""
    from scipy.spatial import cKDTree
    rng = np.random.default_rng(seed)
    gx, gy = np.meshgrid(np.arange(cells), np.arange(cells))
    pts = np.stack([(gx.ravel() + rng.random(gx.size)) / cells, (gy.ravel() + rng.random(gy.size)) / cells], -1) % 1.0
    tree = cKDTree(pts, boxsize=1.0)
    v, u = np.mgrid[0:n, 0:n].astype(np.float64) / n
    d, i = tree.query(np.stack([u.ravel(), v.ravel()], -1), k=k)
    return d.reshape(n, n, k) * cells, i.reshape(n, n, k), pts


def _warp(n, a, amount, seed):
    """Periodic domain warp of a tileable image by smooth noise (keeps it tileable)."""
    from .textures import spectral
    du = spectral(n, 3.0, seed) * amount * n
    dv = spectral(n, 3.0, seed + 1) * amount * n
    v, u = np.mgrid[0:n, 0:n].astype(np.float64)
    return ndimage.map_coordinates(a, [(v + dv) % n, (u + du) % n], order=1, mode="wrap")


def foam(n=1024):
    """T_WaterFoam: R thick foam blobs, G lacy foam network (the cell walls between bubbles), B fine bubbles."""
    from .textures import norm01, spectral
    d1, _i, _p = _worley(n, 14, 21)
    d2, _i, _p = _worley(n, 34, 22)
    lace = np.clip(1.0 - (d1[..., 1] - d1[..., 0]) * 3.2, 0, 1) ** 1.6 * 0.75 \
        + np.clip(1.0 - (d2[..., 1] - d2[..., 0]) * 3.6, 0, 1) ** 2.0 * 0.45
    lace = _warp(n, np.clip(lace, 0, 1), 0.012, 23)
    cloud = norm01(spectral(n, 2.4, 24))
    blobs = np.clip((cloud - 0.42) * 3.2, 0, 1)
    thick = np.clip(blobs * (0.55 + 0.45 * lace) + np.clip(blobs - 0.6, 0, 1) * 0.8, 0, 1)
    d3, _i, _p = _worley(n, 90, 25)
    bubbles = np.clip(1.0 - d3[..., 0] * 2.6, 0, 1) ** 2.0
    bubbles = np.clip(bubbles * 0.9 + norm01(spectral(n, 0.8, 26)) * 0.25, 0, 1)
    return np.stack([thick, np.clip(lace, 0, 1), bubbles], -1).astype(np.float32)


def caustics(n=512):
    """T_Caustics: the bright net sunlight draws on a shallow bed - thin warped cell walls, two scales."""
    d1, _i, _p = _worley(n, 7, 31)
    d2, _i, _p = _worley(n, 12, 32)
    a = np.clip(1.0 - (d1[..., 1] - d1[..., 0]) * 2.4, 0, 1) ** 3.0
    b = np.clip(1.0 - (d2[..., 1] - d2[..., 0]) * 2.6, 0, 1) ** 3.0
    c = _warp(n, a, 0.03, 33) * 0.8 + _warp(n, b, 0.02, 35) * 0.45
    c = ndimage.gaussian_filter(c, 0.8, mode="wrap")
    c = np.clip(c / (np.percentile(c, 99.5) + 1e-9), 0, 1)
    return np.repeat(c[..., None], 3, -1).astype(np.float32)


def ripples(n=512, cells=6, seed=41):
    """T_Ripples (rain-ring data, see Docs/WATER.md): R = 1 at a drop's centre falling to 0 at the ring's
    outer edge, GB = direction away from the centre, A = that drop's time offset."""
    d, i, pts = _worley(n, cells, seed, k=1)
    rng = np.random.default_rng(seed + 1)
    # ring radius in cells: at most half the way to the nearest other drop, so no ring is cut off by its
    # neighbour's (the texture is a Voronoi diagram of the drops)
    from scipy.spatial import cKDTree
    nn = cKDTree(pts, boxsize=1.0).query(pts, k=2)[0][:, 1] * cells
    radius = np.minimum(0.47, nn * 0.5)[i[..., 0]]
    dist = d[..., 0]
    r = np.clip(1.0 - dist / radius, 0.0, 1.0)
    v, u = np.mgrid[0:n, 0:n].astype(np.float64) / n
    c = pts[i[..., 0]]
    dx = (u - c[..., 0] + 0.5) % 1.0 - 0.5
    dy = (v - c[..., 1] + 0.5) % 1.0 - 0.5
    ln = np.hypot(dx, dy) + 1e-9
    live = r > 0.0
    gdir = np.where(live, dx / ln, 0.0) * 0.5 + 0.5
    bdir = np.where(live, dy / ln, 0.0) * 0.5 + 0.5
    offs = rng.random(len(pts))[i[..., 0]]
    return np.stack([r, gdir, bdir, offs], -1).astype(np.float32)


def build_textures(out_textures=None, log=print):
    out = out_textures or C.OUT_TEXTURES
    os.makedirs(out, exist_ok=True)
    _save(detail_normal(), os.path.join(out, "T_WaterDetailN.png"), "RGB")
    _save(foam(), os.path.join(out, "T_WaterFoam.png"), "RGB")
    _save(caustics(), os.path.join(out, "T_Caustics.png"), "RGB")
    _save(ripples(), os.path.join(out, "T_Ripples.png"), "RGBA")
    log("  water textures: T_WaterDetailN, T_WaterFoam, T_Caustics, T_Ripples")
