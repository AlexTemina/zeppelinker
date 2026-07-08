from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass
class FixerState:
    instagram: bool = True
    medium: bool = True
    reddit: bool = True
    tiktok: bool = True
    twitter: bool = True
    youtube: bool = True
    threads: bool = True


# chat_id -> FixerState. The bot runs a single asyncio event loop, so a plain
# dict is safe without the Mutex the original Rust code needed for its threaded runtime.
FIXER_STATE: dict[int, FixerState] = {}


def get_state(chat_id: int) -> FixerState:
    return FIXER_STATE.setdefault(chat_id, FixerState())


FIXER_FIELD_NAMES = {f.name for f in fields(FixerState)}
