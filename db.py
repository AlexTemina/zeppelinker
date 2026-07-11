from __future__ import annotations

import os
import sqlite3

# Points at a Fly Volume mount in production (see fly.toml) so state survives
# restarts and deploys; defaults to a local file for dev. Shared by every
# feature that needs to persist something (fixer toggles, seen links, ...)
# so they all live in one file instead of each opening their own.
DB_PATH = os.environ.get("STATE_DB_PATH", "state.db")

_CONNECTION = sqlite3.connect(DB_PATH)


def connection() -> sqlite3.Connection:
    return _CONNECTION
