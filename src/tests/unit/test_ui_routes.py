from __future__ import annotations

from typing import Mapping

from fastapi.testclient import TestClient

from apps.assistant_api.dependencies import get_orchestrator
from apps.assistant_api.main import create_app


def test_ui_index_renders_chat_page() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert 'hx-post="/ui/chat"' in response.text
    assert "Homework Helper" in response.text


def test_ui_chat_renders_messages() -> None:
    app = create_app()

    def _fake_orchestrator(
        question: str, context: Mapping[str, object] | None
    ) -> Mapping[str, object]:
        assert question == "Define inertia"
        assert context is None
        return {
            "final_answer": "Inertia is the tendency to resist changes in motion.",
            "citations": [
                {
                    "title": "Newton's Laws",
                    "locator": "https://example.com/newton",
                }
            ],
            "diagnostics": {"note": "ok"},
        }

    app.dependency_overrides[get_orchestrator] = lambda: _fake_orchestrator
    client = TestClient(app)

    response = client.post(
        "/ui/chat",
        data={"question": "Define inertia", "messages": "[]"},
    )

    assert response.status_code == 200
    assert "Inertia is the tendency" in response.text
    assert "Sources" in response.text
    assert "Newton's Laws" in response.text


def test_ui_chat_shows_error_message_on_failure() -> None:
    app = create_app()

    def _failing_orchestrator(
        question: str, context: Mapping[str, object] | None
    ) -> Mapping[str, object]:
        raise RuntimeError("boom")

    app.dependency_overrides[get_orchestrator] = lambda: _failing_orchestrator
    client = TestClient(app)

    response = client.post(
        "/ui/chat",
        data={"question": "Define inertia", "messages": "[]"},
    )

    assert response.status_code == 200
    assert "Request failed" in response.text
