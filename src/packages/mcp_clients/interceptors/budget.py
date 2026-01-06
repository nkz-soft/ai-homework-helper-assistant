from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

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


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
