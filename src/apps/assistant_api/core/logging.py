from __future__ import annotations

import json
import logging
import uuid
from contextvars import ContextVar
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from apps.assistant_api.core.settings import Settings

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id_ctx.get()


def set_request_id(value: str) -> None:
    _request_id_ctx.set(value)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Callable,
        header_name: str = "X-Request-ID",
    ) -> None:
        super().__init__(app)
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(self._header_name) or str(uuid.uuid4())
        set_request_id(request_id)
        response = await call_next(request)
        response.headers[self._header_name] = request_id
        return response
