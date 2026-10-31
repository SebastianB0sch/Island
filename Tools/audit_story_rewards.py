import json, collections

ROOT = r"C:\dev\GX\DuelAcademyIsland\Content\Data"
canon = json.load(open(ROOT + r"\Canon\events.json", encoding="utf-8"))["events"]
runtime = {e["id"]: e for e in json.load(open(ROOT + r"\Story\events.json", encoding="utf-8"))["events"]}

same_req = 0
diff_req = 0
missing_rewards = []
for ce in canon:
    i = ce["id"]
    re_ = runtime[i]
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

print("requirement type lists identical:", same_req, "/", len(canon))
print("requirement type lists differ:", diff_req, "/", len(canon))
print("events with missing/modified rewards:", len(missing_rewards))
for i, m in missing_rewards:
    print(i, m)

# choice counts
print("\ncanon choices:", sum(len(e.get("choices", [])) for e in canon))
print("runtime event choices:", sum(len(e.get("choices", [])) for e in runtime.values()))
scenes = json.load(open(ROOT + r"\Story\scenes\full_campaign.json", encoding="utf-8"))["scenes"]
print("runtime scene choice commands:", sum(1 for s in scenes.values() for c in s.get("commands", []) if c.get("type") == "choice"))
dialogue = json.load(open(ROOT + r"\Story\dialogue\full_campaign.json", encoding="utf-8"))["lines"]
print("runtime dialogue-embedded choices:", sum(1 for v in dialogue.values() if v.get("choices")))
