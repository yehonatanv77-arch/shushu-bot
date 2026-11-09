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
from content_generator import HOOK_STYLES

ALI_PROMPT = """You write for SHUSHU, an Israeli fashion discovery community on Telegram and WhatsApp.
Below are AliExpress items (machine-translated titles) found when searching for: {label}. {context}
Pick the ONE item that best fits a stylish Israeli audience right now (prefer items that have a coupon) and actually matches "{label}"
(skip items that are something else, like yarn when searching for coats, or off-season items).
Then write a short post whose job is to make people buy, in Hebrew, short lines easy to scan on a phone.
TONE: write it as a personal recommendation from me to a good friend, in first person ("מצאתי", "תקשיבו", "אני לא מתגבר על", "הייתי לוקח"), warm and honest, the way you text a friend about something you really liked. Not an ad voice, no salesman phrases. Still excited and short, with emojis where they feel natural.
SOUND HUMAN, NOT AI (very important):
- Write like a real Israeli texting on WhatsApp: everyday slang (וואלה, סחתיין, אחלה, מטורף, בקיצור), short and a bit loose, not polished
- Vary the rhythm: lines of different lengths, not every line built the same way, not every line ending with "!"
- Emojis: 1-2 per line at most, and NOT on every line; skip the typical AI emojis ✨ 💫 🌟 and never stack them
- No AI phrases: "בין אם... ובין אם", "לא רק... אלא גם", "מושלם ל", "הפריט האידיאלי", "שדרוג", "חוויה", "פשוט חובה", "מה שהופך את זה ל"
- No lists of three adjectives, no rhetorical summaries at the end, no em dashes, no colons in the middle of sentences
- Never invent a personal experience ("הלכתי איתן יום שלם"); recommend from opinion only ("הייתי לוקח את האפור", "זה בדיוק הסגנון שלי")

Layout:
Exactly this structure:
Line 1: 🔥 / 🚨 opener + a short exciting hook in this style: {hook_style}. End it with 😱 / 🤯 / 😍
Line 2: an emoji + what the item is, in plain words
Blank line
Optional: one line with an everyday problem it solves (e.g. "🔋 מכירים את הרגע שהטלפון עומד להיכבות דווקא כשצריך אותו?")
1-2 lines with fitting emojis: what it does / how it looks, based only on the title; do not invent materials or details
⭐ the real number of orders and the rating from the data (e.g. "⭐ מעל 5,000 נמכרו | דירוג 4.7"), only if orders are 100 or more
Blank line
🔥 רק ₪{{price}}!
Never mention shipping or delivery times. Never mention discounts, "was" prices or sales. Address members in plural (אתם). Hebrew only, no English words.
Wrap the hook (line 1) in single asterisks for bold, e.g. *🔥 בנות, תראו איזה ג'קט מצאנו לכן! 😍*. No other asterisks.
FOMO: add ONE short line with a real sense of urgency where it fits best (usually right before the price), built only on true facts: high demand (many orders), it sold out before / came back, the season is starting, a limited sale or coupon. E.g. "⏳ זה נחטף מהר, אל תחכו" or "🚨 זה חזר למלאי!" only if true. Never invent stock counts or deadlines.
No other markdown, no links, no hashtags, no em dashes.
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
        listing = "\n".join(f"{n}. {i['title'][:120]} | ₪{i['price']} | {i['orders']} orders | rating {i['rating']}%{' | has coupon' if i.get('promo') else ''}"
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
