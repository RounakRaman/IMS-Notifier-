"""
Database layer. We use Supabase (free tier, no expiry) via its Postgres URL.
Works with any Postgres-compatible DB, including a local sqlite fallback for
dev convenience.

Two tables:
  keywords(id, keyword, created_at)
  seen_notifications(hash_id, date, text, link, matched_keyword, sent_at)
  devices(id, fcm_token, created_at)  -- FCM registration tokens for the Android app
"""

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

if USE_POSTGRES:
    import psycopg
    # psycopg wants postgresql:// not postgres://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SQLITE_PATH = os.environ.get("SQLITE_PATH", "ims_notifier.db")


@contextmanager
def get_conn():
    if USE_POSTGRES:
        conn = psycopg.connect(DATABASE_URL, autocommit=False)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _placeholder() -> str:
    return "%s" if USE_POSTGRES else "?"


def init_db() -> None:
    ph = _placeholder()
    with get_conn() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS keywords (
                    id SERIAL PRIMARY KEY,
                    keyword TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS seen_notifications (
                    hash_id TEXT PRIMARY KEY,
                    date TEXT,
                    text TEXT NOT NULL,
                    link TEXT,
                    matched_keyword TEXT,
                    sent_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id SERIAL PRIMARY KEY,
                    fcm_token TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL UNIQUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS seen_notifications (
                    hash_id TEXT PRIMARY KEY,
                    date TEXT,
                    text TEXT NOT NULL,
                    link TEXT,
                    matched_keyword TEXT,
                    sent_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fcm_token TEXT NOT NULL UNIQUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
    logger.info("Database initialized (postgres=%s)", USE_POSTGRES)


# Keywords
def add_keyword(keyword: str) -> bool:
    ph = _placeholder()
    keyword = keyword.strip().upper()
    if not keyword:
        return False
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(f"INSERT INTO keywords (keyword) VALUES ({ph})", (keyword,))
        return True
    except Exception as e:
        logger.warning("Failed to add keyword %s: %s", keyword, e)
        return False


def remove_keyword(keyword: str) -> bool:
    ph = _placeholder()
    keyword = keyword.strip().upper()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM keywords WHERE keyword = {ph}", (keyword,))
        return cur.rowcount > 0


def list_keywords() -> List[str]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT keyword FROM keywords ORDER BY keyword")
        rows = cur.fetchall()
    if USE_POSTGRES:
        return [r[0] for r in rows]
    return [r["keyword"] for r in rows]


# Seen notifications
def is_seen(hash_id: str) -> bool:
    ph = _placeholder()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM seen_notifications WHERE hash_id = {ph}", (hash_id,))
        return cur.fetchone() is not None


def mark_seen(
    hash_id: str,
    date: str,
    text: str,
    link: Optional[str],
    matched_keyword: str,
) -> None:
    ph = _placeholder()
    with get_conn() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute(
                f"""INSERT INTO seen_notifications (hash_id, date, text, link, matched_keyword)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
                    ON CONFLICT (hash_id) DO NOTHING""",
                (hash_id, date, text, link, matched_keyword),
            )
        else:
            cur.execute(
                f"""INSERT OR IGNORE INTO seen_notifications
                    (hash_id, date, text, link, matched_keyword)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph})""",
                (hash_id, date, text, link, matched_keyword),
            )


def recent_matches(limit: int = 50) -> List[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT hash_id, date, text, link, matched_keyword, sent_at "
            "FROM seen_notifications ORDER BY sent_at DESC LIMIT "
            + str(int(limit))
        )
        rows = cur.fetchall()
    if USE_POSTGRES:
        return [
            {
                "hash_id": r[0],
                "date": r[1],
                "text": r[2],
                "link": r[3],
                "matched_keyword": r[4],
                "sent_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ]
    return [dict(r) for r in rows]


# Devices (FCM tokens)
def register_device(fcm_token: str) -> bool:
    ph = _placeholder()
    fcm_token = fcm_token.strip()
    if not fcm_token:
        return False
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            if USE_POSTGRES:
                cur.execute(
                    f"INSERT INTO devices (fcm_token) VALUES ({ph}) "
                    f"ON CONFLICT (fcm_token) DO NOTHING",
                    (fcm_token,),
                )
            else:
                cur.execute(
                    f"INSERT OR IGNORE INTO devices (fcm_token) VALUES ({ph})",
                    (fcm_token,),
                )
        return True
    except Exception as e:
        logger.warning("Failed to register device: %s", e)
        return False


def unregister_device(fcm_token: str) -> None:
    """Called when FCM reports a token as invalid/unregistered."""
    ph = _placeholder()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM devices WHERE fcm_token = {ph}", (fcm_token,))


def list_device_tokens() -> List[str]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT fcm_token FROM devices")
        rows = cur.fetchall()
    if USE_POSTGRES:
        return [r[0] for r in rows]
    return [r["fcm_token"] for r in rows]
