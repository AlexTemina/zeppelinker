from __future__ import annotations

import logging
from collections.abc import Callable
from urllib.parse import urlsplit
from typing import NamedTuple

import httpx
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError

import config
from fixers.router import Router
from urlutils import build_preview_url, get_urls_from_message, scrub_urls

logger = logging.getLogger(__name__)

# Telegram won't render a link-preview video above some size (untested exact cutoff;
# 6.3MB previewed fine, 52.5MB didn't) -- pick a conservative cutoff between those.
PREVIEW_SIZE_LIMIT_BYTES = 20 * 1024 * 1024

# Fixer sites like kkclip.com serve the real redirect only to preview-fetcher-like UAs.
_PREVIEW_FETCH_USER_AGENT = "TelegramBot (like TwitterBot)"


class ButtonData(NamedTuple):
    label: str
    url: str


async def _resolved_content_length(url: str) -> int | None:
    """Size of what `url` resolves to, via a 1-byte Range request (no full download)."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            async with client.stream(
                "GET",
                url,
                headers={"Range": "bytes=0-0", "User-Agent": _PREVIEW_FETCH_USER_AGENT},
            ) as resp:
                content_range = resp.headers.get("content-range", "")
                total = content_range.rsplit("/", 1)[-1]
                if total.isdigit():
                    return int(total)
    except httpx.HTTPError:
        pass
    return None


def is_self_message(message: Message) -> bool:
    forwarder = message.forward_origin.sender_user if message.forward_origin else None
    if forwarder is not None:
        return forwarder.id == config.BOT_ID
    return message.from_user is not None and message.from_user.id == config.BOT_ID


async def reply(bot: Bot, message: Message, text: str) -> Message:
    return await bot.send_message(
        message.chat_id,
        text,
        reply_to_message_id=message.message_id,
        parse_mode=ParseMode.HTML,
    )


async def try_reply_silent(bot: Bot, message: Message, text: str) -> Message | None:
    try:
        reply_target = message.reply_to_message.message_id if message.reply_to_message else None
        return await bot.send_message(
            message.chat_id,
            text,
            reply_to_message_id=reply_target,
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        return None


async def try_reply(bot: Bot, message: Message, text: str) -> Message | None:
    try:
        await bot.send_chat_action(message.chat_id, ChatAction.TYPING)
    except TelegramError:
        pass
    return await try_reply_silent(bot, message, text)


async def replace_chat_message(bot: Bot, message: Message, text: str) -> Message | None:
    try:
        await bot.delete_message(message.chat_id, message.message_id)
    except TelegramError:
        pass
    return await try_reply_silent(bot, message, text)


async def perform_replacement(
    bot: Bot,
    message: Message,
    url_matcher: Router,
    preview_domain: str,
    preview_path_suffix: str | None,
    get_button_data: Callable[[str], ButtonData | None] = lambda _url: None,
) -> Message | None:
    """Returns the newly sent replacement message, or None if the original
    message was left untouched (self-message, no match, oversized video...)."""
    if is_self_message(message):
        return None
    urls = get_urls_from_message(message)
    if not urls:
        return None
    text = scrub_urls(message, urls)
    if text is None:
        return None
    user = message.from_user
    if user is None:
        return None
    url = urls[0]
    parsed = urlsplit(url)
    domain = parsed.hostname
    if not domain:
        return None
    if url_matcher.match(parsed.path) is None:
        return None

    new_text = f"{user.mention_html()}: {text}"
    preview_url = build_preview_url(url, domain, preview_domain, preview_path_suffix)
    preview_options = LinkPreviewOptions(
        is_disabled=False,
        url=preview_url,
        prefer_small_media=False,
        prefer_large_media=True,
        show_above_text=False,
    )
    button = get_button_data(url)
    reply_markup = None
    if button is not None:
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(button.label, url=button.url)]])

    size = await _resolved_content_length(preview_url)
    if size is not None and size > PREVIEW_SIZE_LIMIT_BYTES:
        logger.warning("Skipping replacement, media too large (%d bytes): %s", size, preview_url)
        await reply(
            bot,
            message,
            "⚠️ El vídeo de este enlace pesa demasiado para que Telegram genere la vista previa aquí.",
        )
        return None

    try:
        await bot.delete_message(message.chat_id, message.message_id)
    except TelegramError:
        pass

    reply_target = message.reply_to_message.message_id if message.reply_to_message else None
    return await bot.send_message(
        message.chat_id,
        new_text,
        reply_to_message_id=reply_target,
        parse_mode=ParseMode.HTML,
        link_preview_options=preview_options,
        reply_markup=reply_markup,
    )
