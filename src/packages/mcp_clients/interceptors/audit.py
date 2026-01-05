from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Callable, Mapping

from ..client_factory import McpToolHandle

_REDACTED_VALUE = "[REDACTED]"
_SECRET_KEY_MARKERS = {
    "password",
    "passwd",
    "passphrase",
    "token",
    "api_key",
    "apikey",
    "secret",
    "authorization",
    "bearer",
    "cookie",
    "session",
    "access_key",
    "access_token",
    "refresh_token",
}


def audit_tool_call(
    tool: McpToolHandle,
    arguments: Mapping[str, Any],
    *,
    logger: logging.Logger | None = None,
    clock: Callable[[], float] | None = None,
) -> Mapping[str, Any] | list[Any] | None:
    log = logger or logging.getLogger(__name__)
    timer = clock or time.perf_counter
    start = timer()
    response: Mapping[str, Any] | list[Any] | None = None
    ok = False
    try:
        response = tool.call(arguments)
        ok = True
        return response
    finally:
        elapsed_ms = int((timer() - start) * 1000)
        payload = {
            "event": "mcp_tool_audit",
            "server": tool.server_name,
            "tool": tool.tool_name,
            "args_hash": _hash_arguments(arguments),
            "latency_ms": elapsed_ms,
            "response_size": _response_size_bytes(response),
            "ok": ok,
        }
        log.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _hash_arguments(arguments: Mapping[str, Any]) -> str:
    normalized = _normalize_value(arguments)
    redacted = _redact_secrets(normalized)
    encoded = json.dumps(redacted, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _redact_secrets(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                redacted[str(key)] = _REDACTED_VALUE
            else:
                redacted[str(key)] = _redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SECRET_KEY_MARKERS)


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
