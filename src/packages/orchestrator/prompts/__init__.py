from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Mapping

_PROMPT_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    path = _PROMPT_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


def render_prompt(name: str, values: Mapping[str, str]) -> str:
    template = load_prompt(name)
    return template.format_map(_SafeDict(values))


def synthesis_headers() -> list[str]:
    template = load_prompt("synthesis")
    headers = []
    for line in template.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            headers.append(stripped)
    return headers


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""
