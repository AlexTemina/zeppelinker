from __future__ import annotations

import os
import re

from telegram import Bot, Message

from .. import botext
from ..urlutils import get_urls_from_message, scrub_urls

PROVIDER = os.environ.get("zeppelinker_MEDIUM_PROVIDER", "md.vern.cc")

DOMAINS = ["medium.com"]

# Ported as-is from the Rust regex (the `.` before `medium.com` is an unescaped
# wildcard rather than a literal dot, same as upstream).
MATCH_REGEX = re.compile(r"https://(?P<user>[a-zA-Z0-9]*)?.?(?P<host>medium.com)/(?P<path>.*)")


def build_url(match: re.Match[str]) -> str:
    url = f"{PROVIDER}/{match.group('user')}/{match.group('path')}".replace("//", "/")
    return "https://" + url


async def handle(bot: Bot, message: Message) -> None:
    if botext.is_self_message(message):
        return
    user = message.from_user
    if user is None:
        return
    text = scrub_urls(message, get_urls_from_message(message))
    if text is None:
        return
    match = MATCH_REGEX.search(text)
    if match is None:
        return
    new_text = text.replace(match.group(0), build_url(match))
    new_text = f"{user.mention_html()}: {new_text}"
    await botext.replace_chat_message(bot, message, new_text)
