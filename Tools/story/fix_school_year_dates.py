import json
import pathlib
from story_common import read_json, write_json


def main() -> int:
    path = pathlib.Path(__file__).resolve().parents[2] / "DuelAcademyIsland" / "Content" / "Data" / "Story" / "events.json"
    doc = read_json(path)
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
    write_json(path, doc)
    print("normalized E11/E28/E28b dates to school Year 1")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
