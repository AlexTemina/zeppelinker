from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

# Points at a Fly Volume mount in production (see fly.toml) so state survives
# restarts and deploys; defaults to a local file for dev.
STATE_DB_PATH = os.environ.get("STATE_DB_PATH", "state.db")

FIELD_NAMES = ["instagram", "medium", "reddit", "tiktok", "twitter", "youtube", "threads"]


@dataclass
class FixerState:
    instagram: bool = True
    medium: bool = True
    reddit: bool = True
    tiktok: bool = True
    twitter: bool = True
    youtube: bool = True
    threads: bool = True


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(STATE_DB_PATH)
    columns = ", ".join(f"{name} INTEGER NOT NULL DEFAULT 1" for name in FIELD_NAMES)
    conn.execute(f"CREATE TABLE IF NOT EXISTS fixer_state (chat_id INTEGER PRIMARY KEY, {columns})")
    conn.commit()
    return conn


_DB = _connect()

# chat_id -> FixerState, an in-memory cache over the sqlite table so every
# message doesn't need a disk read -- only writes (toggling a fixer) hit disk.
FIXER_STATE: dict[int, FixerState] = {}


def _load_from_db(chat_id: int) -> FixerState | None:
    row = _DB.execute(
        f"SELECT {', '.join(FIELD_NAMES)} FROM fixer_state WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    if row is None:
        return None
    return FixerState(**{name: bool(value) for name, value in zip(FIELD_NAMES, row)})


def get_state(chat_id: int) -> FixerState:
    if chat_id not in FIXER_STATE:
        FIXER_STATE[chat_id] = _load_from_db(chat_id) or FixerState()
    return FIXER_STATE[chat_id]


def set_field(chat_id: int, field: str, value: bool) -> None:
    state = get_state(chat_id)
    setattr(state, field, value)

    columns = ", ".join(FIELD_NAMES)
    placeholders = ", ".join("?" * len(FIELD_NAMES))
    updates = ", ".join(f"{name}=excluded.{name}" for name in FIELD_NAMES)
    values = [chat_id] + [int(getattr(state, name)) for name in FIELD_NAMES]
    _DB.execute(
        f"INSERT INTO fixer_state (chat_id, {columns}) VALUES (?, {placeholders}) "
        f"ON CONFLICT(chat_id) DO UPDATE SET {updates}",
        values,
    )
    _DB.commit()
