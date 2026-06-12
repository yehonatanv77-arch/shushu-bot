"""
Fetches product and article data directly from Supabase REST API.
Much faster and more reliable than HTML scraping.
"""

import httpx
import os
from dataclasses import dataclass, field
from typing import Optional

SUPABASE_URL = "https://knilxqseqmwubqgjtfhn.supabase.co"
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtuaWx4cXNlcW13dWJxZ2p0ZmhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyNjU3NTQsImV4cCI6MjA4NDg0MTc1NH0.NI9_kfrBKZuKgn_rY-jPJdLY7lsApDvgUuT26XFt6v0",
)
SITE_BASE = "https://shushu-secret.com"

HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
}


@dataclass
class Product:
    id: str
    url: str
    lastmod: str
    name: str = ""
    name_en: str = ""
    brand: str = ""
    description: str = ""
    price: str = ""
    original_price: str = ""
    discount: str = ""
    category: str = ""
    sizes: str = ""
    external_url: str = ""
    gender: str = ""
    images: list = field(default_factory=list)
    in_stock: bool = True


def fetch_sitemap() -> list[dict]:
    """Returns list of {url, id, lastmod} from Supabase products table."""
    entries = []
    offset = 0
    limit = 1000

    with httpx.Client(timeout=30) as client:
        while True:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/products",
                headers={**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset+limit-1}"},
                params={
                    "select": "id,updated_at",
                    "is_active": "eq.true",
                    "order": "updated_at.desc",
                },
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for p in batch:
                entries.append({
                    "id": p["id"],
                    "url": f"{SITE_BASE}/product/{p['id']}",
                    "lastmod": p.get("updated_at", ""),
                })
            if len(batch) < limit:
                break
            offset += limit

    return entries


def fetch_images(product_id: str, client: httpx.Client) -> list[str]:
    """Fetches image URLs for a product from product_images table."""
    r = client.get(
        f"{SUPABASE_URL}/rest/v1/product_images",
        headers=HEADERS,
        params={
            "select": "image_url,sort_order",
            "product_id": f"eq.{product_id}",
            "order": "sort_order.asc",
        },
    )
    if r.status_code != 200:
        return []
    return [row["image_url"] for row in r.json() if row.get("image_url")]


def fetch_product(product_id: str, url: str, lastmod: str) -> Optional[Product]:
    """Fetches full product data from Supabase API."""
    with httpx.Client(timeout=30) as client:
        # Fetch product row
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/products",
            headers=HEADERS,
            params={
                "select": "id,name,name_en,price,description,brand,sizes,external_url,gender,category_id,is_active",
                "id": f"eq.{product_id}",
                "limit": "1",
            },
        )
        if r.status_code != 200 or not r.json():
            return None

        data = r.json()[0]

        if not data.get("is_active"):
            return None

        p = Product(
            id=product_id,
            url=url,
            lastmod=lastmod,
            name=data.get("name") or "",
            name_en=data.get("name_en") or "",
            brand=data.get("brand") or "",
            description=data.get("description") or "",
            price=f"₪{data['price']:.0f}" if data.get("price") else "",
            sizes=data.get("sizes") or "",
            external_url=data.get("external_url") or url,
            gender=data.get("gender") or "",
        )

        # Fetch images
        p.images = fetch_images(product_id, client)

    return p


@dataclass
class DailyLookProduct:
    id: str
    name: str
    name_en: str
    brand: str
    price: str
    url: str


@dataclass
class DailyLook:
    id: str
    look_date: str
    title: str
    description: str
    style_notes: str
    model_image_url: str
    products: list = field(default_factory=list)  # list of DailyLookProduct


def fetch_today_look() -> "Optional[DailyLook]":
    """Fetches today's daily look (or most recent if today not yet created)."""
    with httpx.Client(timeout=30) as client:
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/daily_looks",
            headers=HEADERS,
            params={
                "select": "id,look_date,title,description,style_notes,model_image_url,products",
                "order": "look_date.desc",
                "limit": "1",
            },
        )
        if r.status_code != 200 or not r.json():
            return None

        data = r.json()[0]
        look = DailyLook(
            id=data["id"],
            look_date=data.get("look_date", ""),
            title=data.get("title") or "",
            description=data.get("description") or "",
            style_notes=data.get("style_notes") or "",
            model_image_url=data.get("model_image_url") or "",
        )

        # Fetch each product in the look
        product_ids = data.get("products") or []
        for pid in product_ids:
            prod_r = client.get(
                f"{SUPABASE_URL}/rest/v1/products",
                headers=HEADERS,
                params={
                    "select": "id,name,name_en,brand,price",
                    "id": f"eq.{pid}",
                    "limit": "1",
                },
            )
            if prod_r.status_code == 200 and prod_r.json():
                d = prod_r.json()[0]
                look.products.append(DailyLookProduct(
                    id=pid,
                    name=d.get("name") or "",
                    name_en=d.get("name_en") or "",
                    brand=d.get("brand") or "",
                    price=f"₪{d['price']:.0f}" if d.get("price") else "",
                    url=f"{SITE_BASE}/product/{pid}",
                ))

    return look


@dataclass
class Article:
    id: str
    slug: str
    url: str
    lastmod: str
    title: str = ""
    excerpt: str = ""
    content: str = ""
    cover_image: str = ""
    featured_products: list = field(default_factory=list)


def fetch_articles() -> list[dict]:
    """Returns list of {id, slug, url, lastmod} for all published articles."""
    with httpx.Client(timeout=30) as client:
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/articles",
            headers=HEADERS,
            params={
                "select": "id,slug,updated_at",
                "is_published": "eq.true",
                "order": "updated_at.desc",
            },
        )
        r.raise_for_status()
    return [
        {
            "id": a["id"],
            "slug": a["slug"],
            "url": f"{SITE_BASE}/blog/{a['slug']}",
            "lastmod": a.get("updated_at", ""),
        }
        for a in r.json()
    ]


def fetch_article(article_id: str, slug: str, url: str, lastmod: str) -> Optional[Article]:
    """Fetches full article data from Supabase."""
    with httpx.Client(timeout=30) as client:
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/articles",
            headers=HEADERS,
            params={
                "select": "id,title,slug,excerpt,content,cover_image,featured_products",
                "id": f"eq.{article_id}",
                "limit": "1",
            },
        )
        if r.status_code != 200 or not r.json():
            return None
        data = r.json()[0]

    return Article(
        id=article_id,
        slug=slug,
        url=url,
        lastmod=lastmod,
        title=data.get("title") or "",
        excerpt=data.get("excerpt") or "",
        content=(data.get("content") or "")[:1500],
        cover_image=data.get("cover_image") or "",
        featured_products=data.get("featured_products") or [],
    )
