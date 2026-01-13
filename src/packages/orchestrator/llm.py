from __future__ import annotations

from typing import Any, Mapping, Protocol


class LlmClient(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return a text completion for the prompt."""
