"""Read-only AliExpress check: sale lists + one full post preview. Sends nothing to any group."""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import aliexpress
import ali_post

for name in aliexpress.SALE_LISTS:
    items = aliexpress.featured(name)
    print(f"LIST {name}: {len(items)} items")
    for i in items[:3]:
        print(f"  - {i['title'][:70]} | ₪{i['price']} | under ₪{ali_post._under(i['price'])} | {i['orders']} orders")

post = ali_post.make_post()
print("\nPREVIEW:\n" + (post["text"] if post else "(no deal found)"))
