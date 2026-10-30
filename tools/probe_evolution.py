"""Dry check: WhatsApp connection state. Prints no keys or numbers."""
import sys
sys.path.insert(0, ".")
import httpx
from whatsapp_poster import EVOLUTION_URL, INSTANCE, _headers
r = httpx.get(f"{EVOLUTION_URL}/instance/connectionState/{INSTANCE}", headers=_headers(), timeout=30)
print("STATE:", r.status_code, r.text[:200])
