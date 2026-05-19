from pathlib import Path

from recon_core.config import ProjectConfig, load_project_config
from recon_core.diagnostics import DiagnosticSeverity


def write_project_config(tmp_path: Path, content: str) -> Path:
    project_file = tmp_path / "recon_project.yml"
    project_file.write_text(content, encoding="utf-8")
    return project_file


def test_load_project_config_applies_documented_defaults(tmp_path: Path) -> None:
    project_file = write_project_config(tmp_path, "name: ecommerce_recon\n")

    result = load_project_config(project_file)

    assert result.succeeded
    assert result.diagnostics == ()
    assert result.config == ProjectConfig(
        name="ecommerce_recon",
        version=None,
        config_version=1,
        profile=None,
        contract_paths=("contracts",),
        sample_policy_paths=("sample_policies",),
        tolerance_policy_paths=("tolerances",),
        schema_policy_paths=("schema_policies",),
        check_pack_paths=("check_packs",),
        macro_paths=("macros",),
        target_path="target",
        report_path="reports",
        state_path="state",
    )


def test_load_project_config_maps_hyphenated_yaml_keys_to_snake_case_fields(
    tmp_path: Path,
) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: finance_recon
version: 0.2.0
config-version: 1
profile: dev
contract-paths:
  - recon_contracts
sample-policy-paths:
  - policies/samples
tolerance-policy-paths:
  - policies/tolerances
schema-policy-paths:
  - policies/schemas
check-pack-paths:
  - packs
macro-paths:
  - macros
target-path: build/target
report-path: build/reports
state-path: build/state
""".lstrip(),
    )

    result = load_project_config(project_file)

    assert result.succeeded
    assert result.config is not None
    assert result.config.name == "finance_recon"
    assert result.config.version == "0.2.0"
    assert result.config.config_version == 1
    assert result.config.profile == "dev"
    assert result.config.contract_paths == ("recon_contracts",)
    assert result.config.sample_policy_paths == ("policies/samples",)
    assert result.config.tolerance_policy_paths == ("policies/tolerances",)
    assert result.config.schema_policy_paths == ("policies/schemas",)
    assert result.config.check_pack_paths == ("packs",)
    assert result.config.macro_paths == ("macros",)
    assert result.config.target_path == "build/target"
    assert result.config.report_path == "build/reports"
    assert result.config.state_path == "build/state"


def test_load_project_config_reports_invalid_yaml(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path, "name: ecommerce_recon\ncontract-paths: [contracts\n"
    )

    result = load_project_config(project_file)

    assert not result.succeeded
    assert result.config is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_YAML"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == str(project_file)
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    assert diagnostic.hint is not None


def test_load_project_config_reports_duplicate_yaml_keys(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: ecommerce_recon
name: finance_recon
""".lstrip(),
    )

    result = load_project_config(project_file)

    assert not result.succeeded
    assert result.config is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_YAML"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == str(project_file)
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    assert "Duplicate YAML key" in diagnostic.message


def test_load_project_config_reports_non_mapping_yaml(tmp_path: Path) -> None:
    project_file = write_project_config(tmp_path, "- ecommerce_recon\n")

    result = load_project_config(project_file)

    diagnostic = result.diagnostics[0]
    assert not result.succeeded
    assert result.config is None
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.path == str(project_file)
    assert "top-level mapping" in diagnostic.message


def test_load_project_config_reports_unreadable_config_path(tmp_path: Path) -> None:
    result = load_project_config(tmp_path)

    assert not result.succeeded
    assert result.config is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == str(tmp_path)
    assert "Could not read project config file" in diagnostic.message
    assert diagnostic.hint is not None


def test_load_project_config_reports_missing_required_name(tmp_path: Path) -> None:
    project_file = write_project_config(tmp_path, "profile: dev\n")

    result = load_project_config(project_file)

    diagnostic = result.diagnostics[0]
    assert not result.succeeded
    assert result.config is None
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.path == str(project_file)
    assert "name" in diagnostic.message


def test_load_project_config_reports_wrong_field_type(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: ecommerce_recon
contract-paths: contracts
""".lstrip(),
    )

    result = load_project_config(project_file)

    diagnostic = result.diagnostics[0]
    assert not result.succeeded
    assert result.config is None
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.path == str(project_file)
    assert "contract-paths" in diagnostic.message
    assert diagnostic.hint is not None


def test_load_project_config_reports_unknown_field(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: ecommerce_recon
unexpected-setting: true
""".lstrip(),
    )

    result = load_project_config(project_file)

    diagnostic = result.diagnostics[0]
    assert not result.succeeded
    assert result.config is None
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.path == str(project_file)
    assert "unexpected-setting" in diagnostic.message
