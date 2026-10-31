import json
import pathlib

path = pathlib.Path(r"C:\dev\GX\DuelAcademyIsland\Content\Data\Story\events.json")
doc = json.loads(path.read_text(encoding="utf-8"))
for event in doc["events"]:
    if event["id"] not in {"E11", "E28", "E28b"}:
        continue
    trigger = event.get("trigger", {})
    if trigger.get("type") == "date" and trigger.get("year") == 2:
        trigger["year"] = 1
    when = event.get("when", {})
    date = when.get("date")
    if isinstance(date, dict) and date.get("year") == 2:
        date["year"] = 1
    note = event.get("notes", "")
    suffix = ("Year labels use A02 school-year semantics (October-September); January-March "
              "of the following calendar year is still school Year 1.")
    if suffix not in note:
        event["notes"] = (note + " " + suffix).strip()
path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("normalized E11/E28/E28b dates to school Year 1")
