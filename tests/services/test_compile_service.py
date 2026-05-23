from pathlib import Path

import yaml

from recon_core.services import CompileService
from recon_core.services.results import ExitCategory


def test_compile_service_writes_compiled_artifacts_for_valid_project(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    result = CompileService(start_path=tmp_path).execute()

    contract_path = tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    checks_path = tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == (
        f"Compiled 1 contract. Wrote artifacts to {contract_path.parent} and {checks_path.parent}."
    )
    assert result.diagnostics == ()

    contract_artifact = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    checks_artifact = yaml.safe_load(checks_path.read_text(encoding="utf-8"))

    assert contract_artifact["artifact_type"] == "compiled_contract"
    assert contract_artifact["contract"]["id"] == "contract.ecommerce_recon.customer_revenue"
    assert checks_artifact["artifact_type"] == "compiled_checks"
    assert [check["name"] for check in checks_artifact["checks"]] == [
        "row_count_diff",
        "missing_keys",
        "extra_keys",
        "null_source_keys",
        "null_target_keys",
        "duplicate_source_keys",
        "duplicate_target_keys",
        "total_revenue",
    ]
    assert checks_artifact["checks"][-1]["plan"]["operations"][-1] == {"type": "compare_aggregates"}


def test_compile_service_returns_validation_error_for_invalid_contract(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path, include_grain=False)

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == (
        "Compile completed with 1 diagnostic. Wrote compiled artifacts for 1 contract."
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS"
    ]

    checks_path = tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    checks_artifact = yaml.safe_load(checks_path.read_text(encoding="utf-8"))
    assert checks_artifact["checks"] == []
    assert checks_artifact["diagnostics"][0]["code"] == (
        "RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS"
    )


def test_compile_service_writes_no_artifacts_when_parse_fails(tmp_path: Path) -> None:
    write_project(tmp_path)
    contract_path = tmp_path / "contracts" / "customer_revenue.yml"
    contract_path.write_text(
        """
version: 1
name: customer_revenue
source:
  connection: legacy
  relation: qa.customer_source
target:
  connection: warehouse
  relation: qa.customer_target
""".lstrip(),
        encoding="utf-8",
    )

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed during project parsing."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_returns_runtime_error_when_artifacts_cannot_be_written(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    tmp_path.joinpath("target").write_text("not a directory\n", encoding="utf-8")

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compile completed but artifacts could not be written."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert result.diagnostics[0].path == "target"


def test_compile_service_writes_no_artifacts_when_project_root_is_missing(
    tmp_path: Path,
) -> None:
    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_CONFIG_PROJECT_NOT_FOUND"]
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def write_project(project_root: Path) -> None:
    project_root.joinpath("contracts").mkdir()
    project_root.joinpath("recon_project.yml").write_text(
        """
name: ecommerce_recon
version: 0.1.0
config-version: 1
contract-paths:
  - contracts
target-path: target
""".lstrip(),
        encoding="utf-8",
    )


def write_contract(project_root: Path, *, include_grain: bool = True) -> None:
    grain_yaml = (
        """
grain:
  keys:
    - customer_id
    - month
"""
        if include_grain
        else ""
    )
    project_root.joinpath("contracts", "customer_revenue.yml").write_text(
        f"""
version: 1
name: customer_revenue
source:
  connection: legacy
  relation: qa.customer_source
target:
  connection: warehouse
  relation: qa.customer_target
{grain_yaml}metrics:
  - name: total_revenue
    type: sum
    column: revenue
checks:
  use:
    - recon_core.basic_equivalence
sampling:
  default_policy: full
""".lstrip(),
        encoding="utf-8",
    )
