from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

import botext
import commands
import config
from fixers import deamp, instagram, medium, reddit, threads, tiktok, twitter, youtube
from fixers.state import get_state
from gol import gol
from urlutils import get_urls_from_message, has_matching_urls

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
    chat_state = get_state(message.chat_id)
    urls = get_urls_from_message(message)

    # Recorded before running any fixer so the "is this a repost" check
    # always happens, but the actual GOL reply is sent afterwards, quoting
    # whatever message survives -- a fixer may delete `message` and send a
    # replacement, and citing the (by then deleted) original would leave the
    # reply pointing at nothing.
    is_repost = (
        bool(urls)
        and chat_state.gol
        and not botext.is_self_message(message)
        and gol.check_and_record(message.chat_id, urls)
    )

    target_message = message
    matched_fixer = False
    for module, field in _FIXERS:
        if _should_match(message, module.DOMAINS) and getattr(chat_state, field):
            matched_fixer = True
            target_message = await module.handle(bot, message) or message
            break

    if not matched_fixer and urls and any(deamp.is_amp(url) for url in urls):
        target_message = await deamp.handle(bot, message) or message

    if is_repost:
        await gol.handle(bot, target_message)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled error while processing %r", update, exc_info=context.error)


def main() -> None:
    app = Application.builder().token(config.BOT_TOKEN).build()

    commands.register(app)
    # Only brand-new messages, never edits. filters.ALL would also match
    # edited_message updates (Telegram sends one of those, e.g. when it
    # finishes generating a slow link preview after the message was already
    # sent), and since the bot has no delete rights in some chats the
    # original message is never removed -- reprocessing an edit would send a
    # second, duplicate reply for the same link.
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE, on_message))
    app.add_error_handler(on_error)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
