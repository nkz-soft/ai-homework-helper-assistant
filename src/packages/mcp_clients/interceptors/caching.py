from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from ..client_factory import McpToolHandle


class ToolBudgetExceeded(RuntimeError):
    """Raised when tool-call budgets are exceeded."""


@dataclass(frozen=True)
class ToolBudgetLimits:
    total_calls: int | None = None
    per_server_caps: Mapping[str, int] | None = None
    max_payload_bytes: int | None = None


class ToolBudgetManager:
    def __init__(self, *, limits: ToolBudgetLimits | None = None) -> None:
        resolved = limits or ToolBudgetLimits()
        self._total_limit = resolved.total_calls
        self._per_server_caps = dict(resolved.per_server_caps or {})
        self._max_payload_bytes = resolved.max_payload_bytes
        self._total_calls = 0
        self._per_server_counts: dict[str, int] = {}

    def assert_can_call(self, tool: McpToolHandle) -> None:
        if self._total_limit is not None and self._total_calls >= self._total_limit:
            raise ToolBudgetExceeded(
                f"Tool budget exceeded: total call cap {self._total_limit}."
            )

        server = tool.server_name
        cap = self._per_server_caps.get(server)
        if cap is not None and self._per_server_counts.get(server, 0) >= cap:
            raise ToolBudgetExceeded(
                f"Tool budget exceeded: '{server}' call cap {cap}."
            )

    def record_call(self, tool: McpToolHandle) -> None:
        self._total_calls += 1
        server = tool.server_name
        self._per_server_counts[server] = self._per_server_counts.get(server, 0) + 1

    def check_payload_size(self, payload: Any) -> None:
        if self._max_payload_bytes is None:
            return
        size = _response_size_bytes(payload)
        if size > self._max_payload_bytes:
            raise ToolBudgetExceeded(
                "Tool budget exceeded: "
                f"payload {size} bytes exceeds {self._max_payload_bytes}."
            )


@dataclass(frozen=True)
class _CacheEntry:
    value: Mapping[str, Any] | list[Any] | None
    expires_at: float | None


class ToolCallCache:
    def __init__(
        self,
        *,
        ttl_seconds: float | None = 300.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock or time.monotonic
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> tuple[bool, Mapping[str, Any] | list[Any] | None]:
        entry = self._store.get(key)
        if entry is None:
            return False, None
        if entry.expires_at is not None and entry.expires_at <= self._clock():
            self._store.pop(key, None)
            return False, None
        return True, entry.value

    def set(
        self,
        key: str,
        value: Mapping[str, Any] | list[Any] | None,
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        ttl = self._ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl is not None and ttl <= 0:
            return
        expires_at = None if ttl is None else self._clock() + ttl
        self._store[key] = _CacheEntry(value=value, expires_at=expires_at)


def cache_tool_call(
    tool: McpToolHandle,
    arguments: Mapping[str, Any],
    *,
    cache: ToolCallCache | None = None,
    budget_manager: ToolBudgetManager | None = None,
    ttl_seconds: float | None = None,
    cache_key: str | None = None,
    language: str | None = None,
    subject: str | None = None,
) -> Mapping[str, Any] | list[Any] | None:
    key = cache_key or build_tool_cache_key(
        tool, arguments, language=language, subject=subject
    )
    if cache is not None:
        hit, cached_value = cache.get(key)
        if hit:
            if budget_manager is not None:
                budget_manager.check_payload_size(cached_value)
            return cached_value

    if budget_manager is not None:
        budget_manager.assert_can_call(tool)

    response: Mapping[str, Any] | list[Any] | None = None
    try:
        response = tool.call(arguments)
        if budget_manager is not None:
            budget_manager.check_payload_size(response)
    finally:
        if budget_manager is not None:
            budget_manager.record_call(tool)

    if cache is not None:
        cache.set(key, response, ttl_seconds=ttl_seconds)
    return response


def build_tool_cache_key(
    tool: McpToolHandle,
    arguments: Mapping[str, Any],
    *,
    language: str | None = None,
    subject: str | None = None,
) -> str:
    normalized_args = _normalize_value(_compact_args(arguments))
    resolved_language = _coerce_str(
        language
        or arguments.get("lang")
        or arguments.get("language")
        or arguments.get("locale")
    )
    resolved_subject = _coerce_str(subject or arguments.get("subject"))
    payload = {
        "provider": tool.server_name,
        "tool": tool.tool_name,
        "args": normalized_args,
        "language": resolved_language,
        "subject": resolved_subject,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _compact_args(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in arguments.items() if value is not None}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _response_size_bytes(response: Any) -> int:
    if response is None:
        return 0
    if isinstance(response, bytes):
        return len(response)
    if isinstance(response, (Mapping, list)):
        try:
            encoded = json.dumps(response, separators=(",", ":"))
        except TypeError:
            encoded = json.dumps(_normalize_value(response), separators=(",", ":"))
        return len(encoded.encode("utf-8"))
    if isinstance(response, str):
        return len(response.encode("utf-8"))
    return len(str(response).encode("utf-8"))
