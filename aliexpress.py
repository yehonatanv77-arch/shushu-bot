"""
AliExpress affiliate API (Open Platform, /sync endpoint).
Finds well-rated, no-brand fashion items and returns affiliate links.
"""

import hashlib
import hmac
import os
import re
import time

import httpx

API = "https://api-sg.aliexpress.com/sync"
APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY", "").strip()
APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET", "").strip()
TRACKING_ID = os.environ.get("ALIEXPRESS_TRACKING_ID", "").strip() or "default"

MIN_RATING = 95.0  # positive feedback %, roughly 4.7+ stars
MIN_ORDERS = 300

# Fashion searches per season: (AliExpress category id, keywords, what it is in Hebrew)
SEASON_QUERIES = {
    "autumn": [
        ("200000796", "women jacket", "ז'קט לנשים"), ("200000795", "men jacket", "ז'קט לגברים"),
        ("200000373", "women knit sweater", "סוודר לנשים"), ("201236604", "men knit sweater", "סוודר לגברים"),
        ("200000348", "women oversized hoodie", "קפוצ'ון לנשים"), ("200000344", "men hoodie", "קפוצ'ון לגברים"),
        ("200133142", "women ankle boots", "מגפונים לנשים"), ("200131145", "men leather boots", "מגפיים לגברים"),
        ("201336907", "women shoulder bag", "תיק לנשים"), ("200000399", "women scarf", "צעיף"),
        ("1509", "women gold earrings", "עגילים"), ("200000366", "women wide leg pants", "מכנסיים רחבים"),
    ],
    "winter": [
        ("200000796", "women wool coat", "מעיל לנשים"), ("200000795", "men winter jacket", "מעיל לגברים"),
        ("200128142", "women puffer jacket", "פוך לנשים"), ("200000373", "women knit sweater", "סוודר לנשים"),
        ("201236604", "men knit sweater", "סוודר לגברים"), ("200133142", "women boots", "מגפיים לנשים"),
        ("200131145", "men boots", "מגפיים לגברים"), ("200000399", "women scarf", "צעיף"),
        ("200000402", "beanie hat", "כובע גרב"), ("201336907", "women shoulder bag", "תיק לנשים"),
        ("1509", "women gold jewelry", "תכשיטים"),
    ],
    "spring": [
        ("200000347", "women midi dress", "שמלה"), ("201303001", "women blouse", "חולצה לנשים"),
        ("202235806", "men linen shirt", "חולצה לגברים"), ("200133142", "women loafers", "לופרים לנשים"),
        ("201336907", "women shoulder bag", "תיק לנשים"), ("200000440", "sunglasses", "משקפי שמש"),
        ("1509", "women gold jewelry", "תכשיטים"), ("200000366", "women wide leg pants", "מכנסיים רחבים"),
    ],
    "summer": [
        ("200000347", "women summer dress", "שמלת קיץ"), ("200000778", "women crop top", "טופ"),
        ("200000779", "men t-shirt oversized", "טישרט לגברים"), ("200000367", "women linen shorts", "שורטס"),
        ("200133142", "women sandals", "סנדלים"), ("201296801", "straw beach bag", "תיק חוף"),
        ("200000440", "sunglasses", "משקפי שמש"), ("1509", "women gold jewelry", "תכשיטים"),
    ],
}

# Never surface knockoffs of real brands
BRAND_WORDS = re.compile(
    r"balenciaga|gucci|prada|chanel|dior|louis|vuitton|lv\b|hermes|fendi|versace|celine|loewe|"
    r"miu ?miu|nike|adidas|jordan|yeezy|new balance|rolex|cartier|ralph|lacoste|moncler|"
    r"burberry|givenchy|valentino|bottega|ysl|saint laurent|goyard|north face|stone island|"
    r"style of|inspired|replica|copy|dupe|logo",
    re.IGNORECASE,
)


def _sign(params: dict) -> str:
    base = "".join(f"{k}{params[k]}" for k in sorted(params))
    return hmac.new(APP_SECRET.encode(), base.encode(), hashlib.sha256).hexdigest().upper()


def _call(method: str, **biz) -> dict:
    # Same layout as the official IOP SDK: system params in the URL, business params in the body
    sys_params = {
        "app_key": APP_KEY,
        "method": method,
        "sign_method": "sha256",
        "timestamp": str(int(time.time() * 1000)),
        "partner_id": "iop-sdk-python-20220609",
        "simplify": "false",
        "format": "json",
    }
    biz = {k: str(v) for k, v in biz.items()}
    sys_params["sign"] = _sign({**sys_params, **biz})
    r = httpx.post(API, params=sys_params, data=biz, timeout=30)
    r.raise_for_status()
    return r.json()


def _rating(p: dict) -> float:
    try:
        return float(str(p.get("evaluate_rate", "0")).rstrip("%"))
    except ValueError:
        return 0.0


def search(keywords: str, category_id: str = "", page_size: int = 50) -> list[dict]:
    """Returns clean, well-rated items for the keywords, best sellers first."""
    if not (APP_KEY and APP_SECRET):
        print("[ali] Missing config, skipping")
        return []
    data = _call(
        "aliexpress.affiliate.product.query",
        keywords=keywords,
        **({"category_ids": category_id} if category_id else {}),
        page_size=page_size,
        sort="LAST_VOLUME_DESC",
        target_currency="ILS",
        target_language="HE",
        ship_to_country="IL",
        tracking_id=TRACKING_ID,
    )
    resp = data.get("aliexpress_affiliate_product_query_response", {}).get("resp_result", {})
    if str(resp.get("resp_code")) != "200":
        print(f"[ali] API error: {resp.get('resp_code')} {resp.get('resp_msg')} {str(data.get('error_response', ''))[:200]}")
        return []
    products = (resp.get("result") or {}).get("products", {}).get("product", [])
    clean = []
    for p in products:
        title = p.get("product_title", "")
        if BRAND_WORDS.search(title):
            continue
        if _rating(p) < MIN_RATING or int(p.get("lastest_volume") or 0) < MIN_ORDERS:
            continue
        if not p.get("promotion_link"):
            continue
        clean.append({
            "id": str(p.get("product_id")),
            "title": title,
            "price": p.get("target_sale_price"),
            "original_price": p.get("target_original_price"),
            "discount": p.get("discount"),
            "rating": _rating(p),
            "orders": int(p.get("lastest_volume") or 0),
            "image": p.get("product_main_image_url"),
            "link": p["promotion_link"],
        })
    return clean
