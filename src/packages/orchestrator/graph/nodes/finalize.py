from __future__ import annotations

from typing import Mapping

from packages.orchestrator.graph.state import OrchestratorState


def finalize(state: Mapping[str, object]) -> OrchestratorState:
    final_answer = str(state.get("final_answer") or state.get("draft_answer") or "")
    citations = state.get("citations")
    diagnostics = state.get("diagnostics")
    safety_flags = state.get("safety_flags")

    return {
        "final_answer": final_answer,
        "citations": citations if isinstance(citations, list) else [],
        "diagnostics": diagnostics if isinstance(diagnostics, dict) else {},
        "safety_flags": safety_flags if isinstance(safety_flags, list) else [],
    }
