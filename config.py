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


def _optional_int(name: str) -> int | None:
    value = os.environ.get(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError as e:
        raise RuntimeError(f"{name} must be a valid integer") from e


# Optional: unlike BOT_ID/TELOXIDE_TOKEN this isn't currently set as a Fly secret.
# Without it, only group admins (not a hardcoded owner) can toggle fixers.
BOT_OWNER_ID = _optional_int("BOT_OWNER_ID")
