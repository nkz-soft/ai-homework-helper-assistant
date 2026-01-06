from packages.orchestrator.graph.nodes.synthesize import synthesize


def test_synthesize_builds_answer_and_citations() -> None:
    state = {
        "evidence": [
            {
                "claim": "Photosynthesis converts light energy into chemical energy.",
                "support": "Plants use chlorophyll to capture light.",
                "source": "wikipedia",
                "locator": "https://en.wikipedia.org/wiki/Photosynthesis",
                "license_note": "CC BY-SA 4.0",
            },
            {
                "claim": "Chlorophyll absorbs light mainly in red and blue wavelengths.",
                "support": "Absorption peaks align with red and blue light.",
                "source": "wikipedia",
                "locator": "https://en.wikipedia.org/wiki/Chlorophyll",
                "license_note": "CC BY-SA 4.0",
            },
        ]
    }

    result = synthesize(state)

    assert "final_answer" in result
    assert "citations" in result
    assert len(result["citations"]) == 2
    assert "## Explanation" in result["final_answer"]
    assert "## Sources" in result["final_answer"]
    assert (
        "[wikipedia:https://en.wikipedia.org/wiki/Photosynthesis]"
        in result["final_answer"]
    )


def test_synthesize_handles_empty_evidence() -> None:
    result = synthesize({"evidence": []})

    assert result["citations"] == []
    assert "I do not have enough evidence yet" in result["final_answer"]
