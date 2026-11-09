"""
"המציאה של עלי": one AliExpress find, picked and written up by Claude.
Keeps a price history so event days can show real price drops only.
"""

import json
import math
import os
import random
from datetime import datetime

import aliexpress
import community
import seasons
import tracker
from content_generator import HOOK_STYLES, israel_price_for

ALI_PROMPT = """You write for SHUSHU, an Israeli shopping community on Telegram and WhatsApp.
Below are AliExpress deals (machine-translated titles) found when searching for: {label}. {context}
Every item here is a real deal (AliExpress's 11.11 sale, a real price drop or a coupon). Pick the ONE item that best fits a stylish Israeli audience
right now and actually matches "{label}" (skip items that are something else, like yarn when searching for coats, or off-season items).
Then write a short post whose job is to make people BUY, in Hebrew, short lines easy to scan on a phone.

TONE: a friend excitedly telling friends about a deal they found ("תראו מה מצאנו", "תקשיבו", "מה קורה עם המחיר הזה?!").
Very excited and enthusiastic, but short. Not an ad voice, no salesman phrases.
SOUND HUMAN, NOT AI (very important):
- Write like a real Israeli texting on WhatsApp: everyday slang (וואלה, סחתיין, אחלה, מטורף, בקיצור), a bit loose, not polished
- Vary the rhythm: lines of different lengths, not every line ending with "!"
- Emojis: 1-2 per line at most, not on every line; never ✨ 💫 🌟, never stacked
- No AI phrases: "בין אם... ובין אם", "לא רק... אלא גם", "מושלם ל", "הפריט האידיאלי", "שדרוג", "חוויה", "פשוט חובה"
- No lists of three adjectives, no summaries at the end, no em dashes
- Never invent a personal experience, never push personal taste, do not highlight how many colors there are
- Base every detail only on the title; do not invent materials, specs or brands
- Never mention shipping or delivery times. Address members in plural (אתם). Hebrew only, except numbers and units (mAh, W).

STRUCTURE (exactly this):
Line 1, bold with single asterisks: *🔥 + a short, very excited hook in this style: {hook_style}. End with 😱 / 🤯 / 😳*
Blank line
An emoji that fits + what the item is, in plain words, with what makes it stand out
Optional: an everyday problem it solves, as a question (e.g. "🔋 מכירים את הרגע שהטלפון עומד להיכבות דווקא כשצריך אותו?")
One line: what it does / how to use or wear it
⭐ real orders and rating from the data (e.g. "⭐ מעל 5,000 נמכרו | דירוג 4.7"), only if orders are 100 or more
Blank line
🔥 באלי בפחות מ־[under]₪!  (use the item's exact "under" number; AliExpress prices change per person, so never write an exact price)
FOMO, one short line built only on true facts (the 11.11 sale ends 18/11 if the item is marked "11.11 sale", a price drop, a coupon, many orders, the season), e.g. "⏳ מחיר כזה לא נשאר הרבה זמן"

No other asterisks, no links, no hashtags.
Example of the tone and layout (a different item, do not copy the words):
*🚨 מה קורה עם המחיר הזה?! מטען מגנטי בפחות מ־40₪ 😱*

🧲 מטען מגנטי שנצמד לטלפון וגם הופך למעמד לסרטונים
🔋 מכירים את הרגע שהטלפון עומד להיכבות דווקא כשצריך אותו?
⚡ 5,000mAh וטעינה אלחוטית, נכנס לכיס בקלות
⭐ מעל 5,000 נמכרו | דירוג 4.7

🔥 באלי בפחות מ־40₪!
⏳ מבצע 11.11 נגמר ב־18/11

Items:
{items}
Return only JSON: {{"index": <number>, "post": "..."}} or {{"index": -1}} if none fits."""

MIN_DROP = 0.2  # a "real deal" = at least 20% under the highest price we saw in the last 30 days, or a coupon


def _was_price(item_id: str, price, hist: dict) -> float:
    """Highest earlier price we recorded for this item when today's is at least MIN_DROP lower, else 0."""
    try:
        now_p = float(price)
        before = max(float(p) for d, p in hist.get(item_id, [])[:-1])
    except (TypeError, ValueError):
        return 0
    return before if now_p <= before * (1 - MIN_DROP) else 0


