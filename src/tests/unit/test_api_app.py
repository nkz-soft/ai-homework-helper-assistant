from __future__ import annotations

from typing import Mapping

from fastapi.testclient import TestClient

from apps.assistant_api.dependencies import get_orchestrator
from apps.assistant_api.main import create_app


def test_health_endpoint() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_uses_orchestrator() -> None:
    app = create_app()

    def _fake_orchestrator(
        question: str, context: Mapping[str, object] | None
    ) -> Mapping[str, object]:
        assert question == "What is inertia?"
        assert context == {"subject": "physics"}
        return {
            "final_answer": "Inertia is resistance to changes in motion.",
            "citations": [{"source": "wikipedia", "locator": "https://example.com"}],
            "diagnostics": {"note": "ok", "errors": ["partial_stackoverflow"]},
            "safety_flags": ["coach"],
        }

    app.dependency_overrides[get_orchestrator] = lambda: _fake_orchestrator
    client = TestClient(app)

    response = client.post(
        "/api/v1/chat",
        json={
            "question": "What is inertia?",
            "context": {"subject": "physics"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("Inertia")
    assert payload["citations"]
    assert payload["diagnostics"]["note"] == "ok"
    assert payload["diagnostics"]["errors"] == ["partial_stackoverflow"]
    assert payload["safety_flags"] == ["coach"]
