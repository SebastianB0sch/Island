"""UI portraits rendered from the project's own cel-shaded cast.

The dialogue / duel UI loads 512 x 512 PNGs from Content/Data/Portraits.  The
existing local-only renders came from Duel Links; the missing speakers are
rendered here from the project's own cast models, so every named character and
NPC has art in the same style as the people who actually stand on the island.

The background is flattened onto the exact panel colour used by the UI
(#263541), matching the existing portraits.

Run through Blender (the cast pipeline needs bpy), see Tools/render_portraits.py.
"""

import os

from PIL import Image

from . import build as BUILD
from . import cast as CAST

# Content/Data/Portraits' flat panel background (sRGB 38, 53, 65).
PANEL = (38, 53, 65)
SIZE = 512


def _ensure_scale(entry):
    entry = dict(entry)
    if "scale" not in entry:
        entry["scale"] = CAST.scale_of(entry)
    return entry


def render_rgba(path, cid, entry, res=SIZE, samples=16, view=0.0, distance=1.0, target_z=0.02, log=print):
    """Render one transparent bust (RGBA) to `path`."""
    entry = _ensure_scale(entry)
    BUILD.render_lineup(
        path,
        [cid],
        state="Idle",
        frame=12,
        res=(res, res),
        samples=samples,
        view=view,
        portrait=True,
        transparent=True,
        distance=distance,
        target_z=target_z,
        entries={cid: entry},
        log=log,
    )
    return path


def _flatten(image):
    panel = Image.new("RGBA", image.size, (*PANEL, 255))
    panel.alpha_composite(image.convert("RGBA"))
    return panel.convert("RGB")


def _face_crop(image):
    """Tight square head crop derived from the bust's opaque silhouette.

    The bust is framed the same way for every character, so a square centred
    on the head is stable: the top of the hair to just below the chin.
    """
    alpha = image.convert("RGBA").getchannel("A")
    box = alpha.getbbox()
    if not box:
        return _flatten(image)
    left, top, right, bottom = box
    height = bottom - top
    # Measure the head itself (hair included): the widest opaque row in the upper part of the silhouette.
    # Shoulder width is no guide - a slim figure with a large head would be cropped at the chin.
    import numpy as np
    opaque = np.asarray(alpha) > 32
    rows = opaque[top:top + max(1, int(height * 0.34))]
    cols = np.nonzero(rows.any(axis=0))[0]
    head_w = int(cols[-1] - cols[0] + 1) if len(cols) else right - left
    side = max(8, int(round(head_w * 1.22)))
    cx = int(cols[0] + cols[-1]) // 2 if len(cols) else (left + right) // 2
    cy = top + int(round(side * 0.47))
    half = side // 2
    crop = (cx - half, cy - half, cx - half + side, cy - half + side)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.alpha_composite(image.convert("RGBA").crop(crop))
    return _flatten(out).resize((SIZE, SIZE), Image.LANCZOS)


def render_expression(out_dir, cid, entry, expression, weights, samples=16, view=0.0, distance=0.74,
                      target_z=0.10, log=print):
    """Render one expression frame (head-and-shoulders) for a generated character."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, cid + "_" + expression + ".png")
    rgba_path = os.path.join(out_dir, "." + cid + "_" + expression + ".rgba.png")
    expression_entry = dict(entry)
    expression_entry["expression"] = weights
    try:
        render_rgba(rgba_path, cid, expression_entry, samples=samples, view=view, distance=distance,
                    target_z=target_z, log=log)
        with Image.open(rgba_path) as source:
            _flatten(source.convert("RGBA")).save(path, optimize=True)
    finally:
        if os.path.exists(rgba_path):
            os.remove(rgba_path)
    return path


def render_pair(out_dir, cid, entry, samples=16, view=0.0, distance=1.0, target_z=0.02, log=print):
    """Write <out_dir>/<cid>.png (bust) and <cid>_face.png (head crop)."""
    os.makedirs(out_dir, exist_ok=True)
    bust = os.path.join(out_dir, cid + ".png")
    face = os.path.join(out_dir, cid + "_face.png")
    rgba_path = os.path.join(out_dir, "." + cid + ".rgba.png")
    try:
        render_rgba(rgba_path, cid, entry, samples=samples, view=view, distance=distance,
                    target_z=target_z, log=log)
        with Image.open(rgba_path) as source:
            image = source.convert("RGBA")
            _flatten(image).save(bust, optimize=True)
            _face_crop(image).save(face, optimize=True)
    finally:
        if os.path.exists(rgba_path):
            os.remove(rgba_path)
    return bust, face
