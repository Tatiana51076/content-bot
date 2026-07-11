import sqlite3
from datetime import datetime
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheduled_date DATE NOT NULL,
            day_theme TEXT NOT NULL,
            tone TEXT DEFAULT 'friendly',
            title TEXT,
            text TEXT NOT NULL,
            image_url TEXT,
            image_source TEXT DEFAULT 'ai',
            status TEXT DEFAULT 'pending',
            published_at TIMESTAMP,
            moderation_msg_id INTEGER,
            telegram_msg_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_name TEXT,
            file_url TEXT NOT NULL,
            tag TEXT,
            source TEXT DEFAULT 'driver',
            quality_score REAL DEFAULT 0,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS legal_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source TEXT,
            url TEXT UNIQUE,
            summary TEXT,
            effective_date TEXT,
            affects TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS drivers (
            tg_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            photo_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS moderation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            action TEXT,
            comment TEXT,
            acted_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Настройки по умолчанию
    defaults = {
        "brand_colors": " ".join(
            ["#0C7281", "#043556", "#042134", "#FFFFFB"]
        ),
        "brand_name": "24 Градуса",
        "auto_post": "false",
        "post_time": "08:00",
        "telegram_channel": "",
        "logist_tg_id": "",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )

    conn.commit()
    conn.close()


# ====== ПОСТЫ ======

def save_post(date, theme, tone, text, image_url, image_source="ai"):
    conn = get_conn()
    conn.execute(
        """INSERT INTO posts
           (scheduled_date, day_theme, tone, text, image_url, image_source)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (date, theme, tone, text, image_url, image_source)
    )
    conn.commit()
    post_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return post_id


def get_post(post_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_post_status(post_id, status, msg_id=None):
    conn = get_conn()
    if msg_id:
        conn.execute(
            "UPDATE posts SET status = ?, telegram_msg_id = ?, "
            "published_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, msg_id, post_id)
        )
    else:
        conn.execute(
            "UPDATE posts SET status = ? WHERE id = ?",
            (status, post_id)
        )
    conn.commit()
    conn.close()


def get_today_post(date):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM posts WHERE scheduled_date = ? ORDER BY id DESC LIMIT 1",
        (date,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_posts():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM posts WHERE status = 'pending' ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ====== ФОТО ======

def save_photo(driver_name, file_url, tag, source="driver"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO photos (driver_name, file_url, tag, source) "
        "VALUES (?, ?, ?, ?)",
        (driver_name, file_url, tag, source)
    )
    conn.execute(
        "UPDATE drivers SET photo_count = photo_count + 1 WHERE name = ?",
        (driver_name,)
    )
    conn.commit()
    conn.close()


def get_photos(tag=None, limit=10):
    conn = get_conn()
    if tag:
        rows = conn.execute(
            "SELECT * FROM photos WHERE tag = ? AND used = 0 "
            "ORDER BY quality_score DESC LIMIT ?",
            (tag, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM photos WHERE used = 0 "
            "ORDER BY quality_score DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_photo_used(photo_id):
    conn = get_conn()
    conn.execute("UPDATE photos SET used = 1 WHERE id = ?", (photo_id,))
    conn.commit()
    conn.close()


# ====== ВОДИТЕЛИ ======

def register_driver(tg_id, name):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO drivers (tg_id, name) VALUES (?, ?)",
        (tg_id, name)
    )
    conn.commit()
    conn.close()


def get_driver_rating():
    conn = get_conn()
    rows = conn.execute(
        "SELECT name, photo_count FROM drivers "
        "ORDER BY photo_count DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ====== НОВОСТИ ======

def save_legal_news(title, source, url, summary="",
                    effective_date="", affects=""):
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO legal_news
               (title, source, url, summary, effective_date, affects)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, source, url, summary, effective_date, affects)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # уже есть
    finally:
        conn.close()


def get_unused_news():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM legal_news WHERE status = 'new' ORDER BY id DESC LIMIT 1"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_news_used(news_id):
    conn = get_conn()
    conn.execute(
        "UPDATE legal_news SET status = 'used' WHERE id = ?", (news_id,)
    )
    conn.commit()
    conn.close()


# ====== НАСТРОЙКИ ======

def get_setting(key):
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


# ====== ЛОГ ======

def log_moderation(post_id, action, comment="", acted_by="logist"):
    conn = get_conn()
    conn.execute(
        """INSERT INTO moderation_log
           (post_id, action, comment, acted_by)
           VALUES (?, ?, ?, ?)""",
        (post_id, action, comment, acted_by)
    )
    conn.commit()
    conn.close()
