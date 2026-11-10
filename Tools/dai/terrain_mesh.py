"""
Terrain / water surface meshes built from the heightfield.

Terrain chunks are exported with world-space vertices (pivot at the world
origin) so they line up automatically in Unreal. Normals come from the full
heightfield gradient (custom split normals) so there are no lighting seams at
chunk borders. UV0 maps the whole island to 0..1 (Blender V up = north), which
the terrain material uses to sample the splat maps.
"""

import math
import os

import bpy
import numpy as np

from . import blend
from . import config as C


def _mesh_from_arrays(name, verts, faces, uvs=None, normals=None, mat="M_Terrain", smooth=True):
    mesh = bpy.data.meshes.new(name)
    nv = len(verts)
    nf = len(faces)
    mesh.vertices.add(nv)
    mesh.vertices.foreach_set("co", verts.astype(np.float32).ravel())
    corners = faces.shape[1]
    mesh.loops.add(nf * corners)
    mesh.loops.foreach_set("vertex_index", faces.astype(np.int32).ravel())
    mesh.polygons.add(nf)
    mesh.polygons.foreach_set("loop_start", (np.arange(nf, dtype=np.int32) * corners))
    mesh.polygons.foreach_set("loop_total", np.full(nf, corners, dtype=np.int32))
    mesh.update(calc_edges=True)
    mesh.validate(clean_customdata=False)
    mesh.materials.append(blend.material(mat))
    mesh.polygons.foreach_set("use_smooth", np.full(nf, smooth, dtype=bool))
    if uvs is not None:
        uvl = mesh.uv_layers.new(name="UVMap")
        loop_uv = uvs[faces.ravel()]
        uvl.data.foreach_set("uv", loop_uv.astype(np.float32).ravel())
    if normals is not None:
        mesh.normals_split_custom_set_from_vertices([tuple(n) for n in normals])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def grid_mesh(name, xs, ys, zs, normals=None, uv_fn=None, mat="M_Terrain"):
    """xs: (ncols,), ys: (nrows,), zs: (nrows, ncols). Rows run north->south."""
    nr, nc = zs.shape
    X, Y = np.meshgrid(xs, ys)
    verts = np.stack([X.ravel(), Y.ravel(), zs.ravel()], axis=1)
    r, c = np.meshgrid(np.arange(nr - 1), np.arange(nc - 1), indexing="ij")
    a = (r * nc + c).ravel()
    b = a + 1
    d = a + nc
    e = d + 1
    # CCW seen from above: (a: NW) -> (d: SW) -> (e: SE) -> (b: NE)
    faces = np.stack([a, d, e, b], axis=1)
    uvs = uv_fn(verts) if uv_fn else None
    nrm = normals.reshape(-1, 3) if normals is not None else None
    return _mesh_from_arrays(name, verts, faces, uvs, nrm, mat)


def terrain_uv(verts):
    u = (verts[:, 0] + C.HALF) / C.WORLD_SIZE
    v = (verts[:, 1] + C.HALF) / C.WORLD_SIZE
    return np.stack([u, v], axis=1)


