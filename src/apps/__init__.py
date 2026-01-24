from __future__ import annotations

from typing import Callable, Mapping

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from apps.assistant_api.api.v1.chat import router as chat_router
from apps.assistant_api.core.logging import RequestIdMiddleware, configure_logging
from apps.assistant_api.core.rate_limit import RateLimiter, RateLimitMiddleware
from apps.assistant_api.core.settings import load_settings
from apps.assistant_api.ui import get_static_dir
from apps.assistant_api.ui.routes import router as ui_router


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
    app.mount("/static", StaticFiles(directory=get_static_dir()), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(chat_router)
    app.include_router(ui_router)

    return app


app = create_app()
