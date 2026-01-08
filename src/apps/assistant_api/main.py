from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from packages.orchestrator.graph.build_graph import run as run_orchestrator

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


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    student_context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]]
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    safety_flags: list[str] = Field(default_factory=list)


OrchestratorFn = Callable[[str, Mapping[str, object] | None], Mapping[str, object]]


def get_orchestrator() -> OrchestratorFn:
    return run_orchestrator


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings)
    app = FastAPI(title=settings.app_name)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/chat", response_model=ChatResponse)
    def chat(
        payload: ChatRequest,
        orchestrator: OrchestratorFn = Depends(get_orchestrator),
    ) -> ChatResponse:
        context: dict[str, object] = {}
        if payload.student_context:
            context["student_context"] = payload.student_context
        result = orchestrator(payload.question, context or None)
        return ChatResponse(
            answer=str(result.get("final_answer") or ""),
            citations=_coerce_dict_list(result.get("citations")),
            diagnostics=_coerce_dict(result.get("diagnostics")),
            safety_flags=_coerce_str_list(result.get("safety_flags")),
        )

    return app


app = create_app()


def _coerce_dict_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _coerce_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _coerce_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []
