from __future__ import annotations

import os

from telegram import Bot, Message

import botext
from .router import Router

PROVIDER = os.environ.get("zeppelinker_THREADS_PROVIDER", "fixthreads.net")

DOMAINS = ["threads.net", "threads.com"]

URL_MATCHER = Router(["/@{user}/post/{id}"])


async def handle(bot: Bot, message: Message) -> None:
    await botext.perform_replacement(bot, message, URL_MATCHER, PROVIDER, None)
