from __future__ import annotations

from pathlib import Path
from typing import Mapping, cast

from packages.orchestrator.graph.state import (
    OrchestratorState,
    PlanCall,
    RetrievalPlan,
    SourceName,
)


_DEFAULT_SOURCES: dict[tuple[str, str], list[SourceName]] = {
    ("programming", "debug"): ["stackoverflow", "wikipedia", "textbooks"],
    ("programming", "solve"): ["stackoverflow", "wikipedia", "textbooks"],
    ("programming", "explain"): ["stackoverflow", "wikipedia", "textbooks"],
    ("math", "solve"): ["textbooks", "wikipedia"],
    ("math", "explain"): ["wikipedia", "textbooks"],
    ("general", "explain"): ["wikipedia", "textbooks"],
    ("general", "solve"): ["wikipedia", "textbooks"],
}

_SOURCE_TO_TOOL: dict[SourceName, str] = {
    "stackoverflow": "so_search",
    "wikipedia": "wikipedia_search",
    "textbooks": "textbooks_search",
}
_SOURCE_NAMES = set(_SOURCE_TO_TOOL.keys())


def plan(state: Mapping[str, object]) -> OrchestratorState:
    question = str(state.get("question", "")).strip()
    subject = str(state.get("subject", "general")).strip().lower() or "general"
    intent = str(state.get("intent", "explain")).strip().lower() or "explain"

    subjects_cfg = _load_config("subjects.yaml")
    policies_cfg = _load_config("policies.yaml")

    sources = _determine_sources(subject, intent, subjects_cfg, policies_cfg)
    query_hints = _determine_query_hints(subject, intent, subjects_cfg)
    calls = _build_calls(question, subject, intent, sources, query_hints)

    retrieval_plan: RetrievalPlan = {
        "calls": calls,
        "priority_order": sources,
        "parallelizable": True,
    }

    return {"retrieval_plan": retrieval_plan}


def _build_calls(
    question: str,
    subject: str,
    intent: str,
    sources: list[SourceName],
    query_hints: list[str],
) -> list[PlanCall]:
    calls: list[PlanCall] = []
    query = _build_query(question, subject, intent, query_hints)
    for priority, source in enumerate(sources, start=1):
        tool = _SOURCE_TO_TOOL[source]
        calls.append(
            {
                "source": source,
                "tool": tool,
                "query": query,
                "priority": priority,
            }
        )
    return calls


def _build_query(
    question: str, subject: str, intent: str, query_hints: list[str]
) -> str:
    base = question
    if not base:
        if subject != "general":
            base = f"{intent} {subject}".strip()
        else:
            base = intent
    hint = query_hints[0] if query_hints else ""
    if hint and hint.lower() not in base.lower():
        return f"{base} {hint}".strip()
    return base
    if subject != "general":
        return f"{intent} {subject}".strip()
    return intent


def _determine_sources(
    subject: str,
    intent: str,
    subjects_cfg: dict[str, object],
    policies_cfg: dict[str, object],
) -> list[SourceName]:
    sources = _lookup_subject_sources(subject, intent, subjects_cfg)
    if not sources:
        sources = _DEFAULT_SOURCES.get((subject, intent)) or _DEFAULT_SOURCES.get(
            (subject, "explain"),
            ["wikipedia"],
        )

    allow_list = _get_list_value(policies_cfg, "allow_sources")
    if allow_list:
        sources = [source for source in sources if source in allow_list]

    deny_list = _get_list_value(policies_cfg, "deny_sources")
    if deny_list:
        sources = [source for source in sources if source not in deny_list]

    return sources or ["wikipedia"]


def _determine_query_hints(
    subject: str, intent: str, subjects_cfg: dict[str, object]
) -> list[str]:
    subject_cfg = subjects_cfg.get(subject)
    if isinstance(subject_cfg, dict):
        intent_cfg = subject_cfg.get("intents")
        if isinstance(intent_cfg, dict):
            hints = intent_cfg.get(intent)
            if isinstance(hints, dict):
                intent_hints = hints.get("query_hints")
                if isinstance(intent_hints, list):
                    return _string_list(intent_hints)
        subject_hints = subject_cfg.get("query_hints")
        if isinstance(subject_hints, list):
            return _string_list(subject_hints)

    default_cfg = subjects_cfg.get("default")
    if isinstance(default_cfg, dict):
        default_hints = default_cfg.get("query_hints")
        if isinstance(default_hints, list):
            return _string_list(default_hints)
    return []


def _lookup_subject_sources(
    subject: str,
    intent: str,
    subjects_cfg: dict[str, object],
) -> list[SourceName]:
    subject_cfg = subjects_cfg.get(subject)
    if isinstance(subject_cfg, dict):
        intent_cfg = subject_cfg.get("intents")
        if isinstance(intent_cfg, dict):
            sources = intent_cfg.get(intent)
            if isinstance(sources, list):
                return _normalize_sources(sources)
            sources = intent_cfg.get("sources")
            if isinstance(sources, list):
                return _normalize_sources(sources)
        sources = subject_cfg.get("sources")
        if isinstance(sources, list):
            return _normalize_sources(sources)

    default_cfg = subjects_cfg.get("default")
    if isinstance(default_cfg, dict):
        sources = default_cfg.get("sources")
        if isinstance(sources, list):
            return _normalize_sources(sources)

    return []


def _get_list_value(config: dict[str, object], key: str) -> list[SourceName]:
    value = config.get(key)
    if isinstance(value, list):
        return _normalize_sources(value)
    return []


def _normalize_sources(values: list[object]) -> list[SourceName]:
    normalized: list[SourceName] = []
    for value in values:
        item = str(value).strip()
        if item in _SOURCE_NAMES:
            normalized.append(cast(SourceName, item))
    return normalized


def _string_list(values: list[object]) -> list[str]:
    return [str(value) for value in values if str(value).strip()]


def _load_config(filename: str) -> dict[str, object]:
    config_path = _config_dir() / filename
    if not config_path.exists():
        return {}

    raw = config_path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}

    parsed = _try_yaml_load(raw)
    return parsed if isinstance(parsed, dict) else {}


def _try_yaml_load(raw: str) -> dict[str, object]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_simple_yaml(raw)

    try:
        loaded = yaml.safe_load(raw)
    except Exception:
        return {}

    return loaded if isinstance(loaded, dict) else {}


def _parse_simple_yaml(raw: str) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        parsed[key] = value
    return parsed


def _config_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "config"
