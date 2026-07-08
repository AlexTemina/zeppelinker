from __future__ import annotations

from urllib.parse import urlsplit

import httpx
from telegram import Bot, Message

import botext
from urlutils import get_urls_from_message

BASE_URL = "https://www.amputatorbot.com/api/v1/convert?gac=true&md=3&q="


def is_amp(url: str) -> bool:
    parts = urlsplit(url)
    host = parts.hostname
    if not host:
        return False
    path_segments = [s for s in parts.path.split("/") if s]
    if "amp" in path_segments:
        return True
    if host.endswith(".cdn.ampproject.org"):
        return True
    if parts.query and "amp" in parts.query:
        return True
    return False


async def handle(bot: Bot, message: Message) -> None:
    text = message.text
    user = message.from_user
    if text is None or user is None or botext.is_self_message(message):
        return

    urls = get_urls_from_message(message)
    async with httpx.AsyncClient() as client:
        for url in urls:
            resp = await client.get(f"{BASE_URL}{url}")
            data = resp.json()
            if isinstance(data, list):
                if not data:
                    return
                canonical = data[0]["canonical"]["url"]
                text = text.replace(url, canonical)
            else:
                # Error variant ({"errorMessage": ..., "resultCode": ...}): bail without replying.
                return

    new_text = f"{user.mention_html()}: {text}"
    await botext.replace_chat_message(bot, message, new_text)
