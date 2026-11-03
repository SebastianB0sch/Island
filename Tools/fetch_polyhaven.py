"""
Fetch curated CC0 Poly Haven models (1k glTF) into Tools/thirdparty/polyhaven/models/<asset>/ and write a
SOURCE.txt per asset (author, license evidence, URLs, md5 + sha256 of every file).

    python Tools/fetch_polyhaven.py SchoolDesk_01 Sofa_01 ...
    python Tools/fetch_polyhaven.py --interiors        # everything Tools/thirdparty/registry/interiors.json uses

Files are taken unmodified from Poly Haven's own API (api.polyhaven.com -> dl.polyhaven.org) and checked
against the md5 the API publishes.
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "thirdparty", "polyhaven", "models")
API = "https://api.polyhaven.com"
UA = {"User-Agent": "DuelAcademyIsland-asset-fetch/1.0"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fetch(asset, res="1k", catalog_use=""):
    info = json.loads(get(f"{API}/info/{asset}"))
    files = json.loads(get(f"{API}/files/{asset}"))
    g = (files["gltf"].get(res) or files["gltf"][sorted(files["gltf"])[0]])["gltf"]
    folder = os.path.join(DEST, asset)
    os.makedirs(folder, exist_ok=True)
    entries = [(os.path.basename(g["url"]), g)] + list(g.get("include", {}).items())
    lines = []
    for rel, meta in entries:
        path = os.path.join(folder, rel)
        if not (os.path.exists(path) and hashlib.md5(open(path, "rb").read()).hexdigest() == meta["md5"]):
            data = get(meta["url"])
            if hashlib.md5(data).hexdigest() != meta["md5"]:
                raise RuntimeError(f"{asset}/{rel}: md5 mismatch")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fp:
                fp.write(data)
        data = open(path, "rb").read()
        lines.append(f"  {meta['url']}\n    -> {rel}  md5 {meta['md5']}  sha256 {hashlib.sha256(data).hexdigest()}")
    authors = ", ".join(info.get("authors", {}).keys()) or "Poly Haven"
    src = f"""asset_id: polyhaven_{asset}
title: {info.get('name', asset)} (Poly Haven)
category: interiors
main_file: {os.path.basename(g['url'])}
catalog_use: {catalog_use}
author: {authors}
license: CC0-1.0 (public domain dedication; no attribution required)
original_source_page: https://polyhaven.com/a/{asset}
description: {info.get('description', '').strip()}
polycount: {info.get('polycount')}
downloaded_from (exact files via the Poly Haven API https://api.polyhaven.com/files/{asset}, md5-verified):
{chr(10).join(lines)}
license_evidence: Poly Haven license: "every asset is CC0. Use it for anything, commercial included, with no attribution required." -- https://polyhaven.com/license (CC0 deed); author list from https://api.polyhaven.com/info/{asset}
modifications: none to the files. The pipeline (Tools/dai/thirdparty.py, "toon": true) re-paints the base colour
  texture into flat cel colours, drops the normal/ORM maps and adds an inverted-hull ink outline at build time.
date_retrieved: {datetime.date.today().isoformat()}
"""
    with open(os.path.join(folder, "SOURCE.txt"), "w", encoding="utf-8") as fp:
        fp.write(src)
    return os.path.join("polyhaven", "models", asset, os.path.basename(g["url"])).replace(os.sep, "/")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("assets", nargs="*")
    ap.add_argument("--interiors", action="store_true")
    args = ap.parse_args(argv)
    todo = {a: "" for a in args.assets}
    if args.interiors:
        reg = json.load(open(os.path.join(HERE, "thirdparty", "registry", "interiors.json"), encoding="utf-8"))
        for name, spec in reg["props"].items():
            parts = spec["file"].split("/")
            if parts[0] == "polyhaven":
                todo.setdefault(parts[2], "")
                todo[parts[2]] = (todo[parts[2]] + ", " if todo[parts[2]] else "") + name
    for a, use in todo.items():
        try:
            rel = fetch(a, catalog_use=use)
            print("ok ", a, rel)
        except Exception as e:  # noqa: BLE001
            print("ERR", a, e)


if __name__ == "__main__":
    main(sys.argv[1:])
