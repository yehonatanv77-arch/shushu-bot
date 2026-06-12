"""
Tracks posted products to prevent duplicates.
Stored in posted_products.json — committed back to the repo by GitHub Actions.
"""

import json
import os
from datetime import datetime

TRACKER_FILE = "posted_products.json"


def load() -> dict:
    if not os.path.exists(TRACKER_FILE):
        return {"posted": {}}
    with open(TRACKER_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save(data: dict):
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_posted(product_id: str) -> bool:
    data = load()
    return product_id in data.get("posted", {})


def mark_posted(product_id: str, product_url: str, lastmod: str, message_ids: list):
    data = load()
    data.setdefault("posted", {})[product_id] = {
        "url": product_url,
        "lastmod": lastmod,
        "posted_at": datetime.utcnow().isoformat(),
        "telegram_message_ids": message_ids,
    }
    save(data)


def needs_repost(product_id: str, new_lastmod: str) -> bool:
    """True if product was posted before but has been updated since."""
    data = load()
    entry = data.get("posted", {}).get(product_id)
    if not entry:
        return False
    return entry.get("lastmod", "") != new_lastmod
