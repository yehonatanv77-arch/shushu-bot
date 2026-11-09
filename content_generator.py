"""
Uses Claude to generate dynamic Hebrew Telegram posts.
10 different content formats to keep the feed fresh.
"""

import anthropic
import json
import random
from scraper import Product, Article, DailyLook

client = anthropic.Anthropic()

# 14 different content formats — rotated randomly to keep the feed fresh
FORMATS = [
    {
        "name": "secret_find",
        "instruction": """פורמט: גילוי סודי.
פתח עם משפט אחד שמרגיש כמו סוד שאתה משתף עם חבר קרוב.
תאר את המוצר דרך הרגשה שהוא מעורר, לא דרך פיצ'רים.
סיים עם שאלה קצרה שגורמת לאנשים לחשוב.""",
    },
    {
        "name": "story_hook",
        "instruction": """פורמט: סיפור קצר.
פתח עם תרחיש יומיומי שהקורא מזדהה איתו (30 שניות בבוקר, דקה לפני יציאה מהבית וכו').
המוצר נכנס כפתרון טבעי לתרחיש, לא כפרסומת.
1-2 משפטים על הפריט עצמו.""",
    },
    {
        "name": "discovery_alert",
        "instruction": """פורמט: התרעת גילוי.
פתח עם "מצאנו" / "נפל לנו" / "לא האמנו ש...", תחושת גילוי בלתי צפוי.
הצג את המוצר כאילו זה בדיוק הדבר שחיפשת בלי לדעת.
קצר וחד, מקסימום 5 שורות.""",
    },
    {
        "name": "vibe_check",
        "instruction": """פורמט: ויב צ'ק.
תאר את האנרגיה / הסגנון / הפרסונה שהמוצר מייצג.
מי לובש את זה? איפה? עם מה?
תמונה ויזואלית חדה ואותנטית, בלי להגיד שום מילה על המחיר בהתחלה.""",
    },
    {
        "name": "honest_take",
        "instruction": """פורמט: דעה כנה.
כתוב כאילו אתה בן אדם אמיתי שרוצה לשתף את הדעה שלו על הפריט.
אפשר לציין גם דבר אחד שפחות מושלם, זה עושה את הפוסט אמין יותר.
הגישה: "אני לא בטוח שזה בשביל כולם, אבל אם אתה/את...".""",
    },
    {
        "name": "trend_connect",
        "instruction": """פורמט: חיבור לטרנד.
חבר את המוצר לטרנד עכשווי / עונת שנה / אירוע / מומנט תרבותי.
אל תאמר "טרנדי", הראה למה זה רלוונטי עכשיו בדיוק.
תחושת "זה הרגע הנכון לזה".""",
    },
    {
        "name": "compare_moment",
        "instruction": """פורמט: השוואה חכמה.
פתח עם "במקום X..." / "במקום לשלם..." , הצב את המוצר מול חלופה יקרה יותר.
אל תתקיף מותגים אחרים, רק הצג את הערך.
תחושת "וואו, לא ידעתי שיש כזה דבר".""",
    },
    {
        "name": "one_liner_punch",
        "instruction": """פורמט: פאנץ' קצר.
פוסט קצרצר, מקסימום 4 שורות כולל הקישור.
משפט פתיחה חזק ובלתי צפוי.
תיאור של 2 משפטים בלבד.
CTA של מילה אחת.""",
    },
    {
        "name": "community_rec",
        "instruction": """פורמט: המלצת קהילה.
כתוב כאילו חברים בקהילה דיברו על הפריט הזה.
"הרבה שאלות שקיבלנו על..." / "אחרי שכמה מכם ביקשו..." / "זה הפריט שאנשים שאלו עליו..."
תחושה שיש ביקוש אמיתי.""",
    },
    {
        "name": "weekend_find",
        "instruction": """פורמט: מציאת סוף שבוע.
אנרגיה של גילוי מרגיע, לא דחיפות, אלא עונג.
"שוטטנו..." / "נתקלנו..." / "כשהסתכלנו על..."
תחושה של גלישה נינוחה שהולידה ממצא מוצלח.""",
    },
    {
        "name": "before_after",
        "instruction": """פורמט: לפני ואחרי.
תאר איך הלוק / התחושה / הסיטואציה נראית בלי הפריט הזה, ואיך היא נראית איתו.
אל תהיה דרמטי, תהיה אמיתי וקצת הומוריסטי.
שורה אחת לפני, שורה אחת אחרי.""",
    },
    {
        "name": "gift_idea",
        "instruction": """פורמט: רעיון למתנה.
הצג את המוצר כמתנה מושלמת לאחד מהפרופילים האלה: לעצמך / לחברה / לאמא / לאחות.
אל תאמר "מושלם למתנה", הראה למה בדיוק.
תחושה אישית ומחושבת.""",
    },
    {
        "name": "quality_catch",
        "instruction": """פורמט: תפיסת איכות.
דבר על מה שגורם לפריט הזה להרגיש יותר יקר ממה שהוא עולה.
פרט אחד ספציפי על עיצוב / חומר / פינישינג שמסגיר את האיכות.
תחושה של מישהו שמבין בזה.""",
    },
    {
        "name": "capsule_piece",
        "instruction": """פורמט: פריט בסיסי.
הסבר למה הפריט הזה הוא "בסיסי" שיושב עם הכל ומשדרג כל לוק.
ציין 2 שילובים קצרים וספציפיים (עם מה ללבוש אותו).
אנרגיה של מישהו שבנה ארון לבוש חכם.""",
    },
]

