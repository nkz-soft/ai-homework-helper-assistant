from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any, Coroutine, Mapping, cast

from langgraph.graph import END, StateGraph

from packages.orchestrator.graph.nodes import (
    classify,
    finalize,
    normalize,
    plan,
    retrieve,
    safety,
    self_check,
    synthesize,
)
from packages.orchestrator.graph.state import OrchestratorState


def run(
    question: str, context: Mapping[str, object] | None = None
) -> OrchestratorState:
    state: dict[str, object] = {"question": question}
    if context:
        if "student_context" not in context:
            state["student_context"] = dict(context)
        state.update(context)

    graph = _build_graph()
    return _run_async(
        cast(Coroutine[Any, Any, OrchestratorState], graph.ainvoke(state))
    )


@lru_cache(maxsize=1)
def _build_graph():
    graph = StateGraph(OrchestratorState)
    graph.add_node("classify", classify)
    graph.add_node("plan", plan)
    graph.add_node("retrieve", retrieve)
    graph.add_node("normalize", normalize)
    graph.add_node("safety", safety)
    graph.add_node("synthesize", synthesize)
    graph.add_node("prepare_self_check", _prepare_self_check)
    graph.add_node("self_check", self_check)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "plan")
    graph.add_edge("plan", "retrieve")
    graph.add_edge("retrieve", "normalize")
    graph.add_edge("normalize", "safety")
    graph.add_edge("safety", "synthesize")
    graph.add_edge("synthesize", "prepare_self_check")
    graph.add_edge("prepare_self_check", "self_check")
    graph.add_edge("self_check", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def _prepare_self_check(state: Mapping[str, object]) -> OrchestratorState:
    final_answer = state.get("final_answer")
    if "draft_answer" not in state and isinstance(final_answer, str):
        return {"draft_answer": final_answer}
    return {}


def _run_async(coro: Coroutine[Any, Any, OrchestratorState]) -> OrchestratorState:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    return asyncio.run(coro)
