import os
import json
import requests
from datetime import datetime
from database import get_photos, get_unused_news, mark_news_used

# ---------- Настройки (берутся из секретов или заданы по умолчанию) ----------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BRAND_NAME = os.getenv("BRAND_NAME", "24 Градуса")
# Цвета бренда — список, храним как JSON-строку в переменной окружения или задаём жёстко
try:
    BRAND_COLORS = json.loads(os.getenv("BRAND_COLORS", '["#0C7281", "#043556", "#042134", "#FFFFFB"]'))
except Exception:
    BRAND_COLORS = ["#0C7281", "#043556", "#042134", "#FFFFFB"]

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
}
import asyncio
from telegram.ext import Application

# Берём токены из переменных окружения (секретов GitHub)
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOGIST_TG_ID = int(os.getenv("LOGIST_TG_ID", "123456789"))

# Темы по дням (можно оставить жёстко, это не секрет)
DAYS_THEMES = {
    0: ("итоги_недели", "дружеский"),      # Пн
    1: ("рейс_недели", "дружеский"),        # Вт
    2: ("законодательство", "деловой"),     # Ср
    3: ("команда", "дружеский"),            # Чт
    4: ("лайфхак", "дружеский"),            # Пт
    5: ("погода", "дружеский"),             # Сб
    6: ("поздравление", "дружеский"),       # Вс
}

async def main():
    # Создаём приложение бота
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Определяем тему дня
    today = datetime.now().weekday()
    topic, tone = DAYS_THEMES.get(today, ("итоги_недели", "дружеский"))
    
    # Собираем факты и генерируем пост
    facts = collect_facts(topic)
    post_data = generate_post(topic, tone, facts)
    text = post_data.get("text", "Не удалось сгенерировать пост.")
    
    # Отправляем логисту на утверждение
    await app.bot.send_message(chat_id=LOGIST_TG_ID, text=text)
    print("Пост отправлен на утверждение")

if __name__ == "__main__":
    asyncio.run(main())
# ... (оставьте все остальные функции generate_post, generate_image, collect_facts без изменений)
