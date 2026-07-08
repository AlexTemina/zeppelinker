"""Tiny path-template router, equivalent to the Rust `matchit`-based one.

Route templates use `{name}` for a single path segment, e.g. `/{user}/status/{tweet_id}`.
A trailing slash is always optional, mirroring the original's practice of registering
both a route and its `/`-suffixed variant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Match:
    params: dict[str, str]


_PLACEHOLDER = re.compile(r"\{(\w+)\}")


class Router:
    def __init__(self, patterns: list[str]) -> None:
        self._compiled = [self._compile(p) for p in patterns]

    @staticmethod
    def _compile(pattern: str) -> re.Pattern[str]:
        assert not pattern.endswith("/"), "route patterns must not end in /"
        parts = pattern.split("/")
        regex_parts = []
        for part in parts:
            # A segment can mix literal text and a placeholder, e.g. "@{username}".
            piece, last = [], 0
            for m in _PLACEHOLDER.finditer(part):
                piece.append(re.escape(part[last : m.start()]))
                piece.append(f"(?P<{m.group(1)}>[^/]+)")
                last = m.end()
            piece.append(re.escape(part[last:]))
            regex_parts.append("".join(piece))
        return re.compile("^" + "/".join(regex_parts) + "/?$")

    def match(self, path: str) -> Match | None:
        for compiled in self._compiled:
            m = compiled.match(path)
            if m:
                return Match(params=m.groupdict())
        return None

    def matches(self, path: str) -> bool:
        return self.match(path) is not None
