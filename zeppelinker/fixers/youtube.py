from __future__ import annotations

from urllib.parse import urlsplit

from telegram import Bot, Message

from .. import botext
from ..router import Router
from ..urlutils import get_urls_from_message

DOMAINS = ["youtube.com", "www.youtube.com"]

URL_MATCHER = Router(["/shorts/{id}"])


async def handle(bot: Bot, message: Message) -> None:
    if botext.is_self_message(message):
        return
    text = message.text
    if text is None:
        return
    user = message.from_user
    if user is None:
        return
    urls = get_urls_from_message(message)
    if not urls:
        return
    url = urls[0]
    parsed = urlsplit(url)
    domain = parsed.hostname
    if not domain:
        return
    match = URL_MATCHER.match(parsed.path)
    if match is None:
        return
    video_id = match.params.get("id")
    if not video_id:
        return

    new_text = text.replace(url, f"https://{domain}/watch?v={video_id}")
    new_text = f"{user.mention_html()}: {new_text}"
    await botext.replace_chat_message(bot, message, new_text)
