"""The lake's outline as a field: the ellipse (config.LAKE_CENTER / LAKE_RADII / LAKE_ROT) and its arms
(config.LAKE_INLETS), both as the lake's normalised radius q - < 1 in the water, 1 at its edge.

numpy only (no scipy): the terrain stage shapes the lake with it, the layout stage asks it where the water is,
the lake mesh is sized by it.
"""

import math

import numpy as np

from . import config as C

_INLETS = {}


def inlet_q(X, Y, inlets=None):
    """The lake's arms (config.LAKE_INLETS) as the lake's own normalised radius q: 0 on an arm's middle line,
    1 at its water's edge, then 1 + metres beyond the edge / the arm's bank width. Returns (q, depth): q is
    inf away from every arm, depth the middle-line depth of the arm q belongs to. Any array shape."""
    X = np.asarray(X, np.float64)
    Y = np.asarray(Y, np.float64)
    q = np.full(X.shape, np.inf)
    depth = np.zeros(X.shape)
    if inlets is None:
        if "inlets" not in _INLETS:
            _INLETS["inlets"] = C.lake_inlets()
        inlets = _INLETS["inlets"]
    for rec in inlets:
        p = np.asarray(rec["pts"], np.float64)
        half = np.asarray(rec["half"], np.float64)
        arc = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])
        dist = np.full(X.shape, np.inf)
        s = np.zeros(X.shape)
        for i in range(len(p) - 1):
            (ax, ay), (bx, by) = p[i], p[i + 1]
            dx, dy = bx - ax, by - ay
            t = np.clip(((X - ax) * dx + (Y - ay) * dy) / max(dx * dx + dy * dy, 1e-9), 0.0, 1.0)
            d = np.hypot(X - ax - t * dx, Y - ay - t * dy)
            m = d < dist
            dist = np.where(m, d, dist)
            s = np.where(m, arc[i] + t * (arc[i + 1] - arc[i]), s)
        hw = np.interp(s, arc, half)
        qi = np.where(dist <= hw, dist / hw, 1.0 + (dist - hw) / rec["bank"])
        m = qi < q
        q = np.where(m, qi, q)
        depth = np.where(m, rec["depth"], depth)
    return q, depth


def ellipse_q(x, y):
    """The lake ellipse's normalised radius at world (x, y)."""
    a = math.radians(C.LAKE_ROT)
    dx, dy = np.asarray(x, np.float64) - C.LAKE_CENTER[0], np.asarray(y, np.float64) - C.LAKE_CENTER[1]
    return np.hypot((dx * math.cos(a) + dy * math.sin(a)) / C.LAKE_RADII[0],
                    (-dx * math.sin(a) + dy * math.cos(a)) / C.LAKE_RADII[1])


def lake_q(x, y):
    """The lake's normalised radius at world (x, y) - the ellipse or one of its arms, whichever is nearer -
    without the terrain stage's shoreline noise. < 1 is in the lake."""
    return np.minimum(ellipse_q(x, y), inlet_q(x, y)[0])
