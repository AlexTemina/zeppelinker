from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from . import commands, config, hltb
from .fixers import deamp, instagram, medium, reddit, threads, tiktok, twitter, youtube
from .state import get_state
from .urlutils import get_urls_from_message, has_matching_urls

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("zeppelinker")

# httpx logs full request URLs at INFO, and every Bot API call embeds the bot
# token in its URL path (api.telegram.org/bot<TOKEN>/...) -- silence it so the
# token never hits stdout/Fly logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

REPLACE_SKIP_TOKEN = "#skip"

# Ordered the same as the Rust dispatcher's dptree branches: first match wins.
_FIXERS = [
    (twitter, "twitter"),
    (instagram, "instagram"),
    (youtube, "youtube"),
    (medium, "medium"),
    (reddit, "reddit"),
    (tiktok, "tiktok"),
    (threads, "threads"),
]


def _should_match(message, domains: list[str]) -> bool:
    text = message.text or ""
    if REPLACE_SKIP_TOKEN in text:
        return False
    return has_matching_urls(message, domains)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    bot = context.bot

    if hltb.matches(message, bot.username):
        await hltb.handle(bot, message, bot.username)
        return

    chat_state = get_state(message.chat_id)
    for module, field in _FIXERS:
        if _should_match(message, module.DOMAINS) and getattr(chat_state, field):
            await module.handle(bot, message)
            return

    urls = get_urls_from_message(message)
    if urls and any(deamp.is_amp(url) for url in urls):
        await deamp.handle(bot, message)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled error while processing %r", update, exc_info=context.error)


def main() -> None:
    app = Application.builder().token(config.BOT_TOKEN).build()

    commands.register(app)
    app.add_handler(MessageHandler(filters.ALL, on_message))
    app.add_error_handler(on_error)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