def _record_prices(items: list[dict], today: str):
    data = tracker.load()
    hist = data.setdefault("ali_prices", {})
    for it in items:
        h = hist.setdefault(it["id"], [])
        if not h or h[-1][0] != today:
            h.append([today, it["price"]])
            del h[:-30]
    tracker.save(data)


COUPONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ali_coupons.json")
USD_TO_ILS = 3.7  # rough, only to check a coupon's minimum spend


def _under(price) -> int:
    """Price rounded UP to the next 10: AliExpress shows each person a slightly different price."""
    return int(math.ceil(float(price) / 10.0) * 10)


def _israel_coupon(price, today: str) -> dict:
    """Best valid Israel coupon (from Code Center, kept in ali_coupons.json) that this item reaches."""
    try:
        coupons = json.load(open(COUPONS_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    fits = [c for c in coupons if str(c.get("until", "9999")) >= today
            and float(c.get("min_usd") or 0) * USD_TO_ILS <= float(price)]
    return max(fits, key=lambda c: float(c.get("off_usd") or 0), default={})


def _candidates(now: datetime, posted: set):
    """(label, items) groups to pick from: the 11.11 sale lists first while the sale runs, then seasonal searches."""
    today = now.date().isoformat()
    if today <= aliexpress.SALE_END:
        for name in random.sample(aliexpress.SALE_LISTS, len(aliexpress.SALE_LISTS)):
            try:
                items = [i for i in aliexpress.featured(name) if i["id"] not in posted][:15]
            except Exception as e:
                print(f"[ali] Featured list failed: {e}")
                items = []
            for i in items:
                i["sale"] = True
            if items:
                yield "fashion only: clothing, shoes, bags, jewelry, watches or fashion accessories (no phones, gadgets, tools, home or sports gear)", items
    queries = list(aliexpress.SEASON_QUERIES[seasons.season(now.date())])
    random.shuffle(queries)
    for cat, kw, label in queries[:3]:
        yield label, [i for i in aliexpress.search(kw, cat) if i["id"] not in posted][:15]


def make_post(now: datetime | None = None) -> dict | None:
    """Returns {"text", "image", "link", "id"} or None. Sends nothing."""
    now = now or community.now_il()
    today = now.date().isoformat()
    posted = set(tracker.load().get("ali_posted", {}))
    for label, items in _candidates(now, posted):
        if not items:
            continue
        _record_prices(items, today)
        hist = tracker.load().get("ali_prices", {})
        for i in items:
            i["was"] = _was_price(i["id"], i["price"], hist)
        # Only real deals go out: the 11.11 sale, a real price drop or a coupon
        items = [i for i in items if i.get("sale") or i["was"] or i.get("promo")]
        if not items:
            continue
        listing = "\n".join(
            f"{n}. {i['title'][:120]} | under ₪{_under(i['price'])}" + (" | 11.11 sale" if i.get("sale") else "")
            + (" | price dropped this week" if i["was"] else "")
            + f" | {i['orders']} orders | rating {i['rating']}%" + (" | has coupon" if i.get("promo") else "")
            for n, i in enumerate(items))
        raw = community._claude(ALI_PROMPT.format(label=label, context=community._context(now), items=listing,
                                              hook_style=random.choice(HOOK_STYLES)), 600)
        try:
            pick = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        except ValueError:
            continue
        idx = pick.get("index", -1)
        if not (0 <= idx < len(items)) or not pick.get("post"):
            continue
        it = items[idx]
        text = pick["post"]
        il = israel_price_for(it["title"][:120])
        if il and il > _under(it["price"]) * 1.5:
            # Added in code so the number is exactly what the search found
            text = text.replace("\n🔥 באלי", f"\n🇮🇱 דומים בארץ סביב {il}₪\n🔥 באלי", 1)
        # Coupons are added in code, not by Claude, so they are always copied exactly
        promo = it.get("promo") or {}
        if promo:
            text += f"\n\n🎁 קופון מוכר: {promo['code']}"
            if promo["value"]:
                text += f" ({promo['value']} הנחה" + (f" בקנייה מעל {promo['min_spend']})" if promo["min_spend"] else ")")
        coupon = _israel_coupon(it["price"], today)
        if coupon:
            text += ("\n" if promo else "\n\n") + f"🎁 קופון: {coupon['code']} ({coupon['off_usd']}$ הנחה בקנייה מעל {coupon['min_usd']}$)"
        link = aliexpress.short_link(it["id"]) or it["link"]
        return {"text": text, "image": it["image"], "link": link, "id": it["id"], "label": label}
    return None
