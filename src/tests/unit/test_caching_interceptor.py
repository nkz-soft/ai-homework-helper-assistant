from __future__ import annotations

import unittest
from typing import Any, Mapping

from packages.mcp_clients.interceptors import (
    ToolBudgetExceeded,
    ToolBudgetLimits,
    ToolBudgetManager,
    ToolCallCache,
    cache_tool_call,
)


class _FakeToolHandle:
    def __init__(
        self,
        *,
        server_name: str,
        tool_name: str,
        response: Any,
    ) -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        self.timeout_seconds = 1.0
        self.retry = None
        self._response = response
        self.calls: list[Mapping[str, Any]] = []

    def call(self, arguments: Mapping[str, Any]) -> Any:
        self.calls.append(arguments)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class CachingInterceptorTests(unittest.TestCase):
    def test_cache_hit_skips_tool_call(self) -> None:
        tool = _FakeToolHandle(
            server_name="wikipedia",
            tool_name="summary",
            response={"items": [{"title": "Example"}]},
        )
        cache = ToolCallCache(ttl_seconds=60.0, clock=lambda: 1.0)

        first = cache_tool_call(tool, {"page": "Example"}, cache=cache)
        second = cache_tool_call(tool, {"page": "Example"}, cache=cache)

        self.assertEqual(first, {"items": [{"title": "Example"}]})
        self.assertEqual(second, {"items": [{"title": "Example"}]})
        self.assertEqual(tool.calls, [{"page": "Example"}])

    def test_cache_respects_ttl(self) -> None:
        tool = _FakeToolHandle(
            server_name="stackoverflow",
            tool_name="so_search",
            response={"items": []},
        )
        clock_ticks = iter([0.0, 1.0, 6.0, 6.0])
        cache = ToolCallCache(ttl_seconds=5.0, clock=lambda: next(clock_ticks))

        cache_tool_call(tool, {"query": "foo"}, cache=cache)
        cache_tool_call(tool, {"query": "foo"}, cache=cache)
        cache_tool_call(tool, {"query": "foo"}, cache=cache)

        self.assertEqual(
            tool.calls,
            [{"query": "foo"}, {"query": "foo"}],
        )

    def test_budget_total_calls_enforced(self) -> None:
        tool = _FakeToolHandle(
            server_name="wikipedia",
            tool_name="search",
            response={"items": []},
        )
        budget = ToolBudgetManager(limits=ToolBudgetLimits(total_calls=1))

        cache_tool_call(tool, {"query": "first"}, budget_manager=budget)

        with self.assertRaises(ToolBudgetExceeded):
            cache_tool_call(tool, {"query": "second"}, budget_manager=budget)

        self.assertEqual(tool.calls, [{"query": "first"}])

    def test_budget_per_server_cap_enforced(self) -> None:
        tool = _FakeToolHandle(
            server_name="stackoverflow",
            tool_name="so_search",
            response={"items": []},
        )
        budget = ToolBudgetManager(
            limits=ToolBudgetLimits(per_server_caps={"stackoverflow": 1})
        )

        cache_tool_call(tool, {"query": "first"}, budget_manager=budget)

        with self.assertRaises(ToolBudgetExceeded):
            cache_tool_call(tool, {"query": "second"}, budget_manager=budget)

        self.assertEqual(tool.calls, [{"query": "first"}])

    def test_budget_max_payload_bytes_enforced(self) -> None:
        tool = _FakeToolHandle(
            server_name="textbooks",
            tool_name="read_chunk",
            response="abcd",
        )
        budget = ToolBudgetManager(limits=ToolBudgetLimits(max_payload_bytes=3))

        with self.assertRaises(ToolBudgetExceeded):
            cache_tool_call(tool, {"chunk_id": "1"}, budget_manager=budget)

        self.assertEqual(tool.calls, [{"chunk_id": "1"}])

    def test_cache_hit_does_not_consume_budget(self) -> None:
        tool = _FakeToolHandle(
            server_name="wikipedia",
            tool_name="summary",
            response={"items": [{"title": "Example"}]},
        )
        cache = ToolCallCache(ttl_seconds=30.0, clock=lambda: 5.0)
        budget = ToolBudgetManager(limits=ToolBudgetLimits(total_calls=1))

        cache_tool_call(tool, {"page": "Example"}, cache=cache, budget_manager=budget)
        cache_tool_call(tool, {"page": "Example"}, cache=cache, budget_manager=budget)

        self.assertEqual(tool.calls, [{"page": "Example"}])


if __name__ == "__main__":
    unittest.main()
