import os, httpx
from whatsapp_poster import get_poll_votes, EVOLUTION_URL, INSTANCE, GROUP_JID, _headers
d=httpx.post(f"{EVOLUTION_URL}/chat/findMessages/{INSTANCE}",headers=_headers(),json={"where":{"key":{"remoteJid":GROUP_JID}},"limit":100},timeout=30).json()
for m in d["messages"]["records"]:
    if m.get("messageType")=="pollCreationMessageV3":
        print("POLL", m["message"]["pollCreationMessageV3"]["name"], "VOTES", get_poll_votes(m["key"]["id"]))
