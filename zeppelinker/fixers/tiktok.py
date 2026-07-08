from __future__ import annotations

import os

from telegram import Bot, Message

from .. import botext
from ..router import Router

PROVIDER = os.environ.get("zeppelinker_TIKTOK_PROVIDER", "d.tnktok.com")

DOMAINS = ["tiktok.com", "www.tiktok.com", "vm.tiktok.com"]

URL_MATCHER = Router(
    [
        "/{video_id}",
        "/t/{video_id}",
        "/embed/{video_id}",
        "/@{username}/video/{video_id}",
        "/@{username}/photo/{video_id}",
        "/@{username}/live",
    ]
)


async def handle(bot: Bot, message: Message) -> None:
    await botext.perform_replacement(bot, message, URL_MATCHER, PROVIDER, None)
