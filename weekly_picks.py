"""
Weekly "מה קנינו השבוע" post.
Picks 5 recently posted products and writes a curated roundup.
"""

import sys
import json
import httpx
import os
import random
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import anthropic
from telegram_poster import send_photo, send_text

SUPABASE_URL = "https://knilxqseqmwubqgjtfhn.supabase.co"
ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtuaWx4cXNlcW13dWJxZ2p0ZmhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyNjU3NTQsImV4cCI6MjA4NDg0MTc1NH0.NI9_kfrBKZuKgn_rY-jPJdLY7lsApDvgUuT26XFt6v0"
HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}

WEEKLY_PROMPT = """You are the voice of SHUSHU — an Israeli Telegram community for fashion discovery.

Write a weekly roundup post in Hebrew called "מה קנינו השבוע" (what we bought this week).

RULES:
- Write as if you personally tried/bought these items
- Be honest and specific — not every item is perfect, say something real about each
- Conversational, warm, personal tone
- The post should feel like a WhatsApp message to a close friend, not a newsletter
- 1-2 emojis max, placed naturally
- For each item: 1-2 sentences max — what you liked, what surprised you

Products this week:
{products}

Structure:
[Warm opening — "השבוע היה..." or similar, 1 line]

[For each product: name + one honest sentence]

[Closing — genuine reflection, 1-2 lines]

End with:
👇 כל הפריטים בלינקים:
{links}

Return ONLY the post text."""


def fetch_recent_products(limit: int = 5) -> list[dict]:
    """Gets recently posted product IDs from tracker, fetches their data."""
    tracker_path = "posted_products.json"
    if not os.path.exists(tracker_path):
        return []

    with open(tracker_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    posted = data.get("posted", {})
    # Get product entries only (not articles/looks), sorted by posted_at desc
    product_entries = [
        (k, v) for k, v in posted.items()
        if not k.startswith("article_") and not k.startswith("look_")
    ]
    product_entries.sort(key=lambda x: x[1].get("posted_at", ""), reverse=True)
    recent_ids = [k for k, v in product_entries[:20]]

    if not recent_ids:
        return []

    # Fetch product data from Supabase
    products = []
    with httpx.Client(timeout=30) as client:
        for pid in recent_ids:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/products",
                headers=HEADERS,
                params={
                    "select": "id,name,name_en,brand,price,external_url",
                    "id": f"eq.{pid}",
                    "limit": "1",
                },
            )
            if r.status_code == 200 and r.json():
                d = r.json()[0]
                if d.get("name") or d.get("name_en"):
                    products.append(d)
                if len(products) >= limit:
                    break

    return products


def run():
    print("[weekly] Generating weekly picks post...")
    products = fetch_recent_products(5)

    if len(products) < 3:
        print("[weekly] Not enough products to make a weekly post")
        return

    products_text = "\n".join(
        f"- {p.get('name_en') or p.get('name', '')} | {p.get('brand', '')} | ₪{p.get('price', 0):.0f}"
        for p in products
    )
    links_text = "\n".join(
        f"• {p.get('name_en') or p.get('name', '')}: {p.get('external_url') or f'https://shushu-secret.com/product/{p[\"id\"]}'}"
        for p in products
    )

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": WEEKLY_PROMPT.format(
            products=products_text,
            links=links_text,
        )}],
    )
    post_text = msg.content[0].text.strip()
    print(f"[weekly] Preview:\n{post_text[:300]}...")

    result = send_text(post_text)
    if result:
        print("[weekly] ✅ Weekly picks posted!")
    else:
        print("[weekly] ❌ Failed to post")


if __name__ == "__main__":
    run()
