"""
Планировщик задач.
Запускать в фоне: python scheduler.py
"""

import asyncio
import logging
from datetime import datetime, time, timedelta

from telegram.ext import Application
from config import BOT_TOKEN, POST_TIME
from bot import auto_generate_daily_post

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def daily_post_job(app: Application):
    """Задача: генерация поста каждый день в POST_TIME."""
    logger.info("Running daily post generation...")
    await auto_generate_daily_post(app)
    logger.info("Daily post generation completed.")


async def daily_rss_job():
    """Задача: парсинг RSS раз в день."""
    logger.info("Running RSS parser...")
    from rss_parser import parse_all
    parse_all()
    logger.info("RSS parser completed.")


async def schedule_tasks(app: Application):
    """Планирует задачи на день."""
    now = datetime.now()

    # Время запуска генерации поста
    hour, minute = map(int, POST_TIME.split(":"))
    post_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Если время уже прошло — планируем на завтра
    if now > post_time:
        post_time += timedelta(days=1)
        logger.info(f"Post time passed, scheduling for tomorrow {post_time}")

    delay = (post_time - now).total_seconds()
    logger.info(f"Next post generation at {post_time} (in {delay:.0f}s)")

    await asyncio.sleep(delay)

    while True:
        await daily_post_job(app)
        await daily_rss_job()

        # Ждём до следующего дня
        await asyncio.sleep(24 * 3600)


async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    await app.initialize()
    await app.start()

    logger.info("Scheduler started.")

    try:
        await schedule_tasks(app)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
