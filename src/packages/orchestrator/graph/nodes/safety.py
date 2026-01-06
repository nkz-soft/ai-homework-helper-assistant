from __future__ import annotations

import re
from typing import Literal, Mapping, cast

from packages.orchestrator.graph.state import EvidenceItem, OrchestratorState

_INJECTION_PATTERNS = [
    r"\bignore (all|previous) instructions\b",
    r"\bsystem prompt\b",
    r"\byou are chatgpt\b",
    r"\bdo not follow\b",
    r"\bdeveloper message\b",
    r"\bexecute (this|the following) prompt\b",
    r"\bcall tool\b",
    r"\bexfiltrate\b",
    r"\bconfidential\b",
]

_ACADEMIC_MISUSE_PATTERNS = [
    r"\bdo my homework\b",
    r"\bdo this (for me|for us)\b",
    r"\bjust give me the answer\b",
    r"\bno explanation\b",
    r"\bfinal answer only\b",
    r"\bwrite my (essay|paper)\b",
    r"\bsolve it for me\b",
]


def safety(state: Mapping[str, object]) -> OrchestratorState:
    evidence = _get_evidence(state)
    question = str(state.get("question", "")).strip()

    safety_flags: list[str] = []
    if _has_injection(evidence):
        safety_flags.append("prompt_injection")
        evidence = _filter_injection(evidence)

    if _academic_misuse(question):
        safety_flags.append("academic_integrity")

    mode = _select_mode(state.get("mode"), safety_flags)

    return {
        "evidence": evidence,
        "safety_flags": safety_flags,
        "mode": mode,
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


def _has_injection(evidence: list[EvidenceItem]) -> bool:
    for item in evidence:
        text = f"{item.get('claim', '')} {item.get('support', '')}".strip()
        if _matches_any(text, _INJECTION_PATTERNS):
            return True
    return False


def _filter_injection(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    filtered: list[EvidenceItem] = []
    for item in evidence:
        text = f"{item.get('claim', '')} {item.get('support', '')}".strip()
        if _matches_any(text, _INJECTION_PATTERNS):
            continue
        filtered.append(item)
    return filtered


def _academic_misuse(question: str) -> bool:
    return _matches_any(question, _ACADEMIC_MISUSE_PATTERNS)


def _select_mode(
    existing_mode: object, safety_flags: list[str]
) -> Literal["coach", "solution_allowed", "hint_only"]:
    if "academic_integrity" in safety_flags:
        return "coach"
    if existing_mode in {"coach", "solution_allowed", "hint_only"}:
        return cast(Literal["coach", "solution_allowed", "hint_only"], existing_mode)
    return "coach"


def _matches_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)
