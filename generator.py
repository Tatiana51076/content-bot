import os
import json
import requests
import asyncio
from datetime import datetime
from database import get_photos, get_unused_news, mark_news_used
from telegram.ext import Application

# ---------- Настройки (секреты или значения по умолчанию) ----------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BRAND_NAME = os.getenv("BRAND_NAME", "24 Градуса")
try:
    BRAND_COLORS = json.loads(os.getenv("BRAND_COLORS", '["#0C7281", "#043556", "#042134", "#FFFFFB"]'))
except Exception:
    BRAND_COLORS = ["#0C7281", "#043556", "#042134", "#FFFFFB"]

BOT_TOKEN = os.getenv("BOT_TOKEN")
LOGIST_TG_ID = int(os.getenv("LOGIST_TG_ID", "123456789"))

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
}

DAYS_THEMES = {
    0: ("итоги_недели", "дружеский"),
    1: ("рейс_недели", "дружеский"),
    2: ("законодательство", "деловой"),
    3: ("команда", "дружеский"),
    4: ("лайфхак", "дружеский"),
    5: ("погода", "дружеский"),
    6: ("поздравление", "дружеский"),
}

# ---------- Функции генерации ----------
def generate_post(topic, tone, facts=None):
    if facts is None:
        facts = {}
    theme_descriptions = {
        "рейс_недели": "пост о ярком рейсе за последнюю неделю: маршрут, груз, водитель, особенности, температура",
        "законодательство": "пост об изменении в законодательстве для перевозчиков: суть изменения, когда вступает, кого касается",
        "команда": "пост-знакомство с сотрудником компании: кто, сколько работает, чем гордится, его роль",
        "лайфхак": "полезный пост для клиентов: совет по перевозке, хранению груза, подготовке к рейсу",
        "погода": "пост о погоде и ситуации на трассах: прогноз, сложные участки, рекомендации водителям",
        "поздравление": "поздравительный пост: день рождения сотрудника или профессиональный праздник",
        "итоги_недели": "пост с итогами недели в цифрах: сколько рейсов, километров, тонн, отзывов",
    }
    description = theme_descriptions.get(topic, "пост для транспортной компании")
    colors_str = ", ".join(BRAND_COLORS)
    facts_str = json.dumps(facts, ensure_ascii=False, indent=2) if facts else ""

    prompt = f"""
Ты — SMM-менеджер транспортной компании "{BRAND_NAME}".
Сгенерируй {description}.

Тон: {tone}
Цвета бренда: {colors_str}

Дополнительные данные:
{facts_str}

Формат ответа — строгий JSON (без markdown, без пояснений):
{{
    "text": "текст поста (80-150 слов, с хэштегами в конце, без эмодзи в начале, без markdown разметки, просто текст)",
    "image_prompt": "промпт для генерации изображения (описание: фура, дорога, груз, стиль деловой, цвета бренда, без людей)",
    "image_text_overlay": "короткий заголовок для картинки (3-5 слов)"
}}
"""
    try:
        response = requests.post(
            DEEPSEEK_API,
            headers=HEADERS,
            json={
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": 2000,
                "temperature": 0.8
            },
            timeout=60
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"[ERROR] DeepSeek API error: {e}")
        return {
            "text": f"{BRAND_NAME}: очередной рейс выполнен успешно. Следите за нашими новостями! #автоперевозки #рефрижератор #доставка",
            "image_prompt": "фура на трассе, закат, деловой стиль",
            "image_text_overlay": f"{BRAND_NAME}"
        }

def generate_image(prompt, text_overlay=""):
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/images/generations",
            headers=HEADERS,
            json={
                "model": "deepseek-v4-flash",
                "prompt": f"{prompt}. Цвета: {', '.join(BRAND_COLORS)}",
                "size": "1024x1024",
                "n": 1,
                "quality": "standard"
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()["data"][0]["url"]
    except Exception as e:
        print(f"[ERROR] Image generation error: {e}")
        return None

def collect_facts(topic):
    facts = {}
    if topic == "рейс_недели":
        facts = {
            "маршрут": "Москва — Сочи",
            "груз": "мороженое, 5 тонн",
            "водитель": "Сергей",
            "особенности": "28 часов в пути, +35°C на Кубани, -18°C в будке"
        }
    elif topic == "законодательство":
        news = get_unused_news()
        if news:
            n = news[0]
            facts = {
                "закон": n["title"],
                "суть": n["summary"],
                "вступает_в_силу": n["effective_date"],
                "кого_касается": n["affects"],
                "источник": n["source"]
            }
            mark_news_used(n["id"])
    elif topic == "команда":
        facts = {
            "имя": "Алексей",
            "должность": "водитель",
            "стаж": "12 лет в компании",
            "достижение": "более 500 рейсов без аварий"
        }
    elif topic == "лайфхак":
        facts = {
            "тема": "подготовка рефрижератора к лету",
            "суть": "5 шагов: проверить компрессор, конденсатор, испаритель, уровень фреона, уплотнители дверей"
        }
    elif topic == "погода":
        facts = {
            "м4": "дождь, видимость до 500 м, сложный участок 143-147 км",
            "м5": "ясно, +28°C",
            "м8": "ремонт 85-90 км, объезд через ..."
        }
    elif topic == "поздравление":
        facts = {
            "имя": "Михаил",
            "повод": "день рождения",
            "детали": "40 лет, 15 лет за рулём"
        }
    elif topic == "итоги_недели":
        facts = {
            "рейсов": 12,
            "км": 7200,
            "тонн": 45,
            "нарушений": 0,
            "отзывов": 3,
            "новых_клиентов": 2
        }
    return facts

# ---------- Точка входа (должна быть после всех функций) ----------
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    today = datetime.now().weekday()
    topic, tone = DAYS_THEMES.get(today, ("итоги_недели", "дружеский"))
    facts = collect_facts(topic)
    post_data = generate_post(topic, tone, facts)
    text = post_data.get("text", "Не удалось сгенерировать пост.")
    await app.bot.send_message(chat_id=LOGIST_TG_ID, text=text)
    print("Пост отправлен на утверждение")

if __name__ == "__main__":
    asyncio.run(main())
