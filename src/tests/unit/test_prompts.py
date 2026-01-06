from packages.orchestrator.prompts import load_prompt, render_prompt, synthesis_headers


def test_load_prompt_reads_template() -> None:
    content = load_prompt("system")
    assert "homework coach" in content.lower()


def test_render_prompt_formats_values() -> None:
    rendered = render_prompt(
        "citation",
        {"index": "1", "title": "Example", "url": "https://example.com"},
    )
    assert "Example" in rendered
    assert "https://example.com" in rendered


def test_synthesis_headers_extracts_titles() -> None:
    headers = synthesis_headers()
    assert "## Explanation" in headers
    assert "## Sources" in headers
