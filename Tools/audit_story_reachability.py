import json

ROOT = r"C:\dev\GX\DuelAcademyIsland\Content\Data"
events = json.load(open(ROOT + r"\Story\events.json", encoding="utf-8"))["events"]
by_id = {e["id"]: e for e in events}

TALK = set()
FLAG_BLOCK = {"post_game", "walk_home_partner_3", "stayed_in_room_three_weekends"}

def collect_event_refs(req, out):
    t = req.get("type")
    if t == "event":
        out.append(req.get("event"))
    for key in ("all", "any"):
        for child in req.get(key, []) or []:
            collect_event_refs(child, out)

def has_flag_block(req):
    t = req.get("type")
    if t == "flag" and req.get("flag") in FLAG_BLOCK:
        return True
    for key in ("all", "any"):
        for child in req.get(key, []) or []:
            if has_flag_block(child):
                return True
    return False

print("=== TRIGGER TABLE ===")
for e in events:
    trg = e.get("trigger", {})
    refs = []
    for req in e.get("requirements", []):
        collect_event_refs(req, refs)
    flags = [r.get("flag") for r in e.get("requirements", []) if r.get("type") == "flag"]
    marker = ""
    if trg.get("type") == "talk":
        TALK.add(e["id"])
        marker = "  <-- TALK (no world hook)"
    if has_flag_block(req for req in e.get("requirements", [])) if False else any(has_flag_block(r) for r in e.get("requirements", [])):
        marker += "  <-- UNPRODUCED FLAG"
    print(f"{e['id']:5} trigger={trg.get('type'):9} {str(trg.get('npc') or trg.get('event') or trg.get('flag') or ''):14} reqEvents={refs} reqFlags={flags}{marker}")

# propagate unreachability (direct event requirements). Treat any-talk/flag as blocked.
blocked = set(TALK)
for e in events:
    if any(has_flag_block(r) for r in e.get("requirements", [])):
        blocked.add(e["id"])
    if e.get("trigger", {}).get("type") == "flag" and e["trigger"].get("flag") in FLAG_BLOCK:
        blocked.add(e["id"])

changed = True
while changed:
    changed = False
    for e in events:
        i = e["id"]
        if i in blocked:
            continue
        refs = []
        for r in e.get("requirements", []):
            collect_event_refs(r, refs)
        refs = [r for r in refs if r]
        if refs and all(r in blocked for r in refs):
            # only safe if every direct event ref is blocked; OR-shaped any() not handled precisely
            blocked.add(i)
            changed = True

print("\n=== REACHABILITY UNDER REAL GAMEPLAY HOOKS ===")
print("talk-trigger events (no StartEvent caller):", sorted(TALK))
print("blocked (direct/transitive):", sorted(blocked))
print("reachable count:", len(events) - len(blocked), "/", len(events))
print("blocked count:", len(blocked), "/", len(events))
