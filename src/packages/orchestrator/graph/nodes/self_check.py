from __future__ import annotations

import re
from typing import Mapping, cast

from packages.orchestrator.graph.state import EvidenceItem, OrchestratorState

_SECTION_HEADERS = {
    "Explanation",
    "Steps",
    "Worked Example",
    "Self-Check Questions",
    "Sources",
}


def self_check(state: Mapping[str, object]) -> OrchestratorState:
    evidence = _get_evidence(state)
    draft_answer = str(state.get("draft_answer") or state.get("final_answer") or "")

    supported_lines, unsupported = _filter_supported_sentences(draft_answer, evidence)
    diagnostics = _build_diagnostics(unsupported)

    if not supported_lines:
        supported_lines = ["I don't have enough evidence to support an answer yet."]

    final_answer = "\n".join(supported_lines).strip()

    return {
        "final_answer": final_answer,
        "diagnostics": diagnostics,
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


def _filter_supported_sentences(
    draft_answer: str, evidence: list[EvidenceItem]
) -> tuple[list[str], list[str]]:
    if not draft_answer.strip():
        return ([], [])

    claim_keys, support_keys = _build_support_keys(evidence)
    lines = _split_sentences(draft_answer)
    supported: list[str] = []
    unsupported: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in _SECTION_HEADERS:
            supported.append(stripped)
            continue
        if _is_supported(stripped, claim_keys, support_keys):
            supported.append(stripped)
        else:
            unsupported.append(stripped)

    return supported, unsupported


def _build_support_keys(
    evidence: list[EvidenceItem],
) -> tuple[list[str], list[str]]:
    claims: list[str] = []
    supports: list[str] = []
    for item in evidence:
        claim = str(item.get("claim", "")).strip()
        if claim:
            claims.append(claim.lower())
        support = str(item.get("support", "")).strip()
        if support:
            supports.append(support[:40].lower())
    return claims, supports


def _is_supported(sentence: str, claims: list[str], supports: list[str]) -> bool:
    lowered = sentence.lower()
    return any(claim in lowered for claim in claims) or any(
        support in lowered for support in supports
    )


def _split_sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text.strip())


def _build_diagnostics(unsupported: list[str]) -> dict[str, list[str]]:
    if not unsupported:
        return {"unsupported_claims": []}
    return {"unsupported_claims": unsupported}
