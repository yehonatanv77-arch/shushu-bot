"""
Posts to SHUSHU WhatsApp group via Evolution API (self-hosted).
Runs alongside Telegram — same content, same timing.
"""

import os
import httpx

EVOLUTION_URL = os.environ.get("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_KEY = os.environ.get("EVOLUTION_API_KEY", "")
INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "default")
GROUP_JID = os.environ.get("WHATSAPP_GROUP_JID", "")


def _headers() -> dict:
    return {"apikey": EVOLUTION_KEY, "Content-Type": "application/json"}


def _discover_instance() -> str:
    """Returns the name of a connected instance on the server, or ''."""
    try:
        resp = httpx.get(f"{EVOLUTION_URL}/instance/fetchInstances", headers=_headers(), timeout=15)
        items = resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f"[whatsapp] Instance discovery failed: {e}")
        return ""
    names = []
    for item in items if isinstance(items, list) else []:
        inst = item.get("instance", item)
        name = inst.get("instanceName") or inst.get("name") or ""
        status = inst.get("connectionStatus") or inst.get("status") or inst.get("state") or ""
        if name:
            names.append((name, status))
    print(f"[whatsapp] Configured instance not found. Instances on server: {names}")
    return ""


def _post(endpoint: str, payload: dict) -> httpx.Response:
    resp = httpx.post(f"{EVOLUTION_URL}/message/{endpoint}/{INSTANCE}", json=payload, headers=_headers(), timeout=30)
    if resp.status_code == 404 and "instance does not exist" in resp.text:
        _discover_instance()
    return resp


def send_text_to_group(text: str) -> bool:
    """Sends a plain text message to the WhatsApp group."""
    if not all([EVOLUTION_URL, EVOLUTION_KEY, GROUP_JID]):
        print("[whatsapp] Missing config — skipping")
        return False

    payload = {
        "number": GROUP_JID,
        "text": text,
    }
    try:
        resp = _post("sendText", payload)
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

    payload = {
        "number": GROUP_JID,
        "mediatype": "image",
        "media": image_url,
        "caption": caption,
    }
    try:
        resp = _post("sendMedia", payload)
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


def group_size() -> int:
    """Number of members in the group (0 on failure). Never logs who they are."""
    if not all([EVOLUTION_URL, EVOLUTION_KEY, GROUP_JID]):
        return 0
    try:
        resp = httpx.get(f"{EVOLUTION_URL}/group/participants/{INSTANCE}", params={"groupJid": GROUP_JID},
                         headers=_headers(), timeout=30)
        if resp.status_code != 200:
            print(f"[whatsapp] ❌ Participants error {resp.status_code}")
            return 0
        return len(resp.json().get("participants", []))
    except Exception as e:
        print(f"[whatsapp] ❌ Participants exception: {e}")
        return 0


def send_poll_to_group(question: str, options: list[str]) -> str:
    """Sends a poll; returns its message id ('' on failure)."""
    if not all([EVOLUTION_URL, EVOLUTION_KEY, GROUP_JID]):
        print("[whatsapp] Missing config — skipping")
        return ""
    payload = {"number": GROUP_JID, "name": question, "selectableCount": 1, "values": options}
    try:
        resp = _post("sendPoll", payload)
        if resp.status_code in (200, 201):
            print("[whatsapp] ✅ Poll sent to group")
            return resp.json().get("key", {}).get("id", "") or "sent"
        print(f"[whatsapp] ❌ Error {resp.status_code}: {resp.text[:200]}")
        return ""
    except Exception as e:
        print(f"[whatsapp] ❌ Exception: {e}")
        return ""


def find_poll_id(question: str, max_pages: int = 10) -> str:
    """Finds the id of the newest group poll with this question ('' if not found)."""
    for page in range(1, max_pages + 1):
        try:
            resp = httpx.post(
                f"{EVOLUTION_URL}/chat/findMessages/{INSTANCE}",
                headers=_headers(),
                json={"where": {"key": {"remoteJid": GROUP_JID}}, "page": page, "offset": 100},
                timeout=30,
            )
            block = resp.json().get("messages", {})
        except Exception as e:
            print(f"[whatsapp] Poll lookup failed: {e}")
            return ""
        records = block.get("records", [])
        for m in records:
            msg = m.get("message") or {}
            poll = msg.get("pollCreationMessageV3") or msg.get("pollCreationMessage") or {}
            if poll.get("name") == question:
                return (m.get("key") or {}).get("id", "")
        if page >= int(block.get("pages") or 1) or not records:
            break
    return ""


def get_poll_votes(poll_id: str, max_pages: int = 10) -> dict:
    """Counts votes for a group poll: each voter's latest choice wins."""
    latest = {}
    for page in range(1, max_pages + 1):
        try:
            resp = httpx.post(
                f"{EVOLUTION_URL}/chat/findMessages/{INSTANCE}",
                headers=_headers(),
                json={"where": {"key": {"remoteJid": GROUP_JID}}, "page": page, "offset": 100},
                timeout=30,
            )
            data = resp.json()
        except Exception as e:
            print(f"[whatsapp] Vote fetch failed: {e}")
            break
        block = data.get("messages", {}) if isinstance(data, dict) else {}
        records = block.get("records", [])
        for m in records:
            upd = (m.get("message") or {}).get("pollUpdateMessage")
            if not upd or upd.get("pollCreationMessageKey", {}).get("id") != poll_id:
                continue
            key = m.get("key") or {}
            voter = key.get("participant") or key.get("participantAlt") or key.get("remoteJid")
            ts = int(m.get("messageTimestamp") or 0)
            if voter not in latest or ts >= latest[voter][0]:
                latest[voter] = (ts, upd.get("vote", {}).get("selectedOptions", []))
        if page >= int(block.get("pages") or 1) or not records:
            break
    counts = {}
    for _, options in latest.values():
        for o in options:
            counts[o] = counts.get(o, 0) + 1
    return counts
