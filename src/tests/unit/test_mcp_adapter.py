from __future__ import annotations

import unittest
from typing import Any, Mapping

from mcp import types as mcp_types

from packages.mcp_clients.client_factory import (
    McpClientSettings,
    McpServerTools,
    _coerce_tool_result,
)


class McpAdapterTests(unittest.TestCase):
    def test_server_tools_calls_caller(self) -> None:
        received: dict[str, Any] = {}

        def _caller(
            server_name: str,
            tool_name: str,
            arguments: Mapping[str, Any],
            timeout_seconds: float,
            retry: object,
        ) -> Mapping[str, Any]:
            received.update(
                {
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "arguments": dict(arguments),
                    "timeout_seconds": timeout_seconds,
                }
            )
            return {"ok": True}

        tools = McpServerTools(
            server_name="wikipedia",
            settings=McpClientSettings(timeout_seconds=5.0),
            caller=_caller,
        )

        handle = tools.handle("search_wikipedia")
        result = handle.call({"query": "inertia"})

        self.assertEqual(result, {"ok": True})
        self.assertEqual(received["server_name"], "wikipedia")
        self.assertEqual(received["tool_name"], "search_wikipedia")
        self.assertEqual(received["arguments"], {"query": "inertia"})
        self.assertEqual(received["timeout_seconds"], 5.0)

    def test_coerce_tool_result_prefers_structured_content(self) -> None:
        result = mcp_types.CallToolResult(
            content=[],
            structuredContent={"items": [{"title": "Example"}]},
            isError=False,
        )

        payload = _coerce_tool_result(result)

        self.assertEqual(payload, {"items": [{"title": "Example"}]})

    def test_coerce_tool_result_parses_json_text(self) -> None:
        content = mcp_types.TextContent(type="text", text='{"answer": "ok"}')
        result = mcp_types.CallToolResult(
            content=[content],
            structuredContent=None,
            isError=False,
        )

        payload = _coerce_tool_result(result)

        self.assertEqual(payload, {"answer": "ok"})

    def test_coerce_tool_result_raises_on_error(self) -> None:
        result = mcp_types.CallToolResult(
            content=[],
            structuredContent=None,
            isError=True,
        )

        with self.assertRaises(RuntimeError):
            _coerce_tool_result(result)


if __name__ == "__main__":
    unittest.main()
