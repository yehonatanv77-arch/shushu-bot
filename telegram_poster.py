"""
Posts content to Telegram channel.
"""

import httpx
import os
from typing import Optional


BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_photo(image_url: str, caption: str) -> Optional[dict]:
    """Sends a single photo with caption."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{BASE}/sendPhoto", json={
            "chat_id": CHANNEL_ID,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
        })
    data = resp.json()
    if not data.get("ok"):
        print(f"[telegram] sendPhoto error: {data}")
        return None
    return data["result"]


def send_media_group(image_urls: list[str], caption: str) -> Optional[list]:
    """Sends multiple images as a media group. Caption goes on first image."""
    media = []
    for i, url in enumerate(image_urls[:5]):
        item = {"type": "photo", "media": url}
        if i == 0:
            item["caption"] = caption
            item["parse_mode"] = "HTML"
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
    return data["result"]


def send_text(text: str) -> Optional[dict]:
    """Sends a plain text message (fallback when no images)."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{BASE}/sendMessage", json={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        })
    data = resp.json()
    if not data.get("ok"):
        print(f"[telegram] sendMessage error: {data}")
        return None
    return data["result"]


def post_product(images: list[str], caption: str) -> bool:
    """Posts product to Telegram. Returns True on success."""
    result = None

    if len(images) >= 2:
        result = send_media_group(images, caption)
    elif len(images) == 1:
        result = send_photo(images[0], caption)
    else:
        # No images — skip (brand rule: never post without image)
        print("[telegram] Skipping post — no images available")
        return False

    return result is not None
