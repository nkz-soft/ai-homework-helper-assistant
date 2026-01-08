from __future__ import annotations

from typing import Any, Callable, Mapping

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.assistant_api.dependencies import get_orchestrator

router = APIRouter(prefix="/api/v1")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]]
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    safety_flags: list[str] = Field(default_factory=list)


OrchestratorFn = Callable[[str, Mapping[str, object] | None], Mapping[str, object]]


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    orchestrator: OrchestratorFn = Depends(get_orchestrator),
) -> ChatResponse:
    context = payload.context or {}
    result = orchestrator(payload.question, context or None)
    diagnostics = _coerce_dict(result.get("diagnostics"))
    errors = _coerce_list_of_str(diagnostics.get("errors"))
    if errors:
        diagnostics["errors"] = errors
    return ChatResponse(
        answer=str(result.get("final_answer") or ""),
        citations=_coerce_dict_list(result.get("citations")),
        diagnostics=diagnostics,
        safety_flags=_coerce_str_list(result.get("safety_flags")),
    )


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


def _coerce_list_of_str(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []
