from __future__ import annotations

from typing import Any, Literal, Mapping, NotRequired, TypedDict


class StudentContext(TypedDict, total=False):
    subject_hint: str
    language: str
    level: str
    constraints: list[str]


class ToolBudget(TypedDict, total=False):
    total_calls: int
    per_server_caps: dict[str, int]
    max_bytes: int


class RetrievedItem(TypedDict, total=False):
    source: Literal["wikipedia", "stackoverflow", "textbooks", "other"]
    tool: str
    query: str
    result: dict[str, Any]
    error: NotRequired[str]


class EvidenceItem(TypedDict):
    claim: str
    support: str
    source: Literal["wikipedia", "stackoverflow", "textbooks"]
    locator: str
    license_note: NotRequired[str]
    confidence: NotRequired[float]


class Citation(TypedDict, total=False):
    source: str
    locator: str
    url: str
    title: str


SourceName = Literal["wikipedia", "stackoverflow", "textbooks"]


class PlanCall(TypedDict):
    source: SourceName
    tool: str
    query: str
    priority: int


class RetrievalPlan(TypedDict):
    calls: list[PlanCall]
    priority_order: list[SourceName]
    parallelizable: bool


class OrchestratorState(TypedDict, total=False):
    question: str
    student_context: StudentContext
    tools: Mapping[str, object]
    subject: str
    intent: str
    mode: Literal["coach", "solution_allowed", "hint_only"]
    needs_clarification: bool
    tool_budget: ToolBudget
    retrieval_plan: RetrievalPlan
    retrieved_items: list[RetrievedItem]
    evidence: list[EvidenceItem]
    draft_answer: str
    final_answer: str
    citations: list[Citation]
    safety_flags: list[str]
    diagnostics: dict[str, Any]
