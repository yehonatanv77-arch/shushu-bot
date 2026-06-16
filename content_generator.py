"""
Uses Claude to generate dynamic Hebrew Telegram posts.
10 different content formats to keep the feed fresh.
"""

import anthropic
import json
import random
from scraper import Product, Article, DailyLook

client = anthropic.Anthropic()

# 10 different content formats — rotated to keep the feed dynamic
FORMATS = [
    {
        "name": "secret_find",
        "instruction": """פורמט: גילוי סודי.
פתח עם משפט אחד שמרגיש כמו סוד שאתה משתף עם חבר קרוב.
תאר את המוצר דרך הרגשה שהוא מעורר — לא דרך פיצ'רים.
סיים עם שאלה קצרה שגורמת לאנשים לחשוב.""",
    },
    {
        "name": "story_hook",
        "instruction": """פורמט: סיפור קצר.
פתח עם תרחיש יומיומי שהקורא מזדהה איתו (30 שניות בבוקר, דקה לפני יציאה מהבית וכו').
המוצר נכנס כפתרון טבעי לתרחיש — לא כפרסומת.
1-2 משפטים על הפריט עצמו.""",
    },
    {
        "name": "discovery_alert",
        "instruction": """פורמט: התרעת גילוי.
פתח עם "מצאנו" / "נפל לנו" / "לא האמנו ש..." — תחושת גילוי בלתי צפוי.
הצג את המוצר כאילו זה בדיוק הדבר שחיפשת בלי לדעת.
קצר וחד — מקסימום 5 שורות.""",
    },
    {
        "name": "vibe_check",
        "instruction": """פורמט: ויב צ'ק.
תאר את האנרגיה / הסגנון / הפרסונה שהמוצר מייצג.
מי לובש את זה? איפה? עם מה?
תמונה ויזואלית חדה ואותנטית — בלי להגיד שום מילה על המחיר בהתחלה.""",
    },
    {
        "name": "honest_take",
        "instruction": """פורמט: דעה כנה.
כתוב כאילו אתה בן אדם אמיתי שרוצה לשתף את הדעה שלו על הפריט.
אפשר לציין גם דבר אחד שפחות מושלם — זה עושה את הפוסט אמין יותר.
הגישה: "אני לא בטוח שזה בשביל כולם, אבל אם אתה/את...".""",
    },
    {
        "name": "trend_connect",
        "instruction": """פורמט: חיבור לטרנד.
חבר את המוצר לטרנד עכשווי / עונת שנה / אירוע / מומנט תרבותי.
אל תאמר "טרנדי" — הראה למה זה רלוונטי עכשיו בדיוק.
תחושת "זה הרגע הנכון לזה".""",
    },
    {
        "name": "compare_moment",
        "instruction": """פורמט: השוואה חכמה.
פתח עם "במקום X..." / "במקום לשלם..."  — הצב את המוצר מול חלופה יקרה יותר.
אל תתקיף מותגים אחרים — רק הצג את הערך.
תחושת "וואו, לא ידעתי שיש כזה דבר".""",
    },
    {
        "name": "one_liner_punch",
        "instruction": """פורמט: פאנץ' קצר.
פוסט קצרצר — מקסימום 4 שורות כולל הקישור.
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
אנרגיה של גילוי מרגיע — לא דחיפות, אלא עונג.
"שוטטנו..." / "נתקלנו..." / "כשהסתכלנו על..."
תחושה של גלישה נינוחה שהולידה ממצא מוצלח.""",
    },
]

PRODUCT_POST_PROMPT = """You are the voice of SHUSHU — an Israeli Telegram community for discovering hidden gems.

RULES:
- Write in natural, conversational Hebrew
- Never sound like an ad or salesperson
- Short paragraphs with frequent line breaks
- Use the assigned format strictly
- 1-2 emojis MAX — placed naturally, not at the start of every line
- Never use: "מהמם", "מדהים", "חייבים", "עכשיו!", "הזדמנות!", "אל תפספסו"
- Never use em dashes or long dashes (— or --)
- Do NOT include any URL or link anywhere in the post

ASSIGNED FORMAT: {format_name}
{format_instruction}

PRODUCT DATA:
Name: {name}
Brand: {brand}
Price: {price}
Sizes: {sizes}
Description: {description}
Gender: {gender}

Return ONLY the post text. No URLs, no links, nothing else."""

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


def generate_post(product: Product, format_index: int) -> str:
    """Generates a Hebrew Telegram post in one of 10 rotating formats."""
    fmt = FORMATS[format_index % len(FORMATS)]

    # Use affiliate link if available, fallback to site URL
    buy_url = product.external_url if product.external_url else product.url

    prompt = PRODUCT_POST_PROMPT.format(
        format_name=fmt["name"],
        format_instruction=fmt["instruction"],
        name=product.name_en or product.name,
        brand=product.brand or "מותג פרימיום",
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
