from pathlib import Path

from raphael_agent.localization.code_evidence import (
    build_dependency_graph, coverage_relevance, load_coverage,
)


def test_coverage_and_dependency_adapters(tmp_path: Path):
    (tmp_path / "coverage.json").write_text(
        '{"files":{"app.py":{"executed_lines":[10,11]}}}', encoding="utf-8"
    )
    (tmp_path / "app.py").write_text("import helpers\n", encoding="utf-8")
    (tmp_path / "helpers.py").write_text("def f(): pass\n", encoding="utf-8")
    coverage = load_coverage(tmp_path)
    assert coverage_relevance(coverage, "app.py", 10) == 1.0
    graph = build_dependency_graph(tmp_path)
    assert "helpers" in graph["app.py"]
