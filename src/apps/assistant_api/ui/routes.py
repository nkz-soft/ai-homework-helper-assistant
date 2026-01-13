from __future__ import annotations

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from apps.assistant_api.api.v1.chat import ChatRequest, ChatResponse, chat
from apps.assistant_api.dependencies import get_orchestrator
from apps.assistant_api.ui import get_templates

logger = logging.getLogger(__name__)

router = APIRouter()

templates = get_templates()


class Citation(BaseModel):
    label: str
    url: str | None = None


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    is_error: bool = False


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    messages: list[Message] = []
    return templates.TemplateResponse(
        "chat.html",
        _build_template_context(request, messages),
    )


@router.get("/ui", response_class=HTMLResponse)
def ui_index(request: Request) -> HTMLResponse:
    messages: list[Message] = []
    return templates.TemplateResponse(
        "chat.html",
        _build_template_context(request, messages),
    )


@router.post("/ui/chat", response_class=HTMLResponse)
def ui_chat(
    request: Request,
    question: str = Form(""),
    messages: str = Form(""),
) -> HTMLResponse:
    existing_messages = _parse_messages(messages)
    cleaned_question = question.strip()
    if not cleaned_question:
        existing_messages.append(
            Message(
                role="assistant",
                content="Please enter a question before submitting.",
                is_error=True,
            )
        )
        return templates.TemplateResponse(
            "_messages.html",
            _build_template_context(request, existing_messages),
        )

    existing_messages.append(Message(role="user", content=cleaned_question))

    orchestrator = get_orchestrator()
    try:
        response = chat(
            payload=ChatRequest(question=cleaned_question, context=None),
            orchestrator=orchestrator,
        )
        existing_messages.append(_message_from_response(response))
    except Exception as exc:  # noqa: BLE001 - UI should handle unexpected failures.
        logger.exception("UI chat request failed")
        existing_messages.append(
            Message(
                role="assistant",
                content="Request failed. Please try again.",
                is_error=True,
                diagnostics={"error": str(exc)},
            )
        )

    return templates.TemplateResponse(
        "_messages.html",
        _build_template_context(request, existing_messages),
    )


def _message_from_response(response: ChatResponse) -> Message:
    return Message(
        role="assistant",
        content=response.answer,
        citations=_format_citations(response.citations),
        diagnostics=response.diagnostics,
    )


def _format_citations(raw_citations: list[dict[str, Any]]) -> list[Citation]:
    citations: list[Citation] = []
    for citation in raw_citations:
        if not isinstance(citation, dict):
            continue
        label = (
            citation.get("title")
            or citation.get("source")
            or citation.get("ref")
            or citation.get("locator")
            or "Source"
        )
        url = (
            citation.get("locator")
            if isinstance(citation.get("locator"), str)
            else None
        )
        citations.append(Citation(label=str(label), url=url))
    return citations


def _parse_messages(raw_messages: str) -> list[Message]:
    if not raw_messages:
        return []
    try:
        payload = json.loads(raw_messages)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    messages: list[Message] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            messages.append(Message.model_validate(item))
        except ValidationError:
            continue
    return messages


def _build_template_context(
    request: Request, messages: list[Message]
) -> dict[str, Any]:
    messages_json = json.dumps(
        [message.model_dump() for message in messages],
        ensure_ascii=True,
    )
    return {
        "request": request,
        "messages": messages,
        "messages_json": messages_json,
    }
