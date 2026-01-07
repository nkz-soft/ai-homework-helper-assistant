from __future__ import annotations

import re
from pathlib import Path
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

_DEFAULT_RED_FLAGS = [
    "do my homework",
    "do this for me",
    "just give me the answer",
    "no explanation",
    "final answer only",
    "write my essay",
    "solve it for me",
]


def safety(state: Mapping[str, object]) -> OrchestratorState:
    evidence = _get_evidence(state)
    question = str(state.get("question", "")).strip()
    policies = _load_policies()
    red_flags = _get_red_flags(policies)
    default_mode = _get_default_mode(policies)

    safety_flags: list[str] = []
    if _has_injection(evidence):
        safety_flags.append("prompt_injection")
        evidence = _filter_injection(evidence)

    if _academic_misuse(question, red_flags):
        safety_flags.append("academic_integrity")

    mode = _select_mode(state.get("mode"), safety_flags, default_mode)

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


def _academic_misuse(question: str, red_flags: list[str]) -> bool:
    lowered = question.lower()
    return any(flag in lowered for flag in red_flags)


def _select_mode(
    existing_mode: object,
    safety_flags: list[str],
    default_mode: Literal["coach", "solution_allowed", "hint_only"],
) -> Literal["coach", "solution_allowed", "hint_only"]:
    if "academic_integrity" in safety_flags:
        return "coach"
    if existing_mode in {"coach", "solution_allowed", "hint_only"}:
        return cast(Literal["coach", "solution_allowed", "hint_only"], existing_mode)
    return default_mode


def _matches_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def _load_policies() -> dict[str, object]:
    config_path = _config_dir() / "policies.yaml"
    if not config_path.exists():
        return {}

    raw = config_path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}

    parsed = _try_yaml_load(raw)
    return parsed if isinstance(parsed, dict) else {}


def _get_red_flags(policies: Mapping[str, object]) -> list[str]:
    red_flags = policies.get("red_flags")
    if isinstance(red_flags, list):
        return [str(item).lower() for item in red_flags if str(item)]
    return _DEFAULT_RED_FLAGS


def _get_default_mode(
    policies: Mapping[str, object],
) -> Literal["coach", "solution_allowed", "hint_only"]:
    defaults = policies.get("defaults")
    if isinstance(defaults, Mapping):
        mode = defaults.get("mode")
        if mode in {"coach", "solution_allowed", "hint_only"}:
            return cast(Literal["coach", "solution_allowed", "hint_only"], mode)
    return "coach"


def _try_yaml_load(raw: str) -> dict[str, object]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}

    try:
        loaded = yaml.safe_load(raw)
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _config_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "config"
