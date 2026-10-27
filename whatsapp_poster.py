"""
Posts to SHUSHU WhatsApp group via Evolution API (self-hosted).
Runs alongside Telegram — same content, same timing.
"""

import os
import requests

EVOLUTION_URL = os.environ.get("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_KEY = os.environ.get("EVOLUTION_API_KEY", "")
INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "default")
GROUP_JID = os.environ.get("WHATSAPP_GROUP_JID", "")


def _headers() -> dict:
    return {"apikey": EVOLUTION_KEY, "Content-Type": "application/json"}


def send_text_to_group(text: str) -> bool:
    """Sends a plain text message to the WhatsApp group."""
    if not all([EVOLUTION_URL, EVOLUTION_KEY, GROUP_JID]):
        print("[whatsapp] Missing config — skipping")
        return False

    url = f"{EVOLUTION_URL}/message/sendText/{INSTANCE}"
    payload = {
        "number": GROUP_JID,
        "text": text,
    }
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=15)
        if resp.status_code in (200, 201):
            print("[whatsapp] ✅ Sent to group")
            return True
        print(f"[whatsapp] ❌ Error {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"[whatsapp] ❌ Exception: {e}")
        return False


def send_image_to_group(image_url: str, caption: str) -> bool:
    """Sends an image with caption to the WhatsApp group."""
    if not all([EVOLUTION_URL, EVOLUTION_KEY, GROUP_JID]):
        print("[whatsapp] Missing config — skipping")
        return False

    url = f"{EVOLUTION_URL}/message/sendMedia/{INSTANCE}"
    payload = {
        "number": GROUP_JID,
        "mediatype": "image",
        "media": image_url,
        "caption": caption,
    }
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=15)
        if resp.status_code in (200, 201):
            print("[whatsapp] ✅ Image sent to group")
            return True
        print(f"[whatsapp] ❌ Error {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"[whatsapp] ❌ Exception: {e}")
        return False


def post_product_to_whatsapp(images: list, text: str, buy_url: str = "") -> bool:
    """Posts a product to WhatsApp — image + text + buy link."""
    # Append buy link to text for WhatsApp (no inline buttons like Telegram)
    full_text = text
    if buy_url:
        full_text = f"{text}\n\n🛍️ לרכישה: {buy_url}"

    if images:
        return send_image_to_group(images[0], full_text)
    return send_text_to_group(full_text)
