from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from packages.mcp_clients.client_factory import McpClientFactory, McpConfigError


class McpClientFactoryTests(unittest.TestCase):
    def _write_config(self, directory: Path, payload: dict) -> Path:
        path = directory / "mcp_servers.test.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_loads_enabled_servers_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_config(
                Path(temp_dir),
                {
                    "version": 1,
                    "servers": {
                        "enabled_server": {
                            "transport": "stdio",
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-wikipedia"],
                        },
                        "disabled_server": {
                            "transport": "stdio",
                            "command": "python",
                            "args": ["-m", "mcp_textbooks_server"],
                            "enabled": False,
                        },
                    },
                },
            )
            factory = McpClientFactory(config_path=config_path)
            tools = factory.get_tools()
            self.assertEqual(set(tools.keys()), {"enabled_server"})

    def test_raises_for_missing_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                McpClientFactory(config_path=missing_path)

    def test_raises_for_invalid_server_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_config(
                Path(temp_dir),
                {
                    "version": 1,
                    "servers": {
                        "bad_server": {
                            "transport": 123,
                            "command": "npx",
                            "args": ["-y"],
                        }
                    },
                },
            )
            with self.assertRaises(McpConfigError):
                McpClientFactory(config_path=config_path)

    def test_default_config_path_uses_app_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            config_dir = base_path / "config"
            config_dir.mkdir()
            config_path = config_dir / "mcp_servers.custom.json"
            config_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "servers": {
                            "wikipedia": {
                                "transport": "stdio",
                                "command": "npx",
                                "args": [
                                    "-y",
                                    "@modelcontextprotocol/server-wikipedia",
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            original_env = os.environ.get("APP_ENV")
            os.environ["APP_ENV"] = "custom"
            try:
                factory = McpClientFactory(config_path=config_path)
                self.assertEqual(set(factory.get_tools().keys()), {"wikipedia"})
            finally:
                if original_env is None:
                    os.environ.pop("APP_ENV", None)
                else:
                    os.environ["APP_ENV"] = original_env


if __name__ == "__main__":
    unittest.main()
