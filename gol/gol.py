from __future__ import annotations

import random
from urllib.parse import urlsplit

from telegram import Bot, Message

import botext
from db import connection

_DB = connection()
_DB.execute(
    "CREATE TABLE IF NOT EXISTS seen_links (chat_id INTEGER NOT NULL, url_key TEXT NOT NULL, "
    "PRIMARY KEY (chat_id, url_key))"
)
_DB.commit()

MESSAGES = [
    "GOOOOOL GOLGOLGOLGOLGOLLLLLL ⚽🔥",
    "Buf golazo",
    "GOLGOLGOLGOLGOL",
    "gol",
]


def _normalize(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.rstrip("/").lower()
    return f"{host}{path}"


def check_and_record(chat_id: int, urls: list[str]) -> bool:
    """Record every url from this message as seen for this chat; return True
    if any of them had already been posted before."""
    seen_before = False
    for url in urls:
        key = _normalize(url)
        if not key:
            continue
        row = _DB.execute(
            "SELECT 1 FROM seen_links WHERE chat_id = ? AND url_key = ?", (chat_id, key)
        ).fetchone()
        if row is not None:
            seen_before = True
        else:
            _DB.execute(
                "INSERT INTO seen_links (chat_id, url_key) VALUES (?, ?)", (chat_id, key)
            )
    _DB.commit()
    return seen_before


async def handle(bot: Bot, message: Message) -> None:
    await botext.reply(bot, message, random.choice(MESSAGES))
