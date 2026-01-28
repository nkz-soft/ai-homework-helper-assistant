from __future__ import annotations

import logging
from typing import Mapping, cast

from packages.orchestrator.graph.state import (
    Citation,
    EvidenceItem,
    OrchestratorState,
    get_llm_client,
)
from packages.orchestrator.prompts import load_prompt, render_prompt

log = logging.getLogger(__name__)


def synthesize(state: Mapping[str, object]) -> OrchestratorState:
    evidence = _get_evidence(state)
    if not evidence:
        return {
            "final_answer": _no_evidence_answer(),
            "citations": [],
            "diagnostics": _prompt_diagnostics(state),
        }

    citations = _build_citations(evidence)
    llm_client = get_llm_client(state)
    final_answer = ""
    if llm_client is not None:
        prompt = _build_llm_prompt(state, evidence, citations)
        try:
            final_answer = llm_client.generate(prompt, temperature=0.2, max_tokens=900)
        except Exception as exc:  # noqa: BLE001 - LLM failures should fall back.
            log.warning("LLM synthesis failed: %s", exc)
            diagnostics = _prompt_diagnostics(state)
            _append_diagnostic_error(diagnostics, f"llm_error:{exc}")
            return {
                "final_answer": _fallback_answer(evidence, citations),
                "citations": citations,
                "diagnostics": diagnostics,
            }

    if not final_answer.strip():
        final_answer = _fallback_answer(evidence, citations)

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


def _build_llm_prompt(
    state: Mapping[str, object],
    evidence: list[EvidenceItem],
    citations: list[Citation],
) -> str:
    system_prompt = load_prompt("system")
    question = str(state.get("question", "")).strip()
    mode = str(state.get("mode", "coach"))
    student_context = _format_student_context(state.get("student_context"))
    evidence_lines = _format_evidence(evidence)
    source_lines = _build_sources(citations)
    instruction = (
        "Use only the evidence below. Include citation markers in the form "
        "[source:locator] and keep the section headings exactly as shown."
    )
    return "\n\n".join(
        [
            system_prompt,
            instruction,
            f"Question: {question}" if question else "Question: (none)",
            f"Mode: {mode}",
            f"Student context: {student_context}"
            if student_context
            else "Student context: (none)",
            "Evidence:",
            evidence_lines or "- (none)",
            "Sources:",
            source_lines or "- No sources available.",
            "Respond with these headings: ## Explanation, ## Steps, ## Worked Example, "
            "## Self-Check Questions, ## Sources.",
        ]
    )


def _format_student_context(student_context: object) -> str:
    if not isinstance(student_context, Mapping):
        return ""
    parts: list[str] = []
    for key in ("subject_hint", "language", "level"):
        value = student_context.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(f"{key}={value.strip()}")
    constraints = student_context.get("constraints")
    if isinstance(constraints, list):
        normalized = [str(item).strip() for item in constraints if str(item).strip()]
        if normalized:
            parts.append(f"constraints={', '.join(normalized)}")
    return "; ".join(parts)


def _format_evidence(evidence: list[EvidenceItem]) -> str:
    lines: list[str] = []
    for item in evidence:
        claim = item.get("claim", "").strip()
        support = item.get("support", "").strip()
        source = item.get("source", "").strip()
        locator = item.get("locator", "").strip()
        if not claim and not support:
            continue
        lines.append(
            f"- source={source} locator={locator} claim={claim} support={support}"
        )
    return "\n".join(lines)


def _fallback_answer(evidence: list[EvidenceItem], citations: list[Citation]) -> str:
    explanation = _build_explanation(evidence)
    steps = _build_steps(evidence)
    example = _build_example(evidence)
    self_check = _build_self_check(evidence)
    sources = _build_sources(citations)
    return render_prompt(
        "synthesis",
        {
            "explanation": explanation,
            "steps": steps,
            "example": example,
            "self_check": self_check,
            "sources": sources,
        },
    )


def _append_diagnostic_error(diagnostics: dict[str, object], error: str) -> None:
    errors = diagnostics.get("errors")
    if isinstance(errors, list):
        errors.append(error)
    else:
        diagnostics["errors"] = [error]


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
