import sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime
import community, seasons

# Dry run of the event-day list as if today were Black Friday (nothing is sent)
now = datetime(2026, 11, 27, 12, tzinfo=community.IL)
community.tracker.save = lambda data: None
print("EVENT", seasons.event_today(now.date()))
print("POST", community._event_post(now, "whatsapp", early=True))
import collections; print("CATS", [community._category_slugs.get(p.get("category_id") or "") for p in community._event_items(150, now, 40)])
