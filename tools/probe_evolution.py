import sys
sys.stdout.reconfigure(encoding="utf-8")
import aliexpress
raw = aliexpress._call("aliexpress.affiliate.category.get")
cats = raw["aliexpress_affiliate_category_get_response"]["resp_result"]["result"]["categories"]["category"]
for c in cats:
    print("CAT", c.get("category_id"), c.get("parent_category_id", "-"), c.get("category_name"))
