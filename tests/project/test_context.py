from pathlib import Path

from recon_core.diagnostics import DiagnosticSeverity
from recon_core.project import load_project_context


def test_load_project_context_composes_config_paths_and_profile_candidates(
    tmp_path: Path,
) -> None:
    project_file = tmp_path / "recon_project.yml"
    project_file.write_text(
        """
name: ecommerce_recon
profile: dev
contract-paths:
  - contracts
target-path: build/target
report-path: build/reports
state-path: build/state
""".lstrip(),
        encoding="utf-8",
    )

    result = load_project_context(tmp_path)

    assert result.succeeded
    assert result.context is not None
    assert result.context.project_root == tmp_path
    assert result.context.project_file == project_file
    assert result.context.config.name == "ecommerce_recon"
    assert result.context.config.profile == "dev"
    assert result.context.paths.contract_paths == (tmp_path / "contracts",)
    assert result.context.paths.target_path == tmp_path / "build/target"
    assert result.context.paths.report_path == tmp_path / "build/reports"
    assert result.context.paths.state_path == tmp_path / "build/state"
    assert result.context.profile_paths == (
        tmp_path / "connections" / "profiles.yml.example",
        tmp_path / "connections" / "profiles.yml",
    )
    assert result.diagnostics == ()


def test_load_project_context_loads_from_nested_directory(tmp_path: Path) -> None:
    (tmp_path / "recon_project.yml").write_text("name: ecommerce_recon\n", encoding="utf-8")
    nested_dir = tmp_path / "contracts" / "nested"
    nested_dir.mkdir(parents=True)

    result = load_project_context(nested_dir)

    assert result.succeeded
    assert result.context is not None
    assert result.context.project_root == tmp_path
    assert result.context.config.name == "ecommerce_recon"
    assert result.context.paths.target_path == tmp_path / "target"


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


def test_load_project_context_propagates_project_config_diagnostics(tmp_path: Path) -> None:
    project_file = tmp_path / "recon_project.yml"
    project_file.write_text("profile: dev\n", encoding="utf-8")

    result = load_project_context(tmp_path)

    assert not result.succeeded
    assert result.context is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == str(project_file)
    assert "name" in diagnostic.message
