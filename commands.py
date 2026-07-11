from __future__ import annotations

from collections.abc import Callable

from telegram import Bot, Message, Update
from telegram.ext import CommandHandler, ContextTypes

import botext
import config
from fixers.state import get_state, set_field
from hltb import hltb

NOT_AUTHORIZED = "You are not authorized for this action"

# (fixer display name, FixerState field name) -- shared by the on/off toggle
# commands and by /status, so both stay in sync automatically.
_FIXERS = [
    ("Instagram", "instagram"),
    ("Medium", "medium"),
    ("Reddit", "reddit"),
    ("TikTok", "tiktok"),
    ("Twitter", "twitter"),
    ("YouTube", "youtube"),
    ("Threads", "threads"),
    ("Gol", "gol"),
]

TRUE_VALUES = {"true", "on", "yes", "enable"}
FALSE_VALUES = {"false", "off", "no", "disable"}
_EXPECTED_VALUES = ", ".join(f"'{v}'" for v in (*TRUE_VALUES, *FALSE_VALUES))

HELP_TEXT = (
    "These commands are supported:\n"
    "/help - display this text.\n"
    "/ping - Pong?\n"
    "/status - show on/off state of every link fixer in this chat\n"
    "/instagram - toggle Instagram link replacement\n"
    "/medium - toggle Medium link replacement\n"
    "/reddit - toggle Reddit link replacement\n"
    "/start - display this text.\n"
    "/ttv - generate a twitchtheater link for the given streamers\n"
    "/tiktok - toggle TikTok link replacement\n"
    "/twitter - toggle Twitter link replacement\n"
    "/youtube - toggle YouTube link replacement\n"
    "/threads - toggle Threads link replacement\n"
    "/gol - toggle the GOOOOL reply when a link is posted again\n"
    "/hltb - look up a game on HowLongToBeat, e.g. /hltb Elden Ring"
)


async def check_authorized(bot: Bot, message: Message) -> bool:
    if message.chat.type == "private":
        return True
    from_user = message.from_user
    if from_user is None:
        return False
    if config.BOT_OWNER_ID is not None and from_user.id == config.BOT_OWNER_ID:
        return True
    admins = await bot.get_chat_administrators(message.chat_id)
    return any(admin.user.id == from_user.id for admin in admins)


def _parse_bool(arg: str) -> bool:
    parts = arg.split(" ")
    if len(parts) > 1:
        raise ValueError(f"Unexpected number of arguments. Expected one of: {_EXPECTED_VALUES}.")
    lowered = parts[0].lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    raise ValueError(f"Unexpected argument '{parts[0]}'. Expected one of: {_EXPECTED_VALUES}.")


async def _flip_filter_state(
    bot: Bot,
    message: Message,
    filter_arg: str,
    fixer_name: str,
    field: str,
) -> None:
    state = get_state(message.chat_id)
    if not filter_arg:
        current = "enabled" if getattr(state, field) else "disabled"
        await botext.reply(bot, message, f"{fixer_name} link replacement is {current}")
        return

    if not await check_authorized(bot, message):
        await botext.reply(bot, message, NOT_AUTHORIZED)
        return

    try:
        value = _parse_bool(filter_arg)
    except ValueError as e:
        await botext.reply(bot, message, str(e))
        return

    set_field(message.chat_id, field, value)
    new_state = "enabled" if value else "disabled"
    await botext.reply(bot, message, f"{fixer_name} link replacement is now {new_state}")


def _toggle_command(fixer_name: str, field: str) -> Callable:
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        arg = " ".join(context.args or [])
        await _flip_filter_state(context.bot, message, arg, fixer_name, field)

    return handler


async def _help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await botext.reply(context.bot, update.effective_message, HELP_TEXT)


async def _ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await botext.reply(context.bot, update.effective_message, "Pong")


async def _ttv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    names = " ".join(context.args or [])
    text = f"https://twitchtheater.tv/{names.replace(' ', '/')}"
    await botext.reply(context.bot, update.effective_message, text)


async def _status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    state = get_state(message.chat_id)
    lines = ["<b>Fixer status</b>"]
    for name, field in _FIXERS:
        on = getattr(state, field)
        lines.append(f"{name}: {'✅ on' if on else '❌ off'}")
    await botext.reply(context.bot, message, "\n".join(lines))


async def _hltb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args or [])
    await hltb.handle(context.bot, update.effective_message, query)


def register(app) -> None:
    app.add_handler(CommandHandler(["help", "start"], _help))
    app.add_handler(CommandHandler("ping", _ping))
    app.add_handler(CommandHandler("ttv", _ttv))
    app.add_handler(CommandHandler("status", _status))
    app.add_handler(CommandHandler("hltb", _hltb))
    for name, field in _FIXERS:
        app.add_handler(CommandHandler(field, _toggle_command(name, field)))
