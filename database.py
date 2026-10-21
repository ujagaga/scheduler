import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import appsettings

DB_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), appsettings.SQLITE_PATH)


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def setup_db():
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                hours TEXT NOT NULL DEFAULT '',
                last_triggered TEXT
            );
        """)


def get_urls():
    with _db() as conn:
        urls = [dict(r) for r in conn.execute("SELECT id, url, hours, last_triggered FROM urls ORDER BY id")]
    for u in urls:
        u["hours"] = [int(h) for h in u["hours"].split(",") if h]
        if u["last_triggered"]:
            u["last_triggered"] = datetime.fromisoformat(u["last_triggered"])
    return urls


def add_url(url, hours):
    with _db() as conn:
        conn.execute("INSERT INTO urls (url, hours) VALUES (?, ?)", (url, ",".join(map(str, hours))))


def update_url(url_id, url, hours):
    with _db() as conn:
        conn.execute("UPDATE urls SET url = ?, hours = ? WHERE id = ?", (url, ",".join(map(str, hours)), url_id))


def delete_url(url_id):
    with _db() as conn:
        conn.execute("DELETE FROM urls WHERE id = ?", (url_id,))


def set_last_triggered(url_id, timestamp):
    with _db() as conn:
        conn.execute("UPDATE urls SET last_triggered = ? WHERE id = ?", (timestamp.isoformat(), url_id))
