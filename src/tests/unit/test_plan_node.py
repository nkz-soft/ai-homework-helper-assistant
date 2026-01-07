from packages.orchestrator.graph.nodes.plan import plan


def test_plan_programming_debug_defaults() -> None:
    state = {
        "question": "My Python code throws a traceback error. How to debug?",
        "subject": "programming",
        "intent": "debug",
    }
    result = plan(state)

    retrieval_plan = result["retrieval_plan"]
    assert retrieval_plan["parallelizable"] is True
    assert retrieval_plan["priority_order"] == [
        "stackoverflow",
        "wikipedia",
        "textbooks",
    ]
    assert [call["source"] for call in retrieval_plan["calls"]] == [
        "stackoverflow",
        "wikipedia",
        "textbooks",
    ]


def test_plan_builds_fallback_query() -> None:
    state = {"question": "", "subject": "math", "intent": "solve"}
    result = plan(state)

    retrieval_plan = result["retrieval_plan"]
    assert retrieval_plan["calls"][0]["query"].startswith("solve math")
    assert "step by step" in retrieval_plan["calls"][0]["query"]
