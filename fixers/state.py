from __future__ import annotations

from dataclasses import dataclass

from db import connection

FIELD_NAMES = ["instagram", "medium", "reddit", "tiktok", "twitter", "youtube", "threads", "gol"]


@dataclass
class FixerState:
    instagram: bool = True
    medium: bool = True
    reddit: bool = True
    tiktok: bool = True
    twitter: bool = True
    youtube: bool = True
    threads: bool = True
    gol: bool = True


def _connect() -> None:
    conn = connection()
    columns = ", ".join(f"{name} INTEGER NOT NULL DEFAULT 1" for name in FIELD_NAMES)
    conn.execute(f"CREATE TABLE IF NOT EXISTS fixer_state (chat_id INTEGER PRIMARY KEY, {columns})")

    # Add any column that didn't exist yet in an already-deployed database
    # (e.g. "gol" added after the table was first created in production).
    existing = {row[1] for row in conn.execute("PRAGMA table_info(fixer_state)")}
    for name in FIELD_NAMES:
        if name not in existing:
            conn.execute(f"ALTER TABLE fixer_state ADD COLUMN {name} INTEGER NOT NULL DEFAULT 1")
    conn.commit()


_connect()
_DB = connection()

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
