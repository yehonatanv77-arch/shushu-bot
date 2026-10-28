"""
"המציאה של עלי": one AliExpress find, picked and written up by Claude.
Keeps a price history so event days can show real price drops only.
"""

import json
import random
from datetime import datetime

import aliexpress
import community
import seasons
import tracker

ALI_PROMPT = """You write for SHUSHU, an Israeli fashion discovery community on Telegram and WhatsApp.
Below are AliExpress items (machine-translated titles) found when searching for: {label}. {context}
Pick the ONE item that best fits a stylish Israeli audience right now and actually matches "{label}"
(skip items that are something else, like yarn when searching for coats, or off-season items).
Then write a short post in natural casual Hebrew, 4-6 lines:
- open with a catchy line that starts with "המציאה של עלי:"
- describe the item in plain words (what it is, how to wear it), based only on the title; do not invent materials or details
- mention the price ₪{{price}} exactly as given, and that it ships from AliExpress so delivery takes a while
- never mention discounts, "was" prices or sales
Address members in plural (אתם). Hebrew only, no English words. No markdown, no asterisks, no links, no hashtags.
At most 2 emojis, no em dashes.
Items:
{items}
Return only JSON: {{"index": <number>, "post": "..."}} or {{"index": -1}} if none fits."""


def _record_prices(items: list[dict], today: str):
    data = tracker.load()
    hist = data.setdefault("ali_prices", {})
    for it in items:
        h = hist.setdefault(it["id"], [])
        if not h or h[-1][0] != today:
            h.append([today, it["price"]])
            del h[:-30]
    tracker.save(data)


def make_post(now: datetime | None = None) -> dict | None:
    """Returns {"text", "image", "link", "id"} or None. Sends nothing."""
    now = now or community.now_il()
    posted = set(tracker.load().get("ali_posted", {}))
    queries = list(aliexpress.SEASON_QUERIES[seasons.season(now.date())])
    random.shuffle(queries)
    for cat, kw, label in queries[:3]:
        items = [i for i in aliexpress.search(kw, cat) if i["id"] not in posted][:15]
        if len(items) < 3:
            continue
        _record_prices(items, now.date().isoformat())
        listing = "\n".join(f"{n}. {i['title'][:120]} | ₪{i['price']} | {i['orders']} orders" for n, i in enumerate(items))
        raw = community._claude(ALI_PROMPT.format(label=label, context=community._context(now), items=listing), 600)
        try:
            pick = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        except ValueError:
            continue
        idx = pick.get("index", -1)
        if not (0 <= idx < len(items)) or not pick.get("post"):
            continue
        it = items[idx]
        text = pick["post"].replace("{price}", str(it["price"]))
        return {"text": text, "image": it["image"], "link": it["link"], "id": it["id"], "label": label}
    return None
