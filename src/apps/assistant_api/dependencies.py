from __future__ import annotations

import logging
from functools import lru_cache
from typing import Callable, Mapping

from packages.orchestrator.graph.build_graph import run as run_orchestrator
from packages.orchestrator.llm_client import OpenAiChatClient
from packages.orchestrator.llm_config import LlmConfigLoader

OrchestratorFn = Callable[[str, Mapping[str, object] | None], Mapping[str, object]]

log = logging.getLogger(__name__)


def get_orchestrator() -> OrchestratorFn:
    llm_client = _load_llm_client()

    def _run(
        question: str, context: Mapping[str, object] | None
    ) -> Mapping[str, object]:
        return run_orchestrator(question, context, llm_client=llm_client)

    return _run


@lru_cache(maxsize=1)
def _load_llm_client() -> OpenAiChatClient | None:
    try:
        config = LlmConfigLoader().load()
    except Exception as exc:  # noqa: BLE001 - fail open for local dev.
        log.warning("LLM config unavailable: %s", exc)
        return None
    return OpenAiChatClient(config)
