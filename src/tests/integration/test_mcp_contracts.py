from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from packages.mcp_clients.client_factory import (
    McpClientFactory,
    McpClientSettings,
    RetrySettings,
)


class McpContractTests(unittest.TestCase):
    def _write_config(self, directory: Path, payload: dict) -> Path:
        path = directory / "mcp_servers.test.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_tool_listing_for_enabled_servers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_config(
                Path(temp_dir),
                {
                    "version": 1,
                    "servers": {
                        "wikipedia": {
                            "transport": "stdio",
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-wikipedia"],
                        },
                        "textbooks": {
                            "transport": "stdio",
                            "command": "python",
                            "args": ["-m", "mcp_textbooks_server"],
                            "enabled": False,
                        },
                    },
                },
            )
            settings = McpClientSettings(
                timeout_seconds=5.0,
                retry=RetrySettings(max_retries=1, backoff_seconds=0.1),
            )
            factory = McpClientFactory(config_path=config_path, settings=settings)

            tools = factory.get_tools()
            resources = factory.get_resources()
            prompts = factory.get_prompts()

            self.assertEqual(set(tools.keys()), {"wikipedia"})
            self.assertEqual(set(resources.keys()), {"wikipedia"})
            self.assertEqual(set(prompts.keys()), {"wikipedia"})

            handle = tools["wikipedia"].handle("search")
            self.assertEqual(handle.server_name, "wikipedia")
            self.assertEqual(handle.tool_name, "search")
            self.assertEqual(handle.timeout_seconds, 5.0)

    def test_degraded_behavior_skips_disabled_servers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_config(
                Path(temp_dir),
                {
                    "version": 1,
                    "servers": {
                        "wikipedia": {
                            "transport": "stdio",
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-wikipedia"],
                            "enabled": False,
                        },
                        "stackoverflow": {
                            "transport": "stdio",
                            "command": "npx",
                            "args": ["-y", "mcp-remote", "mcp.stackoverflow.com"],
                        },
                    },
                },
            )
            factory = McpClientFactory(config_path=config_path)

            tools = factory.get_tools()
            self.assertEqual(set(tools.keys()), {"stackoverflow"})


if __name__ == "__main__":
    unittest.main()
