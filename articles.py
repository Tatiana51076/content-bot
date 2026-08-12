"""
Еженедельная генерация статей для Дзен-канала.
Статья генерируется по воскресеньям и отправляется в Telegram логисту для модерации
перед публикацией на https://dzen.ru/globaltruck.online
"""

import os
import json
import glob
import random
import requests
from datetime import datetime

# --- Конфигурация (наследуется из генератора) ---

def _env_brand():
    return os.getenv("BRAND_NAME", "ГлобалТракГарант")

def _env_colors():
    try:
        return json.loads(os.getenv("BRAND_COLORS", '["#0C7281", "#043556", "#042134", "#FFFFFB"]'))
    except Exception:
        return ["#0C7281", "#043556", "#042134", "#FFFFFB"]

DZEN_LINK = os.getenv("DZEN_LINK", "https://dzen.ru/globaltruck.online?share_to=link")
ARTICLE_MODEL = os.getenv("ARTICLE_MODEL") or os.getenv("LLM_MODEL", "deepseek/deepseek-v4-flash")
LOGIST_TG_ID = int(os.getenv("LOGIST_TG_ID", "123456789"))

# Состояние: файл с последними использованными темами (хранится в репозитории между запусками)
STATE_FILE = "article_state.json"

# --- Банк тем (без повторов подряд) ---

ARTICLE_TOPICS = [
    {
        "key": "zakonodatelstvo",
        "title": "Новости и изменения законодательства в логистике",
        "brief": "Свежие изменения законодательства для перевозчиков, ответственность за неисполнение новых требований (штрафы, лишение лицензий, приостановка деятельности).",
    },
    {
        "key": "krazhi",
        "title": "Схемы кражи грузов: как избежать",
        "brief": "Основные схемы хищений грузов в транспортной логистике, красные флаги, почему важно выбирать проверенного перевозчика и как проверить контрагента.",
    },
    {
        "key": "goslog",
        "title": "ГОСЛОГ и электронные ТТН: как работать без ошибок",
        "brief": "Государственная информационная система электронных перевозочных документов, электронные ТТН, как правильно вести документооборот и какие ошибки дорого обходятся.",
    },
    {
        "key": "rejim_temperatury",
        "title": "Рефрижераторные перевозки: контроль температуры",
        "brief": "Почему важен строгий температурный режим, датчики, мониторинг в реальном времени, последствия срыва режима для продуктов и фармацевтики.",
    },
    {
        "key": "kak_vibrat",
        "title": "Как выбрать перевозчика: чек-лист грузовладельца",
        "brief": "Практический чек-лист выбора надёжного перевозчика: документы, страховка, автопарк, опыт, отзывы, что проверить до подписания договора.",
    },
    {
        "key": "sryv_srokov",
        "title": "Срывы сроков доставки: причины и профилактика",
        "brief": "Почему срываются сроки доставки, кто за это отвечает, как логисту минимизировать риски и построить процессы без простоев.",
    },
    {
        "key": "tahografy",
        "title": "Тахографы и режим труда водителей",
        "brief": "Требования к тахографам, режим труда и отдыха водителей, штрафы за нарушения, как компании соблюдать нормы без потери эффективности.",
    },
    {
        "key": "strahovanie",
        "title": "Страхование грузов: что покрывает полис",
        "brief": "Виды страхования грузов в логистике, что покрывает страховка, подводные камни и как грамотно застраховать груз.",
    },
    {
        "key": "skrytye_tarify",
        "title": "Скрытые тарифы в перевозках: как не переплатить",
        "brief": "Какие доплаты возникают после заключения договора, как распознать недобросовестные схемы и построить прозрачную смету перевозки.",
    },
    {
        "key": "mps",
        "title": "Маркировка и прослеживаемость грузов",
        "brief": "Требования к маркировке товаров, система прослеживаемости, как это влияет на перевозчика и что нужно знать логисту.",
    },
]