# Opening-line styles, one picked at random per post so the feed never starts the same way twice
HOOK_STYLES = [
    '"תראו מה נחת אצלנו" + the item, e.g. "תראו מה נחת אצלנו! ג\'קט הג\'ינס של אדידס"',
    '"תראו מה הגיע אלינו" + the item, e.g. "תראו מה הגיע אלינו! הסריג של ראלף לורן"',
    '"תקשיבו, הדגם של" + brand and model, e.g. "תקשיבו, הדגם של ניו באלאנס שכולם מחפשים"',
    '"תראו מה מצאנו לכם" + the item, e.g. "בנות, תראו איזה ג\'קט מצאנו לכן"',
]
# Used instead when we know the Israel price: open with it, the SHUSHU price comes as the surprise
PRICE_HOOK = 'open with the Israel price as a teaser, e.g. "{il}₪ על ניו באלאנס? חכו שתראו את המחיר הזה!"'

PRODUCT_POST_PROMPT = """You are the voice of SHUSHU, an Israeli shopping community. Your job is to make people BUY.

RULES:
- Natural, simple Hebrew, short lines that are easy to scan on a phone
- Never use em dashes or long dashes (-- or any variant)
- Never invent facts: no fake discounts, stock counts or reviews. Use only the product data below
- Do NOT include any URL or link anywhere
- Always name the brand (from Brand below) in line 2, if Brand is empty use only the item name

TONE: write it as a personal recommendation from me to a good friend, in first person ("מצאתי", "תקשיבו", "תראו מה נפל לי"), warm and honest, the way you text a friend about something you really liked. Not an ad voice, no salesman phrases. Very excited and enthusiastic, but short, with emojis where they feel natural.

Wrap the hook (line 1) in single asterisks for bold, e.g. *🔥 בנות, תראו איזה ג'קט מצאנו לכן! 😍*. No other asterisks.
FOMO: add ONE short line with a real sense of urgency where it fits best (usually right before the price), built only on true facts: high demand (many orders), it sold out before / came back, the season is starting, a limited sale or coupon. E.g. "⏳ זה נחטף מהר, אל תחכו" or "🚨 זה חזר למלאי!" only if true. Never invent stock counts or deadlines.

SOUND HUMAN, NOT AI (very important):
- Write like a real Israeli texting on WhatsApp: everyday slang (וואלה, סחתיין, אחלה, מטורף, בקיצור), short and a bit loose, not polished
- Vary the rhythm: lines of different lengths, not every line built the same way, not every line ending with "!"
- Emojis: 1-2 per line at most, and NOT on every line; skip the typical AI emojis ✨ 💫 🌟 and never stack them
- No AI phrases: "בין אם... ובין אם", "לא רק... אלא גם", "מושלם ל", "הפריט האידיאלי", "שדרוג", "חוויה", "פשוט חובה", "מה שהופך את זה ל"
- No lists of three adjectives, no rhetorical summaries at the end, no em dashes, no colons in the middle of sentences
- Never invent a personal experience ("הלכתי איתן יום שלם")
- Never push my personal taste on the reader ("הייתי לוקח את האפור", "זה הסגנון שלי"): show the item and let them decide
- Do not highlight how many colors there are (no "9 צבעים לבחירה")

STRUCTURE (exactly this):
Line 1: 🔥 + a short, very excited hook in this style: {hook_style}. End it with 😍 / 😳 / 😱
Blank line
An emoji that fits the item + brand and model + one vivid line about what makes it stand out
An emoji + how to wear it or what it adds to a look (one line)
Blank line
{israel_line}🤫 ב-SHUSHU רק [price]₪! + what comes with it if the description says so (e.g. "כולל קופסה 📦")
Blank line
📏 מידות [sizes]

Example of the tone and layout (a different item, do not copy the words):
*🔥 650₪ על ניו באלאנס? חכו שתראו את המחיר הזה! 😳*

👟 ניו באלאנס 9060, הדגם עם הסוליה העבה והלוק שאי אפשר להתעלם ממנו!
😍 עם ג'ינס או עם טרנינג, הנעל הזאת עושה את כל ההופעה

🇮🇱 דגמים דומים של המותג בארץ סביב 650₪
🤫 ב-SHUSHU רק 184₪! כולל קופסה 📦

📏 מידות 36 עד 47

Angle for the hook and reasons (use it as inspiration only, keep the structure): {format_instruction}

PRODUCT DATA:
Name: {name}
Brand: {brand}
Price: {price}
Sizes: {sizes}
Description: {description}
Gender: {gender}

Return ONLY the post text. Nothing else."""

