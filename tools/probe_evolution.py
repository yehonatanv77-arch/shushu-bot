import os, json, collections, httpx
U=os.environ["EVOLUTION_API_URL"].rstrip("/"); H={"apikey":os.environ["EVOLUTION_API_KEY"]}
I=os.environ["EVOLUTION_INSTANCE"]; G=os.environ["WHATSAPP_GROUP_JID"]
r=httpx.get(U+"/",headers=H,timeout=20); print("root",r.status_code,r.text[:300])
r=httpx.post(f"{U}/chat/findMessages/{I}",headers=H,json={"where":{"key":{"remoteJid":G}},"limit":100},timeout=30)
print("findMessages",r.status_code)
d=r.json(); recs=d.get("messages",{}).get("records",d) if isinstance(d,dict) else d
recs=recs if isinstance(recs,list) else []
print("count",len(recs), collections.Counter(m.get("messageType") for m in recs))
for m in recs:
    if "poll" in str(m.get("messageType","")).lower():
        print(json.dumps({k:m.get(k) for k in ("messageType","key","message","pollUpdates")},ensure_ascii=False)[:800])
for p in ("/chat/getPollVote/","/message/getPollVote/"):
    r=httpx.post(U+p+I,headers=H,json={},timeout=20); print(p,r.status_code,r.text[:150])
