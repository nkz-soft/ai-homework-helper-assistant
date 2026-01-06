from __future__ import annotations

from typing import Mapping

from packages.orchestrator.graph.state import OrchestratorState


_PROGRAMMING_KEYWORDS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c#",
    "rust",
    "go",
    "golang",
    "ruby",
    "swift",
    "kotlin",
    "php",
    "sql",
    "regex",
    "compiler",
    "stacktrace",
    "traceback",
    "exception",
    "segfault",
    "bug",
    "debug",
    "algorithm",
    "data structure",
    "api",
    "http",
    "json",
}

_MATH_KEYWORDS = {
    "algebra",
    "geometry",
    "calculus",
    "derivative",
    "integral",
    "limit",
    "equation",
    "matrix",
    "vector",
    "probability",
    "statistics",
    "theorem",
    "proof",
    "solve for",
    "simplify",
}

_INTENT_DEBUG_KEYWORDS = {"debug", "error", "exception", "traceback", "stacktrace"}
_INTENT_SOLVE_KEYWORDS = {
    "solve",
    "calculate",
    "compute",
    "derive",
    "prove",
    "simplify",
    "evaluate",
    "find",
}
_INTENT_EXPLAIN_KEYWORDS = {
    "explain",
    "define",
    "what is",
    "how does",
    "why does",
    "meaning of",
}


def classify(state: Mapping[str, object]) -> OrchestratorState:
    question = str(state.get("question", "")).strip()
    lowered = question.lower()

    subject = _classify_subject(lowered)
    intent = _classify_intent(lowered)
    needs_clarification = _needs_clarification(question)

    return {
        "subject": subject,
        "intent": intent,
        "needs_clarification": needs_clarification,
    }


def _classify_subject(text: str) -> str:
    if _contains_any(text, _PROGRAMMING_KEYWORDS):
        return "programming"
    if _contains_any(text, _MATH_KEYWORDS):
        return "math"
    return "general"


def _classify_intent(text: str) -> str:
    if _contains_any(text, _INTENT_DEBUG_KEYWORDS):
        return "debug"
    if _contains_any(text, _INTENT_SOLVE_KEYWORDS):
        return "solve"
    if _contains_any(text, _INTENT_EXPLAIN_KEYWORDS):
        return "explain"
    return "explain"


def _needs_clarification(question: str) -> bool:
    if not question:
        return True
    tokens = [token for token in question.split() if token.strip()]
    return len(tokens) < 3


def _contains_any(text: str, keywords: set[str]) -> bool:
    return any(keyword in text for keyword in keywords)
