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

# ... (оставьте все остальные функции generate_post, generate_image, collect_facts без изменений)
