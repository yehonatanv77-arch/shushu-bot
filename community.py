"""
Community actions, run from the hourly bot by Israel day and hour:
  Sun 13:00  trend of the week with 3 seasonal items (Telegram + WhatsApp)
  Tue 13:00  brand poll (Telegram + WhatsApp)
  Thu 13:00  fun seasonal poll (the WhatsApp group is read-only, members can only vote)
  Fri 13:00  close poll, announce winner, boost that brand for a week
  18:00 the day before a shopping event or holiday  heads-up message
  Black Friday warm-up, 20:00: teaser (-14 days), poll (-10), countdown (-7), prep (-3)
  Event day  hand-picked list under a price cap: WhatsApp 12:00 (early), Telegram 14:00.
             No discount claims, our supplier gives no coupons.
  Daily 21:00  WhatsApp invite to the Telegram channel
Each action runs at most once per day (keys under data["community"]).
"""

import random
import re
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import anthropic
import httpx

import json

import seasons
import tracker
from scraper import SUPABASE_URL, HEADERS
from telegram_poster import send_text, send_poll, stop_poll
from whatsapp_poster import send_text_to_group, send_poll_to_group, get_poll_votes, find_poll_id, group_size

IL = ZoneInfo("Asia/Jerusalem")
TELEGRAM_LINK = "https://t.me/shusu_secret"
SITE = "https://shushu-secret.com"


def site_link(path: str, source: str, campaign: str) -> str:
    """Link to our own site, tagged so site analytics show which channel sent the visit."""
    return f"{SITE}{path}?utm_source={source}&utm_medium=community&utm_campaign={campaign}"
POLL_QUESTION = "איזה מותג להביא יותר בשבוע הבא?"

# weekday: Mon=0 ... Sun=6
SCHEDULE = {
    (6, 13): "trend",
    (1, 13): "poll",
    (3, 13): "fun_poll",
    (4, 13): "poll_close",
}
INVITE_HOUR = 21
WELCOME_HOUR = 17  # once a day, only if the WhatsApp group grew since the last welcome
EVENT_HOUR = 18  # heads-up the evening before a shopping event / holiday
EVENT_LIST_WA_HOUR = 12  # event day: the WhatsApp group gets the list an early hour first
EVENT_LIST_TG_HOUR = 14

# WhatsApp product slots; a community post scheduled for the same hour takes the slot
WA_PRODUCT_HOURS = tuple(range(10, 20))  # 10 product posts a day, 10:00-19:00
ALI_HOURS = (11, 15, 19)  # "המציאה של עלי" takes these product slots


def _event_tomorrow(now: datetime):
    ev = seasons.upcoming_event(now.date(), 1)
    return ev if ev and ev[2] == 1 else None


def now_il() -> datetime:
    return datetime.now(IL)


def whatsapp_product_slot(now: datetime) -> bool:
    if now.hour == EVENT_HOUR and (_event_tomorrow(now) or seasons.event_today(now.date())):
        return False
    if now.hour == EVENT_LIST_WA_HOUR and seasons.event_today(now.date()):
        return False
    return now.hour in WA_PRODUCT_HOURS and (now.weekday(), now.hour) not in SCHEDULE


def favorite_brand() -> str:
    data = tracker.load()
    fav = data.get("favorite_brand") or {}
    if fav.get("until", "") >= now_il().date().isoformat():
        return fav.get("brand", "")
    return ""


# Comeback poll in the WhatsApp group: option -> root category slugs on the site
CATEGORY_POLL_MIN_VOTES = 15
CATEGORY_POLL_QUESTION = "מה הכי מעניין אתכם לראות כאן?"
CATEGORY_POLL_OPTIONS = {
    "נעליים וסניקרס": {"shoes"},
    "תיקים ואקססוריז": {"bags", "accessories"},
    "בגדים": {"clothing"},
    "יוקרה במחיר נגיש": {"luxury"},
}
LUXURY_BRANDS = {
    "Loewe", "Balenciaga", "Chanel", "Gucci", "Prada", "Miu Miu", "Dior", "Louis Vuitton",
    "Saint Laurent", "Valentino", "Bottega Veneta", "Celine", "Burberry", "Versace", "Fendi",
    "Hermes", "Givenchy", "Moncler", "Patek Philippe", "Rolex", "Cartier", "Alexander McQueen",
    "Rick Owens", "Jacquemus", "Golden Goose", "Marc Jacobs",
}