# --- Выбор темы без повторов ---

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def pick_topic():
    # Если задана ручная тема через переменные окружения — используем её (для тестов и по запросу)
    custom_title = os.getenv("ARTICLE_CUSTOM_TITLE")
    custom_brief = os.getenv("ARTICLE_CUSTOM_BRIEF")
    if custom_title:
        return {"key": "custom", "title": custom_title, "brief": custom_brief or custom_title}
    state = load_state()
    recent = state.get("recent_keys", [])
    available = [t for t in ARTICLE_TOPICS if t["key"] not in recent]
    if not available:
        available = ARTICLE_TOPICS
    topic = random.choice(available)
    state["recent_keys"] = (recent + [topic["key"]])[-4:]
    state["last_used"] = datetime.now().strftime("%d.%m.%Y")
    save_state(state)
    return topic

# --- Генерация статьи ---

def generate_article(topic):
    api_key = os.getenv("OPENAI_LIKE_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    api_base = os.getenv("OPENAI_LIKE_API_BASE_URL") or "https://api.vsellm.ru/v1"
    brand = _env_brand()
    colors = ", ".join(_env_colors())
    today = datetime.now().strftime("%d.%m.%Y")

    prompt = f"""
Ты — ведущий копирайтер и редактор с опытом более 10 лет в транспортной логистике.
Ты пишешь экспертные статьи для Дзен-канала компании «{brand}» ({DZEN_LINK}).
Твоя аудитория: грузовладельцы, логисты, коммерческие директора, владельцы бизнеса, перевозчики.
Ты знаешь все тонкости и нюансы работы в транспортной логистике: законодательство, документооборот,
риски, страхование, тарифы, контроль температуры, работу с ГОСЛОГ и электронными ТТН.

Задача: написать качественную статью на тему:
«{topic['title']}»
Краткое содержание: {topic['brief']}

Требования к статье:
- Объём: 4000-6000 знаков (с пробелами).
- Пиши как опытный практик, который реально работал в логистике: конкретика, примеры, цифры, без «воды».
- Структура: заголовок, затем введение, 4-6 смысловых разделов с подзаголовками, заключение с рекомендациями.
- Подзаголовки оформляй как строки с «##» в начале (например: ## Как не попасть на штрафы).
- Тон: экспертный, уверенный, полезный. Избегай рекламных лозунгов и общих фраз.
- Упомяни компанию «{brand}» уместно, но не навязчиво (1-2 раза, как пример практики или экспертности).
- В конце добавь раздел «Заключение» с практическими рекомендациями.
- Не используй эмодзи и markdown-жирность.

Формат ответа — строгий JSON (без markdown, без пояснений):
{{
    "title": "заголовок статьи (до 120 знаков, цепляющий)",
    "text": "полный текст статьи с подзаголовками ##, от 4000 до 6000 знаков"
}}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_err = None
    for attempt in range(3):
        try:
            response = requests.post(
                f"{api_base}/chat/completions",
                headers=headers,
                json={
                    "model": ARTICLE_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 4000,
                    "temperature": 0.8,
                },
                timeout=300,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            print(f"[DEBUG] Article raw response (first 300):\n{content[:300]}")

            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
            elif content.startswith("```"):
                content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
            if content.startswith("\ufeff"):
                content = content[1:]
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                end = content.rfind("}")
                if end != -1:
                    try:
                        return json.loads(content[: end + 1])
                    except Exception:
                        pass
                raise ValueError("Invalid JSON from model for article")
        except Exception as e:
            last_err = e
            print(f"[ERROR] Article generation error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                import time
                time.sleep(10)
    print("[ERROR] Article generation failed after 3 attempts")
    return None

# --- Отправка статьи на модерацию: email (SMTP) + файл в репозитории ---

def send_article_email(title, text, topic):
    """Отправка статьи на email через SMTP (Mail.ru или Yandex)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header
    from email.utils import formataddr

    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    mail_to = os.getenv("MAIL_TO") or smtp_user
    smtp_host = os.getenv("SMTP_HOST", "smtp.mail.ru")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    if not smtp_user or not smtp_pass:
        print("[EMAIL] SMTP_USER/SMTP_PASSWORD не заданы, пропускаю email")
        return False

    today = datetime.now().strftime("%d.%m.%Y")
    body = (
        f"Тема статьи: {topic['title']}\n"
        f"Дата: {today}\n"
        f"Канал Дзен: {DZEN_LINK}\n\n"
        f"=== {title} ===\n\n"
        f"{text}\n\n"
        f"---\nСтатья для модерации. Опубликуйте её в Дзене самостоятельно."
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(f"Статья для Дзена — {today}", "utf-8")
    msg["From"] = formataddr((str(Header("Контент-бот", "utf-8")), smtp_user))
    msg["To"] = mail_to

    try:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=60)
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [mail_to], msg.as_string())
        server.quit()
        print(f"[EMAIL] Статья отправлена на {mail_to} через {smtp_host}")
        return True
    except Exception as e:
        print(f"[EMAIL] Ошибка отправки письма: {e}")
        return False


