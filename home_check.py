"""Run this on the home network (the one the TV uses), then commit home-status.json.

GitHub's servers sit in US data centres, so they see some streams as alive that are
blocked at home, and miss some that only block data centres. This records what the
home network can really reach, and build.py uses it to correct the daily check.
"""
import datetime
import json

from build import HOME_STATUS, collect
from check import check_all

entries = collect()
results = check_all(entries)
status = {url: result[0] for (_, url), result in zip(entries, results)}
with open(HOME_STATUS, "w", encoding="utf-8") as f:
    json.dump({"checked": datetime.date.today().isoformat(), "streams": status}, f, indent=0, sort_keys=True)
print("recorded", len(status), "streams;", sum(s != "dead" for s in status.values()), "reachable from home")