ARTICLE_POST_PROMPT = """You are the voice of SHUSHU — an Israeli Telegram community for fashion discovery.

Write a teaser post in Hebrew for a blog article.

RULES:
- Sound like a friend sharing something interesting they just read
- Pull out 2-3 genuinely surprising or useful insights from the content
- Create curiosity — what will they learn that they didn't know?
- Conversational, short paragraphs
- 1-2 emojis max

Article Title: {title}
Excerpt: {excerpt}
Content: {content}

End with exactly:
👇 לכתבה המלאה:
{url}

Return ONLY the post text."""


def israel_price(product: Product) -> int:
    """Looks up what this item (or the same model) costs in Israeli stores; 0 when not found."""
    query = f"{product.brand} {product.name_en or product.name}".strip()
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": (
                f"Find the regular price in Israel (ILS, Israeli online stores or the brand's Israeli site) of: {query}. "
                "Same model, or the closest model of the same brand and type. "
                'Answer with only JSON: {"price": <number in ILS>} or {"price": 0} if you are not sure.')}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return int(float(json.loads(text[text.find("{"): text.rfind("}") + 1]).get("price") or 0))
    except Exception as e:
        print(f"[content] Israel price lookup failed: {e}")
        return 0


def generate_post(product: Product, format_index: int) -> str:
    """Generates a Hebrew Telegram post using a randomly selected format."""
    fmt = random.choice(FORMATS)

    buy_url = product.external_url if product.external_url else product.url

    il_price = israel_price(product)
    try:
        ours = float(str(product.price).replace("₪", "").replace(",", "").strip())
    except ValueError:
        ours = 0
    israel_line = ""
    if il_price and ours and il_price > ours * 1.3:
        print(f"[content] Israel price: {il_price}")
        # The model writes this line as-is, then a blank line before the vault price
        israel_line = f"🇮🇱 דגמים דומים של המותג בארץ סביב {il_price}₪\n"

    prompt = PRODUCT_POST_PROMPT.format(
        format_name=fmt["name"],
        format_instruction=fmt["instruction"],
        hook_style=PRICE_HOOK.format(il=il_price) if israel_line and random.random() < 0.5 else random.choice(HOOK_STYLES),
        israel_line=israel_line,
        name=product.name_en or product.name,
        brand=product.brand or "",
        price=product.price,
        sizes=product.sizes or "מידות שונות",
        description=(product.description or "")[:400],
        gender=product.gender or "",
        url=buy_url,
    )

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"[content] Post error: {e}")
        return ""


def generate_article_post(article: Article) -> str:
    """Generates a Hebrew Telegram teaser for a blog article."""
    prompt = ARTICLE_POST_PROMPT.format(
        title=article.title,
        excerpt=article.excerpt,
        content=article.content[:1000],
        url=article.url,
    )
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"[content] Article post error: {e}")
        return ""


DAILY_LOOK_PROMPT = """You are the voice of SHUSHU — an Israeli Telegram fashion community.

Write a daily look post in Hebrew. This is posted every morning and should feel like a fresh, editorial morning brief.

RULES:
- Rotate the opening style every time — never start the same way twice
- Possible openers: תיאור ויזואלי / שאלה פתוחה / משפט מצב / תרחיש של בוקר
- Describe the overall VIBE and MOOD of the look — not a list of items
- Then reveal each product naturally, woven into the description (not a bullet list)
- End with the shoppable product list (each on its own line)
- Conversational Hebrew, no corporate language
- 1-2 emojis max

Look Data:
Title: {title}
Date: {look_date}
Description: {description}
Style Notes: {style_notes}

Products in the look:
{products_list}

Structure:
[Opening — vibe/mood/context, 2-3 lines]

[Description of the look with products woven in naturally, 3-4 lines]

🛍️ הפריטים בלוק:
{products_lines}

Return ONLY the post text."""


def generate_daily_look_post(look: DailyLook) -> str:
    """Generates a Hebrew Telegram post for the daily look."""
    products_list = "\n".join(
        f"- {p.name_en or p.name} | {p.brand} | {p.price}"
        for p in look.products
    )
    products_lines = "\n".join(
        f"{p.name_en or p.name} ({p.price}) — {p.url}"
        for p in look.products
    )

    prompt = DAILY_LOOK_PROMPT.format(
        title=look.title,
        look_date=look.look_date,
        description=look.description,
        style_notes=look.style_notes,
        products_list=products_list,
        products_lines=products_lines,
    )

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"[content] Daily look post error: {e}")
        return ""