def build_chunks(h, export=True, log=print, keep=False):
    n = C.MESH_QUADS
    step = (C.FIELD_RES - 1) // n
    hs = h[::step, ::step].astype(np.float64)
    sp = C.WORLD_SIZE / n
    gy, gx = np.gradient(hs, sp)            # gy = dh/drow = -dh/dy
    nrm = np.stack([-gx, gy, np.ones_like(gx)], axis=-1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    q = n // C.CHUNKS
    xs_all = -C.HALF + np.arange(n + 1) * sp
    ys_all = C.HALF - np.arange(n + 1) * sp
    objs = []
    for cj in range(C.CHUNKS):          # rows (north -> south)
        for ci in range(C.CHUNKS):      # cols (west -> east)
            r0, c0 = cj * q, ci * q
            zs = hs[r0:r0 + q + 1, c0:c0 + q + 1]
            name = f"SM_Terrain_{ci:02d}_{cj:02d}"
            o = grid_mesh(name, xs_all[c0:c0 + q + 1], ys_all[r0:r0 + q + 1], zs,
                          nrm[r0:r0 + q + 1, c0:c0 + q + 1], terrain_uv)
            if export:
                blend.export_fbx([o], os.path.join(C.OUT_MESHES, "Terrain", name + ".fbx"))
            if keep:
                objs.append(o)
            else:
                blend.delete([o])
    log(f"  terrain: {C.CHUNKS * C.CHUNKS} chunks of {q}x{q} quads ({sp:.2f} m)")
    return objs


def build_preview_terrain(h, quads=504):
    """Single lower resolution terrain object for Blender preview renders."""
    step = (C.FIELD_RES - 1) // quads
    hs = h[::step, ::step].astype(np.float64)
    sp = C.WORLD_SIZE / quads
    gy, gx = np.gradient(hs, sp)
    nrm = np.stack([-gx, gy, np.ones_like(gx)], axis=-1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    xs = -C.HALF + np.arange(quads + 1) * sp
    ys = C.HALF - np.arange(quads + 1) * sp
    return grid_mesh("PreviewTerrain", xs, ys, hs, nrm, terrain_uv)


def flat_square(name, half, z, cells, mat):
    xs = np.linspace(-half, half, cells + 1)
    ys = np.linspace(half, -half, cells + 1)
    zs = np.full((cells + 1, cells + 1), z)
    nrm = np.zeros((cells + 1, cells + 1, 3))
    nrm[..., 2] = 1.0
    uv = lambda v: np.stack([v[:, 0] / 100.0, v[:, 1] / 100.0], axis=1)
    return grid_mesh(name, xs, ys, zs, nrm, uv, mat)


def tri_mesh(name, verts, tris, uvs, mat, uvs2=None):
    """Triangle soup with shared vertices, flat-up normals, one or two UV sets (water surfaces)."""
    verts = np.asarray(verts, np.float64)
    tris = np.asarray(tris, np.int64).reshape(-1, 3)
    obj = _mesh_from_arrays(name, verts, tris, np.asarray(uvs, np.float64), None, mat)
    mesh = obj.data
    if uvs2 is not None:
        uvl = mesh.uv_layers.new(name="UVData")
        uvl.data.foreach_set("uv", np.asarray(uvs2, np.float32)[tris.ravel()].ravel())
    mesh.update()
    return obj


def _compact(verts, tris, *attrs):
    """Drop unused vertices; returns (verts, tris, *attrs) re-indexed."""
    tris = np.asarray(tris, np.int64).reshape(-1, 3)
    used = np.unique(tris)
    remap = np.full(len(verts), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    return (verts[used], remap[tris]) + tuple(a[used] for a in attrs)


def _grid_tris(keep, nc):
    """Two triangles (CCW from above) for every kept cell of a row-major vertex grid with nc columns;
    keep[r, c] is the cell whose north-west vertex is (r, c). Rows run north -> south."""
    r, c = np.nonzero(keep)
    a = r * nc + c
    b, d = a + 1, a + nc
    e = d + 1
    return np.concatenate([np.stack([a, d, e], 1), np.stack([a, e, b], 1)])


def ocean_surface(h):
    """Ocean mesh for a displaced sea: a 5 m grid over the terrain domain wherever there is sea (or land low
    enough for a wave to wash over), then rings of doubling cell size out to 20 km. The rings are stitched
    2:1 (no T-junctions), and the wave mask is zero from the domain edge outwards, so they stay flat."""
    from . import water as W
    from .terrain import Field
    cell = W.OCEAN_CELL
    half = math.ceil(C.HALF / cell / 2.0) * 2.0 * cell           # 1540 m: an even number of 5 m cells
    n = int(round(2 * half / cell))
    xs = -half + np.arange(n + 1) * cell
    ys = half - np.arange(n + 1) * cell
    X, Y = np.meshgrid(xs, ys)
    low = Field(h)(X, Y) < 1.2                                    # vertices a crest can reach
    keep = low[:-1, :-1] | low[1:, :-1] | low[:-1, 1:] | low[1:, 1:]
    keep[[0, -1], :] = True                                       # the rim the first ring is stitched to
    keep[:, [0, -1]] = True
    verts = [np.stack([X.ravel(), Y.ravel()], 1)]
    tris = [_grid_tris(keep, n + 1)]
    base = (n + 1) * (n + 1)
    # ---- rings: cell size doubles; the ring's inner row of cells fans onto the finer boundary's midpoints
    index = {}
    for i, (x, y) in enumerate(verts[0]):
        if abs(abs(x) - half) < 1e-6 or abs(abs(y) - half) < 1e-6:
            index[(round(x * 4), round(y * 4))] = i
    ring_v = []

    def vid(x, y):
        k = (round(x * 4), round(y * 4))
        if k not in index:
            index[k] = base + len(ring_v)
            ring_v.append((x, y))
        return index[k]

    ring_t = []
    r_in, c = half, cell
    while r_in < C.OCEAN_RADIUS * 1.2:
        c2 = c * 2.0
        width = 2 if int(round(r_in / c2)) % 2 == 0 else 3        # keeps the next boundary on the next grid
        if r_in + width * c2 > C.OCEAN_RADIUS * 1.3:
            width = 1
        r_out = r_in + width * c2
        m = int(round(2 * r_out / c2))
        for j in range(m):
            for i in range(m):
                x0, y1 = -r_out + i * c2, r_out - j * c2          # cell: west edge x0, north edge y1
                x1, y0 = x0 + c2, y1 - c2
                if x0 >= -r_in - 1e-6 and x1 <= r_in + 1e-6 and y0 >= -r_in - 1e-6 and y1 <= r_in + 1e-6:
                    continue                                       # inside the previous level
                nw, ne, sw, se = vid(x0, y1), vid(x1, y1), vid(x0, y0), vid(x1, y0)
                # an edge lying on the inner boundary has a finer vertex at its middle
                mid = None
                if abs(y0 - r_in) < 1e-6 and -r_in - 1e-6 <= x0 and x1 <= r_in + 1e-6:
                    mid = ("s", vid(x0 + c, y0))
                elif abs(y1 + r_in) < 1e-6 and -r_in - 1e-6 <= x0 and x1 <= r_in + 1e-6:
                    mid = ("n", vid(x0 + c, y1))
                elif abs(x1 + r_in) < 1e-6 and -r_in - 1e-6 <= y0 and y1 <= r_in + 1e-6:
                    mid = ("e", vid(x1, y0 + c))
                elif abs(x0 - r_in) < 1e-6 and -r_in - 1e-6 <= y0 and y1 <= r_in + 1e-6:
                    mid = ("w", vid(x0, y0 + c))
                if mid is None:
                    ring_t += [(nw, sw, se), (nw, se, ne)]
                elif mid[0] == "s":
                    ring_t += [(nw, sw, mid[1]), (nw, mid[1], ne), (ne, mid[1], se)]
                elif mid[0] == "n":
                    ring_t += [(sw, se, mid[1]), (sw, mid[1], nw), (mid[1], se, ne)]
                elif mid[0] == "e":
                    ring_t += [(nw, sw, mid[1]), (nw, mid[1], ne), (sw, se, mid[1])]
                else:
                    ring_t += [(sw, se, mid[1]), (mid[1], se, ne), (mid[1], ne, nw)]
        r_in, c = r_out, c2
    v2 = np.vstack(verts + ([np.asarray(ring_v, np.float64)] if ring_v else []))
    t = np.vstack(tris + ([np.asarray(ring_t, np.int64)] if ring_t else []))
    v3 = np.concatenate([v2, np.zeros((len(v2), 1))], 1)
    v3, t = _compact(v3, t)
    uvs = np.stack([v3[:, 0] / 100.0, v3[:, 1] / 100.0], 1)
    return v3, t, uvs


def lake_surface(level):
    """Lake mesh: a 1.5 m grid (fine enough for the lake's wavelets) over every lake cell of the water raster."""
    from scipy import ndimage
    from . import water as W
    from .terrain import Field
    lake = np.isfinite(level) & (np.abs(level - C.LAKE_LEVEL) < 1e-3)
    lake = ndimage.binary_dilation(lake, iterations=2).astype(np.float32)
    lcx, lcy = C.LAKE_CENTER
    ext = max(C.LAKE_RADII) * 1.2
    cell = W.LAKE_CELL
    n = int(2 * ext / cell)
    xs = lcx - ext + np.arange(n + 1) * cell
    ys = lcy + ext - np.arange(n + 1) * cell
    X, Y = np.meshgrid(xs, ys)
    inside = Field(lake)(X, Y) > 0.25
    keep = inside[:-1, :-1] | inside[1:, :-1] | inside[:-1, 1:] | inside[1:, 1:]
    verts = np.stack([X.ravel(), Y.ravel(), np.full(X.size, C.LAKE_LEVEL)], 1)
    verts, tris = _compact(verts, _grid_tris(keep, n + 1))
    uvs = np.stack([verts[:, 0] / 50.0, verts[:, 1] / 50.0], 1)
    return verts, tris, uvs


def river_surface(points, cell=1.5):
    """Water surface of one river (terrain_info.json record points [x, y, level, half, depth], every 2 m).

    A grid, not a ribbon: a ribbon folds over itself in tight bends and round ponds. Every vertex takes its
    height, its flow coordinate and its distance from the centre line from the nearest centre-line point.
    UV0 = (metres from the left bank, metres downstream); UV1 = (foam: rapids and the pool below them,
    bank: 0 mid-stream .. 1 at the water's edge)."""
    from scipy import ndimage
    from .terrain import polyline_distance, smoothstep
    p = np.asarray(points, np.float64)
    arc = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1])))])
    level = p[:, 2].copy()
    half = p[:, 3]
    # under the sea surface at the mouth (the ocean plane takes over); the lake end is 3 cm under the lake
    level = np.where(level < 0.3, level - 0.14 * (1.0 - np.clip(level / 0.3, 0.0, 1.0)), level)
    slope = np.clip(-np.gradient(level, arc), 0.0, None)
    foam = smoothstep(0.015, 0.11, slope)
    tail = np.zeros_like(foam)                       # churned water drifts ~14 m on below a drop
    acc = 0.0
    for i in range(len(foam)):
        acc = max(float(foam[i]), acc * 0.87)
        tail[i] = acc
    foam = np.clip(np.maximum(foam, tail * 0.8), 0.0, 1.0)
    reach = float(half.max()) + 3.0
    x0, x1 = p[:, 0].min() - reach, p[:, 0].max() + reach
    y0, y1 = p[:, 1].min() - reach, p[:, 1].max() + reach
    nx, ny = int((x1 - x0) / cell) + 2, int((y1 - y0) / cell) + 2
    X, Y = np.meshgrid(x0 + np.arange(nx) * cell, y1 - np.arange(ny) * cell)
    dist, sarc = polyline_distance(X.astype(np.float32), Y.astype(np.float32), [tuple(q) for q in p[:, :2]], reach)
    ok = np.isfinite(dist)
    hw = np.interp(sarc, arc, half)
    inside = ok & (dist <= hw + 1.0)
    keep = inside[:-1, :-1] | inside[1:, :-1] | inside[:-1, 1:] | inside[1:, 1:]
    # side of the centre line (left bank = +1 looking downstream), from the nearest segment's direction
    idx = np.clip(np.searchsorted(arc, sarc) - 1, 0, len(arc) - 2)
    tx = (p[idx + 1, 0] - p[idx, 0])
    ty = (p[idx + 1, 1] - p[idx, 1])
    side = np.sign(tx * (Y - p[idx, 1]) - ty * (X - p[idx, 0]))
    d = np.where(ok, dist, reach)
    z = np.interp(sarc, arc, level)
    verts = np.stack([X.ravel(), Y.ravel(), z.ravel()], 1)
    uv0 = np.stack([(hw - side * d).ravel(), sarc.ravel()], 1)
    uv1 = np.stack([np.interp(sarc, arc, foam).ravel(), np.clip(d / np.maximum(hw, 0.5), 0.0, 1.0).ravel() ** 2], 1)
    verts, tris, uv0, uv1 = _compact(verts, _grid_tris(keep, nx), uv0, uv1)
    return verts, tris, uv0, uv1


