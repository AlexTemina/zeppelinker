from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

from telegram import Bot, Message

import botext
from botext import ButtonData
from .router import Router

PROVIDER = os.environ.get("zeppelinker_TWITTER_PROVIDER", "fixupx.com")

DOMAINS = ["twitter.com", "mobile.twitter.com", "x.com", "mobile.x.com"]

URL_MATCHER = Router(
    [
        "/{user}/status/{tweet_id}",
        "/{user}/status/{tweet_id}/photo/{num}",
        "/i/status/{tweet_id}",
    ]
)


def _nitter_button(url: str) -> ButtonData | None:
    parts = urlsplit(url)
    button_url = urlunsplit(parts._replace(netloc="xcancel.com"))
    return ButtonData("Ver en Nitter", button_url)


async def handle(bot: Bot, message: Message) -> None:
    await botext.perform_replacement(
        bot, message, URL_MATCHER, PROVIDER, "/es", _nitter_button
    )
