from __future__ import annotations

from typing import Sequence

from packages.mcp_clients.interceptors.budget import (
    ToolBudgetExceeded,
    ToolBudgetManager,
)
from packages.mcp_clients.tool_wrappers import (
    StackOverflowToolResult,
    StackOverflowToolset,
    so_get_content,
    so_search,
)

_SO_BUDGET_REASON = "stackoverflow_budget_exhausted"


def retrieve_stackoverflow(
    tools: StackOverflowToolset,
    *,
    query: str,
    tags: Sequence[str] | None = None,
    max_items: int = 3,
    budget_manager: ToolBudgetManager | None = None,
) -> list[StackOverflowToolResult]:
    results: list[StackOverflowToolResult] = []
    if budget_manager is not None:
        try:
            budget_manager.assert_can_call(tools.search)
        except ToolBudgetExceeded:
            return [
                _budget_degraded_result(
                    ok=False,
                    reason=_SO_BUDGET_REASON,
                )
            ]

    search_result: StackOverflowToolResult | None = None
    try:
        search_result = so_search(tools, query=query, tags=tags, limit=max_items)
        if budget_manager is not None:
            budget_manager.check_payload_size(search_result)
    except ToolBudgetExceeded:
        if search_result is None:
            return [
                _budget_degraded_result(
                    ok=False,
                    reason=_SO_BUDGET_REASON,
                )
            ]
        _attach_budget_metadata(search_result, _SO_BUDGET_REASON)
        results.append(search_result)
        return results
    finally:
        if budget_manager is not None:
            budget_manager.record_call(tools.search)

    results.append(search_result)

    for item in search_result["items"][:max_items]:
        question_id = item.get("question_id")
        if not question_id:
            continue
        if budget_manager is not None:
            try:
                budget_manager.assert_can_call(tools.get_content)
            except ToolBudgetExceeded:
                _attach_budget_metadata(search_result, _SO_BUDGET_REASON)
                break
        content_result: StackOverflowToolResult | None = None
        try:
            content_result = so_get_content(tools, question_id=question_id)
            if budget_manager is not None:
                budget_manager.check_payload_size(content_result)
        except ToolBudgetExceeded:
            _attach_budget_metadata(search_result, _SO_BUDGET_REASON)
            break
        finally:
            if budget_manager is not None:
                budget_manager.record_call(tools.get_content)

        if content_result is not None:
            results.append(content_result)

    return results


def _attach_budget_metadata(
    result: StackOverflowToolResult, reason: str
) -> StackOverflowToolResult:
    result["metadata"] = {"degraded": True, "reason": reason}
    return result


def _budget_degraded_result(*, ok: bool, reason: str) -> StackOverflowToolResult:
    return {
        "source": "stackoverflow",
        "tool": "so_search",
        "ok": ok,
        "items": [],
        "raw": {},
        "metadata": {"degraded": True, "reason": reason},
    }
