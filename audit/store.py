import json
import sqlite3
import threading
from datetime import datetime, timezone

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_db_path: str | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    started_at   TEXT NOT NULL,
    interface    TEXT,
    llm_provider TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    timestamp    TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    source       TEXT,
    content      TEXT,
    metadata     TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_session   ON audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_type      ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
"""

_MAX_CONTENT = 2000  # chars stored per entry


def _get_conn(db_path: str) -> sqlite3.Connection:
    global _conn, _db_path
    if _conn is None or _db_path != db_path:
        _conn = sqlite3.connect(db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _conn.commit()
        _db_path = db_path
    return _conn


def register_session(db_path: str, session_id: str, interface: str, llm_provider: str) -> None:
    conn = _get_conn(db_path)
    with _lock:
        conn.execute(
            "INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?)",
            (session_id, datetime.now(timezone.utc).isoformat(), interface, llm_provider),
        )
        conn.commit()


def log_event(
    db_path: str,
    session_id: str,
    event_type: str,
    source: str | None = None,
    content: str | None = None,
    metadata: dict | None = None,
) -> None:
    conn = _get_conn(db_path)
    truncated = content[:_MAX_CONTENT] if content else None
    meta_json = json.dumps(metadata) if metadata else None
    with _lock:
        conn.execute(
            "INSERT INTO audit_log (session_id, timestamp, event_type, source, content, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, datetime.now(timezone.utc).isoformat(), event_type, source, truncated, meta_json),
        )
        conn.commit()


def query_events(
    db_path: str,
    session_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    conn = _get_conn(db_path)
    clauses, params = [], []
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT id, session_id, timestamp, event_type, source, content, metadata "
        f"FROM audit_log {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return [dict(r) for r in rows]


def list_sessions(db_path: str) -> list[dict]:
    conn = _get_conn(db_path)
    rows = conn.execute(
        "SELECT s.session_id, s.started_at, s.interface, s.llm_provider, "
        "COUNT(a.id) AS event_count "
        "FROM sessions s LEFT JOIN audit_log a ON s.session_id = a.session_id "
        "GROUP BY s.session_id ORDER BY s.started_at DESC",
    ).fetchall()
    return [dict(r) for r in rows]


def get_session(db_path: str, session_id: str) -> dict | None:
    conn = _get_conn(db_path)
    row = conn.execute(
        "SELECT session_id, started_at, interface, llm_provider FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return dict(row) if row else None
