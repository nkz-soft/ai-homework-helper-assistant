from __future__ import annotations

import asyncio
from typing import Any, Callable, Literal, Mapping

from packages.mcp_clients.client_factory import (
    McpClientFactory,
    McpServerTools,
    McpToolHandle,
)
from packages.mcp_clients.interceptors.budget import (
    ToolBudgetExceeded,
    ToolBudgetLimits,
    ToolBudgetManager,
)
from packages.mcp_clients.interceptors.audit import audit_tool_call
from packages.mcp_clients.tool_wrappers import (
    StackOverflowToolError,
    WikipediaToolError,
    so_get_content,
    so_search,
    stackoverflow_tools,
    wikipedia_search,
    wikipedia_section,
    wikipedia_summary,
    wikipedia_tools,
)
from packages.orchestrator.graph.state import (
    OrchestratorState,
    PlanCall,
    RetrievedItem,
    SourceName,
)


async def retrieve(state: Mapping[str, object]) -> OrchestratorState:
    retrieval_plan = _get_retrieval_plan(state)
    calls = _plan_calls(retrieval_plan.get("calls"))
    if not calls:
        return {"retrieved_items": []}

    tools = _resolve_tools(state)
    budget_manager = _build_budget_manager(state.get("tool_budget"))
    language = _student_language(state.get("student_context"))

    tasks = [_execute_call(call, tools, budget_manager, language) for call in calls]
    results = await asyncio.gather(*tasks)
    return {"retrieved_items": results}


def _get_retrieval_plan(state: Mapping[str, object]) -> Mapping[str, Any]:
    plan = state.get("retrieval_plan")
    if isinstance(plan, Mapping):
        return plan
    return {}


def _plan_calls(raw_calls: object) -> list[PlanCall]:
    if not isinstance(raw_calls, list):
        return []
    calls: list[PlanCall] = []
    for item in raw_calls:
        if not isinstance(item, Mapping):
            continue
        if {"source", "tool", "query"}.issubset(item.keys()):
            calls.append(
                {
                    "source": item["source"],  # type: ignore[typeddict-item]
                    "tool": item["tool"],  # type: ignore[typeddict-item]
                    "query": item["query"],  # type: ignore[typeddict-item]
                    "priority": _coerce_int(item.get("priority")) or 0,
                }
            )
    return calls


def _resolve_tools(state: Mapping[str, object]) -> Mapping[str, McpServerTools]:
    tools = state.get("tools")
    if isinstance(tools, Mapping):
        return {str(key): value for key, value in tools.items()}
    return McpClientFactory().get_tools()


def _build_budget_manager(tool_budget: object) -> ToolBudgetManager | None:
    if not isinstance(tool_budget, Mapping):
        return None
    limits = ToolBudgetLimits(
        total_calls=_coerce_int(tool_budget.get("total_calls")),
        per_server_caps=_coerce_int_map(tool_budget.get("per_server_caps")),
        max_payload_bytes=_coerce_int(tool_budget.get("max_bytes")),
    )
    return ToolBudgetManager(limits=limits)


def _student_language(student_context: object) -> str | None:
    if not isinstance(student_context, Mapping):
        return None
    language = student_context.get("language")
    if isinstance(language, str) and language.strip():
        return language.strip()
    return None


async def _execute_call(
    call: PlanCall,
    tools: Mapping[str, McpServerTools],
    budget_manager: ToolBudgetManager | None,
    language: str | None,
) -> RetrievedItem:
    source = call["source"]
    tool = call["tool"]
    query = call["query"]

    server_tools = tools.get(source)
    if server_tools is None:
        return _error_item(call, f"missing_tools_for_source:{source}")

    try:
        if source == "stackoverflow":
            return await _run_stackoverflow(server_tools, tool, query, budget_manager)
        if source == "wikipedia":
            return await _run_wikipedia(
                server_tools, tool, query, language, budget_manager
            )
        if source == "textbooks":
            return await _run_textbooks(server_tools, tool, query, budget_manager)
    except ToolBudgetExceeded as exc:
        return _error_item(call, f"tool_budget_exceeded:{exc}")
    except TimeoutError:
        return _error_item(call, "timeout")
    except (StackOverflowToolError, WikipediaToolError) as exc:
        return _error_item(call, f"tool_error:{exc}")
    except Exception as exc:  # pragma: no cover - defensive fallback
        return _error_item(call, f"unexpected_error:{exc}")

    return _error_item(call, f"unsupported_source:{source}")


