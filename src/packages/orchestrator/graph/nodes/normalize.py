from __future__ import annotations

from typing import Any, Mapping, cast

from packages.orchestrator.graph.state import (
    EvidenceItem,
    OrchestratorState,
    RetrievedItem,
)

_MAX_EXCERPT_CHARS = 240


def normalize(state: Mapping[str, object]) -> OrchestratorState:
    retrieved_items = _get_retrieved_items(state)
    evidence: list[EvidenceItem] = []
    for item in retrieved_items:
        if item.get("error"):
            continue
        source = item.get("source")
        result = item.get("result")
        if not isinstance(result, Mapping):
            continue
        if source == "stackoverflow":
            evidence.extend(_normalize_stackoverflow(result))
        elif source == "wikipedia":
            evidence.extend(_normalize_wikipedia(result))
        elif source == "textbooks":
            evidence.extend(_normalize_textbooks(result))
    return {"evidence": evidence}


def _get_retrieved_items(state: Mapping[str, object]) -> list[RetrievedItem]:
    raw = state.get("retrieved_items")
    if not isinstance(raw, list):
        return []
    items: list[RetrievedItem] = []
    for entry in raw:
        if isinstance(entry, Mapping):
            items.append(cast(RetrievedItem, dict(entry)))
    return items


def _normalize_stackoverflow(result: Mapping[str, Any]) -> list[EvidenceItem]:
    items = _coerce_list(result.get("items"))
    evidence: list[EvidenceItem] = []
    for entry in items:
        if not isinstance(entry, Mapping):
            continue
        title = _coerce_str(entry.get("title"))
        url = _coerce_str(entry.get("url"))
        question_id = _coerce_str(entry.get("question_id"))
        excerpt = _coerce_str(entry.get("excerpt") or entry.get("content"))
        support = _truncate_excerpt(excerpt) if excerpt else ""
        claim = _build_claim(title, excerpt)
        locator = url or question_id
        if not claim or not locator:
            continue
        evidence.append(
            {
                "claim": claim,
                "support": support,
                "source": "stackoverflow",
                "locator": locator,
                "license_note": "CC BY-SA 4.0",
                "confidence": _stack_overflow_confidence(entry),
            }
        )
    return evidence


def _normalize_wikipedia(result: Mapping[str, Any]) -> list[EvidenceItem]:
    items = _coerce_list(result.get("items"))
    evidence: list[EvidenceItem] = []
    for entry in items:
        if not isinstance(entry, Mapping):
            continue
        title = _coerce_str(entry.get("title"))
        url = _coerce_str(entry.get("url"))
        page_id = _coerce_str(entry.get("page_id"))
        excerpt = _coerce_str(entry.get("excerpt") or entry.get("content"))
        support = _truncate_excerpt(excerpt) if excerpt else ""
        claim = _build_claim(title, excerpt)
        locator = url or page_id
        if not claim or not locator:
            continue
        evidence.append(
            {
                "claim": claim,
                "support": support,
                "source": "wikipedia",
                "locator": locator,
                "license_note": "CC BY-SA 4.0",
            }
        )
    return evidence


def _normalize_textbooks(result: Mapping[str, Any]) -> list[EvidenceItem]:
    items = _coerce_list(result.get("items")) or _coerce_list(result.get("chunks"))
    evidence: list[EvidenceItem] = []
    for entry in items:
        if not isinstance(entry, Mapping):
            continue
        license_note = _coerce_str(entry.get("license") or entry.get("license_note"))
        if not license_note:
            continue
        title = _coerce_str(entry.get("title") or entry.get("heading"))
        locator = _coerce_str(
            entry.get("url") or entry.get("id") or entry.get("chunk_id")
        )
        excerpt = _coerce_str(
            entry.get("excerpt") or entry.get("content") or entry.get("text")
        )
        support = _truncate_excerpt(excerpt) if excerpt else ""
        claim = _build_claim(title, excerpt)
        if not claim or not locator:
            continue
        evidence.append(
            {
                "claim": claim,
                "support": support,
                "source": "textbooks",
                "locator": locator,
                "license_note": license_note,
                "confidence": 0.8,
            }
        )
    return evidence


def _build_claim(title: str | None, excerpt: str | None) -> str:
    if title:
        return title.strip()
    if excerpt:
        return _first_sentence(excerpt.strip())
    return ""


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    for delimiter in (". ", "? ", "! "):
        if delimiter in text:
            return text.split(delimiter, 1)[0].strip() + delimiter.strip()
    return _truncate_excerpt(text)


def _truncate_excerpt(text: str, *, max_chars: int = _MAX_EXCERPT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return f"{text[: max_chars - 3]}..."


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _stack_overflow_confidence(entry: Mapping[str, Any]) -> float:
    accepted = entry.get("accepted") is True
    score = entry.get("score")
    if accepted:
        return 0.75
    if isinstance(score, int) and score >= 5:
        return 0.7
    if isinstance(score, int) and score > 0:
        return 0.6
    return 0.5
