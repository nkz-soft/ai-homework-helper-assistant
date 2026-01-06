from __future__ import annotations

import unittest
from typing import Any, Mapping

from packages.mcp_clients.interceptors import (
    ToolBudgetLimits,
    ToolBudgetManager,
    ToolThrottleLimits,
    ToolThrottleManager,
)
from packages.mcp_clients.interceptors.budget import ToolBudgetExceeded


class _FakeToolHandle:
    def __init__(self, *, server_name: str, tool_name: str = "search") -> None:
        self.server_name = server_name
        self.tool_name = tool_name
        self.timeout_seconds = 1.0
        self.retry = None
        self.calls: list[Mapping[str, Any]] = []

    def call(self, arguments: Mapping[str, Any]) -> Any:
        self.calls.append(arguments)
        return {"ok": True}


class BudgetInterceptorTests(unittest.TestCase):
    def test_budget_module_exports(self) -> None:
        budget = ToolBudgetManager(limits=ToolBudgetLimits(total_calls=1))
        tool = _FakeToolHandle(server_name="wikipedia")

        budget.assert_can_call(tool)
        budget.record_call(tool)

        with self.assertRaises(ToolBudgetExceeded):
            budget.assert_can_call(tool)


class ThrottlingInterceptorTests(unittest.TestCase):
    def test_global_throttle_waits_min_interval(self) -> None:
        ticks = iter([0.0, 0.2])
        sleeps: list[float] = []
        tool = _FakeToolHandle(server_name="wikipedia")
        manager = ToolThrottleManager(
            limits=ToolThrottleLimits(min_interval_seconds=1.0),
            clock=lambda: next(ticks),
            sleep=lambda duration: sleeps.append(duration),
        )

        first = manager.throttle(tool)
        second = manager.throttle(tool)

        self.assertEqual(first, 0.0)
        self.assertEqual(second, 0.8)
        self.assertEqual(sleeps, [0.8])

    def test_per_server_throttle_only_targets_server(self) -> None:
        ticks = iter([0.0, 0.5, 1.0])
        sleeps: list[float] = []
        stack = _FakeToolHandle(server_name="stackoverflow")
        wiki = _FakeToolHandle(server_name="wikipedia")
        manager = ToolThrottleManager(
            limits=ToolThrottleLimits(per_server_min_interval={"stackoverflow": 2.0}),
            clock=lambda: next(ticks),
            sleep=lambda duration: sleeps.append(duration),
        )

        first = manager.throttle(stack)
        second = manager.throttle(wiki)
        third = manager.throttle(stack)

        self.assertEqual(first, 0.0)
        self.assertEqual(second, 0.0)
        self.assertEqual(third, 1.0)
        self.assertEqual(sleeps, [1.0])


if __name__ == "__main__":
    unittest.main()
