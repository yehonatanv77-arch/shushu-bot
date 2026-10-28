"""
Nightly health check, runs on GitHub (no computer needed).
Fails the workflow when something is missing, so GitHub emails the repo owner.
Never prints keys or phone numbers (the repo is public).
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding="utf-8")
IL = ZoneInfo("Asia/Jerusalem")
UTC = ZoneInfo("UTC")
today = datetime.now(IL).date()

with open("posted_products.json", encoding="utf-8-sig") as f:
    data = json.load(f)


def il_date(ts: str, utc: bool):
    if not ts:
        return None
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC if utc else IL)
    return dt.astimezone(IL).date()


posted = data.get("posted", {})
products = sum(1 for k, v in posted.items()
               if not k.startswith(("look_", "article_")) and il_date(v.get("posted_at", ""), True) == today)
look = any(k.startswith("look_") and il_date(v.get("posted_at", ""), True) == today for k, v in posted.items())
ali = sum(1 for ts in data.get("ali_posted", {}).values() if il_date(ts, False) == today)

problems = []
if not look:
    problems.append("הלוק היומי לא פורסם היום")
if products + ali < 8:
    problems.append(f"פורסמו רק {products + ali} מוצרים היום (צפוי בערך 15)")
if ali == 0:
    problems.append("לא פורסמה אף מציאה של עלי היום")

lines = [f"דוח {today:%d.%m}", f"לוק יומי: {'כן' if look else 'לא'}",
         f"מוצרים מהספק: {products}", f"מציאות של עלי: {ali}"]
lines += [f"בעיה: {p}" for p in problems] or ["הכל תקין"]
report = "\n".join(lines)
print(report)
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as f:
        f.write(report.replace("\n", "  \n") + "\n")
sys.exit(1 if problems else 0)
