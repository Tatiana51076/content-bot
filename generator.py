import os
import json
import requests
import asyncio
import glob
import random
from datetime import datetime
from database import get_photos, get_unused_news, mark_news_used
from telegram.ext import Application

# ---------- Настройки (секреты или значения по умолчанию) ----------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BRAND_NAME = os.getenv("BRAND_NAME", "ГлобалТракГарант")
try:
    BRAND_COLORS = json.loads(os.getenv("BRAND_COLORS", '["#0C7281", "#043556", "#042134", "#FFFFFB"]'))
except Exception:
    BRAND_COLORS = ["#0C7281", "#043556", "#042134", "#FFFFFB"]

BOT_TOKEN = os.getenv("BOT_TOKEN")
LOGIST_TG_ID = int(os.getenv("LOGIST_TG_ID", "123456789"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
}

# Темы дней
DAYS_THEMES = {
    0: ("новости_компании", "дружеский"),        # Пн
    1: ("отраслевые_новости", "деловой"),         # Вт
    2: ("законодательство", "деловой"),           # Ср
    3: ("совет_или_лайфхак", "дружеский"),        # Чт
    4: ("вопрос_подписчикам", "дружеский"),       # Пт
    5: ("погода_и_дороги", "дружеский"),          # Сб
    6: ("итоги_недели", "дружеский"),             # Вс
}

# ---------- Функции генерации ----------
def generate_post(topic, tone, facts=None):
    if facts is None:
        facts = {}
    theme_descriptions = {
        "новости_компании": "пост о новости компании: новый клиент, рейс, достижение сотрудника",
        "отраслевые_новости": "пост о трендах и новостях рынка грузоперевозок, полезный для клиентов",
        "законодательство": "пост об изменении в законодательстве для перевозчиков (если есть новость) или полезное напоминание",
        "совет_или_лайфхак": "полезный пост для клиентов: как выбрать перевозчика, советы по перевозке",
        "вопрос_подписчикам": "вовлекающий пост с вопросом к аудитории, призывом к обсуждению",
        "погода_и_дороги": "пост о погоде и дорожной ситуации в Московском регионе без указания конкретных трасс",
        "итоги_недели": "пост с итогами недели в цифрах: рейсы, километры, тонны, отзывы",
    }
    description = theme_descriptions.get(topic, "пост для транспортной компании")
    colors_str = ", ".join(BRAND_COLORS)
    facts_str = json.dumps(facts, ensure_ascii=False, indent=2) if facts else ""

    prompt = f"""
Ты — ведущий маркетинговый стратег и копирайтер в автотранспортной компании "{BRAND_NAME}".
Твой тон: экспертный, уверенный, без «воды», с фокусом на цифры и выгоду клиента.

Целевая аудитория:
- Грузовладельцы (коммерческие директора, логисты, собственники бизнеса) — их боль: срывы сроков, потеря груза, скрытые тарифы, отсутствие прозрачности, проблемы с документами.
- Перевозчики (партнёры-экспедиторы) — их боль: простой, холостой пробег, долгие расчёты, бюрократия, отсутствие обратной связи.

Твоя задача: сгенерировать контент для продвижения, который решает конкретные боли аудитории, доказывает экспертность компании и формирует образ надёжного технологичного лидера.
Пиши коротко, ёмко, структурно (списки, подзаголовки, таблицы там, где уместно). Избегай общих фраз («мы лучшие», «качество важнее всего») — подкрепляй каждое утверждение аргументом, цифрой или кейсом.
Контент должен работать на 3 цели: снятие возражений, демонстрация УТП, призыв к конкретному действию (заявка, звонок, расчёт ставки).

Сейчас тема поста: {description}.
Тон сообщения: {tone} (но в целом жёсткий, экспертный, без лести клиенту, с уважением к его опыту).
Цвета бренда: {colors_str}.

Дополнительные данные (факты, которые можно использовать):
{facts_str}

Мы — компания «ГлобалТракГарант». Работаем с 2016 года, специализируемся на рефрижераторных перевозках по Москве и Московской области. 
У нас собственный автопарк, мы строго следим за техническим состоянием наших автомобилей.
У нас есть разрешения на перевозку опасных грузов, валидация и ВТТ.Термописец,Адвантум.
Наш тон — уверенный, но дружеский, без официоза. Мы гордимся отсутствием срывов и строгим контролем температуры. Наши авто оснащены видеоконтролем 24/7, заказчик может в режиме онлайн посмотреть, как перевозится груз. В каждом посте подчёркиваем надёжность и экспертность.

Формат ответа — строгий JSON (без markdown, без пояснений):
{{
    "text": "текст поста (1500–2000 знаков, с хэштегами в конце, без эмодзи в начале, без markdown разметки, просто текст, возможно со структурой: подзаголовки, списки)",
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
                "max_tokens": 2500,
                "temperature": 0.7
            },
            timeout=90
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        print(f"[DEBUG] Raw model response:\n{content[:500]}...")  # первые 500 символов для диагностики

        # --- Улучшенная очистка JSON ---
        # Убираем возможные обёртки markdown (```json ... ```)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]  # убираем ```json
            if content.endswith("```"):
                content = content[:-3]  # убираем закрывающие ```
        elif content.startswith("```"):
            content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
        # Удаляем BOM (если есть)
        if content.startswith('\ufeff'):
            content = content[1:]
        # Пытаемся парсить
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Последняя попытка: обрезать до последнего }
            end = content.rfind('}')
            if end != -1:
                try:
                    return json.loads(content[:end+1])
                except:
                    pass
            raise ValueError("Invalid JSON from model")
    except Exception as e:
        print(f"[ERROR] DeepSeek API error: {e}")
        # Расширенный резервный пост
        return {
            "text": (
                f"{BRAND_NAME} — надёжные рефрижераторные перевозки по Москве и области. "
                "Контроль температуры 24/7, GPS-мониторинг, отсутствие срывов. "
                "Оставьте заявку на сайте или в Direct, рассчитаем ставку за 15 минут. "
                "#автоперевозки #рефрижератор #доставка #логистика"
            ),
            "image_prompt": "фура на трассе, закат, деловой стиль",
            "image_text_overlay": f"{BRAND_NAME}"
        }

def generate_image(prompt, text_overlay=""):
    """Генерация изображения через DeepSeek V4 Flash."""
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
    if topic == "новости_компании":
        facts = {
            "событие": "новый корпоративный клиент или успешный рейс",
            "детали": "доставка продуктов в сеть ресторанов Москвы, 3 рейса в неделю",
            "комментарий_руководителя": "Мы рады расширять географию и обеспечивать стабильность поставок"
        }
    elif topic == "отраслевые_новости":
        facts = {
            "тема": "рост спроса на рефрижераторные перевозки в Московском регионе",
            "факт": "по данным аналитиков, спрос вырос на 12% за квартал",
            "значение_для_клиента": "своевременная доставка скоропорта становится ещё критичнее"
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
        else:
            facts = {
                "закон": "актуальные правила перевозки грузов в Москве",
                "суть": "напоминаем о требованиях к пропускам и времени въезда в центр",
                "кого_касается": "всех перевозчиков, работающих в пределах ТТК"
            }
    elif topic == "совет_или_лайфхак":
        facts = {
            "тема": "как выбрать надёжного перевозчика для скоропорта",
            "суть": "3 признака: наличие рефрижераторов с температурным мониторингом, опыт от 5 лет, страховка груза"
        }
    elif topic == "вопрос_подписчикам":
        facts = {
            "вопрос": "Какой фактор для вас важнее при выборе перевозчика: цена или скорость доставки?",
            "варианты_ответов": "Цена / Скорость / Надёжность / Всё сразу",
            "призыв": "Делитесь мнением в комментариях!"
        }
    elif topic == "погода_и_дороги":
        facts = {
            "регион": "Москва и Московская область",
            "прогноз": "сегодня дождь, местами гроза, температура +18°C",
            "рекомендация": "водителям соблюдать дистанцию, избегать резких манёвров",
            "пробки": "ожидаются затруднения на МКАД в районе 17:00-19:00"
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

def get_random_media():
    """Возвращает путь к случайному медиафайлу (фото или видео) из assets/photos."""
    extensions = ["*.jpg", "*.jpeg", "*.png", "*.mp4", "*.mov", "*.avi"]
    media_files = []
    for ext in extensions:
        media_files.extend(glob.glob(f"assets/photos/{ext}"))
    if not media_files:
        return None
    return random.choice(media_files)

# ---------- Точка входа ----------
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    today = datetime.now().weekday()
    topic, tone = DAYS_THEMES.get(today, ("итоги_недели", "дружеский"))
    facts = collect_facts(topic)
    post_data = generate_post(topic, tone, facts)
    text = post_data.get("text", "Не удалось сгенерировать пост.")
    image_prompt = post_data.get("image_prompt", "")
    
    # Определяем медиа для поста
    media_path = get_random_media()
    
    if media_path:
        is_video = media_path.lower().endswith(('.mp4', '.mov', '.avi'))
        with open(media_path, "rb") as f:
            if is_video:
                await app.bot.send_video(chat_id=CHANNEL_ID, video=f, caption=text)
            else:
                await app.bot.send_photo(chat_id=CHANNEL_ID, photo=f, caption=text)
    else:
        # Пытаемся сгенерировать изображение через ИИ
        image_url = generate_image(image_prompt) if image_prompt else None
        if image_url:
            await app.bot.send_photo(chat_id=CHANNEL_ID, photo=image_url, caption=text)
        else:
            # Если ничего нет, отправляем просто текст
            await app.bot.send_message(chat_id=CHANNEL_ID, text=text)
    
    # Уведомление вам
    await app.bot.send_message(chat_id=LOGIST_TG_ID, text="✅ Пост опубликован в канале и скоро появится в Дзен")
    print("Пост опубликован в канале")

if __name__ == "__main__":
    asyncio.run(main())
