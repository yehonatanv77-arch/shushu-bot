import sys
sys.stdout.reconfigure(encoding="utf-8")
import json
import community
from community import _claude, _context, _seasonal_products, now_il, FUN_POLL_PROMPT, TREND_PROMPT

now = now_il()
print("CONTEXT", _context(now))
for _ in range(2):
    print("FUN POLL", _claude(FUN_POLL_PROMPT.format(context=_context(now), recent="none"), 200))
ps = _seasonal_products(now)
names = [p.get("name") or p.get("name_en") for p in ps]
print("TREND", _claude(TREND_PROMPT.format(context=_context(now), products="\n".join(f"- {n}" for n in names))))
