from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ci_gates_duckdb_semantics() -> None:
    workflow = (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert 'python -m pip install -e ".[dev,duckdb]"' in workflow
    assert 'RECON_REQUIRE_DUCKDB_TESTS: "1"' in workflow
    assert "pytest tests/adapters/test_duckdb_sql_renderer.py" in workflow
    assert "tests/services/test_run_service.py" in workflow
    assert "tests/cli/test_main.py" in workflow
