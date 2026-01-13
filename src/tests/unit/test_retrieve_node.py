from __future__ import annotations

import asyncio
from typing import Any, Mapping

from packages.orchestrator.graph.nodes.retrieve import retrieve


class _FakeToolHandle:
    def __init__(
        self,
        *,
        server_name: str,
        tool_name: str,
        response: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        self.timeout_seconds = 0.5
        self.retry = None
        self.calls: list[Mapping[str, Any]] = []
        self._response = response or {}
        self._error = error

    def call(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append(arguments)
        if self._error is not None:
            raise self._error
        return dict(self._response)


class _FakeServerTools:
    def __init__(self, server_name: str, handles: dict[str, _FakeToolHandle]) -> None:
        self.server_name = server_name
        self._handles = handles

    def handle(self, tool_name: str) -> _FakeToolHandle:
        return self._handles[tool_name]


def test_retrieve_partial_failure_timeout() -> None:
    stack_search = _FakeToolHandle(
        server_name="stackoverflow",
        tool_name="so_search",
        response={"items": [{"question_id": "1", "title": "First"}]},
    )
    stack_content = _FakeToolHandle(
        server_name="stackoverflow",
        tool_name="get_content",
        response={"items": [{"question_id": "1", "content": "body"}]},
    )
    wiki_search = _FakeToolHandle(
        server_name="wikipedia",
        tool_name="search_wikipedia",
        error=TimeoutError("boom"),
    )
    wiki_summary = _FakeToolHandle(
        server_name="wikipedia",
        tool_name="get_summary",
        response={"items": []},
    )
    wiki_section = _FakeToolHandle(
        server_name="wikipedia",
        tool_name="summarize_article_section",
        response={"items": []},
    )

    tools = {
        "stackoverflow": _FakeServerTools(
            "stackoverflow",
            {
                "so_search": stack_search,
                "get_content": stack_content,
            },
        ),
        "wikipedia": _FakeServerTools(
            "wikipedia",
            {
                "search_wikipedia": wiki_search,
                "get_summary": wiki_summary,
                "summarize_article_section": wiki_section,
            },
        ),
    }

    state = {
        "retrieval_plan": {
            "calls": [
                {
                    "source": "stackoverflow",
                    "tool": "so_search",
                    "query": "python error",
                    "priority": 1,
                },
                {
                    "source": "wikipedia",
                    "tool": "wikipedia_search",
                    "query": "python",
                    "priority": 2,
                },
            ],
        },
        "tools": tools,
    }

    result = asyncio.run(retrieve(state))
    retrieved = result["retrieved_items"]

    assert len(retrieved) == 2
    stack_item = next(item for item in retrieved if item["source"] == "stackoverflow")
    wiki_item = next(item for item in retrieved if item["source"] == "wikipedia")

    assert "error" not in stack_item
    assert stack_item["result"]["ok"] is True
    assert "tool_error" in wiki_item["error"]
    assert "timed out" in wiki_item["error"]
    assert wiki_search.calls


def test_retrieve_budget_enforcement() -> None:
    stack_search = _FakeToolHandle(
        server_name="stackoverflow",
        tool_name="so_search",
        response={"items": [{"question_id": "2", "title": "Second"}]},
    )
    stack_content = _FakeToolHandle(
        server_name="stackoverflow",
        tool_name="get_content",
        response={"items": [{"question_id": "2", "content": "body"}]},
    )
    wiki_search = _FakeToolHandle(
        server_name="wikipedia",
        tool_name="search_wikipedia",
        response={"items": [{"title": "Python"}]},
    )
    wiki_summary = _FakeToolHandle(
        server_name="wikipedia",
        tool_name="get_summary",
        response={"items": []},
    )
    wiki_section = _FakeToolHandle(
        server_name="wikipedia",
        tool_name="summarize_article_section",
        response={"items": []},
    )

    tools = {
        "stackoverflow": _FakeServerTools(
            "stackoverflow",
            {
                "so_search": stack_search,
                "get_content": stack_content,
            },
        ),
        "wikipedia": _FakeServerTools(
            "wikipedia",
            {
                "search_wikipedia": wiki_search,
                "get_summary": wiki_summary,
                "summarize_article_section": wiki_section,
            },
        ),
    }

    state = {
        "retrieval_plan": {
            "calls": [
                {
                    "source": "stackoverflow",
                    "tool": "so_search",
                    "query": "list comprehension",
                    "priority": 1,
                },
                {
                    "source": "wikipedia",
                    "tool": "wikipedia_search",
                    "query": "list comprehension",
                    "priority": 2,
                },
            ],
        },
        "tool_budget": {"per_server_caps": {"wikipedia": 0}},
        "tools": tools,
    }

    result = asyncio.run(retrieve(state))
    retrieved = result["retrieved_items"]

    stack_item = next(item for item in retrieved if item["source"] == "stackoverflow")
    wiki_item = next(item for item in retrieved if item["source"] == "wikipedia")

    assert "error" not in stack_item
    assert stack_item["result"]["ok"] is True
    assert "tool_budget_exceeded" in wiki_item["error"]
    assert not wiki_search.calls
