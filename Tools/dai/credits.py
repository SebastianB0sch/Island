"""
CREDITS.md generator: one row per curated third-party asset folder (Tools/thirdparty/**/SOURCE.txt),
plus the catalog names each asset replaces (from the registry).

The file is published through dai.atomic (temp + replace + fsync).  Its newline
policy is LF, matching the pipeline's LF rule (generated files must be stable
across machines; see Docs/conventions for dai.atomic / jsonio).
"""

import json
import os
import re

from . import atomic
from . import config as C
from . import thirdparty

FIELDS = {
    "author": ("author", "authors", "creator", "artist", "generator"),
    "license": ("license", "licence", "licenses / evidence", "licenses"),
    "source": ("upstream source page", "upstream asset", "original_source_page", "original page", "source page", "upstream", "original source", "source", "source url",
               "source_url", "homepage"),
    "title": ("asset_id", "asset", "name", "title"),
}


def parse_source(path):
    out = {}
    attribution, in_attr = [], False
    with open(path, encoding="utf-8", errors="replace") as fp:
        for line in fp:
            if re.match(r"^(required )?(attribution|credit)([ _](text|line))?\s*(\(.*\))?\s*:", line, re.I):
                in_attr = True
                rest = line.split(":", 1)[1].strip() if ":" in line else ""
                if rest and not rest.startswith("("):
                    attribution.append(rest)
                continue
            if in_attr:
                if line.strip() and line.startswith((" ", "\t")):
                    attribution.append(line.strip())
                    continue
                in_attr = False
            m = re.match(r"^\s*([A-Za-z_ /]+?)\s*:\s*(.+?)\s*$", line)
            if not m:
                continue
            key, val = m.group(1).lower(), m.group(2)
            for field, names in FIELDS.items():
                if key in names and field not in out:
                    out[field] = val
    if attribution:
        text = " ".join(attribution).strip()
        if text.startswith('"') and text.endswith('"') and text.count('"') == 2:
            text = text[1:-1]
        out["attribution"] = text
    return out


def asset_folders():
    for root, dirs, files in os.walk(thirdparty.TP_DIR):
        dirs[:] = sorted(d for d in dirs if not d.startswith("_") and d != "registry")
        if "SOURCE.txt" in files:
            yield os.path.relpath(root, thirdparty.TP_DIR).replace(os.sep, "/")


def usage(folders=None):
    """folder -> sorted list of the names (catalog props, texture sets, layers, skies) it provides."""
    uses = {}
    folders = list(folders) if folders is not None else list(asset_folders())
    reg = thirdparty.registry()

    def add(rel, name):
        rel = rel.replace(os.sep, "/")
        for folder in folders:
            if rel.startswith(folder + "/"):
                uses.setdefault(folder, set()).add(name)
                return

    for section, items in reg.items():
        for name, spec in items.items():
            if not isinstance(spec, dict):
                continue
            for key in ("file", "albedo", "normal", "arm", "rough"):
                if isinstance(spec.get(key), str):
                    label = {"textures": f"texture {name}", "terrain": f"terrain layer {name}",
                             "hdri": f"sky ({name})", "anime_models": f"anime cast base model {name}"}.get(section, name)
                    add(spec[key], label)
    return {k: sorted(v) for k, v in uses.items()}


def write(path=None, log=print):
    folders = list(asset_folders())
    uses = usage(folders)
    rows = []
    overrides = {}
    opath = os.path.join(thirdparty.REG_DIR, "credits_overrides.json")
    if os.path.exists(opath):
        with open(opath, encoding="utf-8") as fp:
            overrides = json.load(fp).get("credits", {})
    for folder in folders:
        info = parse_source(os.path.join(thirdparty.TP_DIR, folder, "SOURCE.txt"))
        info.update(overrides.get(folder, {}))
        rows.append((folder, info, uses.get(folder, [])))
    lines = [
        "# Credits",
        "",
        "Duel Academy Island is an unofficial, non-commercial fan project inspired by *Yu-Gi-Oh! GX*.",
        "Yu-Gi-Oh! and all related names are trademarks of their respective owners; no copyrighted",
        "game or anime assets are included. Buildings are original interpretations modelled by the",
        "procedural pipeline in `Tools/`.",
        "",
        "## Third-party assets",
        "",
        "All third-party art below is **CC0 / public domain**, **CC-BY** (attribution given here) or, for the",
        "VRoid sample avatars the anime cast is built from, the **VRoid Hub conditions of use** embedded in each",
        "model (modification and redistribution allowed, credit not required).",
        "Every folder keeps a `SOURCE.txt` with the download URLs, license evidence and file hashes.",
        "Paths are relative to `Tools/thirdparty/`.",
        "",
        "| Asset folder | Author | License | Source | Used for |",
        "|---|---|---|---|---|",
    ]
    for folder, info, used in rows:
        src = info.get("source", "")
        if src.startswith("http"):
            src = f"<{src.split()[0]}>"
        lines.append(f"| `{folder}` | {info.get('author', '?')} | {info.get('license', '?')} | {src} | "
                     f"{', '.join(used) if used else '-'} |")
    by = [(f, i) for f, i, _ in rows if re.search(r"CC[- ]?BY", i.get("license", ""), re.I)]
    if by:
        lines += ["", "### CC-BY attributions", ""]
        seen = set()
        for folder, info in by:
            text = info.get("attribution") or f"{folder} by {info.get('author', '?')}, {info.get('license', '')}"
            if text in seen:
                continue
            seen.add(text)
            lines.append(f"- `{folder}`: {text}")
    lines += [
        "",
        "## Tools",
        "",
        "- [Blender](https://www.blender.org/) (GPL) as the `bpy` Python module - modelling, import, FBX export, Cycles renders",
        "- [glTF-Transform](https://gltf-transform.dev/) (MIT) - meshopt decompression of glTF downloads",
        "- [EZ-Tree](https://github.com/dgreenheck/ez-tree) (MIT) by Daniel Greenheck - procedural broadleaf / pine tree generation",
        "- NumPy, SciPy, Pillow - terrain, textures and audio synthesis",
        "- Unreal Engine 5.8 - Lumen, Nanite, Enhanced Input, editor Python",
        "",
    ]
    path = path or os.path.join(C.REPO_DIR, "CREDITS.md")
    # atomic.write_text keeps the LF policy explicit for the committed MD file
    atomic.write_text(path, "".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")
    log(f"  credits: {len(rows)} third-party asset folders -> CREDITS.md")
    return rows
