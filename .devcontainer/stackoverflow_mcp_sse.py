from __future__ import annotations

import asyncio
import os

from stackoverflow_mcp.config import ServerConfig
from stackoverflow_mcp import server as so_server


def _load_config() -> ServerConfig:
    config = ServerConfig.load_from_env()
    host = os.getenv("MCP_HOST")
    port = os.getenv("MCP_PORT")
    if host:
        config.host = host
    if port:
        try:
            config.port = int(port)
        except ValueError:
            pass
    return config


async def _run() -> None:
    config = _load_config()
    so_server.server = so_server.StackOverflowServer(config)
    await so_server.mcp.run(transport="sse", host=config.host, port=config.port)


if __name__ == "__main__":
    asyncio.run(_run())
