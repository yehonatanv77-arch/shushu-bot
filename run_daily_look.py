import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from bot import do_daily_look
import community
if community.now_il().hour >= 9:
    do_daily_look()
else:
    print('[look] Before 09:00 IL, skipping')
