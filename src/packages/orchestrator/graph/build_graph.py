from __future__ import annotations

import asyncio
import json
import logging
import time
from functools import lru_cache, wraps
from typing import Any, Callable, Coroutine, Mapping, cast

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
from packages.orchestrator.llm import LlmClient

log = logging.getLogger(__name__)


def run(
    question: str,
    context: Mapping[str, object] | None = None,
    llm_client: LlmClient | None = None,
) -> OrchestratorState:
    state: dict[str, object] = {"question": question}
    if context:
        if "student_context" not in context:
            state["student_context"] = dict(context)
        state.update(context)
    if llm_client is not None:
        state["llm_client"] = llm_client

    graph = _build_graph()
    return _run_async(
        cast(Coroutine[Any, Any, OrchestratorState], graph.ainvoke(state))
    )


@lru_cache(maxsize=1)
def _build_graph():
    graph = StateGraph(OrchestratorState)
    graph.add_node("classify", _with_node_logging("classify", classify))
    graph.add_node("plan", _with_node_logging("plan", plan))
    graph.add_node("retrieve", _with_node_logging("retrieve", retrieve))
    graph.add_node("normalize", _with_node_logging("normalize", normalize))
    graph.add_node("safety", _with_node_logging("safety", safety))
    graph.add_node("synthesize", _with_node_logging("synthesize", synthesize))
    graph.add_node(
        "prepare_self_check",
        _with_node_logging("prepare_self_check", _prepare_self_check),
    )
    graph.add_node("self_check", _with_node_logging("self_check", self_check))
    graph.add_node("finalize", _with_node_logging("finalize", finalize))

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


def _with_node_logging(
    node_name: str, func: Callable[[Mapping[str, object]], Any]
) -> Callable[[Mapping[str, object]], Any]:
    if asyncio.iscoroutinefunction(func):

        @wraps(func)
        async def _async_wrapper(state: Mapping[str, object]) -> Any:
            start = time.perf_counter()
            _log_node_event("start", node_name, state)
            try:
                result = await func(state)
            except Exception:
                _log_node_exception(node_name, start)
                raise
            _log_node_finish(node_name, start, result)
            return result

        return _async_wrapper

    @wraps(func)
    def _sync_wrapper(state: Mapping[str, object]) -> Any:
        start = time.perf_counter()
        _log_node_event("start", node_name, state)
        try:
            result = func(state)
        except Exception:
            _log_node_exception(node_name, start)
            raise
        _log_node_finish(node_name, start, result)
        return result

    return _sync_wrapper


def _log_node_event(phase: str, node_name: str, state: Mapping[str, object]) -> None:
    payload = {
        "event": "orchestrator_node",
        "phase": phase,
        "node": node_name,
        "state_keys": _state_keys(state),
    }
    log.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _log_node_finish(
    node_name: str, start: float, result: Mapping[str, object] | Any
) -> None:
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    payload = {
        "event": "orchestrator_node",
        "phase": "finish",
        "node": node_name,
        "latency_ms": elapsed_ms,
        "result_keys": _state_keys(result) if isinstance(result, Mapping) else [],
        "ok": True,
    }
    log.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _log_node_exception(node_name: str, start: float) -> None:
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    payload = {
        "event": "orchestrator_node",
        "phase": "error",
        "node": node_name,
        "latency_ms": elapsed_ms,
        "ok": False,
    }
    log.exception(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _state_keys(state: Mapping[str, object]) -> list[str]:
    try:
        return sorted(str(key) for key in state.keys())
    except Exception:
        return []


def _run_async(coro: Coroutine[Any, Any, OrchestratorState]) -> OrchestratorState:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    return asyncio.run(coro)
