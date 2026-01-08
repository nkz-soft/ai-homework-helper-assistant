from __future__ import annotations

from typing import Callable, Mapping

from packages.orchestrator.graph.build_graph import run as run_orchestrator

OrchestratorFn = Callable[[str, Mapping[str, object] | None], Mapping[str, object]]


def get_orchestrator() -> OrchestratorFn:
    return run_orchestrator