def save_article_to_file(title, text, topic):
    """Сохраняет статью в файл .md в папке articles/ репозитория (для модерации в GitHub)."""
    import re
    today = datetime.now().strftime("%Y-%m-%d")
    safe_title = re.sub(r'[\\/:*?"<>|]+', '', title)[:60].strip() or "statya"
    os.makedirs("articles", exist_ok=True)
    fname = f"articles/{today}_{safe_title}.md"
    content = (
        f"# {title}\n\n"
        f"**Дата:** {datetime.now().strftime('%d.%m.%Y')}  \n"
        f"**Тема:** {topic['title']}  \n"
        f"**Канал Дзен:** {DZEN_LINK}  \n\n"
        f"---\n\n"
        f"{text}\n\n"
        f"---\n\n"
        f"*Статья сгенерирована автоматически. Проверьте и опубликуйте в Дзене самостоятельно.*"
    )
    with open(fname, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[FILE] Статья сохранена: {fname}")
    return fname


async def send_article(app, article, topic):
    title = article.get("title", "").strip()
    text = article.get("text", "").strip()
    if not text:
        print("[ERROR] Empty article text")
        return False

    # Основной способ — email на почту
    email_ok = send_article_email(title, text, topic)

    # Запасной способ — сохранить в файл репозитория и прислать ссылку в Telegram
    fname = save_article_to_file(title, text, topic)
    repo = os.getenv("GITHUB_REPOSITORY", "Tatiana51076/content-bot")
    url = f"https://github.com/{repo}/blob/main/{fname}"
    raw_url = f"https://raw.githubusercontent.com/{repo}/main/{fname}"

    message = (
        f"📰 Новая статья для Дзен — {datetime.now().strftime('%d.%m.%Y')}\n"
        f"📌 Тема: {topic['title']}\n"
        f"🔗 Канал: {DZEN_LINK}\n\n"
        f"**{title}**\n\n"
        f"{'✅ Отправлена на почту.' if email_ok else '⚠️ Почта не сработала.'}\n"
        f"Резервная копия в репозитории:\n"
        f"{url}\n\n"
        f"Быстрый просмотр (без входа): {raw_url}\n\n"
        f"---\n⚠️ Статья для модерации. Опубликуйте её в Дзене самостоятельно."
    )

    await app.bot.send_message(chat_id=LOGIST_TG_ID, text=message)
    print("Уведомление о статье отправлено логисту")
    return email_ok or True

async def generate_and_send_article(app):
    """Генерирует статью по воскресеньям и отправляет её логисту."""
    topic = pick_topic()
    print(f"[ARTICLE] Topic: {topic['title']}")
    article = generate_article(topic)
    if article is None:
        print("[ERROR] Не удалось сгенерировать статью")
        return False
    return await send_article(app, article, topic)


async def main():
    from telegram.ext import Application
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("[ERROR] BOT_TOKEN не задан")
        return
    app = Application.builder().token(token).build()
    ok = await generate_and_send_article(app)
    print("Готово:", ok)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
