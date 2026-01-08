from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable, Mapping

from fastapi import FastAPI

from apps.assistant_api.api.v1.chat import router as chat_router

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Homework Helper API"
    log_level: str = "INFO"


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Homework Helper API"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def configure_logging(settings: Settings) -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


OrchestratorFn = Callable[[str, Mapping[str, object] | None], Mapping[str, object]]


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings)
    app = FastAPI(title=settings.app_name)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(chat_router)

    return app


app = create_app()