_category_roots = {}
_category_slugs = {}


def _load_categories():
    if _category_roots:
        return
    r = httpx.get(f"{SUPABASE_URL}/rest/v1/categories", headers=HEADERS,
                  params={"select": "id,slug,parent_id"}, timeout=30)
    r.raise_for_status()
    cats = {c["id"]: c for c in r.json()}
    for cid, c in cats.items():
        _category_slugs[cid] = c["slug"]
        while c.get("parent_id") in cats:
            c = cats[c["parent_id"]]
        _category_roots[cid] = c["slug"]


def _root_slug(category_id: str) -> str:
    _load_categories()
    return _category_roots.get(category_id, "")


def matches_season(entry: dict, now: datetime | None = None) -> bool:
    _load_categories()
    slugs = seasons.SEASON_SLUGS[seasons.season((now or now_il()).date())]
    return _category_slugs.get(entry.get("category_id", ""), "") in slugs


def refresh_category_pref(now: datetime):
    """Once a day, re-reads the comeback poll and stores the leading option."""
    data = tracker.load()
    pref = data.get("category_pref") or {}
    if pref.get("date") == now.date().isoformat():
        return
    poll_id = pref.get("wa_id") or find_poll_id(CATEGORY_POLL_QUESTION)
    votes = get_poll_votes(poll_id) if poll_id else {}
    # Until enough people voted, keep a balanced mix instead of pushing one category
    winner = max(votes, key=votes.get) if sum(votes.values()) >= CATEGORY_POLL_MIN_VOTES else ""
    data["category_pref"] = {"wa_id": poll_id, "votes": votes, "winner": winner,
                             "date": now.date().isoformat()}
    tracker.save(data)
    print(f"[community] Category poll votes: {votes}")


def matches_favorite_category(entry: dict) -> bool:
    winner = (tracker.load().get("category_pref") or {}).get("winner", "")
    targets = CATEGORY_POLL_OPTIONS.get(winner)
    if not targets:
        return False
    if "luxury" in targets:
        return brand_of(entry.get("name", "")) in LUXURY_BRANDS
    return _root_slug(entry.get("category_id", "")) in targets


def root_of(entry: dict) -> str:
    try:
        return _root_slug(entry.get("category_id", ""))
    except Exception:
        return ""


def recent_roots(n: int = 2) -> list[str]:
    return (tracker.load().get("recent_roots") or [])[-n:]


def note_root(root: str):
    if not root:
        return
    data = tracker.load()
    data["recent_roots"] = ((data.get("recent_roots") or []) + [root])[-10:]
    tracker.save(data)


def favorite_category() -> str:
    return (tracker.load().get("category_pref") or {}).get("winner", "")


def _done_today(action: str, now: datetime) -> bool:
    return tracker.load().get("community", {}).get(action) == now.date().isoformat()


def _mark_done(action: str, now: datetime, **extra):
    data = tracker.load()
    data.setdefault("community", {})[action] = now.date().isoformat()
    data.update(extra)
    tracker.save(data)


KNOWN_BRANDS = [
    "Ralph Lauren", "Nike", "Adidas", "New Balance", "On Running", "Loewe", "Balenciaga",
    "Chanel", "Gucci", "Prada", "Miu Miu", "Dior", "Louis Vuitton", "Saint Laurent",
    "Valentino", "Bottega Veneta", "Celine", "Burberry", "Versace", "Fendi", "Hermes",
    "Givenchy", "Moncler", "Stone Island", "Off-White", "Fear of God", "Essentials",
    "Lacoste", "Tommy", "Calvin Klein", "Hugo Boss", "Armani", "Michael Kors", "Coach",
    "Ray-Ban", "Apple", "Patek Philippe", "Rolex", "Cartier", "Asics", "Salomon",
    "Converse", "Vans", "Puma", "Jordan", "Alo", "Lululemon", "Skims", "Zara", "Acne Studios",
    "Jacquemus", "Marc Jacobs", "Golden Goose", "Alexander McQueen", "Rick Owens",
]


