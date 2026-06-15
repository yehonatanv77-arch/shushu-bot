"""
Tracks posted products to prevent duplicates.
Stored in posted_products.json — committed back to the repo by GitHub Actions.
"""

import json
import os
import time
from datetime import datetime

TRACKER_FILE = "posted_products.json"
LOCK_FILE = "posted_products.lock"
LOCK_TIMEOUT = 60  # seconds


def _acquire_lock():
    """Spin-wait for the lock file, then claim it."""
    deadline = time.time() + LOCK_TIMEOUT
    while time.time() < deadline:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            # Check if the lock is stale (older than LOCK_TIMEOUT seconds)
            try:
                age = time.time() - os.path.getmtime(LOCK_FILE)
                if age > LOCK_TIMEOUT:
                    os.remove(LOCK_FILE)
                    continue
            except OSError:
                pass
            time.sleep(2)
    print("[tracker] WARNING: Could not acquire lock — proceeding anyway")
    return False


def _release_lock():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def load() -> dict:
    if not os.path.exists(TRACKER_FILE):
        return {"posted": {}}
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[tracker] ERROR reading tracker, resetting: {e}")
        return {"posted": {}}


def save(data: dict):
    # Write to temp file first, then rename — prevents partial writes
    tmp = TRACKER_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRACKER_FILE)


def is_posted(product_id: str) -> bool:
    data = load()
    return product_id in data.get("posted", {})


def mark_posted(product_id: str, product_url: str, lastmod: str, message_ids: list):
    _acquire_lock()
    try:
        data = load()  # re-read inside lock to get latest state
        data.setdefault("posted", {})[product_id] = {
            "url": product_url,
            "lastmod": lastmod,
            "posted_at": datetime.utcnow().isoformat(),
            "telegram_message_ids": message_ids,
        }
        save(data)
    finally:
        _release_lock()


def needs_repost(product_id: str, new_lastmod: str) -> bool:
    """True if product was posted before but has been updated since."""
    data = load()
    entry = data.get("posted", {}).get(product_id)
    if not entry:
        return False
    return entry.get("lastmod", "") != new_lastmod
