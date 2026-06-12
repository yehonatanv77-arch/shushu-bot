"""
SHUSHU Telegram Bot — Main Orchestrator
Posts 1 product per hour via GitHub Actions cron.
Every ARTICLE_EVERY_N_RUNS hours, posts a blog article instead.
"""

import os
import sys
import random
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from scraper import fetch_sitemap, fetch_product, fetch_articles, fetch_article, fetch_today_look
from content_generator import generate_post, generate_article_post, generate_daily_look_post
from telegram_poster import post_product, send_photo, send_text
import tracker

# Every N runs, post an article instead of a product (0 = disable articles)
ARTICLE_EVERY_N_RUNS = int(os.environ.get("ARTICLE_EVERY_N_RUNS", "4"))


def do_daily_look():
    """Fetches today's daily look and posts it to Telegram."""
    print("[bot] Mode: DAILY LOOK")
    look = fetch_today_look()
    if not look:
        print("[bot] No daily look found")
        return False

    look_key = f"look_{look.id}"
    if tracker.is_posted(look_key):
        print(f"[bot] Today's look already posted ({look.look_date})")
        return False

    print(f"[bot] Look: {look.title} ({look.look_date})")
    post_text = generate_daily_look_post(look)
    if not post_text:
        return False

    print(f"[bot] Preview:\n{post_text[:300]}...")

    # Post model image + caption
    if look.model_image_url:
        result = send_photo(look.model_image_url, post_text)
    else:
        result = send_text(post_text)

    if result is not None:
        tracker.mark_posted(look_key, f"https://shushu-secret.com", look.look_date, [])
        print("[bot] ✅ Daily look posted!")
        return True

    print("[bot] ❌ Daily look post failed")
    return False


def should_post_article(run_number: int) -> bool:
    return ARTICLE_EVERY_N_RUNS > 0 and (run_number % ARTICLE_EVERY_N_RUNS == 0)


def do_article():
    print("[bot] Mode: ARTICLE")
    try:
        articles = fetch_articles()
    except Exception as e:
        print(f"[bot] Failed to fetch articles: {e}")
        return False

    unposted = [a for a in articles if not tracker.is_posted(f"article_{a['id']}")]
    if not unposted:
        print("[bot] No new articles — falling back to product")
        return False

    entry = unposted[0]
    article = fetch_article(entry["id"], entry["slug"], entry["url"], entry["lastmod"])
    if not article or not article.title:
        print("[bot] Could not fetch article")
        return False

    print(f"[bot] Article: {article.title}")
    post_text = generate_article_post(article)
    if not post_text:
        return False

    print(f"[bot] Preview:\n{post_text[:250]}...")

    if article.cover_image:
        result = send_photo(article.cover_image, post_text)
    else:
        result = send_text(post_text)

    if result is not None:
        tracker.mark_posted(f"article_{entry['id']}", entry["url"], entry["lastmod"], [])
        print("[bot] ✅ Article posted!")
        return True

    print("[bot] ❌ Article post failed")
    return False


def do_product(run_number: int):
    print("[bot] Mode: PRODUCT")
    try:
        all_products = fetch_sitemap()
    except Exception as e:
        print(f"[bot] Sitemap fetch failed: {e}")
        return False

    # Find next unposted product
    unposted = [p for p in all_products if not tracker.is_posted(p["id"])]

    if not unposted:
        print("[bot] All products have been posted — cycle complete!")
        # Reset tracker to restart the cycle (keep articles tracking)
        data = tracker.load()
        posted = data.get("posted", {})
        # Remove only product entries (not articles)
        data["posted"] = {k: v for k, v in posted.items() if k.startswith("article_")}
        tracker.save(data)
        print("[bot] Tracker reset — restarting product cycle")
        unposted = all_products

    # Pick the next product (use run_number to deterministically rotate through list)
    # Sort by lastmod desc (newest first) to post newest products first
    unposted.sort(key=lambda x: x.get("lastmod", ""), reverse=True)
    entry = unposted[0]

    pid = entry["id"]
    print(f"[bot] Fetching product: {pid}")

    product = fetch_product(pid, entry["url"], entry["lastmod"])
    if not product or not product.name:
        # Mark as seen so we skip it next run
        tracker.mark_posted(pid, entry["url"], entry["lastmod"], [])
        print("[bot] Product has no data — skipped and marked")
        return False

    print(f"[bot] Product: {product.name_en or product.name} | {product.price}")

    # Rotate through 10 content formats based on run number
    format_index = run_number % 10
    post_text = generate_post(product, format_index)
    if not post_text:
        return False

    print(f"[bot] Format #{format_index} preview:\n{post_text[:250]}...")

    if product.images:
        success = post_product(product.images, post_text)
    else:
        # No images — send as text (Telegram generates URL preview automatically)
        result = send_text(post_text)
        success = result is not None

    if success:
        tracker.mark_posted(pid, entry["url"], entry["lastmod"], [])
        print(f"[bot] ✅ Product posted!")
        return True

    print("[bot] ❌ Product post failed")
    return False


def run():
    print(f"\n{'='*50}")
    print(f"SHUSHU Bot — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*50)

    # Load and increment run counter
    data = tracker.load()
    run_number = data.get("run_count", 0) + 1
    data["run_count"] = run_number
    tracker.save(data)

    print(f"[bot] Run #{run_number}")

    if should_post_article(run_number):
        success = do_article()
        if not success:
            # Fallback to product if article fails
            do_product(run_number)
    else:
        do_product(run_number)

    print(f"[bot] Done.")


if __name__ == "__main__":
    run()
