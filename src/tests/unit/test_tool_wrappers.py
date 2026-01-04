from __future__ import annotations

import unittest
from typing import Any, Mapping

from packages.mcp_clients.tool_wrappers import (
    StackOverflowTimeoutError,
    StackOverflowToolError,
    so_get_content,
    so_search,
    stackoverflow_tools,
)


class _FakeToolHandle:
    def __init__(self, tool_name: str, response: Any) -> None:
        self.server_name = "stackoverflow"
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


class ToolWrappersTests(unittest.TestCase):
    def test_so_search_normalizes_items(self) -> None:
        search_handle = _FakeToolHandle(
            "so_search",
            {
                "items": [
                    {
                        "question_id": 123,
                        "title": "How to foo?",
                        "link": "https://example.com/q/123",
                        "summary": "short",
                        "tags": ["python"],
                        "score": "2",
                        "answer_count": 1,
                        "accepted": True,
                    }
                ]
            },
        )
        content_handle = _FakeToolHandle("get_content", {"items": []})
        tools = stackoverflow_tools(
            _FakeTools(search_handle=search_handle, content_handle=content_handle)
        )

        result = so_search(tools, query="foo", tags=["python"], limit=5)

        self.assertTrue(result["ok"])
        self.assertEqual(result["tool"], "so_search")
        self.assertEqual(
            search_handle.calls, [{"query": "foo", "tags": ["python"], "limit": 5}]
        )
        self.assertEqual(len(result["items"]), 1)
        item = result["items"][0]
        self.assertEqual(item["question_id"], "123")
        self.assertEqual(item["title"], "How to foo?")
        self.assertEqual(item["url"], "https://example.com/q/123")
        self.assertEqual(item["excerpt"], "short")
        self.assertEqual(item["tags"], ["python"])
        self.assertEqual(item["score"], 2)
        self.assertEqual(item["answer_count"], 1)
        self.assertTrue(item["accepted"])

    def test_so_get_content_handles_list_payload(self) -> None:
        search_handle = _FakeToolHandle("so_search", {"items": []})
        content_handle = _FakeToolHandle(
            "get_content",
            [
                {
                    "question_id": "99",
                    "body": "content",
                }
            ],
        )
        tools = stackoverflow_tools(
            _FakeTools(search_handle=search_handle, content_handle=content_handle)
        )

        result = so_get_content(tools, question_id="99")

        self.assertEqual(content_handle.calls, [{"question_id": "99"}])
        self.assertEqual(result["tool"], "get_content")
        self.assertEqual(result["items"][0]["content"], "content")

    def test_raises_on_tool_error_payload(self) -> None:
        search_handle = _FakeToolHandle("so_search", {"error": "quota"})
        content_handle = _FakeToolHandle("get_content", {"items": []})
        tools = stackoverflow_tools(
            _FakeTools(search_handle=search_handle, content_handle=content_handle)
        )

        with self.assertRaises(StackOverflowToolError):
            so_search(tools, query="foo")

    def test_raises_on_timeout(self) -> None:
        search_handle = _FakeToolHandle("so_search", TimeoutError("boom"))
        content_handle = _FakeToolHandle("get_content", {"items": []})
        tools = stackoverflow_tools(
            _FakeTools(search_handle=search_handle, content_handle=content_handle)
        )

        with self.assertRaises(StackOverflowTimeoutError):
            so_search(tools, query="foo")


class _FakeTools:
    def __init__(
        self, *, search_handle: _FakeToolHandle, content_handle: _FakeToolHandle
    ) -> None:
        self._search = search_handle
        self._content = content_handle

    def handle(self, tool_name: str) -> _FakeToolHandle:
        if tool_name == "so_search":
            return self._search
        if tool_name == "get_content":
            return self._content
        raise AssertionError(f"Unexpected tool: {tool_name}")


if __name__ == "__main__":
    unittest.main()
