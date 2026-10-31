#!/usr/bin/env python3
"""Validate the A08 world data against the generated island layout.

Checks
------
* unique ids in location_map / interiors / portals / anchors / spawns
* every zone_id exists in SourceAssets/Data/layout.json
* every location, interior, portal and spawn reference resolves
* portal pairs are symmetric and stay inside their interior cells
* anchors referenced by locations / portals / spawns exist
* opening vertical-slice anchors and spawns exist
* optional strict mode turns warnings into failures

Usage
-----
    python Tools/world/validate_layout.py
    python Tools/world/validate_layout.py --json
    python Tools/world/validate_layout.py --strict
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

STATUSES = {"existing", "needs_interior", "merged", "missing"}
ANCHOR_KINDS = {"camera", "player", "npc", "look_at", "stage", "prop"}
ROLES = {"staff", "teacher", "student", "headmaster", "shopkeeper", "chancellor", "event", "duelist"}
DORMS = {"slifer", "ra", "obelisk", "white"}

OPENING_ANCHORS = [
    "gym_assembly_stage",
    "academy_registration_player",
    "slifer_cafeteria_player",
    "slifer_player_room_save",
    "slifer_banner_room_desk",
    "slifer_jaden_room_jaden",
    "academy_classroom_teacher",
    "academy_card_shop_player",
    "academy_arena_field_player",
]


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.missing_anchors: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def missing_anchor(self, message: str) -> None:
        self.missing_anchors.append(message)

    def ok(self) -> bool:
        return not self.errors


def load_json(path: Path, report: Report) -> dict[str, Any] | None:
    if not path.exists():
        report.error(f"missing file: {path}")
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:  # noqa: BLE001 - report the exact data error
        report.error(f"invalid JSON in {path}: {exc}")
        return None
    if not isinstance(data, dict):
        report.error(f"{path} must contain a JSON object")
        return None
    return data


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def vec3(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        out = tuple(float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in out):
        return None
    return out  # type: ignore[return-value]


def bounds(value: Any) -> tuple[float, float, float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 6:
        return None
    try:
        out = tuple(float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in out):
        return None
    if out[0] >= out[3] or out[1] >= out[4] or out[2] >= out[5]:
        return None
    return out  # type: ignore[return-value]


def inside_bounds(point: tuple[float, float, float], box: tuple[float, float, float, float, float, float],
                  margin: float = 0.0) -> bool:
    return (box[0] - margin <= point[0] <= box[3] + margin and
            box[1] - margin <= point[1] <= box[4] + margin and
            box[2] - margin <= point[2] <= box[5] + margin)


def zone_contains(zone: dict[str, Any], point: tuple[float, float, float], margin: float = 0.0) -> bool:
    center = vec3(zone.get("center"))
    extent = vec3(zone.get("extent"))
    if not center or not extent:
        return True
    return (abs(point[0] - center[0]) <= extent[0] + margin and
            abs(point[1] - center[1]) <= extent[1] + margin and
            abs(point[2] - center[2]) <= extent[2] + margin)


def any_zone_contains(zones: dict[str, dict[str, Any]], point: tuple[float, float, float],
                      margin: float = 0.0) -> bool:
    return any(zone_contains(zone, point, margin) for zone in zones.values())


def unique_ids(items: Iterable[dict[str, Any]], label: str, report: Report) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            report.error(f"{label}: entry is not an object")
            continue
        item_id = as_str(item.get("id"))
        if not item_id:
            report.error(f"{label}: entry without id")
            continue
        if item_id in out:
            report.error(f"{label}: duplicate id '{item_id}'")
            continue
        out[item_id] = item
    return out


def check_summary(location_map: dict[str, Any], locations: dict[str, dict[str, Any]], report: Report) -> None:
    summary = location_map.get("summary", {})
    if not isinstance(summary, dict):
        report.warn("location_map.summary is missing or not an object")
        return
    counts = {status: 0 for status in STATUSES}
    for location in locations.values():
        status = as_str(location.get("status"))
        if status in counts:
            counts[status] += 1
    if summary.get("total") != len(locations):
        report.error(f"location_map.summary.total={summary.get('total')} but {len(locations)} rows exist")
    for status, count in counts.items():
        if summary.get(status) != count:
            report.error(f"location_map.summary.{status}={summary.get(status)} but {count} rows exist")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate Content/Data/World against layout.json")
    parser.add_argument("--root", type=Path, default=None, help="repository root (default: two levels above this script)")
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)

    root = args.root.resolve() if args.root else Path(__file__).resolve().parents[2]
    data_dir = root / "DuelAcademyIsland" / "Content" / "Data" / "World"
    layout_path = root / "DuelAcademyIsland" / "SourceAssets" / "Data" / "layout.json"

    report = Report()

    location_map = load_json(data_dir / "location_map.json", report)
    interiors_doc = load_json(data_dir / "interiors.json", report)
    portals_doc = load_json(data_dir / "portals.json", report)
    anchors_doc = load_json(data_dir / "anchors.json", report)
    spawns_doc = load_json(data_dir / "spawns.json", report)
    layout = load_json(layout_path, report) if layout_path.exists() else None
    if layout is None and layout_path.exists():
        report.warn("layout.json could not be read; zone checks are limited")

    if not all((location_map, interiors_doc, portals_doc, anchors_doc, spawns_doc)):
        return emit(report, args, {})

    zones: dict[str, dict[str, Any]] = {}
    if layout:
        for zone in as_list(layout.get("zones")):
            if isinstance(zone, dict) and as_str(zone.get("id")):
                zones[as_str(zone["id"])] = zone

    locations = unique_ids(as_list(location_map.get("locations")), "locations", report)
    cells = unique_ids(as_list(interiors_doc.get("cells")), "interiors", report)
    portals = unique_ids(as_list(portals_doc.get("portals")), "portals", report)
    anchors = unique_ids(as_list(anchors_doc.get("anchors")), "anchors", report)
    spawns = unique_ids(as_list(spawns_doc.get("spawns")), "spawns", report)

    check_summary(location_map, locations, report)

    # ------------------------------------------------------------------ locations
    for loc_id, location in locations.items():
        status = as_str(location.get("status"))
        if status not in STATUSES:
            report.error(f"location '{loc_id}': invalid status '{status}'")
        zone_id = as_str(location.get("gx_zone"))
        if zones and zone_id not in zones:
            report.error(f"location '{loc_id}': unknown gx_zone '{zone_id}'")

        interior_id = as_str(location.get("interior_id"))
        if interior_id and interior_id not in cells:
            report.error(f"location '{loc_id}': unknown interior_id '{interior_id}'")
        if status == "needs_interior" and not interior_id:
            report.error(f"location '{loc_id}': needs_interior but has no interior_id")
        if status == "merged":
            merged_into = as_str(location.get("merged_into"))
            if not merged_into:
                report.error(f"location '{loc_id}': merged but has no merged_into")
            elif merged_into not in locations:
                report.error(f"location '{loc_id}': merged_into '{merged_into}' does not exist")

        anchor_id = as_str(location.get("anchor_id"))
        if anchor_id and anchor_id not in anchors:
            report.error(f"location '{loc_id}': unknown anchor_id '{anchor_id}'")
        if not anchor_id:
            report.missing_anchor(f"location '{loc_id}' has no anchor_id")
            report.warn(f"location '{loc_id}': no anchor_id")

        portal_id = as_str(location.get("portal_id"))
        if portal_id and portal_id not in portals:
            report.error(f"location '{loc_id}': unknown portal_id '{portal_id}'")

        point = vec3(location.get("ue_location"))
        if not point:
            report.error(f"location '{loc_id}': ue_location must be [x, y, z]")
        elif zones and not any_zone_contains(zones, point, 250.0):
            report.warn(f"location '{loc_id}': ue_location {point} is outside every layout zone")

        box = bounds(location.get("bounds_ue"))
        if location.get("bounds_ue") is not None and not box:
            report.error(f"location '{loc_id}': bounds_ue must be six increasing numbers")

    # ------------------------------------------------------------------ interiors
    for cell_id, cell in cells.items():
        zone_id = as_str(cell.get("zone_id"))
        if zones and zone_id not in zones:
            report.error(f"interior '{cell_id}': unknown zone_id '{zone_id}'")

        box = bounds(cell.get("bounds_ue"))
        if not box:
            report.error(f"interior '{cell_id}': bounds_ue must be six increasing numbers")
            continue
        floor_z = cell.get("floor_z")
        ceiling_z = cell.get("ceiling_z")
        if not isinstance(floor_z, (int, float)) or not isinstance(ceiling_z, (int, float)):
            report.error(f"interior '{cell_id}': floor_z/ceiling_z must be numbers")
        elif not (box[2] <= float(floor_z) < float(ceiling_z) <= box[5]):
            report.error(f"interior '{cell_id}': floor/ceiling outside bounds_ue")

        size = as_list(cell.get("size_m"))
        if len(size) != 3 or any(not isinstance(v, (int, float)) or v <= 0 for v in size):
            report.error(f"interior '{cell_id}': size_m must be three positive numbers")
        elif box:
            extents = (box[3] - box[0], box[4] - box[1], box[5] - box[2])
            for axis, (actual, declared) in enumerate(zip(extents, size)):
                if abs(actual - float(declared) * 100.0) > 1.0:
                    report.error(f"interior '{cell_id}': bounds_ue axis {axis} is {actual:.0f} cm but size_m says "
                                 f"{float(declared) * 100.0:.0f} cm")

        origin = vec3(cell.get("origin_ue"))
        if not origin:
            report.error(f"interior '{cell_id}': origin_ue must be [x, y, z]")
        elif box:
            center_x = (box[0] + box[3]) / 2.0
            center_y = (box[1] + box[4]) / 2.0
            if abs(origin[0] - center_x) > 1.0 or abs(origin[1] - center_y) > 1.0 or abs(origin[2] - box[2]) > 1.0:
                report.error(f"interior '{cell_id}': origin_ue {origin} must be the floor centre of bounds_ue")

        for key in ("interior_exit_ue", "arrival_ue"):
            point = vec3(cell.get(key))
            if not point or not inside_bounds(point, box, 0.0):
                report.error(f"interior '{cell_id}': {key} must be inside bounds_ue")

        entrance_id = as_str(cell.get("entrance_portal_id"))
        exterior_id = as_str(cell.get("exterior_portal_id"))
        if entrance_id not in portals:
            report.error(f"interior '{cell_id}': unknown entrance_portal_id '{entrance_id}'")
        if exterior_id not in portals:
            report.error(f"interior '{cell_id}': unknown exterior_portal_id '{exterior_id}'")

        cell_anchors = [a for a in anchors.values() if as_str(a.get("interior_id")) == cell_id]
        if not any(as_str(a.get("kind")) == "camera" for a in cell_anchors):
            report.missing_anchor(f"interior '{cell_id}' has no camera anchor")
        if not any(as_str(a.get("kind")) in {"player", "npc", "stage"} for a in cell_anchors):
            report.missing_anchor(f"interior '{cell_id}' has no player/npc/stage anchor")

    # ------------------------------------------------------------------ portals
    for portal_id, portal in portals.items():
        zone_id = as_str(portal.get("zone_id"))
        if zones and zone_id not in zones:
            report.error(f"portal '{portal_id}': unknown zone_id '{zone_id}'")
        location_id = as_str(portal.get("location_id"))
        if location_id not in locations:
            report.error(f"portal '{portal_id}': unknown location_id '{location_id}'")
        interior_id = as_str(portal.get("interior_id"))
        if interior_id not in cells:
            report.error(f"portal '{portal_id}': unknown interior_id '{interior_id}'")

        role = as_str(portal.get("role"))
        if role not in {"entrance", "exit"}:
            report.error(f"portal '{portal_id}': role must be entrance or exit")

        target_id = as_str(portal.get("target_portal_id"))
        target = portals.get(target_id)
        if not target:
            report.error(f"portal '{portal_id}': unknown target_portal_id '{target_id}'")
        elif as_str(target.get("target_portal_id")) != portal_id:
            report.error(f"portal '{portal_id}': target '{target_id}' does not point back")

        point = vec3(portal.get("location_ue"))
        if not point:
            report.error(f"portal '{portal_id}': location_ue must be [x, y, z]")
        elif role == "entrance" and zones and not any_zone_contains(zones, point, 250.0):
            report.warn(f"portal '{portal_id}': entrance {point} is outside every layout zone")

        target_point = vec3(portal.get("target_location_ue"))
        if not target_point:
            report.error(f"portal '{portal_id}': target_location_ue must be [x, y, z]")

        extent = vec3(portal.get("trigger_extent"))
        if not extent or any(v <= 0 for v in extent):
            report.error(f"portal '{portal_id}': trigger_extent must be positive [x, y, z]")

        if interior_id in cells:
            cell_box = bounds(cells[interior_id].get("bounds_ue"))
            if cell_box:
                if role == "exit" and point and not inside_bounds(point, cell_box, 0.0):
                    report.error(f"portal '{portal_id}': exit trigger {point} is outside interior bounds")
                if role == "entrance" and target_point and not inside_bounds(target_point, cell_box, 0.0):
                    report.error(f"portal '{portal_id}': arrival {target_point} is outside interior bounds")
                if role == "exit" and target_point and inside_bounds(target_point, cell_box, 0.0):
                    report.warn(f"portal '{portal_id}': exit arrival {target_point} is still inside the cell")

        lock = portal.get("lock", {})
        if not isinstance(lock, dict):
            report.error(f"portal '{portal_id}': lock must be an object")
        else:
            if not isinstance(lock.get("locked", False), bool):
                report.error(f"portal '{portal_id}': lock.locked must be a bool")
            if not isinstance(lock.get("required_flag", ""), str):
                report.error(f"portal '{portal_id}': lock.required_flag must be a string")

        fade = portal.get("fade", {})
        if not isinstance(fade, dict):
            report.error(f"portal '{portal_id}': fade must be an object")
        else:
            for key in ("out", "in"):
                value = fade.get(key)
                if not isinstance(value, (int, float)) or value < 0:
                    report.error(f"portal '{portal_id}': fade.{key} must be a non-negative number")
            color = as_list(fade.get("color"))
            if len(color) != 4 or any(not isinstance(v, (int, float)) for v in color):
                report.error(f"portal '{portal_id}': fade.color must be four numbers")

    for cell_id, cell in cells.items():
        entrances = [p for p in portals.values() if as_str(p.get("interior_id")) == cell_id and as_str(p.get("role")) == "entrance"]
        exits = [p for p in portals.values() if as_str(p.get("interior_id")) == cell_id and as_str(p.get("role")) == "exit"]
        if len(entrances) != 1:
            report.error(f"interior '{cell_id}': expected exactly one entrance portal, found {len(entrances)}")
        if len(exits) != 1:
            report.error(f"interior '{cell_id}': expected exactly one exit portal, found {len(exits)}")

    for loc_id, location in locations.items():
        if as_str(location.get("status")) != "needs_interior":
            continue
        interior_id = as_str(location.get("interior_id"))
        portal_id = as_str(location.get("portal_id"))
        if portal_id:
            portal = portals.get(portal_id)
            if portal and as_str(portal.get("interior_id")) != interior_id:
                report.error(f"location '{loc_id}': portal '{portal_id}' points at the wrong interior")

    # ------------------------------------------------------------------ anchors
    for anchor_id, anchor in anchors.items():
        zone_id = as_str(anchor.get("zone_id"))
        if zones and zone_id not in zones:
            report.error(f"anchor '{anchor_id}': unknown zone_id '{zone_id}'")
        location_id = as_str(anchor.get("location_id"))
        if location_id not in locations:
            report.error(f"anchor '{anchor_id}': unknown location_id '{location_id}'")
        interior_id = as_str(anchor.get("interior_id"))
        if interior_id and interior_id not in cells:
            report.error(f"anchor '{anchor_id}': unknown interior_id '{interior_id}'")

        kind = as_str(anchor.get("kind"))
        if kind not in ANCHOR_KINDS:
            report.error(f"anchor '{anchor_id}': invalid kind '{kind}'")

        point = vec3(anchor.get("position_ue"))
        if not point:
            report.error(f"anchor '{anchor_id}': position_ue must be [x, y, z]")
            continue
        if not isinstance(anchor.get("yaw"), (int, float)):
            report.error(f"anchor '{anchor_id}': yaw must be a number")

        if interior_id in cells:
            cell_box = bounds(cells[interior_id].get("bounds_ue"))
            if cell_box and not inside_bounds(point, cell_box, 200.0):
                report.error(f"anchor '{anchor_id}': {point} is outside interior '{interior_id}'")
            if location_id in locations:
                anchor_location_interior = as_str(locations[location_id].get("interior_id"))
                if anchor_location_interior not in ("", interior_id):
                    report.warn(f"anchor '{anchor_id}': location '{location_id}' has a different interior_id")
        elif zones and not any_zone_contains(zones, point, 500.0):
            report.warn(f"anchor '{anchor_id}': {point} is outside every layout zone")

        if kind == "camera":
            fov = anchor.get("fov")
            if not isinstance(fov, (int, float)) or not (10.0 <= float(fov) <= 120.0):
                report.error(f"anchor '{anchor_id}': camera fov must be 10..120")
            if not vec3(anchor.get("look_at_ue")):
                report.error(f"anchor '{anchor_id}': camera anchor has no look_at_ue")

        tags = anchor.get("tags")
        if tags is not None and not isinstance(tags, list):
            report.error(f"anchor '{anchor_id}': tags must be a list")

    for loc_id, location in locations.items():
        anchor_id = as_str(location.get("anchor_id"))
        if anchor_id and anchor_id not in anchors:
            report.missing_anchor(f"location '{loc_id}' references missing anchor '{anchor_id}'")

    # ------------------------------------------------------------------ spawns
    for spawn_id, spawn in spawns.items():
        zone_id = as_str(spawn.get("zone_id"))
        if zones and zone_id not in zones:
            report.error(f"spawn '{spawn_id}': unknown zone_id '{zone_id}'")
        location_id = as_str(spawn.get("location_id"))
        if location_id not in locations:
            report.error(f"spawn '{spawn_id}': unknown location_id '{location_id}'")
        anchor_id = as_str(spawn.get("anchor_id"))
        anchor = anchors.get(anchor_id)
        if not anchor:
            report.error(f"spawn '{spawn_id}': unknown anchor_id '{anchor_id}'")
        interior_id = as_str(spawn.get("interior_id"))
        if interior_id and interior_id not in cells:
            report.error(f"spawn '{spawn_id}': unknown interior_id '{interior_id}'")
        if anchor and as_str(anchor.get("interior_id")) not in ("", interior_id):
            report.warn(f"spawn '{spawn_id}': interior_id '{interior_id}' differs from anchor '{anchor_id}'")

        if not as_str(spawn.get("schedule_id")):
            report.error(f"spawn '{spawn_id}': schedule_id is empty")
        tags = spawn.get("schedule_tags")
        if not isinstance(tags, list) or not tags:
            report.error(f"spawn '{spawn_id}': schedule_tags must be a non-empty list")
        role = as_str(spawn.get("role"))
        if role not in ROLES:
            report.error(f"spawn '{spawn_id}': invalid role '{role}'")
        dorm = as_str(spawn.get("dorm"))
        if dorm not in DORMS:
            report.error(f"spawn '{spawn_id}': invalid dorm '{dorm}'")
        wander = spawn.get("wander_radius_cm")
        if not isinstance(wander, (int, float)) or wander < 0:
            report.error(f"spawn '{spawn_id}': wander_radius_cm must be a non-negative number")
        z_offset = spawn.get("spawn_z_offset_cm")
        if not isinstance(z_offset, (int, float)) or z_offset < 0:
            report.error(f"spawn '{spawn_id}': spawn_z_offset_cm must be a non-negative number")
        if not isinstance(spawn.get("spawn_on_begin_play", False), bool):
            report.error(f"spawn '{spawn_id}': spawn_on_begin_play must be a bool")
        if not isinstance(spawn.get("event_override", ""), str):
            report.error(f"spawn '{spawn_id}': event_override must be a string")

    # ------------------------------------------------------------------ opening requirements
    required_anchors = as_list(anchors_doc.get("opening_anchor_requirements")) or OPENING_ANCHORS
    for anchor_id in required_anchors:
        if as_str(anchor_id) not in anchors:
            report.missing_anchor(f"opening requirement: missing anchor '{anchor_id}'")
            report.error(f"opening anchor requirement missing: '{anchor_id}'")

    required_spawns = as_list(spawns_doc.get("opening_spawn_requirements"))
    for spawn_id in required_spawns:
        if as_str(spawn_id) not in spawns:
            report.error(f"opening spawn requirement missing: '{spawn_id}'")

    for loc_id, location in locations.items():
        if as_str(location.get("status")) == "missing":
            report.error(f"location '{loc_id}' is marked missing; release blocker")

    summary = {
        "root": str(root),
        "zones": len(zones),
        "locations": len(locations),
        "interiors": len(cells),
        "portals": len(portals),
        "anchors": len(anchors),
        "spawns": len(spawns),
        "statuses": {status: sum(1 for l in locations.values() if as_str(l.get("status")) == status)
                     for status in sorted(STATUSES)},
        "missing_anchors": len(report.missing_anchors),
    }
    return emit(report, args, summary)


def emit(report: Report, args: argparse.Namespace, summary: dict[str, Any]) -> int:
    if args.strict:
        report.errors.extend(f"strict: {warning}" for warning in report.warnings)
        report.warnings = []
        report.errors.extend(f"strict: {missing}" for missing in report.missing_anchors)

    payload = {
        "ok": report.ok(),
        "summary": summary,
        "errors": report.errors,
        "warnings": report.warnings,
        "missing_anchors": report.missing_anchors,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("A08 world validation")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        print()
        if report.errors:
            print(f"ERRORS ({len(report.errors)}):")
            for error in report.errors:
                print(f"  - {error}")
        if report.warnings:
            print(f"WARNINGS ({len(report.warnings)}):")
            for warning in report.warnings:
                print(f"  - {warning}")
        if report.missing_anchors:
            print(f"MISSING ANCHORS ({len(report.missing_anchors)}):")
            for missing in report.missing_anchors:
                print(f"  - {missing}")
        print()
        print("PASS" if report.ok() else "FAIL")
    return 0 if report.ok() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
