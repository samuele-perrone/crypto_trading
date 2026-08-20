"""
Position state storage, backed by a local SQLite file.

The database path comes from BOT_DB_PATH; otherwise it defaults to
bot_state.db next to this file.

WARNING for serverless deploys: on Vercel only /tmp is writable, and it is
wiped between invocations. There the store falls back to /tmp/bot_state.db
and every tick starts with an empty database — see is_ephemeral().
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

_REPO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.db")


def db_path():
    explicit = os.environ.get("BOT_DB_PATH")
    if explicit:
        return explicit
    if os.environ.get("VERCEL"):
        return "/tmp/bot_state.db"  # writable, but not persistent
    return _REPO_DB


def is_ephemeral():
    """True when state cannot survive to the next run (serverless /tmp)."""
    return bool(os.environ.get("VERCEL")) and not os.environ.get("BOT_DB_PATH")


def _connect():
    path = db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("""
        create table if not exists bot_state (
          key        text primary key,
          value      text,
          updated_at text
        )
    """)
    return conn


def load_position(key):
    """Return the stored position dict, or None if there is no open position."""
    with _connect() as conn:
        row = conn.execute("select value from bot_state where key = ?", (key,)).fetchone()
    if row is None or row[0] is None:
        return None
    return json.loads(row[0])


def save_position(key, position):
    """Store a position dict, or None to clear it."""
    with _connect() as conn:
        conn.execute(
            "insert into bot_state (key, value, updated_at) values (?, ?, ?) "
            "on conflict(key) do update set value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, json.dumps(position), datetime.now(timezone.utc).isoformat()),
        )
