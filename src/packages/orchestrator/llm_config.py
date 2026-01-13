from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path


class LlmConfigError(ValueError):
    """Raised when LLM configuration is invalid."""


@dataclass(frozen=True)
class LlmConfig:
    model: str
    base_url: str
    api_key: str


class LlmConfigLoader:
    def __init__(
        self,
        *,
        env: str | None = None,
        config_path: Path | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._config_path = config_path or self._default_config_path(env)

    def load(self) -> LlmConfig:
        if not self._config_path.exists():
            raise FileNotFoundError(f"LLM config not found: {self._config_path}")

        raw = json.loads(self._config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise LlmConfigError("LLM config must be a JSON object.")

        model = raw.get("model")
        base_url = raw.get("base_url")
        api_key = raw.get("api_key")

        if not isinstance(model, str) or not model.strip():
            raise LlmConfigError("LLM config must include a non-empty 'model'.")
        if not isinstance(base_url, str) or not base_url.strip():
            raise LlmConfigError("LLM config must include a non-empty 'base_url'.")
        if not isinstance(api_key, str) or not api_key.strip():
            raise LlmConfigError("LLM config must include a non-empty 'api_key'.")

        model = _expand_env(model.strip())
        if not model:
            raise LlmConfigError("LLM config 'model' resolved to an empty value.")

        base_url = _expand_env(base_url.strip())
        if not base_url:
            raise LlmConfigError("LLM config 'base_url' resolved to an empty value.")

        api_key = _expand_env(api_key.strip())
        if not api_key:
            raise LlmConfigError("LLM config 'api_key' resolved to an empty value.")

        config = LlmConfig(
            model=model,
            base_url=base_url,
            api_key=api_key,
        )

        self._logger.info(
            "Loaded LLM configuration",
            extra={
                "event": "llm_config_loaded",
                "config_path": str(self._config_path),
                "model": config.model,
                "base_url": config.base_url,
            },
        )
        return config

    def _default_config_path(self, env: str | None) -> Path:
        env_name = (env or os.getenv("APP_ENV") or "dev").lower()
        base_path = Path(__file__).resolve().parents[2]
        return base_path / "config" / f"llm.{env_name}.json"


def _expand_env(value: str) -> str:
    expanded = os.path.expandvars(value)
    if expanded.startswith("$"):
        return ""
    return expanded
