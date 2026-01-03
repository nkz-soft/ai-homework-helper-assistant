from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence, TypedDict

from .client_factory import McpServerTools, McpToolHandle


class StackOverflowToolError(RuntimeError):
    """Raised when a StackOverflow MCP tool returns an error payload."""


class StackOverflowTimeoutError(StackOverflowToolError):
    """Raised when a StackOverflow MCP tool times out."""


class StackOverflowItem(TypedDict, total=False):
    question_id: str
    title: str
    url: str
    excerpt: str
    tags: list[str]
    score: int
    answer_count: int
    accepted: bool
    content: str


class StackOverflowToolResult(TypedDict):
    source: Literal["stackoverflow"]
    tool: Literal["so_search", "get_content"]
    ok: bool
    items: list[StackOverflowItem]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class StackOverflowToolset:
    search: McpToolHandle
    get_content: McpToolHandle


def stackoverflow_tools(
    tools: McpServerTools,
    *,
    search_tool: str = "so_search",
    content_tool: str = "get_content",
) -> StackOverflowToolset:
    return StackOverflowToolset(
        search=tools.handle(search_tool),
        get_content=tools.handle(content_tool),
    )


def so_search(
    tools: StackOverflowToolset,
    *,
    query: str,
    tags: Sequence[str] | None = None,
    limit: int | None = None,
) -> StackOverflowToolResult:
    raw = _call_tool(
        tools.search,
        _compact_args(
            {
                "query": query,
                "tags": list(tags) if tags else None,
                "limit": limit,
            }
        ),
    )
    items = _normalize_items(raw)
    return {
        "source": "stackoverflow",
        "tool": "so_search",
        "ok": True,
        "items": items,
        "raw": raw,
    }


def so_get_content(
    tools: StackOverflowToolset,
    *,
    question_id: str,
) -> StackOverflowToolResult:
    raw = _call_tool(
        tools.get_content,
        _compact_args({"question_id": question_id}),
    )
    items = _normalize_items(raw)
    return {
        "source": "stackoverflow",
        "tool": "get_content",
        "ok": True,
        "items": items,
        "raw": raw,
    }


def get_content(
    tools: StackOverflowToolset,
    *,
    question_id: str,
) -> StackOverflowToolResult:
    return so_get_content(tools, question_id=question_id)


def _call_tool(tool: McpToolHandle, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        raw = tool.call(arguments)
    except TimeoutError as exc:
        raise StackOverflowTimeoutError(
            f"StackOverflow tool '{tool.tool_name}' timed out."
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive for adapter implementations
        raise StackOverflowToolError(
            f"StackOverflow tool '{tool.tool_name}' failed."
        ) from exc

    if raw is None:
        raise StackOverflowToolError(
            f"StackOverflow tool '{tool.tool_name}' returned no data."
        )
    if isinstance(raw, list):
        raw = {"items": raw}
    if not isinstance(raw, Mapping):
        raise StackOverflowToolError(
            f"StackOverflow tool '{tool.tool_name}' returned invalid payload."
        )
    _raise_if_error(raw, tool.tool_name)
    return raw


def _raise_if_error(raw: Mapping[str, Any], tool_name: str) -> None:
    error_value = raw.get("error") or raw.get("errors") or raw.get("message")
    status = raw.get("status")
    if error_value or status in {"error", "failed", "timeout"}:
        raise StackOverflowToolError(
            f"StackOverflow tool '{tool_name}' error: {error_value or status}."
        )


def _normalize_items(raw: Mapping[str, Any]) -> list[StackOverflowItem]:
    items = raw.get("items") or raw.get("results") or raw.get("data")
    if isinstance(items, Mapping):
        items = [items]
    if not isinstance(items, list):
        items = []
    normalized: list[StackOverflowItem] = []
    for entry in items:
        if not isinstance(entry, Mapping):
            continue
        normalized.append(_normalize_item(entry))
    if not normalized and raw:
        normalized.append(_normalize_item(raw))
    return normalized


def _normalize_item(entry: Mapping[str, Any]) -> StackOverflowItem:
    title = _coerce_str(entry.get("title"))
    content = _coerce_str(entry.get("body") or entry.get("content"))
    item: StackOverflowItem = {}
    question_id = _coerce_str(entry.get("question_id") or entry.get("id"))
    if question_id:
        item["question_id"] = question_id
    if title:
        item["title"] = title
    url = _coerce_str(entry.get("url") or entry.get("link"))
    if url:
        item["url"] = url
    excerpt = _coerce_str(entry.get("excerpt") or entry.get("summary"))
    if excerpt:
        item["excerpt"] = excerpt
    tags = _coerce_str_list(entry.get("tags"))
    if tags:
        item["tags"] = tags
    score = _coerce_int(entry.get("score"))
    if score is not None:
        item["score"] = score
    answer_count = _coerce_int(entry.get("answer_count"))
    if answer_count is not None:
        item["answer_count"] = answer_count
    accepted = _coerce_bool(entry.get("accepted"))
    if accepted is not None:
        item["accepted"] = accepted
    if content:
        item["content"] = content
    return item


def _compact_args(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in arguments.items() if value is not None}


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None
