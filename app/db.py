"""
db.py – Unified database layer.
Tries MySQL first; if unavailable, falls back to SQLite automatically.
SQLite uses '?' placeholders while MySQL uses '%s' — this module normalises them.
"""

import re
import os
import sqlite3

_backend = None          # 'mysql' | 'sqlite'
_sqlite_path = None      # resolved on first call inside app context


# ── Placeholder normalisation ──────────────────────────────────────────
def _to_sqlite(sql):
    """Convert %s placeholders to ? for SQLite."""
    return re.sub(r"%s", "?", sql)


# ── Connection helpers ─────────────────────────────────────────────────
def _get_mysql(cfg):
    import mysql.connector
    return mysql.connector.connect(
        host=cfg["DB_HOST"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"],
        autocommit=True,
        connection_timeout=5,
    )


def _get_sqlite(path):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Public API ─────────────────────────────────────────────────────────
def get_db():
    from flask import current_app, g
    global _backend, _sqlite_path

    if "db" in g:
        return g.db

    cfg = current_app.config

    # Determine / cache the backend once per process
    if _backend is None:
        try:
            conn = _get_mysql(cfg)
            conn.close()
            _backend = "mysql"
        except Exception as e:
            print(f"[db] MySQL unavailable ({e}). Using SQLite fallback.")
            _backend = "sqlite"
            _sqlite_path = os.path.join(
                os.path.dirname(__file__), "knowledgebase.db"
            )

    if _backend == "mysql":
        g.db = _get_mysql(cfg)
    else:
        g.db = _get_sqlite(_sqlite_path)

    return g.db


def close_db(e=None):
    from flask import g
    db = g.pop("db", None)
    if db is None:
        return
    if _backend == "mysql":
        if db.is_connected():
            db.close()
    else:
        db.close()


def query(sql, params=(), one=False, commit=False):
    """
    Execute *sql* with *params*.
    - commit=True  → INSERT/UPDATE/DELETE; returns lastrowid
    - commit=False → SELECT; returns one row (dict) or list of dicts
    """
    db = get_db()

    if _backend == "sqlite":
        sql = _to_sqlite(sql)
        cur = db.execute(sql, params)
        if commit:
            db.commit()
            return cur.lastrowid
        rows = cur.fetchone() if one else cur.fetchall()
        if rows is None:
            return None
        if one:
            return dict(rows)
        return [dict(r) for r in rows]
    else:
        cur = db.cursor(dictionary=True)
        cur.execute(sql, params)
        if commit:
            db.commit()
            return cur.lastrowid
        result = cur.fetchone() if one else cur.fetchall()
        cur.close()
        return result


# ── SQLite schema bootstrap ────────────────────────────────────────────
_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL,
  filename      TEXT NOT NULL,
  original_name TEXT NOT NULL,
  file_type     TEXT NOT NULL,
  uploaded_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_chunks (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id   INTEGER NOT NULL,
  chunk_text    TEXT NOT NULL,
  chunk_index   INTEGER NOT NULL,
  vector_id     INTEGER NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chats (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL,
  question    TEXT NOT NULL,
  answer      TEXT NOT NULL,
  sources     TEXT,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


def init_sqlite_schema():
    """Create all tables in the SQLite database (called once at startup)."""
    if _backend != "sqlite":
        return
    conn = sqlite3.connect(_sqlite_path)
    conn.executescript(_SQLITE_SCHEMA)
    conn.commit()
    conn.close()
    print("[db] SQLite schema initialised.")
