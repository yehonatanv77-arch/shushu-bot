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

# Fixed-date events: (month, day, name, hint for the copy)
EVENTS = [
    (11, 11, "11.11", "יום הקניות הגדול של השנה באתרים הסיניים, הנחות חזקות לכמה שעות"),
    (2, 14, "ולנטיין", "רעיונות למתנה לבן או בת הזוג"),
]

# Events that move every year (Jewish holidays, Black Friday). Add the next year when it gets close.
DATED_EVENTS = [
    (date(2026, 11, 27), "בלאק פריידיי", "הנחות גדולות בכל האתרים, כדאי להכין רשימה מראש"),
    (date(2026, 11, 30), "סייבר מאנדיי", "הזדמנות אחרונה למבצעי בלאק פריידיי"),
    (date(2026, 12, 4), "חנוכה", "מתנות קטנות ושוות לחנוכה"),
    (date(2027, 4, 21), "פסח", "לוקים לחג והתחדשות לאביב"),
    (date(2027, 10, 1), "ראש השנה", "לוק לחג ומתנות לשנה החדשה"),
    (date(2027, 11, 26), "בלאק פריידיי", "הנחות גדולות בכל האתרים, כדאי להכין רשימה מראש"),
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


def upcoming_event(today: date, days: int = 7):
    """Returns (name, hint, days_left) for the nearest event within `days`, else None."""
    best = None
    candidates = list(DATED_EVENTS)
    for month, day, name, hint in EVENTS:
        d = date(today.year, month, day)
        candidates.append((d if d >= today else date(today.year + 1, month, day), name, hint))
    for d, name, hint in candidates:
        left = (d - today).days
        if left < 0:
            continue
        if left <= days and (best is None or left < best[2]):
            best = (name, hint, left)
    return best
