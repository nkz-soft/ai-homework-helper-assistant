from __future__ import annotations

from typing import Mapping, cast

from packages.orchestrator.graph.state import Citation, EvidenceItem, OrchestratorState
from packages.orchestrator.prompts import load_prompt, render_prompt


def synthesize(state: Mapping[str, object]) -> OrchestratorState:
    evidence = _get_evidence(state)
    if not evidence:
        return {
            "final_answer": _no_evidence_answer(),
            "citations": [],
            "diagnostics": _prompt_diagnostics(state),
        }

    citations = _build_citations(evidence)
    explanation = _build_explanation(evidence)
    steps = _build_steps(evidence)
    example = _build_example(evidence)
    self_check = _build_self_check(evidence)
    sources = _build_sources(citations)

    final_answer = render_prompt(
        "synthesis",
        {
            "explanation": explanation,
            "steps": steps,
            "example": example,
            "self_check": self_check,
            "sources": sources,
        },
    )

    return {
        "final_answer": final_answer,
        "citations": citations,
        "diagnostics": _prompt_diagnostics(state),
    }


def _get_evidence(state: Mapping[str, object]) -> list[EvidenceItem]:
    raw = state.get("evidence")
    if not isinstance(raw, list):
        return []
    evidence: list[EvidenceItem] = []
    for item in raw:
        if isinstance(item, dict):
            evidence.append(cast(EvidenceItem, item))
    return evidence


def _build_explanation(evidence: list[EvidenceItem]) -> str:
    lines: list[str] = []
    for item in evidence[:3]:
        claim = item.get("claim", "").strip()
        if claim:
            lines.append(f"- {claim} {_citation_marker(item)}".strip())
    return "\n".join(lines) if lines else "No evidence-backed explanation yet."


def _build_steps(evidence: list[EvidenceItem]) -> str:
    steps: list[str] = []
    for index, item in enumerate(evidence[:4], start=1):
        claim = item.get("claim", "").strip()
        if claim:
            steps.append(f"{index}. {claim} {_citation_marker(item)}".strip())
    return "\n".join(steps) if steps else "1. Gather more details."


def _build_example(evidence: list[EvidenceItem]) -> str:
    item = evidence[0]
    support = item.get("support", "").strip()
    claim = item.get("claim", "").strip()
    if support:
        return f"{support} {_citation_marker(item)}".strip()
    if claim:
        return f"{claim} {_citation_marker(item)}".strip()
    return "Example unavailable without evidence."


def _build_self_check(evidence: list[EvidenceItem]) -> str:
    questions: list[str] = []
    for item in evidence[:3]:
        claim = item.get("claim", "").strip()
        if claim:
            questions.append(f"- How would you explain: {claim}?")
    return "\n".join(questions) if questions else "- What details are still missing?"


def _build_sources(citations: list[Citation]) -> str:
    if not citations:
        return "- No sources available."
    lines = []
    for index, cite in enumerate(citations, start=1):
        label = cite.get("title") or cite.get("locator") or cite.get("source")
        url = cite.get("url") or cite.get("locator") or ""
        line = render_prompt(
            "citation",
            {"index": str(index), "title": str(label), "url": str(url)},
        )
        lines.append(line.rstrip("— ").rstrip())
    return "\n".join(lines)


def _build_citations(evidence: list[EvidenceItem]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        source = item.get("source", "")
        locator = item.get("locator", "")
        key = (source, locator)
        if not source or not locator or key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "source": source,
                "locator": locator,
                "url": locator,
                "title": item.get("claim", ""),
            }
        )
    return citations


def _citation_marker(item: EvidenceItem) -> str:
    source = item.get("source")
    locator = item.get("locator")
    if not source or not locator:
        return ""
    return f"[{source}:{locator}]"


def _no_evidence_answer() -> str:
    return render_prompt(
        "synthesis",
        {
            "explanation": "I do not have enough evidence yet to answer confidently.",
            "steps": "1. Share more context or details about the problem.",
            "example": "Example unavailable without sources.",
            "self_check": "- What details are still missing?",
            "sources": "- No sources available.",
        },
    )


def _prompt_diagnostics(state: Mapping[str, object]) -> dict[str, object]:
    diagnostics = state.get("diagnostics")
    merged = dict(diagnostics) if isinstance(diagnostics, Mapping) else {}
    merged.setdefault("system_prompt", load_prompt("system"))
    return merged
