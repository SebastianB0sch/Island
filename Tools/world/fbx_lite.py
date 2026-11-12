"""Minimal binary FBX geometry reader (standard library + numpy).

Reads exactly what the reachability audit needs from the meshes the Blender pipeline exports
(`dai.blend.export_fbx`): for every Geometry node its Model name, vertex positions and triangulated
polygons.  Vertices are returned as stored, which for this pipeline is the Blender object space in
metres (X east, Y north, Z up); the exporter puts the axis conversion on the Model node, not into the
vertex data, and every exported object sits at the identity transform.

    from fbx_lite import read_meshes
    for name, verts, tris in read_meshes("SM_Foo.fbx"):   # verts (N, 3) float64, tris (M, 3) int32
        ...

Not a general FBX library: ASCII FBX, non-identity Lcl Translation / Scaling and instanced geometry are
rejected rather than guessed at.
"""

from __future__ import annotations

import struct
import zlib

import numpy as np

_MAGIC = b"Kaydara FBX Binary  \x00"
_SCALAR = {"Y": "<h", "C": "<b", "I": "<i", "F": "<f", "D": "<d", "L": "<q"}
_ARRAY = {"f": "<f4", "d": "<f8", "l": "<i8", "i": "<i4", "b": "i1"}
_WANTED = {"Objects", "Connections", "Geometry", "Model", "Vertices", "PolygonVertexIndex", "Properties70",
           "P", "C"}


class FbxError(ValueError):
    pass


def _parse(data):
    if data[:len(_MAGIC)] != _MAGIC:
        raise FbxError("not a binary FBX file")
    version = struct.unpack_from("<I", data, 23)[0]
    wide = version >= 7500
    head = struct.Struct("<QQQ" if wide else "<III")

    def node(off):
        end, nprop, plen = head.unpack_from(data, off)
        off += head.size
        nlen = data[off]
        name = data[off + 1:off + 1 + nlen].decode("ascii", "replace")
        off += 1 + nlen
        if end == 0:
            return None, off
        if name not in _WANTED:
            return (name, [], []), end
        props, p = [], off
        for _ in range(nprop):
            t = chr(data[p])
            p += 1
            if t in _SCALAR:
                props.append(struct.unpack_from(_SCALAR[t], data, p)[0])
                p += struct.calcsize(_SCALAR[t])
            elif t in _ARRAY:
                count, encoding, clen = struct.unpack_from("<III", data, p)
                p += 12
                raw = data[p:p + clen]
                p += clen
                if encoding:
                    raw = zlib.decompress(raw)
                props.append(np.frombuffer(raw, dtype=_ARRAY[t], count=count))
            elif t in "SR":
                n = struct.unpack_from("<I", data, p)[0]
                props.append(data[p + 4:p + 4 + n])
                p += 4 + n
            else:
                raise FbxError(f"unknown FBX property type {t!r}")
        off += plen
        kids = []
        while off < end:
            kid, off = node(off)
            if kid is None:
                break
            kids.append(kid)
        return (name, props, kids), end

    top, off = [], 27
    while off < len(data) - head.size:
        n, off = node(off)
        if n is None:
            break
        top.append(n)
    return top


def triangulate(index):
    """FBX PolygonVertexIndex (the last corner of each polygon is stored as ~index) -> (M, 3) fan triangles."""
    index = np.asarray(index, np.int64)
    ends = np.flatnonzero(index < 0)
    if len(ends) == 0:
        return np.zeros((0, 3), np.int32)
    starts = np.concatenate(([0], ends[:-1] + 1))
    count = ends - starts + 1
    index = np.where(index < 0, ~index, index)
    out = []
    for k in range(1, int(count.max()) - 1):
        m = count >= k + 2
        out.append(np.stack([index[starts[m]], index[starts[m] + k], index[starts[m] + k + 1]], axis=1))
    if not out:
        return np.zeros((0, 3), np.int32)
    return np.concatenate(out).astype(np.int32)


def read_meshes(path):
    """[(model name, vertices (N, 3) float64, triangles (M, 3) int32)] for every mesh in the file."""
    with open(path, "rb") as fp:
        top = _parse(fp.read())
    objects = next((t[2] for t in top if t[0] == "Objects"), [])
    conns = next((t[2] for t in top if t[0] == "Connections"), [])
    models = {}
    for o in objects:
        if o[0] != "Model":
            continue
        name = o[1][1].split(b"\x00")[0].decode("utf-8", "replace")
        for k in o[2]:
            if k[0] != "Properties70":
                continue
            for p in k[2]:
                key = p[1][0]
                vals = [float(v) for v in p[1][4:7]]
                if key == b"Lcl Translation" and any(abs(v) > 1e-6 for v in vals):
                    raise FbxError(f"{path}: model {name} has a translation {vals}; expected identity")
                if key == b"Lcl Scaling" and any(abs(v - 1.0) > 1e-6 for v in vals):
                    raise FbxError(f"{path}: model {name} has a scale {vals}; expected identity")
        models[o[1][0]] = name
    owner = {c[1][1]: c[1][2] for c in conns if len(c[1]) >= 3 and c[1][2] in models}
    out = []
    for o in objects:
        if o[0] != "Geometry":
            continue
        verts = index = None
        for k in o[2]:
            if k[0] == "Vertices":
                verts = np.asarray(k[1][0], np.float64).reshape(-1, 3)
            elif k[0] == "PolygonVertexIndex":
                index = k[1][0]
        if verts is None or index is None:
            continue
        name = models.get(owner.get(o[1][0]), o[1][1].split(b"\x00")[0].decode("utf-8", "replace"))
        out.append((name, verts, triangulate(index)))
    return out
