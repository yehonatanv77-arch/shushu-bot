import os, sys, json, collections, httpx
U=os.environ["EVOLUTION_API_URL"].rstrip("/"); H={"apikey":os.environ["EVOLUTION_API_KEY"]}
I=os.environ["EVOLUTION_INSTANCE"]
inst=[x for x in httpx.get(U+"/instance/fetchInstances",headers=H,timeout=20).json() if x.get("name")==I][0]
own=inst.get("ownerJid"); print("owner set:",bool(own))
mode=sys.argv[1] if len(sys.argv)>1 else "read"
if mode=="send":
    r=httpx.post(f"{U}/message/sendPoll/{I}",headers=H,json={"number":own.split("@")[0],"name":"בדיקת סקר SHUSHU","selectableCount":1,"values":["אפשרות א","אפשרות ב","אפשרות ג"]},timeout=30)
    print("sendPoll",r.status_code)
r=httpx.post(f"{U}/chat/findMessages/{I}",headers=H,json={"where":{"key":{"remoteJid":own}},"limit":50},timeout=30)
d=r.json(); recs=d.get("messages",{}).get("records",[]) if isinstance(d,dict) else d
print("count",len(recs), collections.Counter(m.get("messageType") for m in recs))
for m in recs:
    if "poll" in str(m.get("messageType","")).lower():
        m=dict(m); m.pop("key",None); m.pop("instanceId",None)
        print(json.dumps(m,ensure_ascii=False)[:1500])
