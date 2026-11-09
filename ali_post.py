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
from content_generator import HOOK_STYLES, israel_price_for

ALI_PROMPT = """You write for SHUSHU, an Israeli shopping community on Telegram and WhatsApp.
Below are AliExpress deals (machine-translated titles) found when searching for: {label}. {context}
Every item here is a real deal (a real price drop or a coupon). Pick the ONE item that best fits a stylish Israeli audience
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
If the item has "was" price: "📉 ירד מ־[was]₪ ל־[price]₪ השבוע" using the exact numbers from the data
🔥 רק [price]₪!
FOMO, one short line built only on true facts (the price drop, a coupon, many orders, the season), e.g. "⏳ מחיר כזה לא נשאר הרבה זמן"

No other asterisks, no links, no hashtags.
Example of the tone and layout (a different item, do not copy the words):
*🚨 מה קורה עם המחיר הזה?! מטען מגנטי ב־38₪ 😱*

🧲 מטען מגנטי שנצמד לטלפון וגם הופך למעמד לסרטונים
🔋 מכירים את הרגע שהטלפון עומד להיכבות דווקא כשצריך אותו?
⚡ 5,000mAh וטעינה אלחוטית, נכנס לכיס בקלות
⭐ מעל 5,000 נמכרו | דירוג 4.7

📉 ירד מ־61₪ ל־38₪ השבוע
🔥 רק 38₪!
⏳ מחיר כזה לא נשאר הרבה זמן

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


def make_post(now: datetime | None = None) -> dict | None:
    """Returns {"text", "image", "link", "id"} or None. Sends nothing."""
    now = now or community.now_il()
    posted = set(tracker.load().get("ali_posted", {}))
    queries = list(aliexpress.SEASON_QUERIES[seasons.season(now.date())])
    random.shuffle(queries)
    for cat, kw, label in queries[:3]:
        items = [i for i in aliexpress.search(kw, cat) if i["id"] not in posted][:15]
        if not items:
            continue
        _record_prices(items, now.date().isoformat())
        hist = tracker.load().get("ali_prices", {})
        for i in items:
            i["was"] = _was_price(i["id"], i["price"], hist)
        # Only real deals go out: a real price drop or a coupon
        items = [i for i in items if i["was"] or i.get("promo")]
        if not items:
            continue
        listing = "\n".join(
            f"{n}. {i['title'][:120]} | ₪{i['price']}" + (f" | was ₪{i['was']:g}" if i["was"] else "")
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
        text = pick["post"].replace("{price}", str(it["price"]))
        il = israel_price_for(it["title"][:120])
        try:
            if il and il > float(it["price"]) * 1.5:
                # Added in code so the number is exactly what the search found
                text = text.replace("\n🔥 רק", f"\n🇮🇱 דומים בארץ סביב {il}₪\n🔥 רק", 1)
        except (TypeError, ValueError):
            pass
        promo = it.get("promo") or {}
        if promo:
            # Added in code, not by Claude, so the coupon is always copied exactly
            text += f"\n\n🎁 קופון: {promo['code']}"
            if promo["value"]:
                text += f" ({promo['value']} הנחה"
                text += f" בקנייה מעל {promo['min_spend']})" if promo["min_spend"] else ")"
        link = aliexpress.short_link(it["id"]) or it["link"]
        return {"text": text, "image": it["image"], "link": link, "id": it["id"], "label": label}
    return None
