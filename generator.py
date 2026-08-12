import os
import json
import requests
import asyncio
import glob
import random
from datetime import datetime
from telegram.ext import Application

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
# Генерация текста: «Все LLM» (vsellm.ru) OpenAI-совместимый API, либо DeepSeek как fallback
LLM_API_KEY = os.getenv("OPENAI_LIKE_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
LLM_API_BASE = os.getenv("OPENAI_LIKE_API_BASE_URL") or "https://api.vsellm.ru/v1"
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek/deepseek-v4-flash")
BRAND_NAME = os.getenv("BRAND_NAME", "ГлобалТракГарант")
try:
    BRAND_COLORS = json.loads(os.getenv("BRAND_COLORS", '["#0C7281", "#043556", "#042134", "#FFFFFB"]'))
except Exception:
    BRAND_COLORS = ["#0C7281", "#043556", "#042134", "#FFFFFB"]

BOT_TOKEN = os.getenv("BOT_TOKEN")
LOGIST_TG_ID = int(os.getenv("LOGIST_TG_ID", "123456789"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

DZEN_LINK = os.getenv("DZEN_LINK", "https://dzen.ru/globaltruck.online?share_to=link")

# История последних постов (хранится в репозитории, чтобы текст не повторялся)
POST_HISTORY_FILE = "post_history.json"


def load_post_history():
    if os.path.exists(POST_HISTORY_FILE):
        try:
            with open(POST_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_post_history(history):
    with open(POST_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-6:], f, ensure_ascii=False, indent=2)


def remember_post(text):
    history = load_post_history()
    history.append({"date": datetime.now().strftime("%d.%m.%Y"), "text": text})
    save_post_history(history)

LLM_API = f"{LLM_API_BASE}/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {LLM_API_KEY}",
    "Content-Type": "application/json"
}

DAYS_THEMES = {
    0: ("новости_компании", "дружеский"),
    1: ("отраслевые_новости", "деловой"),
    2: ("законодательство", "деловой"),
    3: ("совет_или_лайфхак", "дружеский"),
    4: ("вопрос_подписчикам", "дружеский"),
    5: ("трудовые_будни", "дружеский"),
    6: ("итоги_недели", "дружеский"),
}

def generate_post(topic, tone, facts=None, history=None):
    if facts is None:
        facts = {}
    if history is None:
        history = []
    theme_descriptions = {
        "новости_компании": "пост о новости компании: новый клиент, рейс, достижение сотрудника",
        "отраслевые_новости": "пост о трендах и новостях рынка грузоперевозок, полезный для клиентов",
        "законодательство": "пост об изменении в законодательстве для перевозчиков (если есть новость) или полезное напоминание",
        "совет_или_лайфхак": "полезный пост для клиентов: как выбрать перевозчика, советы по перевозке",
        "вопрос_подписчикам": "вовлекающий пост с вопросом к аудитории, призывом к обсуждению",
        "трудовые_будни": "пост о рабочих буднях: тюнинг, доработка, ремонт техники, фото процесса",
        "итоги_недели": "пост с итогами недели в цифрах: рейсы, километры, тонны, нарушения",
    }
    description = theme_descriptions.get(topic, "пост для транспортной компании")
    colors_str = ", ".join(BRAND_COLORS)
    facts_str = json.dumps(facts, ensure_ascii=False, indent=2) if facts else ""
    today = datetime.now().strftime("%d.%m.%Y")

    # Предыдущие посты — чтобы текст НЕ повторялся
    prev_posts = ""
    if history:
        prev_texts = [h.get("text", "") for h in history if h.get("text")]
        if prev_texts:
            prev_posts = "\n".join(f"- {t[:300]}" for t in prev_texts[-5:])

    # Оформление изображения под тему: для «оформительских» тем — без фото машин
    if topic == "итоги_недели":
        image_style = "красивое деловое оформление в фирменных цветах: стильная графика с цифрами и иконками (стрелки, маршруты, термометр), без фотографий машин и людей"
    elif topic == "вопрос_подписчикам":
        image_style = "яркая графика с большим вопросительным знаком в фирменных цветах, деловой минимализм, без фото машин и людей"
    elif topic in ("новости_компании", "отраслевые_новости", "законодательство"):
        image_style = "деловая графика в фирменных цветах: силуэт фуры на маршруте, иконки логистики, без людей и текста на картинке"
    else:
        image_style = "фура-рефрижератор на дороге, деловой стиль, фирменные цвета, без людей"

    prompt = f"""
Ты — ведущий маркетинговый стратег и копирайтер в автотранспортной компании "{BRAND_NAME}".
Твой тон: экспертный, уверенный, без «воды», с фокусом на цифры и выгоду клиента.

Целевая аудитория:
- Грузовладельцы (коммерческие директора, логисты, собственники бизнеса) — их боль: срывы сроков, потеря груза, скрытые тарифы, отсутствие прозрачности, проблемы с документами.
- Перевозчики (партнёры-экспедиторы) — их боль: простой, холостой пробег, долгие расчёты, бюрократия, отсутствие обратной связи.

Твоя задача: сгенерировать контент для продвижения, который решает конкретные боли аудитории, доказывает экспертность компании и формирует образ надёжного технологичного лидера.
Пиши коротко, ёмко. Избегай общих фраз — подкрепляй каждое утверждение аргументом.

Сейчас тема поста: {description}.
Тон сообщения: {tone}.
Сегодняшняя дата: {today}.

Дополнительные данные (факты, которые можно использовать):
{facts_str}

Мы — компания «ГлобалТракГарант». Работаем с 2016 года, специализируемся на рефрижераторных перевозках по Москве и Московской области.
У нас собственный автопарк, строгий контроль температуры, видеоконтроль 24/7.

ПРЕДЫДУЩИЕ ПОСТЫ (НЕ ПОВТОРЯЙ их смысл, формулировки, примеры и цифры — напиши совсем другой текст):
{prev_posts}

ВАЖНОЕ ТРЕБОВАНИЕ К РАЗНООБРАЗИЮ:
- Текст должен быть НОВЫМ и отличаться от любых предыдущих постов: меняй структуру, вступления, примеры и формулировки.
- Не начинай пост одинаковыми фразами каждый раз. Используй разные стили начала: вопрос, цифра, факт, история, прямое обращение.
- Не перечисляй в каждом посте одно и то же — если это итоги недели, НЕ пиши про количество новых клиентов и НЕ пиши про отзывы, только про работу: рейсы, километры, тонны, отсутствие нарушений.

ОБЯЗАТЕЛЬНО: в конце поста (перед хэштегами) добавь строку с приглашением читать подробные статьи и материалы на нашем Дзен-канале, указав ссылку: {DZEN_LINK}

Формат ответа — строгий JSON (без markdown, без пояснений):
{{
    "text": "текст поста (максимум 850-950 знаков, строго до 1000, с хэштегами в конце, без эмодзи и markdown, просто текст)",
    "image_prompt": "промпт для генерации изображения: {image_style}",
    "image_text_overlay": "короткий заголовок для картинки (3-5 слов)"
}}
"""
    try:
        response = requests.post(
            LLM_API,
            headers=HEADERS,
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": 1500,
                "temperature": 0.9
            },
            timeout=90
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        print(f"[DEBUG] Raw model response:\n{content[:500]}...")

        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
        elif content.startswith("```"):
            content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
        if content.startswith('\ufeff'):
            content = content[1:]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            end = content.rfind('}')
            if end != -1:
                try:
                    return json.loads(content[:end+1])
                except:
                    pass
            raise ValueError("Invalid JSON from model")
    except Exception as e:
        print(f"[ERROR] DeepSeek API error: {e}")
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
    # Генерация изображений через «Все LLM» (vsellm.ru), OpenAI-совместимый API
    image_api_key = os.getenv("IMAGE_API_KEY") or os.getenv("OPENAI_LIKE_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    image_api_base = os.getenv("IMAGE_API_BASE_URL") or os.getenv("OPENAI_LIKE_API_BASE_URL") or "https://api.vsellm.ru/v1"
    image_model = os.getenv("IMAGE_MODEL", "openai/gpt-image-1-mini")
    if not image_api_key:
        print("[ERROR] No image API key set")
        return None
    try:
        headers = {
            "Authorization": f"Bearer {image_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": image_model,
            "prompt": f"{prompt}. Цвета бренда: {', '.join(BRAND_COLORS)}",
            "size": "1024x1024",
            "n": 1,
        }
        if text_overlay:
            payload["prompt"] += f" Заголовок на изображении: «{text_overlay}»."
        response = requests.post(
            f"{image_api_base}/images/generations",
            headers=headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        data = response.json()["data"][0]
        if data.get("url"):
            return data["url"]
        if data.get("b64_json"):
            import base64
            fname = f"assets/generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with open(fname, "wb") as f:
                f.write(base64.b64decode(data["b64_json"]))
            return fname
        return None
    except Exception as e:
        print(f"[ERROR] Image generation error: {e}")
        return None

def collect_facts(topic):
    facts = {}
    if topic == "новости_компании":
        facts = random.choice([
            {
                "событие": "новый корпоративный клиент или успешный рейс",
                "детали": "доставка продуктов в сеть ресторанов Москвы, 3 рейса в неделю",
                "комментарий_руководителя": "Мы рады расширять географию и обеспечивать стабильность поставок"
            },
            {
                "событие": "расширение маршрутной сети",
                "детали": "начали перевозки в новом направлении по Московской области",
                "комментарий_руководителя": "Каждый новый маршрут — это проверка наших стандартов качества"
            },
            {
                "событие": "обновление автопарка",
                "детали": "вывод новой техники на линию, модернизация оборудования",
                "комментарий_руководителя": "Инвестируем в технику, чтобы ваши грузы всегда приезжали вовремя"
            },
        ])
    elif topic == "отраслевые_новости":
        facts = random.choice([
            {
                "тема": "рост спроса на рефрижераторные перевозки в Московском регионе",
                "факт": "по данным аналитиков, спрос вырос на 12% за квартал",
                "значение_для_клиента": "своевременная доставка скоропорта становится ещё критичнее"
            },
            {
                "тема": "развитие экспресс-доставки скоропортящихся грузов",
                "факт": "рынок ускоряется, клиенты ждут вывоза в день обращения",
                "значение_для_клиента": "скорость реакции логиста решает, останется ли груз свежим"
            },
            {
                "тема": "цифровизация автопарков",
                "факт": "всё больше перевозчиков внедряют температурный мониторинг в реальном времени",
                "значение_для_клиента": "прозрачность и контроль температуры становятся стандартом"
            },
        ])
    elif topic == "законодательство":
        facts = random.choice([
            {
                "закон": "актуальные правила перевозки грузов в Москве",
                "суть": "напоминаем о требованиях к пропускам и времени въезда в центр",
                "кого_касается": "всех перевозчиков, работающих в пределах ТТК"
            },
            {
                "закон": "изменения в правилах перевозки скоропорта",
                "суть": "ужесточение требований к температурному режиму и оформлению документов",
                "кого_касается": "перевозчиков продуктов и фармацевтики"
            },
            {
                "закон": "требования к режиму труда и отдыха водителей",
                "суть": "напомним про тахографы и контроль рабочего времени",
                "кого_касается": "транспортных компаний и логистов"
            },
        ])
    elif topic == "совет_или_лайфхак":
        facts = random.choice([
            {
                "тема": "как выбрать надёжного перевозчика для скоропорта",
                "суть": "3 признака: наличие рефрижераторов с температурным мониторингом, опыт от 5 лет, страховка груза"
            },
            {
                "тема": "как подготовить скоропорт к перевозке",
                "суть": "правильная термоупаковка, предварительное охлаждение, согласование режима с логистом"
            },
            {
                "тема": "как сэкономить на перевозке без потери качества",
                "суть": "консолидация грузов, планирование маршрута, понятные тарифы без скрытых доплат"
            },
        ])
    elif topic == "вопрос_подписчикам":
        facts = random.choice([
            {
                "вопрос": "Какой фактор для вас важнее при выборе перевозчика: цена или скорость доставки?",
                "варианты_ответов": "Цена / Скорость / Надёжность / Всё сразу",
                "призыв": "Делитесь мнением в комментариях!"
            },
            {
                "вопрос": "Что чаще всего срывает сроки доставки в вашей практике?",
                "варианты_ответов": "Погода / Документы / Загрузка / Другое",
                "призыв": "Напишите свой вариант — обсудим!"
            },
            {
                "вопрос": "Насколько важно для вас видеть температуру груза в реальном времени?",
                "варианты_ответов": "Критично / Желательно / Не задумывался",
                "призыв": "Голосуйте в комментариях!"
            },
        ])
    elif topic == "трудовые_будни":
        facts = random.choice([
            {
                "работа": "тюнинг и доработка грузовиков",
                "что_делаем": "установка дополнительного оборудования, подготовка к рейсу, ремонт",
                "суть": "показать клиентам, как мы заботимся о технике и качестве"
            },
            {
                "работа": "подготовка автопарка к сезону",
                "что_делаем": "проверка холодильных установок, ревизия техники перед пиком нагрузки",
                "суть": "техника проходит строгую проверку, чтобы рейсы шли без срывов"
            },
            {
                "работа": "работа диспетчерской",
                "что_делаем": "координация рейсов, контроль температур, связь с водителями",
                "суть": "показываем, как устроена наша логистика изнутри"
            },
        ])
    elif topic == "итоги_недели":
        facts = {
            "рейсов": 12,
            "км": 7200,
            "тонн": 45,
            "нарушений": 0
        }
    return facts

def get_random_media(topic=""):
    folder = "assets/photos"
    # Для фото машин и процессов используем только изображения, не видео
    extensions = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
    media_files = []
    for ext in extensions:
        media_files.extend(glob.glob(f"{folder}/{ext}"))
    if not media_files:
        return None
    return random.choice(media_files)

# Темы, для которых генерируем изображение через ИИ (красивое оформление, без фото машин)
GENERATE_IMAGE_TOPICS = {
    "новости_компании",
    "отраслевые_новости",
    "законодательство",
    "совет_или_лайфхак",
    "вопрос_подписчикам",
    "итоги_недели",
}

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    today = datetime.now().weekday()
    topic, tone = DAYS_THEMES.get(today, ("итоги_недели", "дружеский"))
    facts = collect_facts(topic)
    history = load_post_history()
    post_data = generate_post(topic, tone, facts, history)
    text = post_data.get("text", "Не удалось сгенерировать пост.")
    image_prompt = post_data.get("image_prompt", "")
    image_overlay = post_data.get("image_text_overlay", "")

    if len(text) > 1000:
        text = text[:997] + "..."

    # Смешанная логика: оформительские темы — генерируем изображение,
    # «трудовые будни» и прочие — берём загруженное фото из папки.
    sent = False
    if topic in GENERATE_IMAGE_TOPICS:
        image_result = generate_image(image_prompt, image_overlay)
        if image_result:
            if image_result.startswith("assets/"):
                with open(image_result, "rb") as f:
                    await app.bot.send_photo(chat_id=CHANNEL_ID, photo=f, caption=text)
                try:
                    os.remove(image_result)
                except OSError:
                    pass
            else:
                await app.bot.send_photo(chat_id=CHANNEL_ID, photo=image_result, caption=text)
            sent = True

    if not sent:
        media_path = get_random_media(topic)
        if media_path:
            with open(media_path, "rb") as f:
                await app.bot.send_photo(chat_id=CHANNEL_ID, photo=f, caption=text)
        else:
            await app.bot.send_message(chat_id=CHANNEL_ID, text=text)

    remember_post(text)
    await app.bot.send_message(chat_id=LOGIST_TG_ID, text="✅ Пост опубликован в канале")
    print("Пост опубликован в канале")

    # По воскресеньям (день 6) дополнительно генерируем статью для Дзена на модерацию
    if today == 6:
        try:
            import articles
            await articles.generate_and_send_article(app)
        except Exception as e:
            print(f"[ERROR] Не удалось сгенерировать статью: {e}")

if __name__ == "__main__":
    asyncio.run(main())
