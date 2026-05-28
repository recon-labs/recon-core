from pathlib import Path

import pytest
import yaml

from recon_core.services import CompileService
from recon_core.services.results import ExitCategory


def test_compile_service_writes_compiled_artifacts_for_valid_project(tmp_path: Path) -> None:
    write_project(tmp_path)
    nulls = {
        "treat_as_null": {
            "values": ["", "NULL"],
            "regex": ["^\\s*$"],
        }
    }
    write_contract(tmp_path, tolerance_policy="finance", nulls=nulls)

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
    assert contract_artifact["artifact_version"] == 1
    assert contract_artifact["policies"]["tolerance_policy"] == "finance"
    assert contract_artifact["policies"]["nulls"] == nulls
    assert "normalization" not in contract_artifact["policies"]
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


def test_compile_service_ignores_indexed_non_contract_files_for_compiled_output(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    (tmp_path / "check_packs").mkdir()
    (tmp_path / "sample_policies").mkdir()
    (tmp_path / "tolerances").mkdir()
    (tmp_path / "schema_policies").mkdir()
    (tmp_path / "macros").mkdir()
    (tmp_path / "check_packs" / "company.yml").write_text(
        "this is not valid: [\n",
        encoding="utf-8",
    )
    (tmp_path / "sample_policies" / "stable.yml").write_text(
        "name: stable\n",
        encoding="utf-8",
    )
    (tmp_path / "tolerances" / "default.yml").write_text(
        "name: default\n",
        encoding="utf-8",
    )
    (tmp_path / "schema_policies" / "cdc.yml").write_text(
        "name: cdc\n",
        encoding="utf-8",
    )
    (tmp_path / "macros" / "normalize.sql").write_text(
        "lower(trim({{ column }}))\n",
        encoding="utf-8",
    )

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.diagnostics == ()
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()
    assert not (tmp_path / "target" / "compiled_contracts" / "company.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "company.yml").exists()
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_compile_service_removes_stale_artifacts_for_explicit_missing_resource_path(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    first_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()

    write_project(tmp_path, check_pack_paths=("custom_packs",))

    second_result = CompileService(start_path=tmp_path).execute()

    assert second_result.exit_category is ExitCategory.VALIDATION_ERROR
    assert second_result.message == "Compile failed during project parsing."
    assert [diagnostic.code for diagnostic in second_result.diagnostics] == [
        "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
    ]
    assert second_result.diagnostics[0].resource_type == "check_pack_path"
    assert second_result.diagnostics[0].path == str(tmp_path / "custom_packs")
    assert not (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").exists()


def test_compile_service_overwrites_previous_compiled_artifacts(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    first_result = CompileService(start_path=tmp_path).execute()
    second_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert second_result.exit_category is ExitCategory.SUCCESS


def test_compile_service_removes_stale_compiled_artifacts_for_removed_contract(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path, name="customer_revenue", file_name="customer_revenue.yml")
    write_contract(tmp_path, name="orders_revenue", file_name="orders_revenue.yml")

    first_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_contracts" / "orders_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "orders_revenue.yml").is_file()

    (tmp_path / "contracts" / "orders_revenue.yml").unlink()

    second_result = CompileService(start_path=tmp_path).execute()

    assert second_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert not (tmp_path / "target" / "compiled_contracts" / "orders_revenue.yml").exists()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()
    assert not (tmp_path / "target" / "compiled_checks" / "orders_revenue.yml").exists()


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


def test_compile_service_writes_no_artifacts_when_no_contracts_are_found(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_NO_CONTRACTS_FOUND"
    ]
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_removes_stale_compiled_artifacts_when_parse_fails(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    first_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()

    tmp_path.joinpath("contracts", "customer_revenue.yml").write_text(
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

    second_result = CompileService(start_path=tmp_path).execute()

    assert second_result.exit_category is ExitCategory.VALIDATION_ERROR
    assert second_result.message == "Compile failed during project parsing."
    assert [diagnostic.code for diagnostic in second_result.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]
    assert not (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").exists()


def test_compile_service_rejects_symlinked_compiled_artifact_directories(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    target_path = tmp_path / "target"
    external_path = tmp_path / "external"
    external_path.mkdir()
    external_artifact = external_path / "stale.yml"
    external_artifact.write_text("stale\n", encoding="utf-8")
    target_path.mkdir()
    try:
        (target_path / "compiled_contracts").symlink_to(
            external_path,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert "symlink" in result.diagnostics[0].message
    assert external_artifact.read_text(encoding="utf-8") == "stale\n"


def test_compile_service_rejects_symlinked_target_directory_before_cleanup(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    target_path = tmp_path / "target"
    external_path = tmp_path / "external_target"
    external_contracts = external_path / "compiled_contracts"
    external_checks = external_path / "compiled_checks"
    external_contracts.mkdir(parents=True)
    external_checks.mkdir(parents=True)
    external_contract_artifact = external_contracts / "customer_revenue.yml"
    external_check_artifact = external_checks / "customer_revenue.yml"
    external_contract_artifact.write_text("stale contract\n", encoding="utf-8")
    external_check_artifact.write_text("stale checks\n", encoding="utf-8")
    try:
        target_path.symlink_to(external_path, target_is_directory=True)
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert "symlink" in result.diagnostics[0].message
    assert external_contract_artifact.read_text(encoding="utf-8") == "stale contract\n"
    assert external_check_artifact.read_text(encoding="utf-8") == "stale checks\n"


def test_compile_service_writes_no_artifacts_for_invalid_stable_id_parts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, project_name="ecommerce-recon")
    write_contract(tmp_path)

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_INVALID_STABLE_ID_PART"
    ]
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_removes_stale_compiled_artifacts_for_fatal_compile_validation(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    first_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()

    tmp_path.joinpath("recon_project.yml").write_text(
        """
name: ecommerce-recon
version: 0.1.0
config-version: 1
contract-paths:
  - contracts
target-path: target
""".lstrip(),
        encoding="utf-8",
    )

    second_result = CompileService(start_path=tmp_path).execute()

    assert second_result.exit_category is ExitCategory.VALIDATION_ERROR
    assert second_result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in second_result.diagnostics] == [
        "RC_VALIDATE_INVALID_STABLE_ID_PART"
    ]
    assert not (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").exists()


def test_compile_service_writes_no_artifacts_for_duplicate_contract_names(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    tmp_path.joinpath("contracts", "duplicate.yml").write_text(
        tmp_path.joinpath("contracts", "customer_revenue.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_PARSE_DUPLICATE_CONTRACT"]
    assert result.diagnostics[0].path == "contracts/duplicate.yml"
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_writes_no_artifacts_for_case_colliding_artifact_names(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path, name="Sales", file_name="sales_upper.yml")
    write_contract(tmp_path, name="sales", file_name="sales_lower.yml")

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_COMPILED_ARTIFACT_FILENAME_COLLISION"
    ]
    assert result.diagnostics[0].path in {
        "contracts/sales_lower.yml",
        "contracts/sales_upper.yml",
    }
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_returns_validation_error_for_non_string_check_mapping_key(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    tmp_path.joinpath("contracts", "customer_revenue.yml").write_text(
        """
version: 1
name: customer_revenue
source:
  connection: legacy
  relation: qa.customer_source
target:
  connection: warehouse
  relation: qa.customer_target
grain:
  keys:
    - customer_id
checks:
  use:
    - recon_core.basic_equivalence
  1: true
""".lstrip(),
        encoding="utf-8",
    )

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_PARSE_INVALID_CONTRACT"]
    assert "string keys" in result.diagnostics[0].message
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


def write_project(
    project_root: Path,
    *,
    project_name: str = "ecommerce_recon",
    check_pack_paths: tuple[str, ...] | None = None,
) -> None:
    check_pack_paths_yaml = _path_list_yaml("check-pack-paths", check_pack_paths)
    project_root.joinpath("contracts").mkdir(exist_ok=True)
    project_root.joinpath("recon_project.yml").write_text(
        f"""
name: {project_name}
version: 0.1.0
config-version: 1
contract-paths:
  - contracts
{check_pack_paths_yaml}
target-path: target
""".lstrip(),
        encoding="utf-8",
    )


def _path_list_yaml(field_name: str, paths: tuple[str, ...] | None) -> str:
    if paths is None:
        return ""
    path_items = "\n".join(f"  - {path}" for path in paths)
    return f"{field_name}:\n{path_items}"


def write_contract(
    project_root: Path,
    *,
    name: str = "customer_revenue",
    file_name: str = "customer_revenue.yml",
    include_grain: bool = True,
    tolerance_policy: str | None = None,
    nulls: dict[str, object] | None = None,
) -> None:
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
    tolerance_policy_yaml = (
        yaml.safe_dump({"tolerance_policy": tolerance_policy}, sort_keys=False)
        if tolerance_policy is not None
        else ""
    )
    nulls_yaml = (
        yaml.safe_dump({"nulls": nulls}, sort_keys=False) if nulls is not None else ""
    )
    project_root.joinpath("contracts", file_name).write_text(
        f"""
version: 1
name: {name}
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
{tolerance_policy_yaml}{nulls_yaml}
""".lstrip(),
        encoding="utf-8",
    )
