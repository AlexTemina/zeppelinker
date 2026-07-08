from __future__ import annotations

import os

from telegram import Bot, Message

from .. import botext
from ..router import Router

PROVIDER = os.environ.get("zeppelinker_INSTAGRAM_PROVIDER", "kkclip.com")

DOMAINS = ["instagram.com", "www.instagram.com"]

URL_MATCHER = Router(
    [
        "/p/{id}",
        "/reel/{id}",
        "/reels/{id}",
        "/tv/{id}",
        "/{username}/p/{id}",
        "/{username}/reel/{id}",
        "/{username}/reels/{id}",
        "/share/p/{id}",
        "/share/reel/{id}",
        "/share/reels/{id}",
    ]
)


async def handle(bot: Bot, message: Message) -> None:
    await botext.perform_replacement(bot, message, URL_MATCHER, PROVIDER, None)
