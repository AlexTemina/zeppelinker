from __future__ import annotations

import os

from telegram import Bot, Message

import botext
from .router import Router

PROVIDER = os.environ.get("zeppelinker_REDDIT_PROVIDER", "vxreddit.com")

DOMAINS = ["reddit.com", "redd.it", "www.reddit.com"]

URL_MATCHER = Router(
    [
        "/r/{username}/comments/{id}/{slug}/{comment}",
        "/r/{username}/comments/{id}/{slug}",
        "/r/{username}/comments/{id}",
        "/r/{username}/s/{id}/{slug}/{comment}",
        "/r/{username}/s/{id}/{slug}",
        "/r/{username}/s/{id}",
        "/u/{username}/comments/{id}/{slug}/{comment}",
        "/u/{username}/comments/{id}/{slug}",
        "/u/{username}/comments/{id}",
        "/u/{username}/s/{id}/{slug}/{comment}",
        "/u/{username}/s/{id}/{slug}",
        "/u/{username}/s/{id}",
        "/user/{username}/comments/{id}/{slug}/{comment}",
        "/user/{username}/comments/{id}/{slug}",
        "/user/{username}/comments/{id}",
        "/user/{username}/s/{id}/{slug}/{comment}",
        "/user/{username}/s/{id}/{slug}",
        "/user/{username}/s/{id}",
        "/{id}",
    ]
)


async def handle(bot: Bot, message: Message) -> Message | None:
    return await botext.perform_replacement(bot, message, URL_MATCHER, PROVIDER, None)
