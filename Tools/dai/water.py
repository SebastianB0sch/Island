"""
Water data for the realistic water shading (numpy only, no Blender - unit-testable).

  clipmap        the ocean surface: a square grid that is dense round its centre and doubles its spacing in
                 every ring outwards (geometry clipmap). ADAOcean keeps it centred under the camera (snapped
                 to OCEAN_SNAP so vertices never slide along the waves), and M_DA_Water displaces it with
                 Gerstner waves - so the waves are finely tessellated wherever you look from, at a fixed cost.
                 Rings are stitched with fans (the fine ring's extra edge vertices are part of the coarse ring's
                 border triangles), so displaced rings never open cracks.
  water_field    T_WaterField over the terrain square: R = water depth under the local surface (sea or
                 lake), G = distance to the shore, B = 1 in the lake. The water material reads it (by world XY)
                 to calm the waves over shallows, roll surf bands onto the beaches and paint shore foam.
  caustics       T_Caustics: light focused by a rippled surface (simulated, tileable) for the sea and lake beds.
"""

import math

import numpy as np

# ------------------------------------------------------------------ ocean clipmap
OCEAN_CORE_CELLS = 64        # core grid (cells per side); every ring has the same 2:1 cell count
OCEAN_CORE_SPACING = 1.5     # m between core vertices (the finest waves are ~8 m long)
OCEAN_LEVELS = 9             # rings after the core: 48 m core half-size * 2**9 = 24.6 km reach
OCEAN_SNAP = 24.0            # m: ADAOcean's snap step = the spacing of ring 4 (384..768 m), where waves fade


def clipmap(core_cells=OCEAN_CORE_CELLS, spacing=OCEAN_CORE_SPACING, levels=OCEAN_LEVELS):
    """(verts (N, 3) float64 metres at z = 0, tris (M, 3) int64 CCW seen from above).

    Coordinates are built on an integer lattice in units of the core spacing, so shared border vertices of
    neighbouring rings are bit-identical and get merged."""
    assert core_cells % 4 == 0, "core_cells must be a multiple of 4 (ring borders sit on half cells)"
    n = core_cells // 2                      # half-size of every level in its own cells
    index = {}
    verts = []
    tris = []

    def vid(ix, iy):
        k = (ix, iy)
        v = index.get(k)
        if v is None:
            v = index[k] = len(verts)
            verts.append(k)
        return v

    def quad(p0, p1, p2, p3):                # CCW corners
        tris.append((p0, p1, p2))
        tris.append((p0, p2, p3))

    # core: (2n x 2n) cells of 1 unit
    for j in range(-n, n):
        for i in range(-n, n):
            quad(vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1))
    for k in range(1, levels + 1):
        s = 2 ** k                           # spacing in core units
        h = n // 2                           # inner border at +-h cells (= the previous level's outer edge)
        for j in range(-n, n):
            for i in range(-n, n):
                if -h <= i < h and -h <= j < h:
                    continue                 # inside: covered by the finer levels
                x0, y0, x1, y1 = i * s, j * s, (i + 1) * s, (j + 1) * s
                c = [vid(x0, y0), vid(x1, y0), vid(x1, y1), vid(x0, y1)]     # SW SE NE NW
                m = s // 2
                # edges touching the finer level get its midpoint vertex (fan of 3 triangles)
                if j == h and -h <= i < h:            # south edge on the inner border
                    mid = vid(x0 + m, y0)
                    tris.extend([(c[0], mid, c[3]), (mid, c[2], c[3]), (mid, c[1], c[2])])
                elif j == -h - 1 and -h <= i < h:     # north edge
                    mid = vid(x0 + m, y1)
                    tris.extend([(c[2], mid, c[1]), (mid, c[0], c[1]), (mid, c[3], c[0])])
                elif i == h and -h <= j < h:          # west edge
                    mid = vid(x0, y0 + m)
                    tris.extend([(c[3], mid, c[2]), (mid, c[1], c[2]), (mid, c[0], c[1])])
                elif i == -h - 1 and -h <= j < h:     # east edge
                    mid = vid(x1, y0 + m)
                    tris.extend([(c[1], mid, c[0]), (mid, c[3], c[0]), (mid, c[2], c[3])])
                else:
                    quad(*c)
    v = np.asarray(verts, np.float64) * spacing
    v = np.concatenate([v, np.zeros((len(v), 1))], axis=1)
    return v, np.asarray(tris, np.int64)


def boundary_edges(tris):
    """Edges used by exactly one triangle (a crack-free sheet has them only on its outer rim)."""
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    e = np.sort(e, axis=1)
    u, cnt = np.unique(e, axis=0, return_counts=True)
    return u[cnt == 1]


# ------------------------------------------------------------------ water field (T_WaterField)
FIELD_TEX = 1024             # texels per side over the terrain square (3 m each)
FIELD_DEPTH = 40.0           # m: R = depth / FIELD_DEPTH
SHORE_MIN, SHORE_MAX = -50.0, 500.0   # m: G = (signed shore distance - SHORE_MIN) / (SHORE_MAX - SHORE_MIN)
EXPOSURE_RADIUS = 120.0      # m: B = how much open, deep sea surrounds a point (sheltered harbour -> low)


