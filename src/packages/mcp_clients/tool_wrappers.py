from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence, TypedDict

from .client_factory import McpServerTools, McpToolHandle


class StackOverflowToolError(RuntimeError):
    """Raised when a StackOverflow MCP tool returns an error payload."""


class StackOverflowTimeoutError(StackOverflowToolError):
    """Raised when a StackOverflow MCP tool times out."""


class WikipediaToolError(RuntimeError):
    """Raised when a Wikipedia MCP tool returns an error payload."""


class WikipediaTimeoutError(WikipediaToolError):
    """Raised when a Wikipedia MCP tool times out."""


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


class WikipediaItem(TypedDict, total=False):
    page_id: str
    title: str
    url: str
    excerpt: str
    content: str
    section: str


class WikipediaToolResult(TypedDict):
    source: Literal["wikipedia"]
    tool: Literal["search", "summary", "section"]
    ok: bool
    items: list[WikipediaItem]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class StackOverflowToolset:
    search: McpToolHandle
    get_content: McpToolHandle


@dataclass(frozen=True)
class WikipediaToolset:
    search: McpToolHandle
    summary: McpToolHandle
    section: McpToolHandle


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


def wikipedia_tools(
    tools: McpServerTools,
    *,
    search_tool: str = "search",
    summary_tool: str = "summary",
    section_tool: str = "section",
) -> WikipediaToolset:
    return WikipediaToolset(
        search=tools.handle(search_tool),
        summary=tools.handle(summary_tool),
        section=tools.handle(section_tool),
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


def wikipedia_search(
    tools: WikipediaToolset,
    *,
    query: str,
    language: str | None = None,
    limit: int | None = None,
    max_chars: int = 2000,
) -> WikipediaToolResult:
    raw = _call_wikipedia_tool(
        tools.search,
        _compact_args({"query": query, "lang": language, "limit": limit}),
    )
    items = _normalize_wikipedia_items(raw, max_chars=max_chars)
    return {
        "source": "wikipedia",
        "tool": "search",
        "ok": True,
        "items": items,
        "raw": raw,
    }


def wikipedia_summary(
    tools: WikipediaToolset,
    *,
    page_id_or_title: str,
    language: str | None = None,
    max_chars: int = 2000,
) -> WikipediaToolResult:
    raw = _call_wikipedia_tool(
        tools.summary,
        _compact_args({"page": page_id_or_title, "lang": language}),
    )
    items = _normalize_wikipedia_items(raw, max_chars=max_chars)
    return {
        "source": "wikipedia",
        "tool": "summary",
        "ok": True,
        "items": items,
        "raw": raw,
    }


def wikipedia_section(
    tools: WikipediaToolset,
    *,
    page_id_or_title: str,
    section: str,
    language: str | None = None,
    max_chars: int = 2000,
) -> WikipediaToolResult:
    raw = _call_wikipedia_tool(
        tools.section,
        _compact_args(
            {"page": page_id_or_title, "section": section, "lang": language}
        ),
    )
    items = _normalize_wikipedia_items(
        raw, max_chars=max_chars, section=section
    )
    return {
        "source": "wikipedia",
        "tool": "section",
        "ok": True,
        "items": items,
        "raw": raw,
    }


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


def _call_wikipedia_tool(
    tool: McpToolHandle, arguments: Mapping[str, Any]
) -> Mapping[str, Any]:
    try:
        raw = tool.call(arguments)
    except TimeoutError as exc:
        raise WikipediaTimeoutError(
            f"Wikipedia tool '{tool.tool_name}' timed out."
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive for adapter implementations
        raise WikipediaToolError(
            f"Wikipedia tool '{tool.tool_name}' failed."
        ) from exc

    if raw is None:
        raise WikipediaToolError(
            f"Wikipedia tool '{tool.tool_name}' returned no data."
        )
    if isinstance(raw, list):
        raw = {"items": raw}
    if not isinstance(raw, Mapping):
        raise WikipediaToolError(
            f"Wikipedia tool '{tool.tool_name}' returned invalid payload."
        )
    _raise_if_wikipedia_error(raw, tool.tool_name)
    return raw


def _raise_if_error(raw: Mapping[str, Any], tool_name: str) -> None:
    error_value = raw.get("error") or raw.get("errors") or raw.get("message")
    status = raw.get("status")
    if error_value or status in {"error", "failed", "timeout"}:
        raise StackOverflowToolError(
            f"StackOverflow tool '{tool_name}' error: {error_value or status}."
        )


def _raise_if_wikipedia_error(raw: Mapping[str, Any], tool_name: str) -> None:
    error_value = raw.get("error") or raw.get("errors") or raw.get("message")
    status = raw.get("status")
    if error_value or status in {"error", "failed", "timeout"}:
        raise WikipediaToolError(
            f"Wikipedia tool '{tool_name}' error: {error_value or status}."
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


def _normalize_wikipedia_items(
    raw: Mapping[str, Any],
    *,
    max_chars: int,
    section: str | None = None,
) -> list[WikipediaItem]:
    items = (
        raw.get("items")
        or raw.get("pages")
        or raw.get("results")
        or raw.get("data")
    )
    if isinstance(items, Mapping):
        items = [items]
    if not isinstance(items, list):
        items = []
    normalized: list[WikipediaItem] = []
    for entry in items:
        if not isinstance(entry, Mapping):
            continue
        normalized.append(
            _normalize_wikipedia_item(entry, max_chars=max_chars, section=section)
        )
    if not normalized and raw:
        normalized.append(
            _normalize_wikipedia_item(raw, max_chars=max_chars, section=section)
        )
    return normalized


def _normalize_wikipedia_item(
    entry: Mapping[str, Any],
    *,
    max_chars: int,
    section: str | None = None,
) -> WikipediaItem:
    item: WikipediaItem = {}
    page_id = _coerce_str(
        entry.get("page_id") or entry.get("pageid") or entry.get("id")
    )
    if page_id:
        item["page_id"] = page_id
    title = _coerce_str(entry.get("title"))
    if title:
        item["title"] = title
    url = _coerce_str(entry.get("url") or entry.get("link") or entry.get("fullurl"))
    if url:
        item["url"] = url
    excerpt = _coerce_str(
        entry.get("excerpt") or entry.get("snippet") or entry.get("summary")
    )
    if excerpt:
        item["excerpt"] = _truncate_text(excerpt, max_chars=max_chars)
    content = _coerce_str(
        entry.get("content") or entry.get("extract") or entry.get("text")
    )
    if content:
        item["content"] = _truncate_text(content, max_chars=max_chars)
    if section:
        item["section"] = section
    return item


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


def _truncate_text(value: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return f"{value[: max_chars - 3]}..."


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
