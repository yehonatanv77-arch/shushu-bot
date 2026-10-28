import sys
sys.stdout.reconfigure(encoding="utf-8")
import aliexpress

# Dry run: search a few fashion keywords, print results only (nothing is posted)
raw = aliexpress._call("aliexpress.affiliate.product.query", keywords="women winter coat", page_size=5,
                       target_currency="ILS", target_language="HE", ship_to_country="IL",
                       tracking_id=aliexpress.TRACKING_ID)
resp = raw.get("aliexpress_affiliate_product_query_response", {}).get("resp_result", {})
print("RESP", resp.get("resp_code"), resp.get("resp_msg"), str(raw.get("error_response", ""))[:200])
for kw in ["women winter coat", "knit sweater women", "crossbody bag women", "chunky boots women"]:
    items = aliexpress.search(kw)
    print(f"KW {kw}: {len(items)} clean")
    for it in items[:3]:
        print(f"ITEM {it['title'][:80]} | ₪{it['price']} (was ₪{it['original_price']}, {it['discount']}) | {it['rating']}% | {it['orders']} orders")
