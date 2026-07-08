from __future__ import annotations

from urllib.parse import urlsplit

from telegram import Message, MessageEntity


def get_urls_from_message(message: Message) -> list[str]:
    """Extract plain `url` entities from a message (ignores commands and text_link masks)."""
    entities = message.entities
    text = message.text
    if not entities or not text:
        return []
    if entities[0].type == MessageEntity.BOT_COMMAND:
        return []
    parsed = message.parse_entities(types=[MessageEntity.URL])
    return list(parsed.values())


def check_matches_domain(url: str, domains: list[str]) -> bool:
    host = urlsplit(url).hostname
    if not host:
        return False
    host = host.removeprefix("www.")
    return host in domains


def has_matching_urls(message: Message, domains: list[str]) -> bool:
    return any(check_matches_domain(url, domains) for url in get_urls_from_message(message))


def get_preview_url(url: str, from_domain: str, to_domain: str) -> str:
    return url.replace(from_domain, to_domain)


def get_preview_url_with_suffix(
    url: str, from_domain: str, to_domain: str, suffix: str | None
) -> str:
    result = get_preview_url(url, from_domain, to_domain)
    if suffix:
        result += suffix
    return result


def scrub_urls(message: Message, urls: list[str]) -> str | None:
    """Strip query strings from any of `urls` as they appear in the message text."""
    text = message.text
    if text is None:
        return None
    final_text = text
    for url in urls:
        query = urlsplit(url).query
        if query:
            scrubbed = url.replace(f"?{query}", "")
            final_text = final_text.replace(url, scrubbed)
    return final_text
