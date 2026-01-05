from __future__ import annotations

import unittest
from typing import Any, Mapping

from packages.mcp_clients.tool_wrappers import stackoverflow_tools
from packages.orchestrator.retrieval import retrieve_stackoverflow


class _FakeToolHandle:
    def __init__(self, tool_name: str) -> None:
        self.server_name = "stackoverflow"
        self.tool_name = tool_name
        self.timeout_seconds = 1.0
        self.retry = None
        self.calls: list[Mapping[str, Any]] = []

    def call(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append(arguments)
        if self.tool_name == "so_search":
            return {
                "items": [
                    {"question_id": "1", "title": "First"},
                    {"question_id": "2", "title": "Second"},
                    {"title": "No id"},
                ]
            }
        if self.tool_name == "get_content":
            question_id = arguments.get("question_id")
            return {"items": [{"question_id": question_id, "content": "body"}]}
        raise AssertionError(f"Unexpected tool: {self.tool_name}")


class _FakeTools:
    def __init__(self) -> None:
        self.search_handle = _FakeToolHandle("so_search")
        self.content_handle = _FakeToolHandle("get_content")

    def handle(self, tool_name: str) -> _FakeToolHandle:
        if tool_name == "so_search":
            return self.search_handle
        if tool_name == "get_content":
            return self.content_handle
        raise AssertionError(f"Unexpected tool: {tool_name}")


class RetrievalTests(unittest.TestCase):
    def test_retrieve_stackoverflow_calls_content_for_items(self) -> None:
        tools = stackoverflow_tools(_FakeTools())

        results = retrieve_stackoverflow(
            tools,
            query="unit test",
            tags=["python"],
            max_items=2,
        )

        self.assertEqual(
            tools.search.calls, [{"query": "unit test", "tags": ["python"], "limit": 2}]
        )
        self.assertEqual(
            tools.get_content.calls,
            [{"question_id": "1"}, {"question_id": "2"}],
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["tool"], "so_search")
        self.assertEqual(results[1]["tool"], "get_content")
        self.assertEqual(results[2]["tool"], "get_content")

    def test_retrieve_stackoverflow_skips_missing_question_id(self) -> None:
        tools = stackoverflow_tools(_FakeTools())

        results = retrieve_stackoverflow(
            tools,
            query="unit test",
            tags=None,
            max_items=3,
        )

        self.assertEqual(
            tools.get_content.calls,
            [{"question_id": "1"}, {"question_id": "2"}],
        )
        self.assertEqual(len(results), 3)


if __name__ == "__main__":
    unittest.main()
