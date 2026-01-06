from packages.orchestrator.graph.nodes.classify import classify


def test_classify_programming_debug_intent() -> None:
    state = {"question": "My Python code throws a traceback error. How to debug?"}
    result = classify(state)

    assert result["subject"] == "programming"
    assert result["intent"] == "debug"
    assert result["needs_clarification"] is False


def test_classify_math_solve_intent() -> None:
    state = {"question": "Solve for x in this equation: 2x + 3 = 11"}
    result = classify(state)

    assert result["subject"] == "math"
    assert result["intent"] == "solve"
    assert result["needs_clarification"] is False


def test_classify_explain_intent_default_subject() -> None:
    state = {"question": "Explain what photosynthesis means"}
    result = classify(state)

    assert result["subject"] == "general"
    assert result["intent"] == "explain"
    assert result["needs_clarification"] is False


def test_classify_needs_clarification_for_short_prompt() -> None:
    state = {"question": "Help me"}
    result = classify(state)

    assert result["needs_clarification"] is True
