from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Mapping

from packages.orchestrator.llm import LlmClient
from packages.orchestrator.llm_config import LlmConfig

log = logging.getLogger(__name__)


class LlmApiError(RuntimeError):
    """Raised when the LLM API returns an invalid response."""


class OpenAiChatClient(LlmClient):
    def __init__(self, config: LlmConfig, *, timeout_seconds: float = 30.0) -> None:
        self._config = config
        self._timeout_seconds = timeout_seconds

    def generate(
        self,
        prompt: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        url = _build_chat_url(self._config.base_url)
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            log.error("LLM API error: %s", exc)
            raise LlmApiError(f"LLM API error: {exc}") from exc
        except urllib.error.URLError as exc:
            log.error("LLM API connection error: %s", exc)
            raise LlmApiError(f"LLM API connection error: {exc}") from exc

        return _parse_chat_response(body)


def _build_chat_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    return f"{trimmed}/chat/completions"


def _parse_chat_response(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LlmApiError("LLM API response was not valid JSON.") from exc

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LlmApiError("LLM API response contained no choices.")

    choice = choices[0]
    if isinstance(choice, Mapping):
        message = choice.get("message")
        if isinstance(message, Mapping):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        text = choice.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()

    raise LlmApiError("LLM API response did not include content.")
