"""
Position state storage: a SQLite file, optionally kept durable in Vercel Blob.

Off Vercel the file simply lives on disk. On Vercel only /tmp is writable and
it is wiped between invocations, so when BLOB_READ_WRITE_TOKEN is present the
file is pulled from Blob before every read and pushed back after every write.
The database is still an ordinary SQLite file; Blob is only where it rests
between ticks.

Environment:
    BOT_DB_PATH         local SQLite path (default: repo file, or /tmp when
                        Blob-backed, where it is just a scratch copy)
    BLOB_READ_WRITE_TOKEN   enables Blob syncing (set by `vercel blob create-store`)
    BOT_BLOB_PATHNAME   object name in the store
                        (default: "<VERCEL_ENV>/bot_state.db", so a local run
                        cannot clobber production's position)

A pull that fails raises rather than falling back to an empty database: acting
on "no position" when the real state is unknown is how a bot forgets it is
holding and buys again.
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timezone

import requests

_BLOB_API = "https://blob.vercel-storage.com"
_BLOB_API_VERSION = "12"
_TIMEOUT = 15
_PULL_RETRIES = 3      # extra reads when a 404 contradicts the list API
_RETRY_SLEEP = 1.0     # seconds, multiplied by the attempt number

_REPO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.db")


# ---------------------------------------------------------------------------
# Vercel Blob (durable resting place for the SQLite file)
# ---------------------------------------------------------------------------

def _token():
    return os.environ.get("BLOB_READ_WRITE_TOKEN")


def blob_enabled():
    return bool(_token())


def _blob_pathname():
    explicit = os.environ.get("BOT_BLOB_PATHNAME")
    if explicit:
        return explicit
    return f"{os.environ.get('VERCEL_ENV') or 'development'}/bot_state.db"


def _blob_url(token):
    # Token format: vercel_blob_rw_<storeId>_<random>; the host is the store id
    # lowercased, which is how the official SDK derives it too.
    store_id = token.split("_")[3].lower()
    return f"https://{store_id}.private.blob.vercel-storage.com/{_blob_pathname()}"


def _blob_exists():
    """Authoritative existence check via the list API (not the cached CDN read)."""
    token = _token()
    pathname = _blob_pathname()
    r = requests.get(f"{_BLOB_API}/",
                     params={"prefix": pathname, "limit": "100"},
                     headers={"Authorization": f"Bearer {token}",
                              "x-api-version": _BLOB_API_VERSION},
                     timeout=_TIMEOUT)
    r.raise_for_status()
    return any(b.get("pathname") == pathname for b in r.json().get("blobs", []))


def _get_blob(token):
    return requests.get(_blob_url(token),
                        headers={"Authorization": f"Bearer {token}"},
                        # Blob reads are CDN-cached and will serve a stale file
                        # otherwise -- a stale position is a wrong trade.
                        params={"cb": str(time.time_ns())},
                        timeout=_TIMEOUT)


def _pull(path):
    """Fetch the SQLite file from Blob. Returns False when none is stored yet.

    Blob reads are eventually consistent: an object that definitely exists was
    observed returning 404 on roughly one read in eight. A 404 is therefore
    never taken at face value, because "no state" is the dangerous wrong
    answer -- it makes the bot buy again while already holding, and never sell
    what it holds. Absence is confirmed against the list API, and a 404 for an
    object that does exist is retried and then raised.
    """
    token = _token()
    r = _get_blob(token)
    if r.status_code == 200:
        with open(path, "wb") as f:
            f.write(r.content)
        return True
    if r.status_code != 404:
        r.raise_for_status()

    if not _blob_exists():
        # Genuinely nothing stored yet (first run, or state deliberately cleared).
        if os.path.exists(path):
            os.remove(path)  # don't let a leftover /tmp copy masquerade as state
        return False

    for attempt in range(_PULL_RETRIES):
        time.sleep(_RETRY_SLEEP * (attempt + 1))
        r = _get_blob(token)
        if r.status_code == 200:
            with open(path, "wb") as f:
                f.write(r.content)
            return True
    raise RuntimeError(
        f"{_blob_pathname()} exists but returned 404 on "
        f"{_PULL_RETRIES + 1} reads; refusing to assume there is no position"
    )


def delete_blob():
    """Remove the stored state object entirely. Used by the rehearsal cleanup."""
    token = _token()
    r = requests.post(f"{_BLOB_API}/delete",
                      headers={"Authorization": f"Bearer {token}",
                               "x-api-version": _BLOB_API_VERSION,
                               "Content-Type": "application/json"},
                      json={"urls": [_blob_url(token)]}, timeout=_TIMEOUT)
    r.raise_for_status()


def _push(path):
    token = _token()
    with open(path, "rb") as f:
        body = f.read()
    r = requests.put(f"{_BLOB_API}/",
                     params={"pathname": _blob_pathname()},
                     headers={
                         "Authorization": f"Bearer {token}",
                         "x-api-version": _BLOB_API_VERSION,
                         "x-vercel-blob-access": "private",
                         "x-add-random-suffix": "0",
                         "x-allow-overwrite": "1",
                         "x-cache-control-max-age": "0",
                         "Content-Type": "application/octet-stream",
                     },
                     data=body, timeout=_TIMEOUT)
    r.raise_for_status()


# ---------------------------------------------------------------------------
# Local SQLite file
# ---------------------------------------------------------------------------

def db_path():
    explicit = os.environ.get("BOT_DB_PATH")
    if explicit:
        return explicit
    if blob_enabled() or os.environ.get("VERCEL"):
        return "/tmp/bot_state.db"
    return _REPO_DB


def is_ephemeral():
    """True when state cannot survive to the next run."""
    return bool(os.environ.get("VERCEL")) and not blob_enabled()


def state_location():
    """Human-readable description of where state actually rests."""
    if blob_enabled():
        return f"vercel-blob:{_blob_pathname()}"
    return db_path()


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
    if blob_enabled():
        _pull(db_path())
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
    if blob_enabled():
        _push(db_path())
