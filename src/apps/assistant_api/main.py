from __future__ import annotations

from typing import Callable, Mapping

from fastapi import FastAPI

from apps.assistant_api.api.v1.chat import router as chat_router
from apps.assistant_api.core.logging import RequestIdMiddleware, configure_logging
from apps.assistant_api.core.rate_limit import RateLimiter, RateLimitMiddleware
from apps.assistant_api.core.settings import load_settings


OrchestratorFn = Callable[[str, Mapping[str, object] | None], Mapping[str, object]]


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings)
    app = FastAPI(title=settings.app_name)
    limiter = RateLimiter(
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(chat_router)

    return app


app = create_app()
