#!/usr/bin/env python3
"""Report-only audit: canon event requirements/rewards vs the runtime story graph.

    python Tools/story/audits/audit_story_rewards.py
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # Tools/, for the shared common package
from common.jsonio import read_json  # noqa: E402
from common.paths import DATA_DIR as ROOT  # noqa: E402

canon = read_json(ROOT / "Canon" / "events.json")["events"]
runtime = {e["id"]: e for e in read_json(ROOT / "Story" / "events.json")["events"]}

same_req = 0
diff_req = 0
missing_rewards = []
for ce in canon:
    i = ce["id"]
    re_ = runtime.get(i)
    if re_ is None:
        print(i, "MISSING FROM RUNTIME")
        continue
    ct = [x.get("type") for x in ce.get("requirements", [])]
    rt = [x.get("type") for x in re_.get("requirements", [])]
    if ct == rt:
        same_req += 1
    else:
        diff_req += 1
    canon_types = collections.Counter(x.get("type") for x in ce.get("rewards", []))
    run_types = collections.Counter(x.get("type") for x in re_.get("rewards", []))
    # outcomes can also contain rewards
    outcome_types = collections.Counter(x.get("type") for x in re_.get("outcomes", []))
    missing = []
    for t, n in canon_types.items():
        # map canon names to runtime names
        rt_name = {"email_unlock": "unlock_email", "tutorial": "tutorial"}.get(t, t)
        if run_types.get(rt_name, 0) + outcome_types.get(rt_name, 0) < n:
            missing.append(f"{t}x{n}")
    if missing:
        missing_rewards.append((i, missing))

def main(argv=None) -> int:
    root = DEFAULT_ROOT
    canon = json.load(open(root / "Canon" / "events.json", encoding="utf-8"))["events"]
    runtime = {e["id"]: e for e in json.load(open(root / "Story" / "events.json", encoding="utf-8"))["events"]}

# choice counts
print("\ncanon choices:", sum(len(e.get("choices", [])) for e in canon))
print("runtime event choices:", sum(len(e.get("choices", [])) for e in runtime.values()))
scenes = read_json(ROOT / "Story" / "scenes" / "full_campaign.json")["scenes"]
print("runtime scene choice commands:", sum(1 for s in scenes.values() for c in s.get("commands", []) if c.get("type") == "choice"))
dialogue = read_json(ROOT / "Story" / "dialogue" / "full_campaign.json")["lines"]
print("runtime dialogue-embedded choices:", sum(1 for v in dialogue.values() if v.get("choices")))
