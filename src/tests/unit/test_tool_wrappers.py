from __future__ import annotations

import unittest
from typing import Any, Mapping

from packages.mcp_clients.tool_wrappers import (
    StackOverflowTimeoutError,
    StackOverflowToolError,
    WikipediaTimeoutError,
    WikipediaToolError,
    so_get_content,
    so_search,
    stackoverflow_tools,
    wikipedia_search,
    wikipedia_section,
    wikipedia_summary,
    wikipedia_tools,
)


class _FakeToolHandle:
    def __init__(
        self, tool_name: str, response: Any, *, server_name: str = "stackoverflow"
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

    def test_wikipedia_search_truncates_and_passes_lang(self) -> None:
        search_handle = _FakeToolHandle(
            "search_wikipedia",
            {
                "items": [
                    {
                        "pageid": 42,
                        "title": "Example",
                        "snippet": "x" * 20,
                        "fullurl": "https://en.wikipedia.org/wiki/Example",
                    }
                ]
            },
            server_name="wikipedia",
        )
        summary_handle = _FakeToolHandle(
            "get_summary", {"items": []}, server_name="wikipedia"
        )
        section_handle = _FakeToolHandle(
            "summarize_article_section", {"items": []}, server_name="wikipedia"
        )
        tools = wikipedia_tools(
            _FakeWikipediaTools(
                search_handle=search_handle,
                summary_handle=summary_handle,
                section_handle=section_handle,
            )
        )

        result = wikipedia_search(
            tools, query="Example", language="en", limit=3, max_chars=10
        )

        self.assertEqual(search_handle.calls, [{"query": "Example", "limit": 3}])
        self.assertEqual(result["tool"], "search")
        self.assertEqual(result["items"][0]["excerpt"], "xxxxxxx...")

    def test_wikipedia_summary_uses_page_arg(self) -> None:
        summary_handle = _FakeToolHandle(
            "get_summary",
            {"title": "Example", "extract": "content"},
            server_name="wikipedia",
        )
        tools = wikipedia_tools(
            _FakeWikipediaTools(
                search_handle=_FakeToolHandle(
                    "search_wikipedia", {"items": []}, server_name="wikipedia"
                ),
                summary_handle=summary_handle,
                section_handle=_FakeToolHandle(
                    "summarize_article_section", {"items": []}, server_name="wikipedia"
                ),
            )
        )

        result = wikipedia_summary(tools, page_id_or_title="Example", language=None)

        self.assertEqual(summary_handle.calls, [{"title": "Example"}])
        self.assertEqual(result["items"][0]["content"], "content")

    def test_wikipedia_section_handles_errors(self) -> None:
        section_handle = _FakeToolHandle(
            "summarize_article_section", {"error": "missing"}, server_name="wikipedia"
        )
        tools = wikipedia_tools(
            _FakeWikipediaTools(
                search_handle=_FakeToolHandle(
                    "search_wikipedia", {"items": []}, server_name="wikipedia"
                ),
                summary_handle=_FakeToolHandle(
                    "get_summary", {"items": []}, server_name="wikipedia"
                ),
                section_handle=section_handle,
            )
        )

        with self.assertRaises(WikipediaToolError):
            wikipedia_section(tools, page_id_or_title="Example", section="History")

    def test_wikipedia_section_timeout(self) -> None:
        section_handle = _FakeToolHandle(
            "summarize_article_section", TimeoutError("boom"), server_name="wikipedia"
        )
        tools = wikipedia_tools(
            _FakeWikipediaTools(
                search_handle=_FakeToolHandle(
                    "search_wikipedia", {"items": []}, server_name="wikipedia"
                ),
                summary_handle=_FakeToolHandle(
                    "get_summary", {"items": []}, server_name="wikipedia"
                ),
                section_handle=section_handle,
            )
        )

        with self.assertRaises(WikipediaTimeoutError):
            wikipedia_section(tools, page_id_or_title="Example", section="History")

    def test_so_search_rejects_missing_payload(self) -> None:
        search_handle = _FakeToolHandle("so_search", None)
        content_handle = _FakeToolHandle("get_content", {"items": []})
        tools = stackoverflow_tools(
            _FakeTools(search_handle=search_handle, content_handle=content_handle)
        )

        with self.assertRaises(StackOverflowToolError):
            so_search(tools, query="foo")

    def test_so_search_rejects_invalid_payload_type(self) -> None:
        search_handle = _FakeToolHandle("so_search", "not-a-mapping")
        content_handle = _FakeToolHandle("get_content", {"items": []})
        tools = stackoverflow_tools(
            _FakeTools(search_handle=search_handle, content_handle=content_handle)
        )

        with self.assertRaises(StackOverflowToolError):
            so_search(tools, query="foo")

    def test_wikipedia_section_includes_section_label(self) -> None:
        section_handle = _FakeToolHandle(
            "summarize_article_section",
            {
                "items": [
                    {
                        "pageid": 7,
                        "title": "Example",
                        "extract": "content",
                    }
                ]
            },
            server_name="wikipedia",
        )
        tools = wikipedia_tools(
            _FakeWikipediaTools(
                search_handle=_FakeToolHandle(
                    "search_wikipedia", {"items": []}, server_name="wikipedia"
                ),
                summary_handle=_FakeToolHandle(
                    "get_summary", {"items": []}, server_name="wikipedia"
                ),
                section_handle=section_handle,
            )
        )

        result = wikipedia_section(
            tools, page_id_or_title="Example", section="History", max_chars=100
        )

        self.assertEqual(result["items"][0]["section"], "History")

    def test_wikipedia_search_truncate_edge_cases(self) -> None:
        search_handle = _FakeToolHandle(
            "search_wikipedia",
            {
                "items": [
                    {
                        "pageid": 7,
                        "title": "Example",
                        "snippet": "abcd",
                    }
                ]
            },
            server_name="wikipedia",
        )
        tools = wikipedia_tools(
            _FakeWikipediaTools(
                search_handle=search_handle,
                summary_handle=_FakeToolHandle(
                    "get_summary", {"items": []}, server_name="wikipedia"
                ),
                section_handle=_FakeToolHandle(
                    "summarize_article_section", {"items": []}, server_name="wikipedia"
                ),
            )
        )

        result_zero = wikipedia_search(tools, query="Example", max_chars=0)
        result_two = wikipedia_search(tools, query="Example", max_chars=2)

        self.assertEqual(result_zero["items"][0]["excerpt"], "")
        self.assertEqual(result_two["items"][0]["excerpt"], "ab")

    def test_stackoverflow_item_omits_invalid_score(self) -> None:
        search_handle = _FakeToolHandle(
            "so_search",
            {
                "items": [
                    {
                        "question_id": "1",
                        "title": "Example",
                        "score": "not-a-number",
                    }
                ]
            },
        )
        tools = stackoverflow_tools(
            _FakeTools(
                search_handle=search_handle,
                content_handle=_FakeToolHandle("get_content", {"items": []}),
            )
        )

        result = so_search(tools, query="foo")

        self.assertNotIn("score", result["items"][0])

    def test_wikipedia_summary_fallbacks_to_raw_entry(self) -> None:
        summary_handle = _FakeToolHandle(
            "get_summary",
            {"title": "Example", "extract": "content"},
            server_name="wikipedia",
        )
        tools = wikipedia_tools(
            _FakeWikipediaTools(
                search_handle=_FakeToolHandle(
                    "search_wikipedia", {"items": []}, server_name="wikipedia"
                ),
                summary_handle=summary_handle,
                section_handle=_FakeToolHandle(
                    "summarize_article_section", {"items": []}, server_name="wikipedia"
                ),
            )
        )

        result = wikipedia_summary(tools, page_id_or_title="Example")

        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["title"], "Example")


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


class _FakeWikipediaTools:
    def __init__(
        self,
        *,
        search_handle: _FakeToolHandle,
        summary_handle: _FakeToolHandle,
        section_handle: _FakeToolHandle,
    ) -> None:
        self._search = search_handle
        self._summary = summary_handle
        self._section = section_handle

    def handle(self, tool_name: str) -> _FakeToolHandle:
        if tool_name == "search_wikipedia":
            return self._search
        if tool_name == "get_summary":
            return self._summary
        if tool_name == "summarize_article_section":
            return self._section
        raise AssertionError(f"Unexpected tool: {tool_name}")


if __name__ == "__main__":
    unittest.main()
