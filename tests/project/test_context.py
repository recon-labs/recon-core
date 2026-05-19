from pathlib import Path

from recon_core.diagnostics import DiagnosticSeverity
from recon_core.project import load_project_context


def test_load_project_context_returns_root_and_project_file(tmp_path: Path) -> None:
    project_file = tmp_path / "recon_project.yml"
    project_file.write_text("name: ecommerce_recon\n", encoding="utf-8")

    result = load_project_context(tmp_path)

    assert result.succeeded
    assert result.context is not None
    assert result.context.project_root == tmp_path
    assert result.context.project_file == project_file
    assert result.diagnostics == ()


def test_load_project_context_reports_missing_project(tmp_path: Path) -> None:
    result = load_project_context(tmp_path)

    assert not result.succeeded
    assert result.context is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_CONFIG_PROJECT_NOT_FOUND"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "project"
    assert diagnostic.path == str(tmp_path)
    assert "recon_project.yml" in diagnostic.message
    assert diagnostic.hint is not None
    assert "recon init <project_name>" in diagnostic.hint