async def _run_stackoverflow(
    server_tools: McpServerTools,
    tool: str,
    query: str,
    budget_manager: ToolBudgetManager | None,
) -> RetrievedItem:
    toolset = stackoverflow_tools(server_tools)
    if tool == "get_content":
        handler = toolset.get_content

        def call() -> Any:
            return so_get_content(toolset, question_id=query)
    else:
        handler = toolset.search

        def call() -> Any:
            return so_search(toolset, query=query)

    result = await _run_with_budget(handler, call, budget_manager)
    return _result_item("stackoverflow", tool, query, result)


async def _run_wikipedia(
    server_tools: McpServerTools,
    tool: str,
    query: str,
    language: str | None,
    budget_manager: ToolBudgetManager | None,
) -> RetrievedItem:
    toolset = wikipedia_tools(server_tools)
    if tool == "wikipedia_summary":
        handler = toolset.summary

        def call() -> Any:
            return wikipedia_summary(
                toolset,
                page_id_or_title=query,
                language=language,
            )
    elif tool == "wikipedia_section":
        handler = toolset.section

        def call() -> Any:
            return wikipedia_section(
                toolset,
                page_id_or_title=query,
                section="intro",
                language=language,
            )
    else:
        handler = toolset.search

        def call() -> Any:
            return wikipedia_search(toolset, query=query, language=language)

    result = await _run_with_budget(handler, call, budget_manager)
    return _result_item("wikipedia", tool, query, result)


async def _run_textbooks(
    server_tools: McpServerTools,
    tool: str,
    query: str,
    budget_manager: ToolBudgetManager | None,
) -> RetrievedItem:
    handler = server_tools.handle(tool)

    def call() -> Any:
        return audit_tool_call(handler, {"query": query})

    result = await _run_with_budget(handler, call, budget_manager)
    return _result_item("textbooks", tool, query, result)


async def _run_with_budget(
    handler: McpToolHandle,
    func: Callable[[], Any],
    budget_manager: ToolBudgetManager | None,
) -> Any:
    if budget_manager is not None:
        budget_manager.assert_can_call(handler)

    timeout_seconds = handler.timeout_seconds
    result = await asyncio.wait_for(asyncio.to_thread(func), timeout=timeout_seconds)

    if budget_manager is not None:
        budget_manager.check_payload_size(result)
        budget_manager.record_call(handler)

    return result


def _result_item(
    source: SourceName | Literal["other"],
    tool: str,
    query: str,
    result: Any,
) -> RetrievedItem:
    return {
        "source": source,
        "tool": tool,
        "query": query,
        "result": _ensure_mapping(result),
    }


def _error_item(call: PlanCall, error: str) -> RetrievedItem:
    return {
        "source": call["source"],
        "tool": call["tool"],
        "query": call["query"],
        "result": {},
        "error": error,
    }


def _ensure_mapping(result: Any) -> dict[str, Any]:
    if isinstance(result, Mapping):
        return dict(result)
    return {"value": result}


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_int_map(value: object) -> dict[str, int] | None:
    if not isinstance(value, Mapping):
        return None
    output: dict[str, int] = {}
    for key, raw in value.items():
        coerced = _coerce_int(raw)
        if coerced is None:
            continue
        output[str(key)] = coerced
    return output or None
