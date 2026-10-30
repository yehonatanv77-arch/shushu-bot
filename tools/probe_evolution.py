"""Dry check: why group reads fail. Prints no keys or numbers."""
import re, sys
sys.path.insert(0, ".")
import httpx
from whatsapp_poster import EVOLUTION_URL, INSTANCE, GROUP_JID, _headers
def clean(t): return re.sub(r"\d{8,}", "<num>", t)[:300]
r = httpx.get(f"{EVOLUTION_URL}/group/participants/{INSTANCE}", params={"groupJid": GROUP_JID}, headers=_headers(), timeout=30)
print("PARTICIPANTS:", r.status_code, clean(r.text))
r = httpx.get(f"{EVOLUTION_URL}/group/fetchAllGroups/{INSTANCE}", params={"getParticipants": "false"}, headers=_headers(), timeout=60)
print("GROUPS:", r.status_code, len(r.json()) if r.status_code == 200 else clean(r.text))