def brand_of(name: str) -> str:
    for b in KNOWN_BRANDS:
        if re.search(r"(?<![A-Za-z])" + re.escape(b) + r"(?![A-Za-z])", name or "", re.IGNORECASE):
            return b
    return ""


def _top_brands(n: int = 12) -> list[str]:
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/products",
        headers=HEADERS,
        params={"select": "name_en,name,brand", "is_active": "eq.true", "limit": "5000"},
        timeout=30,
    )
    r.raise_for_status()
    counts = Counter(brand_of(p.get("name_en") or p.get("name") or "") or (p.get("brand") or "").strip()
                     for p in r.json())
    counts.pop("", None)
    return [b for b, c in counts.most_common(n) if c >= 3]


def do_poll(now: datetime):
    brands = _top_brands()
    if len(brands) < 4:
        print("[community] Not enough brands for a poll")
        return
    options = random.sample(brands, 4)
    tg = send_poll(POLL_QUESTION, options)
    wa_id = send_poll_to_group(POLL_QUESTION, options)
    _mark_done("poll", now, brand_poll={
        "message_id": tg["message_id"] if tg else None,
        "options": options,
        "wa_id": wa_id,
        "date": now.date().isoformat(),
    })
    print(f"[community] ✅ Poll sent: {options}")


def do_poll_close(now: datetime):
    poll = tracker.load().get("brand_poll") or {}
    if not poll.get("message_id") and not poll.get("wa_id"):
        print("[community] No open poll")
        _mark_done("poll_close", now)
        return
    votes = {o: 0 for o in poll.get("options", [])}
    if poll.get("message_id"):
        result = stop_poll(poll["message_id"])
        for o in (result or {}).get("options", []):
            votes[o["text"]] = votes.get(o["text"], 0) + o["voter_count"]
    if poll.get("wa_id"):
        for o, c in get_poll_votes(poll["wa_id"]).items():
            votes[o] = votes.get(o, 0) + c
    print(f"[community] Poll votes: {votes}")
    if not votes or max(votes.values()) == 0:
        _mark_done("poll_close", now, brand_poll={})
        return
    winner = max(votes, key=votes.get)
    text = (
        f"הסקר נסגר, ו-{winner} ניצח 🏆\n\n"
        f"השבוע נעלה לכם יותר פריטים של {winner}. תודה לכל מי שהצביע!"
    )
    send_text(text)
    send_text_to_group(text)
    until = (now.date() + timedelta(days=7)).isoformat()
    _mark_done("poll_close", now, brand_poll={},
               favorite_brand={"brand": winner, "until": until, "votes": votes})
    print(f"[community] ✅ Winner: {winner} (boosted until {until})")


QUESTION_PROMPT = """You write for SHUSHU, an Israeli fashion discovery community on Telegram and WhatsApp.
Write ONE short open question in natural, casual Hebrew that invites members to reply.
Topic ideas: what they wear this season, a brand they wish we found, their best online find, how they style one item.
Rules: 1-2 lines, at most 1 emoji, no em dashes, no hashtags, no links.
Return only the question."""


def do_question(now: datetime):
    msg = anthropic.Anthropic().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        messages=[{"role": "user", "content": QUESTION_PROMPT}],
    )
    text = msg.content[0].text.strip().replace("—", ",").replace("–", ",")
    send_text(text)
    send_text_to_group(text)
    _mark_done("question", now)
    print(f"[community] ✅ Question: {text}")


def _context(now: datetime) -> str:
    s = seasons.SEASON_HE[seasons.season(now.date())]
    ev = seasons.upcoming_event(now.date(), 14)
    text = f"Current season in Israel: {s}."
    if ev:
        text += f" Coming up in {ev[2]} days: {ev[0]} ({ev[1]})."
    return text


