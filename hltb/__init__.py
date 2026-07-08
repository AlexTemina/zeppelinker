from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, urlsplit

import httpx
from telegram import Bot, Message, MessageEntity
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError

import botext
import config

HLTB_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HLTB_ORIGIN = "https://howlongtobeat.com"

_HLTB_HTTP = httpx.AsyncClient(headers={"User-Agent": HLTB_USER_AGENT}, timeout=15.0)


def _bleed_json_headers() -> dict[str, str]:
    return {
        "User-Agent": HLTB_USER_AGENT,
        "Origin": HLTB_ORIGIN,
        "Referer": f"{HLTB_ORIGIN}/",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def bot_handle_lc(bot_username: str | None) -> str | None:
    """Lowercase `@handle` without `@`, falling back to BOT_NAME if the bot has no username."""
    if bot_username:
        name = bot_username.strip().lower()
        if name:
            return name
    return config.BOT_NAME


def _utf16_slice(text: str, offset: int, length: int) -> str | None:
    b = text.encode("utf-16-le")
    start, end = offset * 2, (offset + length) * 2
    if end > len(b):
        return None
    return b[start:end].decode("utf-16-le", errors="ignore")


def _utf16_tail(text: str, start_units: int) -> str | None:
    b = text.encode("utf-16-le")
    start = start_units * 2
    if start > len(b):
        return None
    return b[start:].decode("utf-16-le", errors="ignore")


def _parse_tail_for_query(tail: str) -> str | None:
    parts = tail.lstrip().split()
    if not parts:
        return None
    if parts[0].lower() != "hltb":
        return None
    query = " ".join(parts[1:])
    return query or None


def _text_link_is_bot(url: str, bot_id: int) -> bool:
    parts = urlsplit(url)
    if parts.scheme != "tg" or parts.hostname != "user":
        return False
    params = parse_qs(parts.query)
    ids = params.get("id", [])
    return any(v.isdigit() and int(v) == bot_id for v in ids)


def _message_text_and_entities(message: Message) -> tuple[str, tuple] | None:
    if message.text is not None:
        return message.text, message.entities or ()
    if message.caption is not None:
        return message.caption, message.caption_entities or ()
    return None


def _parse_from_entities(message: Message, bot_username: str | None) -> str | None:
    found = _message_text_and_entities(message)
    if found is None:
        return None
    text, entities = found
    bot_name_lc = bot_handle_lc(bot_username)

    for entity in entities:
        mention_is_bot = False
        if entity.type == MessageEntity.MENTION:
            if not bot_name_lc:
                continue
            slice_ = _utf16_slice(text, entity.offset, entity.length)
            if slice_ is None:
                continue
            mention_is_bot = slice_.removeprefix("@").lower() == bot_name_lc
        elif entity.type == MessageEntity.TEXT_MENTION:
            mention_is_bot = entity.user is not None and entity.user.id == config.BOT_ID
        elif entity.type == MessageEntity.TEXT_LINK:
            mention_is_bot = entity.url is not None and _text_link_is_bot(
                entity.url, config.BOT_ID
            )
        else:
            continue

        if not mention_is_bot:
            continue

        tail = _utf16_tail(text, entity.offset + entity.length)
        if tail is None:
            continue
        query = _parse_tail_for_query(tail)
        if query is not None:
            return query

    return None


def _parse_with_regex(text: str, bot_username: str | None) -> str | None:
    bot = bot_handle_lc(bot_username)
    if not bot:
        return None
    escaped = re.escape(bot)
    nbsp = " "
    pattern = rf"(?:^|\s)@{escaped}(?:\s|{nbsp})+hltb(?:\s|{nbsp})+(.+)$"
    match = re.search(pattern, text.strip(), re.IGNORECASE)
    if match is None:
        return None
    query = match.group(1).strip()
    return query or None


def _parse_private_plain_hltb(message: Message) -> str | None:
    if message.chat.type != "private":
        return None
    text = message.text or message.caption
    if text is None:
        return None
    text = text.strip()
    if text.startswith("/"):
        return None
    parts = text.split()
    if not parts or parts[0].lower() != "hltb":
        return None
    query = " ".join(parts[1:])
    return query or None


def parse_hltb_query(message: Message, bot_username: str | None) -> str | None:
    return (
        _parse_from_entities(message, bot_username)
        or _parse_with_regex(message.text or message.caption or "", bot_username)
        or _parse_private_plain_hltb(message)
    )


def matches(message: Message, bot_username: str | None) -> bool:
    return parse_hltb_query(message, bot_username) is not None


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class HltbGame:
    title: str
    main: str
    extra: str
    completionist: str
    cover_url: str | None


def _format_hltb_seconds(seconds: int) -> str:
    if seconds <= 0:
        return "—"
    if seconds < 60:
        return "<1m"
    hours, mins = divmod(seconds // 60, 60)
    if hours == 0:
        return f"{mins}m"
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"


def _json_seconds_field(obj: dict, key: str) -> str:
    v = obj.get(key)
    if v is None:
        return "—"
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "—"
    if isinstance(v, (int, float)):
        return _format_hltb_seconds(round(v))
    return "—"


def _games_from_data_array(data: list[dict]) -> list[HltbGame]:
    games = []
    for item in data[:10]:
        title = item.get("game_name") or "?"
        main = _json_seconds_field(item, "comp_main")
        extra = _json_seconds_field(item, "comp_plus")
        completionist = _json_seconds_field(item, "comp_100")
        image = item.get("game_image")
        cover_url = f"{HLTB_ORIGIN}/games/{image}" if image else None
        games.append(HltbGame(title, main, extra, completionist, cover_url))
    return games


def _parse_search_response(body: str) -> list[HltbGame] | None:
    import json

    try:
        v = json.loads(body)
    except ValueError:
        return None
    data = v.get("data") if isinstance(v, dict) else None
    if not isinstance(data, list):
        return None
    return _games_from_data_array(data)


def _build_bleed_search_json(search_terms: list[str]) -> dict:
    return {
        "searchType": "games",
        "searchTerms": search_terms,
        "searchPage": 1,
        "size": 20,
        "searchOptions": {
            "games": {
                "userId": 0,
                "platform": "",
                "sortCategory": "popular",
                "rangeCategory": "main",
                "rangeTime": {"min": 0, "max": 0},
                "gameplay": {"perspective": "", "flow": "", "genre": "", "difficulty": ""},
                "rangeYear": {"min": "", "max": ""},
                "modifier": "",
            },
            "users": {"sortCategory": "postcount"},
            "lists": {"sortCategory": "follows"},
            "filter": "",
            "sort": 0,
            "randomizer": 0,
        },
        "useCache": True,
    }


@dataclass
class _BleedCreds:
    token: str
    hp_key: str
    hp_val: str


async def _fetch_bleed_init() -> _BleedCreds | None:
    ts = int(time.time() * 1000)
    url = f"{HLTB_ORIGIN}/api/bleed/init?t={ts}"
    try:
        res = await _HLTB_HTTP.get(url, headers=_bleed_json_headers())
    except httpx.HTTPError:
        return None
    if res.status_code >= 400:
        return None
    v = res.json()
    token, hp_key, hp_val = v.get("token"), v.get("hpKey"), v.get("hpVal")
    if not token or not hp_key or not hp_val:
        return None
    return _BleedCreds(token, hp_key, hp_val)


async def _post_bleed_search(
    creds: _BleedCreds, search_terms: list[str]
) -> httpx.Response | None:
    body = _build_bleed_search_json(search_terms)
    body[creds.hp_key] = creds.hp_val

    headers = _bleed_json_headers()
    headers["x-auth-token"] = creds.token
    headers["x-hp-key"] = creds.hp_key
    headers["x-hp-val"] = creds.hp_val

    try:
        return await _HLTB_HTTP.post(f"{HLTB_ORIGIN}/api/bleed", headers=headers, json=body)
    except httpx.HTTPError:
        return None


async def _search_howlongtobeat_bleed(search_terms: list[str]) -> list[HltbGame] | None:
    creds = await _fetch_bleed_init()
    if creds is None:
        return None

    for attempt in range(2):
        res = await _post_bleed_search(creds, search_terms)
        if res is None:
            return None

        if res.status_code == 403 and attempt == 0:
            creds = await _fetch_bleed_init()
            if creds is None:
                return None
            continue

        if res.status_code >= 400:
            return None

        return _parse_search_response(res.text)

    return None


async def search_games(query: str) -> list[HltbGame]:
    search_terms = query.split()
    if not search_terms:
        return []
    games = await _search_howlongtobeat_bleed(search_terms)
    return games or []


def _site_search_url(query: str) -> str:
    return f"https://howlongtobeat.com/?q={quote_plus(query)}"


def _games_reply_html(games: list[HltbGame]) -> str:
    out = ["<b>HowLongToBeat</b>\n"]
    for i, g in enumerate(games[:5]):
        if i > 0:
            out.append("")
        out.append(
            f"<b>{_escape_html(g.title)}</b>\n"
            f"Main: {_escape_html(g.main)}\n"
            f"+ Extras: {_escape_html(g.extra)}\n"
            f"Completionist: {_escape_html(g.completionist)}"
        )
    if len(games) > 5:
        out.append(f"\n… and {len(games) - 5} more.")
    out.append("<i>Data from howlongtobeat.com (unofficial).</i>")
    return "\n".join(out)


def _truncate_caption_html(s: str, max_bytes: int) -> str:
    if len(s.encode()) <= max_bytes:
        return s
    out = ""
    for ch in s:
        if len((out + ch).encode()) > max_bytes - 3:
            break
        out += ch
    return out + "…"


async def handle(bot: Bot, message: Message, bot_username: str | None) -> None:
    query = parse_hltb_query(message, bot_username)
    if query is None:
        return
    if message.from_user is not None and message.from_user.id == config.BOT_ID:
        return

    games = await search_games(query)

    if not games:
        href = _escape_html(_site_search_url(query))
        reply_text = (
            f"No HowLongToBeat results for <i>{_escape_html(query)}</i>. "
            f'Try on the site: <a href="{href}">howlongtobeat.com</a>.'
        )
        await botext.try_reply(bot, message, reply_text)
        return

    reply_text = _games_reply_html(games)
    reply_target = message.reply_to_message.message_id if message.reply_to_message else message.message_id

    cover_url = games[0].cover_url
    if cover_url:
        try:
            await bot.send_chat_action(message.chat_id, ChatAction.UPLOAD_PHOTO)
            await bot.send_photo(
                message.chat_id,
                photo=cover_url,
                caption=_truncate_caption_html(reply_text, 1024),
                parse_mode=ParseMode.HTML,
                reply_to_message_id=reply_target,
            )
            return
        except TelegramError:
            pass

    await botext.try_reply(bot, message, reply_text)
