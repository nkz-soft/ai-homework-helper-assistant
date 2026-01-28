from packages.orchestrator.graph.nodes.normalize import normalize


def test_normalize_builds_evidence_from_sources() -> None:
    state = {
        "retrieved_items": [
            {
                "source": "stackoverflow",
                "tool": "search_questions",
                "query": "python list",
                "result": {
                    "items": [
                        {
                            "question_id": "123",
                            "title": "How to build a list in Python?",
                            "url": "https://stackoverflow.com/q/123",
                            "excerpt": "Use list literals to build lists.",
                            "score": 10,
                        }
                    ]
                },
            },
            {
                "source": "wikipedia",
                "tool": "search",
                "query": "photosynthesis",
                "result": {
                    "items": [
                        {
                            "page_id": "42",
                            "title": "Photosynthesis",
                            "url": "https://en.wikipedia.org/wiki/Photosynthesis",
                            "excerpt": "Photosynthesis converts light energy into chemical energy.",
                        }
                    ]
                },
            },
            {
                "source": "textbooks",
                "tool": "textbooks_search",
                "query": "derivative",
                "result": {
                    "items": [
                        {
                            "chunk_id": "abc",
                            "title": "Derivative Basics",
                            "content": "A derivative measures the rate of change.",
                            "license": "CC BY 4.0",
                        }
                    ]
                },
            },
        ]
    }

    result = normalize(state)
    evidence = result["evidence"]

    assert len(evidence) == 3
    assert {item["source"] for item in evidence} == {
        "stackoverflow",
        "wikipedia",
        "textbooks",
    }
    stack_item = next(item for item in evidence if item["source"] == "stackoverflow")
    assert stack_item["locator"] == "https://stackoverflow.com/q/123"
    assert stack_item["license_note"] == "CC BY-SA 4.0"
    assert stack_item["support"]


def test_normalize_skips_errors_and_unlicensed_textbooks() -> None:
    state = {
        "retrieved_items": [
            {
                "source": "textbooks",
                "tool": "textbooks_search",
                "query": "calculus",
                "result": {
                    "items": [
                        {
                            "chunk_id": "no-license",
                            "title": "Missing License",
                            "content": "Do not include without license.",
                        }
                    ]
                },
            },
            {
                "source": "wikipedia",
                "tool": "search",
                "query": "math",
                "result": {},
                "error": "timeout",
            },
        ]
    }

    result = normalize(state)
    assert result["evidence"] == []


def test_normalize_truncates_excerpt() -> None:
    long_excerpt = "A" * 400
    state = {
        "retrieved_items": [
            {
                "source": "wikipedia",
                "tool": "search",
                "query": "long",
                "result": {
                    "items": [
                        {
                            "page_id": "99",
                            "title": "Long Excerpt",
                            "url": "https://example.com",
                            "excerpt": long_excerpt,
                        }
                    ]
                },
            }
        ]
    }

    result = normalize(state)
    evidence = result["evidence"]

    assert len(evidence) == 1
    assert len(evidence[0]["support"]) < len(long_excerpt)
