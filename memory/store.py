import sqlite3
import threading

from config import settings

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.memory_db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def remember_fact(key: str, value: str) -> None:
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT OR REPLACE INTO facts (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key.lower().strip(), value),
        )
        conn.commit()
        conn.close()


def recall_facts(query: str = "") -> dict[str, str]:
    with _lock:
        conn = _connect()
        if query:
            rows = conn.execute(
                "SELECT key, value FROM facts WHERE key LIKE ? OR value LIKE ?",
                (f"%{query.lower()}%", f"%{query.lower()}%"),
            ).fetchall()
        else:
            rows = conn.execute("SELECT key, value FROM facts").fetchall()
        conn.close()
    return {k: v for k, v in rows}
