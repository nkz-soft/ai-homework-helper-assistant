from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Mapping

from ..client_factory import McpToolHandle


@dataclass(frozen=True)
class ToolThrottleLimits:
    min_interval_seconds: float | None = None
    per_server_min_interval: Mapping[str, float] | None = None


class ToolThrottleManager:
    def __init__(
        self,
        *,
        limits: ToolThrottleLimits | None = None,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        resolved = limits or ToolThrottleLimits()
        self._min_interval = resolved.min_interval_seconds
        self._per_server_min = dict(resolved.per_server_min_interval or {})
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._last_call_at: float | None = None
        self._last_server_call_at: dict[str, float] = {}

    def throttle(self, tool: McpToolHandle) -> float:
        now = self._clock()
        wait_until = now
        if self._min_interval is not None and self._last_call_at is not None:
            wait_until = max(wait_until, self._last_call_at + self._min_interval)

        server = tool.server_name
        per_server = self._per_server_min.get(server)
        if per_server is not None:
            last_server = self._last_server_call_at.get(server)
            if last_server is not None:
                wait_until = max(wait_until, last_server + per_server)

        delay = max(0.0, wait_until - now)
        if delay > 0:
            self._sleep(delay)
            now = wait_until

        self._last_call_at = now
        self._last_server_call_at[server] = now
        return delay
