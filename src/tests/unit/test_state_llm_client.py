from __future__ import annotations

from typing import Any, Mapping

from packages.orchestrator.graph.state import get_llm_client


class _FakeLlmClient:
    def generate(
        self,
        prompt: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return "ok"


def test_get_llm_client_returns_client() -> None:
    state = {"llm_client": _FakeLlmClient()}
    assert get_llm_client(state) is state["llm_client"]


def test_get_llm_client_handles_missing() -> None:
    assert get_llm_client({}) is None


def test_get_llm_client_rejects_invalid() -> None:
    assert get_llm_client({"llm_client": object()}) is None
