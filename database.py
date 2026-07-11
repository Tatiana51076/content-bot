import sqlite3

DB_PATH = "content_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS news
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       title TEXT, summary TEXT, effective_date TEXT,
                       affects TEXT, source TEXT, used INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def get_unused_news():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM news WHERE used = 0 LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return [{"id": row[0], "title": row[1], "summary": row[2],
                 "effective_date": row[3], "affects": row[4], "source": row[5]}]
    return []

def mark_news_used(news_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE news SET used = 1 WHERE id = ?", (news_id,))
    conn.commit()
    conn.close()

def get_photos():
    return []
