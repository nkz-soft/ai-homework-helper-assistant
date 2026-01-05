from __future__ import annotations

import json
import logging
import unittest
from io import StringIO
from typing import Any, Mapping

from packages.mcp_clients.interceptors import audit_tool_call
from packages.mcp_clients.interceptors.audit import _hash_arguments


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


class AuditInterceptorTests(unittest.TestCase):
    def test_audit_logs_payload(self) -> None:
        stream = StringIO()
        logger = logging.getLogger("tests.audit.payload")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)

        tool = _FakeToolHandle(
            server_name="wikipedia",
            tool_name="summary",
            response={"items": [{"title": "Example"}]},
        )

        clock_calls = iter([10.0, 10.125])
        response = audit_tool_call(
            tool,
            {"page": "Example", "token": "secret"},
            logger=logger,
            clock=lambda: next(clock_calls),
        )

        self.assertEqual(response, {"items": [{"title": "Example"}]})
        handler.flush()
        payload = json.loads(stream.getvalue().strip())

        expected_size = len(
            json.dumps({"items": [{"title": "Example"}]}, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        self.assertEqual(payload["event"], "mcp_tool_audit")
        self.assertEqual(payload["server"], "wikipedia")
        self.assertEqual(payload["tool"], "summary")
        self.assertEqual(payload["latency_ms"], 125)
        self.assertEqual(payload["response_size"], expected_size)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(len(payload["args_hash"]), 64)

    def test_audit_logs_on_exception(self) -> None:
        stream = StringIO()
        logger = logging.getLogger("tests.audit.exception")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)

        tool = _FakeToolHandle(
            server_name="stackoverflow",
            tool_name="so_search",
            response=RuntimeError("boom"),
        )
        clock_calls = iter([2.0, 2.5])

        with self.assertRaises(RuntimeError):
            audit_tool_call(
                tool,
                {"query": "foo"},
                logger=logger,
                clock=lambda: next(clock_calls),
            )

        handler.flush()
        payload = json.loads(stream.getvalue().strip())
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["response_size"], 0)
        self.assertEqual(payload["latency_ms"], 500)
        self.assertEqual(payload["server"], "stackoverflow")
        self.assertEqual(payload["tool"], "so_search")

    def test_hash_redacts_secret_values(self) -> None:
        hash_one = _hash_arguments(
            {"token": "abc", "nested": {"password": "first"}, "query": "foo"}
        )
        hash_two = _hash_arguments(
            {"token": "xyz", "nested": {"password": "second"}, "query": "foo"}
        )
        hash_three = _hash_arguments(
            {"token": "xyz", "nested": {"password": "second"}, "query": "bar"}
        )

        self.assertEqual(hash_one, hash_two)
        self.assertNotEqual(hash_one, hash_three)

    def test_response_size_for_bytes_payload(self) -> None:
        stream = StringIO()
        logger = logging.getLogger("tests.audit.bytes")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)

        tool = _FakeToolHandle(
            server_name="textbooks",
            tool_name="read_chunk",
            response=b"abc",
        )

        audit_tool_call(
            tool,
            {"chunk_id": "1"},
            logger=logger,
            clock=lambda: 1.0,
        )

        handler.flush()
        payload = json.loads(stream.getvalue().strip())
        self.assertEqual(payload["response_size"], 3)


if __name__ == "__main__":
    unittest.main()
