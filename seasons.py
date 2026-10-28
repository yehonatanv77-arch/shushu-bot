"""
Season and shopping-event calendar (Israel).
Feeds the product picker (seasonal boost), the Sunday trend post and event heads-ups.
"""

from datetime import date

# Leaf or root category slugs that fit each season
SEASON_SLUGS = {
    "winter": {"jackets", "boots", "hoodies", "sweatshirts", "sweaters-and-knitwear", "scarves",
               "hats", "pants", "loafers", "slippers", "vests"},
    "spring": {"sneakers", "shirts", "dresses", "skirts", "crossbody-bags", "glasses", "loafers",
               "ballerina-and-mary-jane-shoes", "sweatshirts"},
    "summer": {"sandals", "slides", "swimwear", "shorts", "tank-tops", "glasses", "hats",
               "basket-and-straw-bags", "dresses", "water-bottles"},
    "autumn": {"jackets", "boots", "sneakers", "hoodies", "sweatshirts", "pants",
               "sweaters-and-knitwear", "backpacks"},
}

SEASON_HE = {"winter": "חורף", "spring": "אביב", "summer": "קיץ", "autumn": "סתיו"}

# Our supplier gives no coupons, so events are framed around curated lists, never discounts.
# Fixed-date events: (month, day, name, hint for the copy, price cap for the event list in ILS)
EVENTS = [
    (11, 11, "11.11", "יום קניות גדול ברשת, הזדמנות להתחדש לחורף", 150),
    (2, 14, "ולנטיין", "רעיונות למתנה לבן או בת הזוג", 250),
]

# Events that move every year (Jewish holidays, Black Friday). Add the next year when it gets close.
DATED_EVENTS = [
    (date(2026, 11, 27), "בלאק פריידיי", "יום הקניות הגדול של השנה, הזמן להשלים את הארון לחורף", 150),
    (date(2026, 12, 4), "חנוכה", "מתנות קטנות ושוות לחנוכה", 150),
    (date(2027, 4, 21), "פסח", "לוקים לחג והתחדשות לאביב", 200),
    (date(2027, 10, 1), "ראש השנה", "לוק לחג ומתנות לשנה החדשה", 200),
    (date(2027, 11, 26), "בלאק פריידיי", "יום הקניות הגדול של השנה, הזמן להשלים את הארון לחורף", 150),
]


def season(today: date) -> str:
    m = today.month
    if m in (12, 1, 2):
        return "winter"
    if m in (3, 4, 5):
        return "spring"
    if m in (6, 7, 8, 9):
        return "summer"
    return "autumn"


def _all_events(today: date):
    out = list(DATED_EVENTS)
    for month, day, name, hint, cap in EVENTS:
        d = date(today.year, month, day)
        out.append((d if d >= today else date(today.year + 1, month, day), name, hint, cap))
    return out


def upcoming_event(today: date, days: int = 7):
    """Returns (name, hint, days_left) for the nearest event within `days`, else None."""
    best = None
    for d, name, hint, _ in _all_events(today):
        left = (d - today).days
        if 0 <= left <= days and (best is None or left < best[2]):
            best = (name, hint, left)
    return best


def event_today(today: date):
    """Returns (name, hint, price_cap) if an event is today, else None."""
    for d, name, hint, cap in _all_events(today):
        if d == today:
            return name, hint, cap
    return None
