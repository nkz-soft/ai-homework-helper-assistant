from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from packages.orchestrator.llm_config import LlmConfigError, LlmConfigLoader


class LlmConfigLoaderTests(unittest.TestCase):
    def _write_config(self, directory: Path, payload: dict) -> Path:
        path = directory / "llm.test.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_loads_config_and_expands_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_config(
                Path(temp_dir),
                {
                    "version": 1,
                    "model": "${TEST_LLM_MODEL}",
                    "base_url": "${TEST_LLM_BASE_URL}",
                    "api_key": "${TEST_LLM_API_KEY}",
                },
            )
            original = os.environ.get("TEST_LLM_API_KEY")
            original_model = os.environ.get("TEST_LLM_MODEL")
            original_base_url = os.environ.get("TEST_LLM_BASE_URL")
            os.environ["TEST_LLM_API_KEY"] = "secret-key"
            os.environ["TEST_LLM_MODEL"] = "test-model"
            os.environ["TEST_LLM_BASE_URL"] = "https://example.com/v1"
            try:
                loader = LlmConfigLoader(config_path=config_path)
                config = loader.load()
            finally:
                if original is None:
                    os.environ.pop("TEST_LLM_API_KEY", None)
                else:
                    os.environ["TEST_LLM_API_KEY"] = original
                if original_model is None:
                    os.environ.pop("TEST_LLM_MODEL", None)
                else:
                    os.environ["TEST_LLM_MODEL"] = original_model
                if original_base_url is None:
                    os.environ.pop("TEST_LLM_BASE_URL", None)
                else:
                    os.environ["TEST_LLM_BASE_URL"] = original_base_url

        self.assertEqual(config.model, "test-model")
        self.assertEqual(config.base_url, "https://example.com/v1")
        self.assertEqual(config.api_key, "secret-key")

    def test_raises_for_missing_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = self._write_config(
                Path(temp_dir),
                {
                    "version": 1,
                    "base_url": "https://example.com/v1",
                    "api_key": "value",
                },
            )
            loader = LlmConfigLoader(config_path=config_path)
            with self.assertRaises(LlmConfigError):
                loader.load()
