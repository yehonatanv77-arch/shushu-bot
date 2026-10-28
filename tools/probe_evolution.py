import sys
sys.stdout.reconfigure(encoding="utf-8")
import aliexpress
for cat, kw in [("200131145", "men leather boots"), ("200000795", "men jacket")]:
    for it in aliexpress.search(kw, cat)[:4]:
        print("LINKCHK", it["id"], it["link"])
