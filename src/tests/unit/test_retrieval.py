from __future__ import annotations

import unittest
from typing import Any, Mapping

from packages.mcp_clients.interceptors import ToolBudgetLimits, ToolBudgetManager
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
        if self.tool_name == "search_questions":
            return {
                "items": [
                    {"question_id": "1", "title": "First"},
                    {"question_id": "2", "title": "Second"},
                    {"title": "No id"},
                ]
            }
        if self.tool_name == "get_question":
            question_id = arguments.get("question_id")
            return {"items": [{"question_id": question_id, "content": "body"}]}
        raise AssertionError(f"Unexpected tool: {self.tool_name}")


class _FakeTools:
    def __init__(self) -> None:
        self.search_handle = _FakeToolHandle("search_questions")
        self.content_handle = _FakeToolHandle("get_question")

    def handle(self, tool_name: str) -> _FakeToolHandle:
        if tool_name == "search_questions":
            return self.search_handle
        if tool_name == "get_question":
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

        self.assertEqual(tools.search.calls, [{"query": "unit test", "limit": 2}])
        self.assertEqual(
            tools.get_content.calls,
            [{"question_id": 1}, {"question_id": 2}],
        )
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["tool"], "search_questions")
        self.assertEqual(results[1]["tool"], "get_question")
        self.assertEqual(results[2]["tool"], "get_question")

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
            [{"question_id": 1}, {"question_id": 2}],
        )
        self.assertEqual(len(results), 3)

    def test_retrieve_stackoverflow_skips_content_when_budget_exhausted(self) -> None:
        tools = stackoverflow_tools(_FakeTools())
        budget = ToolBudgetManager(limits=ToolBudgetLimits(total_calls=1))

        results = retrieve_stackoverflow(
            tools,
            query="unit test",
            tags=None,
            max_items=2,
            budget_manager=budget,
        )

        self.assertEqual(tools.search.calls, [{"query": "unit test", "limit": 2}])
        self.assertEqual(tools.get_content.calls, [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tool"], "search_questions")
        self.assertTrue(results[0]["metadata"]["degraded"])
        self.assertEqual(
            results[0]["metadata"]["reason"], "stackoverflow_budget_exhausted"
        )

    def test_retrieve_stackoverflow_returns_metadata_when_budget_blocks_search(
        self,
    ) -> None:
        tools = stackoverflow_tools(_FakeTools())
        budget = ToolBudgetManager(limits=ToolBudgetLimits(total_calls=0))

        results = retrieve_stackoverflow(
            tools,
            query="unit test",
            tags=None,
            max_items=2,
            budget_manager=budget,
        )

        self.assertEqual(tools.search.calls, [])
        self.assertEqual(tools.get_content.calls, [])
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["ok"])
        self.assertTrue(results[0]["metadata"]["degraded"])
        self.assertEqual(
            results[0]["metadata"]["reason"], "stackoverflow_budget_exhausted"
        )


if __name__ == "__main__":
    unittest.main()