def _claude(prompt: str, max_tokens: int = 400) -> str:
    msg = anthropic.Anthropic().messages.create(
        model="claude-opus-5-5",
        max_tokens=max_tokens + 1500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(getattr(b, "text", None) or "" for b in msg.content if getattr(b, "type", "") == "text")
    return text.strip().replace("—", ",").replace("–", ",").replace("**", "")


FUN_POLL_PROMPT = """You write for SHUSHU, an Israeli fashion discovery community. Members cannot write in the WhatsApp group, they can only vote in polls.
Create ONE fun, light poll in natural casual Hebrew that fits right now. {context}
Ideas: this or that between two styles, what are you buying this season, budget per item, which trend should stay or go, what to wear to an upcoming event.
Address members in plural (אתם), never feminine-only (אתן). Hebrew only, no English words except brand names. No markdown, no asterisks.
Rules: question up to 12 words, 2 to 4 short options (up to 4 words each), at most 1 emoji in the question, no em dashes.
Avoid repeating these recent questions: {recent}
Return only JSON: {{"question": "...", "options": ["...", "..."]}}"""


def do_fun_poll(now: datetime):
    recent = tracker.load().get("fun_polls", [])[-6:]
    raw = _claude(FUN_POLL_PROMPT.format(context=_context(now), recent=recent or "none"), 200)
    poll = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    question, options = poll["question"], poll["options"][:4]
    send_poll(question, options)
    send_poll_to_group(question, options)
    data = tracker.load()
    data["fun_polls"] = (data.get("fun_polls", []) + [question])[-20:]
    tracker.save(data)
    _mark_done("fun_poll", now)
    print(f"[community] ✅ Fun poll: {question} {options}")


def _seasonal_category(now: datetime, n: int = 3):
    """Picks a seasonal category with enough items; returns (slug, products) or ("", [])."""
    _load_categories()
    slugs = list(seasons.SEASON_SLUGS[seasons.season(now.date())])
    random.shuffle(slugs)
    for slug in slugs:
        ids = [cid for cid, s in _category_slugs.items() if s == slug]
        if not ids:
            continue
        r = httpx.get(
            f"{SUPABASE_URL}/rest/v1/products",
            headers=HEADERS,
            params={"select": "id,name,name_en", "is_active": "eq.true",
                    "category_id": f"in.({','.join(ids)})", "order": "updated_at.desc", "limit": "40"},
            timeout=30,
        )
        r.raise_for_status()
        items = [p for p in r.json() if p.get("name") or p.get("name_en")]
        if len(items) >= n:
            return slug, random.sample(items, n)
    return "", []


TREND_PROMPT = """You write for SHUSHU, an Israeli fashion discovery community on Telegram and WhatsApp.
Write a short "trend of the week" post in natural casual Hebrew. {context}
Pick one concrete trend that fits the season (a style, color, fabric or item) and explain in 2-3 lines why it is in now and how to wear it.
Then present these 3 items as the way to get the look, one short line each, using the exact names below.
Do not claim colors or materials that are not in the item names:
{products}
Address members in plural (אתם), never feminine-only (אתן). Hebrew only, no English words except brand names. No markdown, no asterisks.
Write simple, correct everyday Hebrew like a stylish friend. No made-up slang, no transliterated foreign phrases, no word games.
Rules: open with a title line "טרנד השבוע: " followed by the trend name in plain words, at most 2 emojis, no em dashes, no hashtags, no links (links are added after).
Return only the post."""


def do_trend(now: datetime):
    slug, products = _seasonal_category(now)
    if not products:
        print("[community] Not enough seasonal products for a trend post")
        _mark_done("trend", now)
        return
    names = [p.get("name") or p.get("name_en") for p in products]
    text = _claude(TREND_PROMPT.format(context=_context(now), products="\n".join(f"- {n}" for n in names)))
    path = f"/category/{slug}"
    cta = "👉 את כל הפריטים בסגנון הזה תמצאו באתר:"
    send_text(f"{text}\n\n{cta}\n{site_link(path, 'telegram', 'trend')}")
    send_text_to_group(f"{text}\n\n{cta}\n{site_link(path, 'whatsapp', 'trend')}")
    _mark_done("trend", now)
    print(f"[community] ✅ Trend post sent ({slug})")


EVENT_PROMPT = """You write for SHUSHU, an Israeli fashion discovery community.
Tomorrow is {name} ({hint}). Write a short heads-up message in natural casual Hebrew (2-4 lines):
tell members it is tomorrow, give one practical tip, and say that tomorrow at noon this group gets our hand-picked list first, an hour before everyone else.
Never promise discounts, sales or coupons.
Address members in plural (אתם), never feminine-only (אתן). Hebrew only, no English words except brand names. No markdown, no asterisks.
At most 1 emoji, no em dashes, no hashtags, no links. Return only the message."""


def do_event(now: datetime):
    ev = _event_tomorrow(now)
    if not ev:
        return
    text = _claude(EVENT_PROMPT.format(name=ev[0], hint=ev[1]), 200)
    send_text(text)
    send_text_to_group(text)
    _mark_done("event", now)
    print(f"[community] ✅ Event heads-up: {ev[0]}")


EVENT_LIST_PROMPT = """You write for SHUSHU, an Israeli fashion discovery community.
Today is {name} ({hint}). Write a short opening (2-3 lines) in natural casual Hebrew for our hand-picked list of items under {cap} ₪.
{early}
Never promise discounts, sales or coupons; the value is our curation and the prices.
Address members in plural (אתם). Hebrew only, no English words except brand names. No markdown, no asterisks.
At most 1 emoji, no em dashes, no hashtags, no links. Return only the opening."""


def _event_items(cap: int, now: datetime, n: int = 8) -> list[dict]:
    _load_categories()
    off = seasons.OFF_SEASON[seasons.season(now.date())]
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/products",
        headers=HEADERS,
        params={"select": "id,name,name_en,price,category_id", "is_active": "eq.true", "price": f"lte.{cap}",
                "order": "updated_at.desc", "limit": "150"},
        timeout=30,
    )
    r.raise_for_status()
    items = [p for p in r.json() if (p.get("name") or p.get("name_en")) and p.get("price")
             and _category_slugs.get(p.get("category_id") or "", "") not in off]
    random.shuffle(items)
    # Half the list from what members asked for in the warm-up poll, if they voted
    wanted = WARMUP_POLL_OPTIONS.get((tracker.load().get("warmup_poll") or {}).get("winner", ""))
    if wanted:
        top = [p for p in items if _category_roots.get(p.get("category_id") or "", "") in wanted][: n // 2]
        items = top + [p for p in items if p not in top]
    return items[:n]


# Black Friday warm-up, 20:00 Israel time (after the product slots, before the invite)
WARMUP_EVENT = "בלאק פריידיי"
WARMUP_HOUR = 20
WARMUP_STAGES = {
    14: "teaser",     # two weeks out: something is coming
    10: "poll",       # what are you waiting for (shapes the event list)
    7: "countdown",   # one week, start a wish list
    3: "prep",        # check sizes and return policy, save items
}
WARMUP_POLL_QUESTION = "מה אתם הכי מחכים למצוא בבלאק פריידיי? 🖤"
WARMUP_POLL_OPTIONS = {
    "נעליים וסניקרס": {"shoes"},
    "מעילים ובגדי חורף": {"clothing"},
    "תיקים ואקססוריז": {"bags", "accessories"},
    "שעונים ותכשיטים": {"watches", "accessories"},
}

WARMUP_PROMPT = """You write for SHUSHU, an Israeli fashion discovery community on Telegram and WhatsApp.
We are warming members up for {name}, which is in {days} days ({date}). Stage: {stage}.
Stages:
- teaser: short intriguing message that we are preparing something special for {name}: a hand-picked list of the best finds under 150 ₪, and the WhatsApp group gets it an hour before everyone.
- countdown: one week left. Suggest starting a wish list now, tell them what to expect on the day.
- prep: three days left. One practical tip (check sizes, return policy, save items in advance) and a reminder that the list lands here on the day at noon.
Write 2-4 lines in natural casual Hebrew. Never promise discounts, sales or coupons; the value is our curation and early access.
Address members in plural (אתם). Hebrew only, no English words except brand names. No markdown, no asterisks.
At most 2 emojis, no em dashes, no hashtags, no links. Return only the message."""


def _warmup_stage(now: datetime):
    for d, name, _hint, _cap in seasons._all_events(now.date()):
        if name == WARMUP_EVENT:
            days = (d - now.date()).days
            if days in WARMUP_STAGES:
                return WARMUP_STAGES[days], days, d
    return None


def do_warmup(now: datetime):
    stage = _warmup_stage(now)
    if not stage:
        return
    kind, days, day = stage
    if kind == "poll":
        options = list(WARMUP_POLL_OPTIONS)
        tg = send_poll(WARMUP_POLL_QUESTION, options)
        wa_id = send_poll_to_group(WARMUP_POLL_QUESTION, options)
        _mark_done("warmup", now, warmup_poll={
            "message_id": tg["message_id"] if tg else None, "wa_id": wa_id, "winner": "",
        })
        print("[community] ✅ Warm-up poll sent")
        return
    text = _claude(WARMUP_PROMPT.format(name=WARMUP_EVENT, days=days, date=day.strftime("%d.%m"), stage=kind), 250)
    send_text(text)
    send_text_to_group(text)
    _mark_done("warmup", now)
    print(f"[community] ✅ Warm-up ({kind}) sent")


def refresh_warmup_poll():
    """Counts the warm-up poll (WhatsApp votes) so the event list can lean toward what members want."""
    data = tracker.load()
    poll = data.get("warmup_poll") or {}
    if not poll.get("wa_id"):
        return
    votes = get_poll_votes(poll["wa_id"])
    poll["votes"] = votes
    poll["winner"] = max(votes, key=votes.get) if votes else ""
    data["warmup_poll"] = poll
    tracker.save(data)
    print(f"[community] Warm-up poll votes: {votes}")


def _event_post(now: datetime, source: str, early: bool) -> str:
    name, hint, cap = seasons.event_today(now.date())
    data = tracker.load()
    lst = data.get("event_list") or {}
    if lst.get("date") != now.date().isoformat():
        lst = {"date": now.date().isoformat(), "items": _event_items(cap, now)}
        data["event_list"] = lst
        tracker.save(data)
    early_line = ("Mention that this group gets the list an hour before everyone else."
                  if early else "")
    opening = _claude(EVENT_LIST_PROMPT.format(name=name, hint=hint, cap=cap, early=early_line), 200)
    lines = [
        f"• {p.get('name') or p.get('name_en')}, ₪{float(p['price']):.0f}\n"
        f"{site_link('/product/' + p['id'], source, 'event')}"
        for p in lst["items"]
    ]
    return f"{opening}\n\n" + "\n\n".join(lines)


def do_event_list_wa(now: datetime):
    post = _event_post(now, "whatsapp", early=True)
    send_text_to_group(post)
    _mark_done("event_list_wa", now)
    print("[community] ✅ Event list sent to WhatsApp")


def do_event_list_tg(now: datetime):
    send_text(_event_post(now, "telegram", early=False))
    _mark_done("event_list_tg", now)
    print("[community] ✅ Event list sent to Telegram")


INVITES = [
    "בטלגרם עלו היום {n} מציאות שלא שלחנו כאן 👀\nכל המוצרים, כל שעה, בערוץ:\n{link}",
    "כאן אנחנו שולחים רק את הנבחרים. את כל {n} הפריטים של היום תמצאו בערוץ הטלגרם שלנו:\n{link}",
    "מי שרוצה לראות ראשון: היום עלו בטלגרם {n} פריטים חדשים 🛍️\n{link}",
]


def do_invite(now: datetime):
    posted = tracker.load().get("posted", {})
    today = now.date().isoformat()
    n = 0
    for v in posted.values():
        ts = v.get("posted_at", "")
        if ts:
            local = datetime.fromisoformat(ts).replace(tzinfo=ZoneInfo("UTC")).astimezone(IL)
            n += local.date().isoformat() == today
    if n < 3:
        print(f"[community] Only {n} posts today, skipping invite")
        _mark_done("invite", now)
        return
    send_text_to_group(random.choice(INVITES).format(n=n, link=TELEGRAM_LINK))
    _mark_done("invite", now)
    print(f"[community] ✅ Invite sent ({n} posts today)")


# WhatsApp hides history from new members, so newcomers get a short "what happens here" once a day
WELCOMES = [
    "ברוכים הבאים לכל מי שהצטרף היום 👋\n\n"
    "מה מחכה לכם כאן:\n"
    "👗 כל בוקר ב-9:00 לוק יומי מוכן\n"
    "🛍️ במשך היום מציאות נבחרות, כל אחת עם קישור ישיר\n"
    "📊 סקרים קטנים, כדי שנביא בדיוק את מה שאתם אוהבים\n\n"
    "הקבוצה שקטה, אז רק אנחנו שולחים ואתם לא מקבלים הצפה של הודעות.\n"
    "כל הקטלוג באתר:\n{site}\n\n"
    "ומי שרוצה עוד מציאות כל שעה, יש לנו ערוץ טלגרם:\n{tg}",
    "היי למצטרפים החדשים 🖤\n\n"
    "כאן תקבלו כל יום לוק מוכן ב-9 בבוקר, מציאות אופנה שבחרנו בשבילכם וסקרים שקובעים מה נביא הלאה.\n"
    "ההודעות הקודמות לא מופיעות אצלכם, אז הכול נמצא באתר:\n{site}\n\n"
    "רוצים יותר? בערוץ הטלגרם עולה פריט חדש כל שעה:\n{tg}",
    "שלום לכל מי שהגיע היום ✨\n\n"
    "בקצרה, מה קורה פה:\n"
    "☀️ ב-9:00 הלוק של היום\n"
    "🔥 לאורך היום פריטים נבחרים במחירים שווים\n"
    "🗳️ מדי פעם סקר, ואתם מחליטים מה יעלה\n\n"
    "את כל הפריטים, גם אלה שפספסתם, תמצאו באתר:\n{site}\n\n"
    "ובטלגרם יש עוד הרבה יותר:\n{tg}",
]


def do_welcome(now: datetime):
    size = group_size()
    if not size:
        return
    data = tracker.load()
    last = data.get("wa_group_size")
    if last is None or size <= last:
        # First run sets the baseline; no growth means nobody new to greet
        data["wa_group_size"] = size
        data.setdefault("community", {})["welcome"] = now.date().isoformat()
        tracker.save(data)
        print(f"[community] No new members (size {size})")
        return
    text = random.choice(WELCOMES).format(site=site_link("/", "whatsapp", "welcome"), tg=TELEGRAM_LINK)
    if send_text_to_group(text):
        _mark_done("welcome", now, wa_group_size=size)
        print(f"[community] ✅ Welcome sent (+{size - last} members)")


ACTIONS = {"poll": do_poll, "question": do_question, "fun_poll": do_fun_poll, "trend": do_trend,
           "poll_close": do_poll_close, "invite": do_invite, "event": do_event,
           "event_list_wa": do_event_list_wa, "warmup": do_warmup, "event_list_tg": do_event_list_tg}


def run_scheduled(now: datetime | None = None):
    now = now or now_il()
    if now.hour == WELCOME_HOUR and not _done_today("welcome", now):
        try:
            do_welcome(now)
        except Exception as e:
            print(f"[community] ❌ welcome failed: {e}")
    try:
        refresh_category_pref(now)
    except Exception as e:
        print(f"[community] ❌ category refresh failed: {e}")
    action =SCHEDULE.get((now.weekday(), now.hour))
    if now.hour == INVITE_HOUR:
        action = "invite"
    if now.hour == EVENT_HOUR and _event_tomorrow(now):
        action = "event"
    if now.hour == WARMUP_HOUR and _warmup_stage(now):
        action = "warmup"
    if seasons.event_today(now.date()):
        if now.hour == EVENT_LIST_WA_HOUR and not _done_today("event_list_wa", now):
            try:
                refresh_warmup_poll()
            except Exception as e:
                print(f"[community] ❌ warm-up poll count failed: {e}")
        if now.hour == EVENT_LIST_WA_HOUR:
            action = "event_list_wa"
        elif now.hour == EVENT_LIST_TG_HOUR:
            action = "event_list_tg"
    if not action or _done_today(action, now):
        return
    try:
        ACTIONS[action](now)
    except Exception as e:
        print(f"[community] ❌ {action} failed: {e}")