def build_water(h, export=True, log=print):
    """Ocean (graded grid), sea floor plane, lake and river surfaces -> Meshes/Water."""
    from . import jsonio, terrain
    objs = {}
    v, t, uv = ocean_surface(h)
    objs["SM_Ocean"] = tri_mesh("SM_Ocean", v, t, uv, "M_Ocean")
    n_ocean = len(t)
    objs["SM_SeaFloor"] = flat_square("SM_SeaFloor", 20000.0, C.SEA_FLOOR - 0.4, 8, "M_Sand")
    level = terrain.load_water()
    v, t, uv = lake_surface(level)
    objs["SM_LakeSurface"] = tri_mesh("SM_LakeSurface", v, t, uv, "M_LakeWater")
    n_lake = len(t)
    info = jsonio.read_json(os.path.join(C.CACHE_DIR, "terrain_info.json"))
    n_river = 0
    for rec in info.get("rivers", []):
        v, t, uv0, uv1 = river_surface(rec["points"])
        name = river_mesh_name(rec["id"])
        objs[name] = tri_mesh(name, v, t, uv0, "M_River", uvs2=uv1)
        n_river += len(t)
    if export:
        for name, o in objs.items():
            blend.export_fbx([o], os.path.join(C.OUT_MESHES, "Water", name + ".fbx"))
    log(f"  water: ocean {n_ocean} tris, lake {n_lake}, rivers {n_river} ({len(info.get('rivers', []))})")
    return objs


def river_mesh_name(river_id):
    from . import waterways
    return waterways.mesh_name(river_id)