def water_field(height, world_size, lake_level, lake_center, lake_radii, lake_rot_deg, n=FIELD_TEX):
    """(n, n, 4) float32 in 0..1, row 0 = north (+Y in Blender, -Y in Unreal), column 0 = west.

      R  depth below the local water surface (lake level inside the lake basin, sea level elsewhere)
      G  signed distance to the shoreline of that water (+ in the water, - on land)
      B  exposure: Gaussian-weighted share of open (> 6 m deep) sea around the point - waves and surf scale with it
         (1 in the lake, whose material sets its own small waves)
      A  1 inside the lake basin
    `height` is the (res, res) heightfield (row 0 = north) covering the same square."""
    from scipy import ndimage

    half = world_size / 2.0
    res = height.shape[0]
    sp = world_size / (res - 1)
    t = (np.arange(n) + 0.5) / n * world_size - half                 # texel centres (m)
    X, Y = np.meshgrid(t, -t)                                         # row 0 = north
    fc = np.clip((X + half) / sp, 0, res - 1.001)
    fr = np.clip((half - Y) / sp, 0, res - 1.001)
    c0, r0 = fc.astype(int), fr.astype(int)
    tc, tr = fc - c0, fr - r0
    h = (height[r0, c0] * (1 - tc) * (1 - tr) + height[r0, c0 + 1] * tc * (1 - tr)
         + height[r0 + 1, c0] * (1 - tc) * tr + height[r0 + 1, c0 + 1] * tc * tr)
    a = math.radians(lake_rot_deg)
    dx, dy = X - lake_center[0], Y - lake_center[1]
    lx = dx * math.cos(a) + dy * math.sin(a)
    ly = -dx * math.sin(a) + dy * math.cos(a)
    lake = ((lx / lake_radii[0]) ** 2 + (ly / lake_radii[1]) ** 2 < 1.3 ** 2) & (h > 0.5 * lake_level)
    surface = np.where(lake, lake_level, 0.0)
    depth = surface - h
    wet = depth > 0.0
    texel = world_size / n
    d_in = ndimage.distance_transform_edt(wet) * texel                # water -> nearest land
    d_out = ndimage.distance_transform_edt(~wet) * texel              # land -> nearest water
    signed = np.where(wet, d_in - 0.5 * texel, -(d_out - 0.5 * texel))
    deep = ((depth > 6.0) & ~lake).astype(np.float64)
    expo = ndimage.gaussian_filter(deep, EXPOSURE_RADIUS / texel, mode="nearest")
    expo = np.clip(expo / 0.4, 0.0, 1.0)                              # 40 % of the neighbourhood open = fully exposed
    expo = np.where(lake, 1.0, expo)                                  # the lake's own (small) waves need no damping
    out = np.stack([np.clip(depth / FIELD_DEPTH, 0, 1),
                    np.clip((signed - SHORE_MIN) / (SHORE_MAX - SHORE_MIN), 0, 1),
                    expo, lake.astype(np.float64)], axis=-1)
    return out.astype(np.float32)


# ------------------------------------------------------------------ caustics (T_Caustics)
def caustics(n=512, seed=7, focus=2.6, waves=20, photons=4):
    """Tileable caustic pattern, traced: rays of sunlight are bent by a periodic rippled surface and counted
    where they land on a flat bed (photons x photons rays per texel). Past the focal distance (focus > 1)
    the light piles up in the bright network of focal lines that real shallows show. (n, n) float32 0..1."""
    from scipy import ndimage
    r = np.random.default_rng(seed)
    m = n * photons
    v, u = np.mgrid[0:m, 0:m].astype(np.float64)
    u = (u + r.random((m, m))) / m               # jittered rays: no moire from a regular ray grid
    v = (v + r.random((m, m))) / m
    gx = np.zeros((m, m))
    gy = np.zeros((m, m))
    curv = 0.0
    for _ in range(waves):                       # periodic ripples (integer wave numbers keep it tileable)
        kx, ky = int(r.integers(-6, 7)), int(r.integers(-6, 7))
        k = math.hypot(kx, ky)
        if k == 0:
            continue
        amp = 1.0 / k ** 2.2
        ph = 2 * math.pi * (kx * u + ky * v) + r.uniform(0, 2 * math.pi)
        c = np.cos(ph) * amp * 2 * math.pi
        gx += c * kx                             # gradient of amp * sin(ph)
        gy += c * ky
        curv += amp * (2 * math.pi * k) ** 2
    s = focus / curv                             # ray offset = -s * slope; s * curvature = 1 is the focus
    px = ((u - s * gx) % 1.0 * n).astype(np.int64) % n
    py = ((v - s * gy) % 1.0 * n).astype(np.int64) % n
    img = np.bincount((py * n + px).ravel(), minlength=n * n).reshape(n, n).astype(np.float64)
    img = ndimage.gaussian_filter(img / (photons * photons), 0.9, mode="wrap")    # 1.0 = unfocused light
    return np.clip((img - 0.3) / 2.2, 0, 1).astype(np.float32)


# ------------------------------------------------------------------ 16-bit PNG (depth needs more than 8 bits)
def save_png16(path, a):
    """Write a (h, w, 3|4) float array in 0..1 as a 16-bit RGB(A) PNG (Pillow cannot)."""
    import struct
    import zlib
    from . import atomic
    a = np.clip(np.asarray(a, np.float64), 0, 1)
    h, w, ch = a.shape
    raw = (a * 65535 + 0.5).astype(">u2").reshape(h, w * ch)
    rows = np.concatenate([np.zeros((h, 1), np.uint8), raw.view(np.uint8).reshape(h, w * ch * 2)], axis=1)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 16, 6 if ch == 4 else 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows.tobytes(), 9)) + chunk(b"IEND", b""))
    with atomic.atomic_path(path) as tmp:
        with open(tmp, "wb") as f:
            f.write(png)
    return path
