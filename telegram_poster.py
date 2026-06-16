"""
Posts content to Telegram channel.
"""

import httpx
import os
from typing import Optional


BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def _buy_button(url: str) -> dict:
    """Inline keyboard with a single purchase button."""
    return {"inline_keyboard": [[{"text": "🛍️ לרכישה ישירה", "url": url}]]}


def _is_image_accessible(url: str) -> bool:
    try:
        with httpx.Client(timeout=5) as client:
            r = client.head(url)
            return r.status_code == 200
    except Exception:
        return False


def _sanitize(text: str) -> str:
    """Escape HTML special chars so parse_mode HTML never rejects the message."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_photo(image_url: str, caption: str, buy_url: str = "") -> Optional[dict]:
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": image_url,
        "caption": _sanitize(caption),
    }
    if buy_url:
        payload["reply_markup"] = _buy_button(buy_url)

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{BASE}/sendPhoto", json=payload)
    data = resp.json()
    if not data.get("ok"):
        print(f"[telegram] sendPhoto error: {data}")
        return None
    return data["result"]


def send_media_group(image_urls: list[str], caption: str, buy_url: str = "") -> Optional[list]:
    """Sends multiple images. Caption + button on first image."""
    valid_urls = [u for u in image_urls[:5] if _is_image_accessible(u)]

    if not valid_urls:
        print(f"[telegram] No accessible images from {len(image_urls)} candidates")
        return None

    if len(valid_urls) == 1:
        return send_photo(valid_urls[0], caption, buy_url)

    # Send media group — Telegram doesn't support inline_keyboard on media groups
    # so we send a follow-up message with the buy button
    media = []
    for i, url in enumerate(valid_urls):
        item = {"type": "photo", "media": url}
        if i == 0:
            item["caption"] = _sanitize(caption)
        media.append(item)

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{BASE}/sendMediaGroup", json={
            "chat_id": CHANNEL_ID,
            "media": media,
        })
    data = resp.json()
    if not data.get("ok"):
        print(f"[telegram] sendMediaGroup error: {data}")
        return None

    if buy_url:
        with httpx.Client(timeout=30) as client:
            client.post(f"{BASE}/sendMessage", json={
                "chat_id": CHANNEL_ID,
                "text": "👆 לפרטים ורכישה:",
                "reply_markup": _buy_button(buy_url),
            })

    return data["result"]


def send_text(text: str, buy_url: str = "") -> Optional[dict]:
    payload = {
        "chat_id": CHANNEL_ID,
        "text": _sanitize(text),
        "disable_web_page_preview": False,
    }
    if buy_url:
        payload["reply_markup"] = _buy_button(buy_url)

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{BASE}/sendMessage", json=payload)
    data = resp.json()
    if not data.get("ok"):
        print(f"[telegram] sendMessage error: {data}")
        return None
    return data["result"]


def post_product(images: list[str], caption: str, buy_url: str = "") -> bool:
    """Posts product to Telegram with buy button. Returns True on success."""
    if len(images) >= 2:
        result = send_media_group(images, caption, buy_url)
    elif len(images) == 1:
        result = send_photo(images[0], caption, buy_url)
    else:
        result = send_text(caption, buy_url)

    return result is not None
