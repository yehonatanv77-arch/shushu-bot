import sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime
import community
from community import IL, _warmup_stage, _claude, WARMUP_PROMPT, WARMUP_EVENT

# Dry run of the warm-up texts (nothing is sent)
for d in [13, 17, 20, 24]:
    now = datetime(2026, 11, d, 20, tzinfo=IL)
    st = _warmup_stage(now)
    print(f"===== 2026-11-{d}: {st and st[0]}")
    if st and st[0] != "poll":
        print(_claude(WARMUP_PROMPT.format(name=WARMUP_EVENT, days=st[1], date=st[2].strftime("%d.%m"), stage=st[0]), 250))
    elif st:
        print(community.WARMUP_POLL_QUESTION, list(community.WARMUP_POLL_OPTIONS))
