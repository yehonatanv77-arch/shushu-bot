import os, re, json, collections, httpx
U=os.environ["EVOLUTION_API_URL"].rstrip("/"); H={"apikey":os.environ["EVOLUTION_API_KEY"]}
I=os.environ["EVOLUTION_INSTANCE"]; G=os.environ["WHATSAPP_GROUP_JID"]
def red(s): return re.sub(r"\d{8,}", "<num>", s)
r=httpx.post(f"{U}/chat/findMessages/{I}",headers=H,json={"where":{"key":{"remoteJid":G}},"limit":100},timeout=30)
d=r.json(); recs=d.get("messages",{}).get("records",[]) if isinstance(d,dict) else d
print("count",len(recs), collections.Counter(m.get("messageType") for m in recs))
for m in recs:
    if "poll" in str(m.get("messageType","")).lower():
        print("FIELDS", list(m.keys()))
        print("UPDATES", red(json.dumps(m.get("MessageUpdate"),ensure_ascii=False))[:1500])
        print("MSG", red(json.dumps(m.get("message"),ensure_ascii=False))[:1200])
