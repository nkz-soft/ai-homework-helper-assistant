from __future__ import annotations

from typing import Sequence

from packages.mcp_clients.tool_wrappers import (
    StackOverflowToolResult,
    StackOverflowToolset,
    so_get_content,
    so_search,
)


def retrieve_stackoverflow(
    tools: StackOverflowToolset,
    *,
    query: str,
    tags: Sequence[str] | None = None,
    max_items: int = 3,
) -> list[StackOverflowToolResult]:
    results: list[StackOverflowToolResult] = []
    search_result = so_search(tools, query=query, tags=tags, limit=max_items)
    results.append(search_result)

    for item in search_result["items"][:max_items]:
        question_id = item.get("question_id")
        if not question_id:
            continue
        results.append(so_get_content(tools, question_id=question_id))

    return results
