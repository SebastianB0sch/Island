import json

ROOT = r"C:\dev\GX\DuelAcademyIsland\Content\Data"
events = json.load(open(ROOT + r"\Story\events.json", encoding="utf-8"))["events"]
FLAG_BLOCK = {"post_game", "walk_home_partner_3", "stayed_in_room_three_weekends"}

def req_event_refs(req, out):
    t = req.get("type")
    if t == "event":
        out.append(req.get("event"))
    for key in ("all", "any"):
        for child in req.get(key, []) or []:
            req_event_refs(child, out)

def has_flag_block(req):
    t = req.get("type")
    if t == "flag" and req.get("flag") in FLAG_BLOCK:
        return True
    for key in ("all", "any"):
        for child in req.get(key, []) or []:
            if has_flag_block(child):
                return True
    return False

blocked = set()
for e in events:
    trg = e.get("trigger", {})
    if trg.get("type") == "talk":
        blocked.add(e["id"])
    if trg.get("type") == "flag" and trg.get("flag") in FLAG_BLOCK:
        blocked.add(e["id"])
    if any(has_flag_block(r) for r in e.get("requirements", [])):
        blocked.add(e["id"])

changed = True
while changed:
    changed = False
    for e in events:
        i = e["id"]
        if i in blocked:
            continue
        deps = []
        trg = e.get("trigger", {})
        if trg.get("type") == "event" and trg.get("event"):
            deps.append(trg["event"])
        for r in e.get("requirements", []):
            req_event_refs(r, deps)
        deps = [d for d in deps if d]
        if deps and all(d in blocked for d in deps):
            blocked.add(i)
            changed = True

print("talk/no-hook:", sorted(e["id"] for e in events if e.get("trigger", {}).get("type") == "talk"))
print("blocked:", sorted(blocked))
print("reachable:", sorted(e["id"] for e in events if e["id"] not in blocked))
print(f"reachable {len(events)-len(blocked)}/{len(events)}, blocked {len(blocked)}/{len(events)}")
