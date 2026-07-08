from __future__ import annotations

import os


def _required_int(name: str) -> int:
    value = os.environ.get(name)
    if value is None:
        raise RuntimeError(f"{name} must be defined")
    try:
        return int(value)
    except ValueError as e:
        raise RuntimeError(f"{name} must be a valid integer") from e


BOT_TOKEN = os.environ.get("TELOXIDE_TOKEN") or ""
if not BOT_TOKEN:
    raise RuntimeError("TELOXIDE_TOKEN must be defined")

BOT_ID = _required_int("BOT_ID")
BOT_OWNER_ID = _required_int("BOT_OWNER_ID")
BOT_NAME = os.environ.get("BOT_NAME", "").strip().lstrip("@").lower() or None
