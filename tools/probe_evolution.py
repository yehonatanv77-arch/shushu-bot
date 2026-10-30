"""Dry check: WhatsApp connection + group read. Prints no keys or numbers."""
import re, sys
sys.path.insert(0, ".")
import os
os.environ["WHATSAPP_PAUSED"] = "0"
import httpx
from whatsapp_poster import EVOLUTION_URL, INSTANCE, GROUP_JID, _headers
def clean(t): return re.sub(r"\d{8,}", "<num>", t)[:200]
r = httpx.get(f"{EVOLUTION_URL}/instance/connectionState/{INSTANCE}", headers=_headers(), timeout=30)
print("STATE:", r.status_code, clean(r.text))
r = httpx.get(f"{EVOLUTION_URL}/group/participants/{INSTANCE}", params={"groupJid": GROUP_JID}, headers=_headers(), timeout=30)
print("PARTICIPANTS:", r.status_code, len(r.json().get("participants", [])) if r.status_code == 200 else clean(r.text))
