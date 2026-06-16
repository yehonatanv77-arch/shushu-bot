import json, sys, httpx
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SUPABASE_URL = 'https://knilxqseqmwubqgjtfhn.supabase.co'
ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtuaWx4cXNlcW13dWJxZ2p0ZmhuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyNjU3NTQsImV4cCI6MjA4NDg0MTc1NH0.NI9_kfrBKZuKgn_rY-jPJdLY7lsApDvgUuT26XFt6v0'
HEADERS = {'apikey': ANON_KEY, 'Authorization': 'Bearer ' + ANON_KEY}

# Load tracker to get posted IDs
with open('posted_products.json', 'r', encoding='utf-8-sig') as f:
    data = json.load(f)
posted = set(data.get('posted', {}).keys())
print(f"Posted count: {len(posted)}, run_count: {data.get('run_count')}")

# Fetch top 10 unposted products
with httpx.Client(timeout=30) as client:
    r = client.get(f'{SUPABASE_URL}/rest/v1/products', headers=HEADERS, params={
        'select': 'id,name,name_en,brand,price,description,is_active,external_url,updated_at',
        'order': 'updated_at.desc',
        'is_active': 'eq.true',
        'limit': '30'
    })
    all_products = r.json()

unposted = [p for p in all_products if p['id'] not in posted][:10]
print(f"\nTop {len(unposted)} unposted products:")
for p in unposted:
    name = p.get('name') or p.get('name_en') or 'NO NAME'
    price = p.get('price')
    desc = (p.get('description') or '')[:50]
    print(f"  {p['id'][:8]} | {name[:35]} | price={price} | desc={desc!r}")

# Test fetch_product on first one
if unposted:
    print("\nFetching full product data for first candidate...")
    from scraper import fetch_product
    pid = unposted[0]['id']
    prod = fetch_product(pid, f'https://shushu-secret.com/product/{pid}', unposted[0].get('updated_at',''))
    if prod:
        print(f"  name={prod.name!r}")
        print(f"  name_en={prod.name_en!r}")
        print(f"  price={prod.price!r}")
        print(f"  images={len(prod.images)}")
        print(f"  external_url={prod.external_url[:60]!r}")

        # Test generate_post
        print("\nGenerating post...")
        from content_generator import generate_post
        text = generate_post(prod, 0)
        print(f"  Generated: {len(text)} chars")
        print(f"  Preview: {text[:200]}")
    else:
        print("  fetch_product returned None!")
