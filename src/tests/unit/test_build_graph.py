from __future__ import annotations

from typing import Any, Mapping

from packages.orchestrator.graph.build_graph import run


class _FakeToolHandle:
    def __init__(
        self,
        *,
        server_name: str,
        tool_name: str,
        response: Mapping[str, Any],
    ) -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        self.timeout_seconds = 0.5
        self.retry = None
        self.calls: list[Mapping[str, Any]] = []
        self._response = response

    def call(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append(arguments)
        return dict(self._response)


class _FakeServerTools:
    def __init__(self, server_name: str, handles: dict[str, _FakeToolHandle]) -> None:
        self.server_name = server_name
        self._handles = handles

    def handle(self, tool_name: str) -> _FakeToolHandle:
        return self._handles[tool_name]


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


def test_run_builds_answer_with_citations() -> None:
    stack_search = _FakeToolHandle(
        server_name="stackoverflow",
        tool_name="search_questions",
        response={
            "items": [
                {
                    "question_id": "1",
                    "title": "Why does Python throw a TypeError?",
                    "url": "https://stackoverflow.com/q/1",
                    "excerpt": "TypeError happens when operands are incompatible.",
                    "score": 7,
                }
            ]
        },
    )
    wiki_search = _FakeToolHandle(
        server_name="wikipedia",
        tool_name="search",
        response={
            "items": [
                {
                    "page_id": "10",
                    "title": "Type system",
                    "url": "https://en.wikipedia.org/wiki/Type_system",
                    "excerpt": "Type systems classify values and expressions.",
                }
            ]
        },
    )
    wiki_summary = _FakeToolHandle(
        server_name="wikipedia",
        tool_name="summary",
        response={"items": []},
    )
    wiki_section = _FakeToolHandle(
        server_name="wikipedia",
        tool_name="section",
        response={"items": []},
    )

    tools = {
        "stackoverflow": _FakeServerTools(
            "stackoverflow",
            {"search_questions": stack_search, "get_question": stack_search},
        ),
        "wikipedia": _FakeServerTools(
            "wikipedia",
            {
                "search": wiki_search,
                "summary": wiki_summary,
                "section": wiki_section,
            },
        ),
    }

    result = run(
        "Python error",
        {
            "tools": tools,
            "student_context": {"language": "en"},
        },
    )

    assert "final_answer" in result
    assert "citations" in result
    assert result["citations"]
    assert "Explanation" in result["final_answer"]


def test_run_accepts_llm_client() -> None:
    tools = {
        "wikipedia": _FakeServerTools(
            "wikipedia",
            {
                "search": _FakeToolHandle(
                    server_name="wikipedia",
                    tool_name="search",
                    response={
                        "items": [
                            {
                                "page_id": "10",
                                "title": "Type system",
                                "url": "https://en.wikipedia.org/wiki/Type_system",
                                "excerpt": "Type systems classify values and expressions.",
                            }
                        ]
                    },
                ),
                "summary": _FakeToolHandle(
                    server_name="wikipedia",
                    tool_name="summary",
                    response={"items": []},
                ),
                "section": _FakeToolHandle(
                    server_name="wikipedia",
                    tool_name="section",
                    response={"items": []},
                ),
            },
        ),
    }

    result = run(
        "What is a type system?",
        {"tools": tools},
        llm_client=_FakeLlmClient(),
    )

    assert "final_answer" in result
