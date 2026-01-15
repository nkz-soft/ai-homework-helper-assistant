from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import threading
import time
from datetime import timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

import anyio
from mcp import types as mcp_types
from mcp.client import session as mcp_session
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client


class McpConfigError(ValueError):
    """Raised when MCP server configuration is invalid."""


@dataclass(frozen=True)
class RetrySettings:
    max_retries: int = 1
    backoff_seconds: float = 0.5


@dataclass(frozen=True)
class McpClientSettings:
    timeout_seconds: float = 90.0
    retry: RetrySettings = field(default_factory=RetrySettings)


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    transport: str
    command: str
    args: tuple[str, ...]
    env: Mapping[str, str] = field(default_factory=dict)
    enabled: bool = True
    protocol_version: str | None = None
    minimal_init: bool = False


@dataclass(frozen=True)
class McpToolHandle:
    server_name: str
    tool_name: str
    timeout_seconds: float
    retry: RetrySettings
    caller: (
        Callable[
            [Mapping[str, Any]],
            Mapping[str, Any] | list[Any] | None,
        ]
        | None
    ) = None

    def call(
        self, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any] | list[Any] | None:
        if self.caller is None:
            raise NotImplementedError("Tool execution requires a concrete MCP adapter.")
        return self.caller(arguments)


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
    caller: Callable[
        [str, str, Mapping[str, Any], float, RetrySettings],
        Mapping[str, Any] | list[Any] | None,
    ]

    def handle(self, tool_name: str) -> McpToolHandle:
        def _call(arguments: Mapping[str, Any]) -> Mapping[str, Any] | list[Any] | None:
            return self.caller(
                self.server_name,
                tool_name,
                arguments,
                self.settings.timeout_seconds,
                self.settings.retry,
            )

        return McpToolHandle(
            server_name=self.server_name,
            tool_name=tool_name,
            timeout_seconds=self.settings.timeout_seconds,
            retry=self.settings.retry,
            caller=_call,
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
            name: McpServerTools(
                server_name=name,
                settings=settings,
                caller=self._unsupported_tool_call,
            )
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

    def _unsupported_tool_call(
        self,
        server_name: str,
        tool_name: str,
        arguments: Mapping[str, Any],
        timeout_seconds: float,
        retry: RetrySettings,
    ) -> Mapping[str, Any] | list[Any] | None:
        raise NotImplementedError("Tool execution requires a concrete MCP adapter.")


class StdioMcpClientAdapter:
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
            name: McpServerTools(
                server_name=name,
                settings=settings,
                caller=self._call_tool,
            )
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

    def _call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Mapping[str, Any],
        timeout_seconds: float,
        retry: RetrySettings,
    ) -> Mapping[str, Any] | list[Any] | None:
        config = self._servers.get(server_name)
        if config is None:
            raise McpConfigError(f"Unknown MCP server '{server_name}'.")
        if config.transport not in {"stdio", "sse"}:
            raise NotImplementedError(
                f"Transport '{config.transport}' is not supported."
            )

        last_error: Exception | None = None
        for attempt in range(retry.max_retries + 1):
            try:
                if config.transport == "sse":
                    return _call_sse_tool(
                        config=config,
                        tool_name=tool_name,
                        arguments=arguments,
                        timeout_seconds=timeout_seconds,
                    )
                return _call_stdio_tool(
                    config=config,
                    tool_name=tool_name,
                    arguments=arguments,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:  # pragma: no cover - defensive retry
                self._logger.error(
                    "MCP tool call failed: %s",
                    _describe_exception(exc),
                    extra={
                        "event": "mcp_tool_error",
                        "server": server_name,
                        "tool": tool_name,
                        "attempt": attempt + 1,
                        "transport": config.transport,
                        "error_type": type(exc).__name__,
                        "error": _describe_exception(exc),
                    },
                    exc_info=True,
                )
                last_error = exc
                if attempt >= retry.max_retries:
                    raise
                time.sleep(retry.backoff_seconds * (2**attempt))
        if last_error is not None:
            raise last_error
        return None


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
        self._adapter = adapter or StdioMcpClientAdapter(
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
            protocol_version = raw.get("protocol_version")
            minimal_init = raw.get("minimal_init", False)

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
            if protocol_version is not None and not isinstance(protocol_version, str):
                raise McpConfigError(
                    f"Server '{name}' protocol_version must be a string."
                )
            if not isinstance(minimal_init, bool):
                raise McpConfigError(
                    f"Server '{name}' minimal_init must be a boolean."
                )

            servers[name] = McpServerConfig(
                name=name,
                transport=transport,
                command=command,
                args=tuple(args),
                env=env,
                enabled=enabled,
                protocol_version=protocol_version,
                minimal_init=minimal_init,
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


@dataclass
class _SseServerProcess:
    process: subprocess.Popen[str] | None
    url: str


_SSE_PROCESS_LOCK = threading.Lock()
_SSE_PROCESSES: dict[str, _SseServerProcess] = {}


def _call_stdio_tool(
    *,
    config: McpServerConfig,
    tool_name: str,
    arguments: Mapping[str, Any],
    timeout_seconds: float,
) -> Mapping[str, Any] | list[Any] | None:
    async def _run() -> mcp_types.CallToolResult:
        params = StdioServerParameters(
            command=config.command,
            args=list(config.args),
            env=dict(config.env) if config.env else None,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                timeout = timedelta(seconds=timeout_seconds)
                with anyio.fail_after(timeout_seconds):
                    await _initialize_session(
                        session,
                        config.protocol_version,
                        minimal_init=config.minimal_init,
                    )
                    return await session.call_tool(
                        tool_name,
                        dict(arguments),
                        read_timeout_seconds=timeout,
                    )

    result = anyio.run(_run)
    return _coerce_tool_result(result)


def _call_sse_tool(
    *,
    config: McpServerConfig,
    tool_name: str,
    arguments: Mapping[str, Any],
    timeout_seconds: float,
) -> Mapping[str, Any] | list[Any] | None:
    server = _ensure_sse_server(config)

    async def _run() -> mcp_types.CallToolResult:
        sse_read_timeout = max(timeout_seconds * 2, 300.0)
        async with sse_client(
            server.url,
            timeout=timeout_seconds,
            sse_read_timeout=sse_read_timeout,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                with anyio.fail_after(timeout_seconds):
                    await _initialize_session(
                        session,
                        config.protocol_version,
                        minimal_init=config.minimal_init,
                    )
                    return await session.call_tool(
                        tool_name,
                        dict(arguments),
                        read_timeout_seconds=timedelta(seconds=timeout_seconds),
                    )

    result = anyio.run(_run)
    return _coerce_tool_result(result)


async def _initialize_session(
    session: ClientSession,
    protocol_version: str | None,
    *,
    minimal_init: bool,
) -> mcp_types.InitializeResult:
    if minimal_init:
        capabilities = mcp_types.ClientCapabilities()
    else:
        sampling = (
            (session._sampling_capabilities or mcp_types.SamplingCapability())
            if session._sampling_callback is not mcp_session._default_sampling_callback
            else None
        )
        elicitation = (
            mcp_types.ElicitationCapability(
                form=mcp_types.FormElicitationCapability(),
                url=mcp_types.UrlElicitationCapability(),
            )
            if session._elicitation_callback is not mcp_session._default_elicitation_callback
            else None
        )
        roots = (
            mcp_types.RootsCapability(listChanged=True)
            if session._list_roots_callback is not mcp_session._default_list_roots_callback
            else None
        )
        capabilities = mcp_types.ClientCapabilities(
            sampling=sampling,
            elicitation=elicitation,
            experimental=None,
            roots=roots,
            tasks=session._task_handlers.build_capability(),
        )

    result = await session.send_request(
        mcp_types.ClientRequest(
            mcp_types.InitializeRequest(
                params=mcp_types.InitializeRequestParams(
                    protocolVersion=protocol_version or mcp_types.LATEST_PROTOCOL_VERSION,
                    capabilities=capabilities,
                    clientInfo=session._client_info,
                ),
            )
        ),
        mcp_types.InitializeResult,
    )

    if result.protocolVersion not in mcp_session.SUPPORTED_PROTOCOL_VERSIONS:
        raise RuntimeError(
            f"Unsupported protocol version from the server: {result.protocolVersion}"
        )

    session._server_capabilities = result.capabilities
    await session.send_notification(
        mcp_types.ClientNotification(mcp_types.InitializedNotification())
    )
    return result


def _ensure_sse_server(config: McpServerConfig) -> _SseServerProcess:
    if config.transport != "sse":
        raise ValueError("SSE server requested for non-SSE config.")
    host = _extract_arg_value(config.args, "--host") or "127.0.0.1"
    port = _extract_arg_value(config.args, "--port")
    if port is None:
        port = str(_find_free_port())
    url = f"http://{host}:{port}/sse"
    external_host = host not in {"127.0.0.1", "localhost"}

    with _SSE_PROCESS_LOCK:
        existing = _SSE_PROCESSES.get(config.name)
        if existing:
            if existing.process is None:
                try:
                    _wait_for_port(host, int(port), timeout_seconds=2.0)
                    return existing
                except TimeoutError:
                    _SSE_PROCESSES.pop(config.name, None)
            elif existing.process.poll() is None:
                return existing

        if _is_port_open(host, int(port)):
            server = _SseServerProcess(process=None, url=url)
            _SSE_PROCESSES[config.name] = server
            return server

        try:
            _wait_for_port(host, int(port), timeout_seconds=5.0)
            server = _SseServerProcess(process=None, url=url)
            _SSE_PROCESSES[config.name] = server
            return server
        except TimeoutError:
            if external_host:
                raise TimeoutError(
                    f"SSE server for '{config.name}' not reachable on {host}:{port}."
                )

        args = list(config.args)
        if "--transport" not in args:
            args.extend(["--transport", "sse"])
        if "--host" not in args:
            args.extend(["--host", host])
        if "--port" not in args:
            args.extend(["--port", port])

        env = dict(config.env) if config.env else None
        process = subprocess.Popen(  # noqa: S603
            [config.command, *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
        )
        _wait_for_port(host, int(port), timeout_seconds=10.0)
        server = _SseServerProcess(process=process, url=url)
        _SSE_PROCESSES[config.name] = server
        return server


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _is_port_open(host: str, port: int, timeout_seconds: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _extract_arg_value(args: tuple[str, ...], flag: str) -> str | None:
    if flag not in args:
        return None
    index = args.index(flag)
    if index + 1 < len(args):
        return args[index + 1]
    return None


def _wait_for_port(host: str, port: int, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"SSE server not ready on {host}:{port}")


def _describe_exception(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        parts = ", ".join(_describe_exception(item) for item in exc.exceptions)
        return f"{type(exc).__name__}({parts})"
    return f"{type(exc).__name__}: {exc}"


def _coerce_tool_result(
    result: mcp_types.CallToolResult,
) -> Mapping[str, Any] | list[Any] | None:
    if result.isError:
        raise RuntimeError("MCP tool call returned an error.")

    if result.structuredContent is not None:
        return result.structuredContent

    if not result.content:
        return {}

    text_items: list[str] = []
    for item in result.content:
        if isinstance(item, mcp_types.TextContent):
            text_items.append(item.text)
        else:
            try:
                payload = item.model_dump()
            except AttributeError:
                payload = {"content": str(item)}
            return {"content": payload}

    if len(text_items) == 1:
        return _maybe_parse_json(text_items[0])
    return {"content": text_items}


def _maybe_parse_json(payload: str) -> Mapping[str, Any] | list[Any] | dict[str, str]:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {"content": payload}
    if isinstance(parsed, (dict, list)):
        return parsed
    return {"content": str(parsed)}
