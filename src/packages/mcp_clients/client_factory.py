from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol


class McpConfigError(ValueError):
    """Raised when MCP server configuration is invalid."""


@dataclass(frozen=True)
class RetrySettings:
    max_retries: int = 2
    backoff_seconds: float = 0.5


@dataclass(frozen=True)
class McpClientSettings:
    timeout_seconds: float = 10.0
    retry: RetrySettings = field(default_factory=RetrySettings)


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    transport: str
    command: str
    args: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass(frozen=True)
class McpToolHandle:
    server_name: str
    tool_name: str
    timeout_seconds: float
    retry: RetrySettings

    def call(self, arguments: Mapping[str, Any]) -> Mapping[str, Any] | list[Any] | None:
        raise NotImplementedError("Tool execution requires a concrete MCP adapter.")


@dataclass(frozen=True)
class McpResourceHandle:
    server_name: str
    resource_name: str
    timeout_seconds: float
    retry: RetrySettings


@dataclass(frozen=True)
class McpPromptHandle:
    server_name: str
    prompt_name: str
    timeout_seconds: float
    retry: RetrySettings


@dataclass(frozen=True)
class McpServerTools:
    server_name: str
    settings: McpClientSettings

    def handle(self, tool_name: str) -> McpToolHandle:
        return McpToolHandle(
            server_name=self.server_name,
            tool_name=tool_name,
            timeout_seconds=self.settings.timeout_seconds,
            retry=self.settings.retry,
        )


@dataclass(frozen=True)
class McpServerResources:
    server_name: str
    settings: McpClientSettings

    def handle(self, resource_name: str) -> McpResourceHandle:
        return McpResourceHandle(
            server_name=self.server_name,
            resource_name=resource_name,
            timeout_seconds=self.settings.timeout_seconds,
            retry=self.settings.retry,
        )


@dataclass(frozen=True)
class McpServerPrompts:
    server_name: str
    settings: McpClientSettings

    def handle(self, prompt_name: str) -> McpPromptHandle:
        return McpPromptHandle(
            server_name=self.server_name,
            prompt_name=prompt_name,
            timeout_seconds=self.settings.timeout_seconds,
            retry=self.settings.retry,
        )


class McpClientAdapter(Protocol):
    def get_tools(self) -> Mapping[str, McpServerTools]: ...

    def get_resources(self) -> Mapping[str, McpServerResources]: ...

    def get_prompts(self) -> Mapping[str, McpServerPrompts]: ...


class StaticMcpClientAdapter:
    def __init__(
        self,
        servers: Mapping[str, McpServerConfig],
        settings: McpClientSettings,
        logger: logging.Logger,
    ) -> None:
        self._settings = settings
        self._logger = logger
        self._servers = dict(servers)
        self._tools = {
            name: McpServerTools(server_name=name, settings=settings)
            for name in self._servers
        }
        self._resources = {
            name: McpServerResources(server_name=name, settings=settings)
            for name in self._servers
        }
        self._prompts = {
            name: McpServerPrompts(server_name=name, settings=settings)
            for name in self._servers
        }

        self._logger.info(
            "Initialized MCP client adapter",
            extra={
                "event": "mcp_adapter_initialized",
                "server_count": len(self._servers),
                "servers": list(self._servers.keys()),
            },
        )

    def get_tools(self) -> Mapping[str, McpServerTools]:
        return self._tools

    def get_resources(self) -> Mapping[str, McpServerResources]:
        return self._resources

    def get_prompts(self) -> Mapping[str, McpServerPrompts]:
        return self._prompts


class McpClientFactory:
    def __init__(
        self,
        *,
        env: str | None = None,
        config_path: Path | None = None,
        settings: McpClientSettings | None = None,
        logger: logging.Logger | None = None,
        adapter: McpClientAdapter | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._settings = settings or McpClientSettings()
        self._config_path = config_path or self._default_config_path(env)
        self._servers = self._load_config(self._config_path)
        self._adapter = adapter or StaticMcpClientAdapter(
            servers=self._servers,
            settings=self._settings,
            logger=self._logger,
        )

    def get_tools(self) -> Mapping[str, McpServerTools]:
        return self._adapter.get_tools()

    def get_resources(self) -> Mapping[str, McpServerResources]:
        return self._adapter.get_resources()

    def get_prompts(self) -> Mapping[str, McpServerPrompts]:
        return self._adapter.get_prompts()

    def _default_config_path(self, env: str | None) -> Path:
        env_name = (env or os.getenv("APP_ENV") or "dev").lower()
        base_path = Path(__file__).resolve().parents[2]
        return base_path / "config" / f"mcp_servers.{env_name}.json"

    def _load_config(self, path: Path) -> Mapping[str, McpServerConfig]:
        if not path.exists():
            raise FileNotFoundError(f"MCP config not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise McpConfigError("MCP config must be a JSON object.")

        raw_servers = data.get("servers")
        if not isinstance(raw_servers, dict):
            raise McpConfigError("MCP config must contain a 'servers' object.")

        servers: dict[str, McpServerConfig] = {}
        for name, raw in raw_servers.items():
            if not isinstance(raw, dict):
                raise McpConfigError(f"Server config for '{name}' must be an object.")

            enabled = raw.get("enabled", True)
            if not isinstance(enabled, bool):
                raise McpConfigError(f"Server '{name}' enabled flag must be boolean.")
            if not enabled:
                continue

            transport = raw.get("transport")
            command = raw.get("command")
            args = raw.get("args", [])
            env = raw.get("env", {})

            if not isinstance(transport, str) or not transport:
                raise McpConfigError(f"Server '{name}' transport must be a string.")
            if not isinstance(command, str) or not command:
                raise McpConfigError(f"Server '{name}' command must be a string.")
            if not isinstance(args, list) or not all(
                isinstance(arg, str) for arg in args
            ):
                raise McpConfigError(f"Server '{name}' args must be a list of strings.")
            if env is None:
                env = {}
            if not isinstance(env, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in env.items()
            ):
                raise McpConfigError(f"Server '{name}' env must be string keys/values.")

            servers[name] = McpServerConfig(
                name=name,
                transport=transport,
                command=command,
                args=tuple(args),
                env=env,
                enabled=enabled,
            )

        self._logger.info(
            "Loaded MCP server configuration",
            extra={
                "event": "mcp_config_loaded",
                "config_path": str(path),
                "server_count": len(servers),
                "servers": list(servers.keys()),
            },
        )
        return servers
