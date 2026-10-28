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
APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY", "")
APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET", "")
TRACKING_ID = os.environ.get("ALIEXPRESS_TRACKING_ID", "") or "default"

MIN_RATING = 95.0  # positive feedback %, roughly 4.7+ stars
MIN_ORDERS = 300

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
    params = {
        "app_key": APP_KEY,
        "method": method,
        "sign_method": "sha256",
        "timestamp": str(int(time.time() * 1000)),
        **{k: str(v) for k, v in biz.items()},
    }
    params["sign"] = _sign(params)
    r = httpx.post(API, data=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _rating(p: dict) -> float:
    try:
        return float(str(p.get("evaluate_rate", "0")).rstrip("%"))
    except ValueError:
        return 0.0


def search(keywords: str, page_size: int = 50) -> list[dict]:
    """Returns clean, well-rated items for the keywords, best sellers first."""
    if not (APP_KEY and APP_SECRET):
        print("[ali] Missing config, skipping")
        return []
    data = _call(
        "aliexpress.affiliate.product.query",
        keywords=keywords,
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
