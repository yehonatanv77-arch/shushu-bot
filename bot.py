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
    data = tracker.load()
    posted_ids = set(data.get("posted", {}).keys())
    unposted = [p for p in all_products if p["id"] not in posted_ids]

    if not unposted:
        print("[bot] All products have been posted — cycle complete!")
        # Reset only product entries (keep articles and looks)
        data["posted"] = {k: v for k, v in data.get("posted", {}).items()
                         if k.startswith("article_") or k.startswith("look_")}
        tracker.save(data)
        print("[bot] Tracker reset — restarting product cycle")
        unposted = all_products

    # Pick from the 100 newest, shuffled — prevents always retrying the same failures
    unposted.sort(key=lambda x: x.get("lastmod", ""), reverse=True)
    pool = unposted[:100]
    random.shuffle(pool)
    candidates = pool[:10]

    format_index = run_number % 10
    for entry in candidates:
        pid = entry["id"]
        print(f"[bot] Fetching product: {pid}")

        product = fetch_product(pid, entry["url"], entry["lastmod"])
        if not product or not product.name:
            tracker.mark_posted(pid, entry["url"], entry["lastmod"], [])
            print("[bot] No data — skipping to next")
            continue

        print(f"[bot] Product: {product.name_en or product.name} | {product.price}")

        post_text = generate_post(product, format_index)
        if not post_text:
            continue

        print(f"[bot] Format #{format_index} preview:\n{post_text[:250]}...")

        # Final duplicate check right before sending (guards against concurrent runs)
        if tracker.is_posted(pid):
            print(f"[bot] {pid} was already posted — skipping")
            continue

        buy_url = product.external_url if product.external_url else product.url
        if product.images:
            success = post_product(product.images, post_text, buy_url)
        else:
            result = send_text(post_text, buy_url)
            success = result is not None

        if success:
            tracker.mark_posted(pid, entry["url"], entry["lastmod"], [])
            print(f"[bot] ✅ Product posted!")
            return True

        print("[bot] ❌ Telegram failed, trying next product")

    print("[bot] No product posted this run")
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
