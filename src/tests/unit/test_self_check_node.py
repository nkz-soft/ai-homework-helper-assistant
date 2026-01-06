from packages.orchestrator.graph.nodes.self_check import self_check


def test_self_check_removes_unsupported_claims() -> None:
    state = {
        "draft_answer": "\n".join(
            [
                "Explanation",
                "Photosynthesis converts light energy into chemical energy.",
                "It happens on Mars.",
                "Sources",
            ]
        ),
        "evidence": [
            {
                "claim": "Photosynthesis converts light energy into chemical energy.",
                "support": "Plants use chlorophyll to capture light.",
                "source": "wikipedia",
                "locator": "https://en.wikipedia.org/wiki/Photosynthesis",
                "license_note": "CC BY-SA 4.0",
            }
        ],
    }

    result = self_check(state)

    assert "It happens on Mars." not in result["final_answer"]
    assert (
        "Photosynthesis converts light energy into chemical energy."
        in result["final_answer"]
    )
    assert "Explanation" in result["final_answer"]
    assert "Sources" in result["final_answer"]
    assert result["diagnostics"]["unsupported_claims"] == ["It happens on Mars."]


def test_self_check_falls_back_without_supported_sentences() -> None:
    state = {
        "draft_answer": "Unrelated statement.",
        "evidence": [
            {
                "claim": "Supported claim.",
                "support": "Backed by evidence.",
                "source": "wikipedia",
                "locator": "https://example.com",
                "license_note": "CC BY-SA 4.0",
            }
        ],
    }

    result = self_check(state)

    assert "don't have enough evidence" in result["final_answer"]
    assert result["diagnostics"]["unsupported_claims"] == ["Unrelated statement."]
