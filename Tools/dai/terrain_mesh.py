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


def build_water(h, export=True, log=print):
    """Ocean plane, sea floor plane and lake surface."""
    from .terrain import grid
    objs = {}
    ocean = flat_square("SM_Ocean", 20000.0, 0.0, 40, "M_Ocean")
    seafloor = flat_square("SM_SeaFloor", 20000.0, C.SEA_FLOOR - 0.4, 8, "M_Sand")
    objs["SM_Ocean"] = ocean
    objs["SM_SeaFloor"] = seafloor

    # lake: grid of 3 m cells covering the lake ellipse, keep cells near/inside the shore
    lcx, lcy = C.LAKE_CENTER
    rx, ry = C.LAKE_RADII
    ext = max(rx, ry) * 1.15
    cells = int(2 * ext / 3.0)
    xs = np.linspace(lcx - ext, lcx + ext, cells + 1)
    ys = np.linspace(lcy + ext, lcy - ext, cells + 1)
    X, Y = np.meshgrid(xs, ys)
    from .terrain import Field
    hf = Field(h)
    H = hf(X, Y)
    a = math.radians(C.LAKE_ROT)
    dx, dy = X - lcx, Y - lcy
    lx = dx * math.cos(a) + dy * math.sin(a)
    ly = -dx * math.sin(a) + dy * math.cos(a)
    qq = np.sqrt((lx / rx) ** 2 + (ly / ry) ** 2)
    inside = (H < C.LAKE_LEVEL + 1.5) & (qq < 1.3)
    verts = np.stack([X.ravel(), Y.ravel(), np.full(X.size, C.LAKE_LEVEL)], axis=1)
    nr, nc = X.shape
    faces = []
    for r in range(nr - 1):
        for c in range(nc - 1):
            if inside[r, c] or inside[r + 1, c] or inside[r, c + 1] or inside[r + 1, c + 1]:
                a0 = r * nc + c
                faces.append((a0, a0 + nc, a0 + nc + 1, a0 + 1))
    faces = np.array(faces, dtype=np.int64)
    used = np.unique(faces)
    remap = np.full(len(verts), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    verts = verts[used]
    faces = remap[faces]
    uvs = np.stack([verts[:, 0] / 50.0, verts[:, 1] / 50.0], axis=1)
    nrm = np.tile([0.0, 0.0, 1.0], (len(verts), 1))
    lake = _mesh_from_arrays("SM_LakeSurface", verts, faces, uvs, nrm, "M_LakeWater")
    objs["SM_LakeSurface"] = lake
    if export:
        for name, o in objs.items():
            blend.export_fbx([o], os.path.join(C.OUT_MESHES, "Water", name + ".fbx"))
    log(f"  water: ocean, sea floor, lake ({len(faces)} quads)")
    return objs
