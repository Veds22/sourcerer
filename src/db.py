"""SQLite schema and connection management for the sourcerer DB."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable

DB_PATH = Path(__file__).parent.parent / "data" / "sourcerer.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    referral TEXT,
    status TEXT NOT NULL DEFAULT 'applied',
    applied_date TEXT NOT NULL,
    last_update_date TEXT NOT NULL,
    deadline TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS application_status_history (
    id INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    status TEXT NOT NULL,
    changed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reading_items (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT,
    url TEXT,
    summary TEXT,
    tags TEXT,
    raw_content_ref TEXT,
    saved_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT,
    tags TEXT,
    saved_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    due_date TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    application_id INTEGER REFERENCES applications(id),
    reading_item_id INTEGER REFERENCES reading_items(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    direction TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and foreign keys enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def log_message(direction: str, content: str, tool_calls: str | None = None) -> int:
    """Insert one message row (inbound/outbound/summary) and return its id."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO messages (direction, content, tool_calls) VALUES (?, ?, ?)",
        (direction, content, tool_calls),
    )
    conn.commit()
    message_id = cursor.lastrowid
    conn.close()
    return message_id


def get_recent_messages(limit: int = 10) -> list[dict]:
    """Fetch the last N messages, oldest first, for injecting into LLM context."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]


def clear_message_history() -> int:
    """Delete all messages. Returns the number of rows deleted. Not LLM-invokable by design."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM messages")
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted


def summarize_and_trim(
    summarizer_fn: Callable[[list[dict]], str],
    keep_recent: int = 200,
    chunk_size: int = 100,
) -> dict:
    """Collapse the oldest chunk of messages into one summary row once the table grows past keep_recent.

    summarizer_fn takes a list of message dicts and returns a summary string;
    it's injected so this module never imports the LLM client directly.
    """
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"]

    if total <= keep_recent:
        conn.close()
        return {"trimmed": False, "total": total}

    oldest_rows = conn.execute(
        "SELECT * FROM messages ORDER BY created_at ASC LIMIT ?", (chunk_size,)
    ).fetchall()
    oldest_dicts = [dict(row) for row in oldest_rows]
    oldest_ids = [row["id"] for row in oldest_rows]

    summary_text = summarizer_fn(oldest_dicts)

    placeholders = ",".join("?" * len(oldest_ids))
    conn.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", oldest_ids)
    conn.execute(
        "INSERT INTO messages (direction, content) VALUES ('summary', ?)",
        (summary_text,),
    )
    conn.commit()
    conn.close()
    return {"trimmed": True, "chunk_size": len(oldest_ids), "summary": summary_text}


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")