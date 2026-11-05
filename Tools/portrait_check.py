"""Report portrait coverage for every named dialogue speaker and duel opponent.

    python Tools/portrait_check.py
    python Tools/portrait_check.py --strict     # exit 1 on a missing bust or declared expression frame

The runtime loader (`UCharacterPortraitSubsystem`) checks, in order:
  <id>_<expression>.png -> <id>_face.png -> <id>.png -> monogram fallback.
This tool checks the base bust, the face crop and the declared expression
frames, and lists the speakers that would still show the empty "NO PORTRAIT"
frame.
"""

import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "DuelAcademyIsland", "Content", "Data")
PORTRAITS = os.path.join(DATA, "Portraits")

# Narration and the PDA use their own UI art; they are not character portraits.
UI_SPEAKERS = {"narrator", "pda", "none"}
# Event-only opponents that are not human portrait subjects.
NON_HUMAN = {"pharaoh", "goblin_king", "jinzo"}
# Named opponents with no story expressions get the six generic duel cut-ins.
DUEL_ONLY = {"jasmine", "mindy", "conklin", "damon"}
DUEL_EXPRESSIONS = {"happy", "angry", "determined", "shocked", "sad", "laugh"}


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _story_speakers():
    out = {}
    for path in sorted(glob.glob(os.path.join(DATA, "Story", "dialogue", "*.json"))):
        data = _load_json(path)
        for speaker, spec in data.get("speakers", {}).items():
            item = out.setdefault(speaker, {"files": set(), "fallback": "", "expressions": set()})
            item["files"].add(os.path.basename(path))
            item["fallback"] = spec.get("fallback", item["fallback"])
            item["expressions"].update(spec.get("expressions", []))
    return out


def _ui_speakers():
    out = {}
    path = os.path.join(DATA, "UI", "ui.json")
    if not os.path.exists(path):
        return out
    data = _load_json(path)
    for line in data.get("lines", []):
        speaker = line.get("speakerId")
        if speaker:
            out.setdefault(speaker, {"files": {"ui.json"}, "fallback": "", "expressions": set()})
    return out


def _opponents():
    path = os.path.join(DATA, "Canon", "opponents.json")
    if not os.path.exists(path):
        return set()
    return {item["id"] for item in _load_json(path).get("opponents", []) if item.get("id")}


def _has(name):
    return os.path.exists(os.path.join(PORTRAITS, name + ".png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 if a named human speaker has no bust")
    ap.add_argument("--json", action="store_true", help="write the report as JSON")
    a = ap.parse_args()

    speakers = _story_speakers()
    speakers.update(_ui_speakers())
    opponents = _opponents()

    rows = []
    for speaker in sorted(set(speakers) | opponents):
        if speaker in UI_SPEAKERS:
            continue
        spec = speakers.get(speaker, {"files": {"opponents.json"}, "fallback": "", "expressions": set()})
        fallback = spec.get("fallback", "")
        bust = _has(speaker)
        face = _has(speaker + "_face")
        fallback_ok = bool(fallback) and _has(fallback)
        wanted_expressions = set(spec["expressions"])
        if speaker in DUEL_ONLY:
            wanted_expressions |= DUEL_EXPRESSIONS
        missing_expr = sorted(e for e in wanted_expressions if not _has(speaker + "_" + e))
        rows.append({
            "id": speaker,
            "bust": bust,
            "face": face,
            "fallback": fallback,
            "fallback_ok": fallback_ok,
            "missing_expressions": missing_expr,
            "sources": sorted(spec["files"]),
            "opponent": speaker in opponents,
        })

    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        width = max(len(row["id"]) for row in rows) if rows else 0
        for row in rows:
            art = "BUST" if row["bust"] else ("FALLBACK" if row["fallback_ok"] else "MISSING")
            face = "face" if row["face"] else "no-face"
            expr = ("  expr:" + ",".join(row["missing_expressions"])) if row["missing_expressions"] else ""
            print("%-*s  %-8s  %-7s%s" % (width, row["id"], art, face, expr))
        missing = [row["id"] for row in rows if not row["bust"] and not row["fallback_ok"]]
        non_human = [sid for sid in missing if sid in NON_HUMAN]
        human = [sid for sid in missing if sid not in NON_HUMAN]
        expr_missing = [row["id"] for row in rows if row["missing_expressions"]]
        print()
        print("named human speakers without art: %d" % len(human))
        if human:
            print("  " + ", ".join(human))
        if non_human:
            print("non-human event opponents without art: %s" % ", ".join(non_human))
        print("named speakers with a face crop: %d/%d" % (sum(1 for r in rows if r["face"]), len(rows)))
        print("characters with a missing declared expression frame: %d" % len(expr_missing))
        if expr_missing:
            print("  " + ", ".join(expr_missing))
        if a.strict and (human or expr_missing):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
