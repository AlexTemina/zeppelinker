from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlsplit
from typing import NamedTuple

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
from urlutils import get_preview_url_with_suffix, get_urls_from_message, scrub_urls


class ButtonData(NamedTuple):
    label: str
    url: str


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
) -> None:
    if is_self_message(message):
        return
    urls = get_urls_from_message(message)
    if not urls:
        return
    text = scrub_urls(message, urls)
    if text is None:
        return
    user = message.from_user
    if user is None:
        return
    url = urls[0]
    parsed = urlsplit(url)
    domain = parsed.hostname
    if not domain:
        return
    if url_matcher.match(parsed.path) is None:
        return

    new_text = f"{user.mention_html()}: {text}"
    preview_url = get_preview_url_with_suffix(url, domain, preview_domain, preview_path_suffix)
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

    try:
        await bot.delete_message(message.chat_id, message.message_id)
    except TelegramError:
        pass

    reply_target = message.reply_to_message.message_id if message.reply_to_message else None
    await bot.send_message(
        message.chat_id,
        new_text,
        reply_to_message_id=reply_target,
        parse_mode=ParseMode.HTML,
        link_preview_options=preview_options,
        reply_markup=reply_markup,
    )
