from __future__ import annotations

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimiter:
    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: int,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._clock = clock or time.time
        self._requests: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        window_start = now - self._window_seconds
        timestamps = [ts for ts in self._requests.get(key, []) if ts >= window_start]
        if len(timestamps) >= self._max_requests:
            self._requests[key] = timestamps
            return False
        timestamps.append(now)
        self._requests[key] = timestamps
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Callable,
        limiter: RateLimiter,
        header_name: str = "X-Forwarded-For",
    ) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client = request.client
        ip = request.headers.get(self._header_name) or (client.host if client else "")
        if not self._limiter.allow(ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded."},
            )
        return await call_next(request)
