"""One-off: resend today's daily look to WhatsApp only (Telegram already has it)."""
import sys
sys.path.insert(0, ".")
from scraper import fetch_today_look
from content_generator import generate_daily_look_post
from whatsapp_poster import post_product_to_whatsapp
import community

look = fetch_today_look()
text = generate_daily_look_post(look)
text = f"{text}\n\n👗 כל הפריטים של הלוק באתר:\n{community.site_link('/', 'whatsapp', 'daily_look')}"
print("LOOK:", look.title, look.look_date)
print("SENT:", post_product_to_whatsapp([look.model_image_url] if look.model_image_url else [], text))
