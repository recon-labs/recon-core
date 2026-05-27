import json
from pathlib import Path

import pytest

from recon_core.services import ParseService
from recon_core.services.results import ExitCategory


def write_project(
    project_root: Path,
    *,
    contract_paths: tuple[str, ...] = ("contracts",),
    target_path: str = "target",
    include_contract_dir: bool = True,
) -> None:
    contract_paths_yaml = "\n".join(f"  - {contract_path}" for contract_path in contract_paths)
    project_root.joinpath("recon_project.yml").write_text(
        f"""
name: ecommerce_recon
version: 0.1.0
config-version: 1
contract-paths:
{contract_paths_yaml}
target-path: {target_path}
""".lstrip(),
        encoding="utf-8",
    )
    if include_contract_dir:
        for contract_path in contract_paths:
            (project_root / contract_path).mkdir(parents=True, exist_ok=True)


def write_contract(
    project_root: Path,
    relative_path: str = "contracts/customer_revenue.yml",
    *,
    name: str = "customer_revenue",
) -> Path:
    contract_path = project_root / relative_path
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        f"""
version: 1
name: {name}
source:
  connection: legacy
  relation: qa.customer_source
target:
  connection: warehouse
  relation: qa.customer_target
checks:
  use:
    - recon_core.basic_equivalence
tags:
  - finance
""".lstrip(),
        encoding="utf-8",
    )
    return contract_path


def read_manifest(project_root: Path, target_path: str = "target") -> dict[str, object]:
    manifest_path = project_root / target_path / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def test_parse_service_writes_manifest_for_valid_project(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    result = ParseService(start_path=tmp_path).execute()

    manifest_path = tmp_path / "target" / "manifest.json"
    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == f"Parsed 1 contract. Wrote manifest to {manifest_path}."
    assert result.diagnostics == ()

    manifest = read_manifest(tmp_path)
    assert manifest["artifact_type"] == "manifest"
    assert manifest["project"] == {
        "name": "ecommerce_recon",
        "config_version": 1,
        "version": "0.1.0",
    }
    assert list(manifest["files"]) == ["contracts/customer_revenue.yml"]
    assert list(manifest["contracts"]) == ["customer_revenue"]
    assert manifest["diagnostics"] == []


def test_parse_service_manifest_includes_indexed_non_contract_files(
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

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.diagnostics == ()

    manifest = read_manifest(tmp_path)
    assert {path: file_info["resource_type"] for path, file_info in manifest["files"].items()} == {
        "check_packs/company.yml": "check_pack",
        "contracts/customer_revenue.yml": "contract",
        "macros/normalize.sql": "macro_file",
        "sample_policies/stable.yml": "sample_policy",
        "schema_policies/cdc.yml": "schema_policy",
        "tolerances/default.yml": "tolerance_policy",
    }
    assert list(manifest["contracts"]) == ["customer_revenue"]
    assert manifest["diagnostics"] == []


def test_parse_service_writes_manifest_with_diagnostics_for_invalid_contract(
    tmp_path: Path,
) -> None:
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

    result = ParseService(start_path=tmp_path).execute()

    manifest_path = tmp_path / "target" / "manifest.json"
    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == (
        f"Parse completed with 1 diagnostic. Wrote manifest to {manifest_path}."
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]

    manifest = read_manifest(tmp_path)
    assert manifest["contracts"] == {}
    assert [diagnostic["code"] for diagnostic in manifest["diagnostics"]] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]


def test_parse_service_preserves_valid_multi_contract_entries_with_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    tmp_path.joinpath("contracts", "grouped.yml").write_text(
        """
version: 1
contracts:
  - name: customer_revenue
    source:
      connection: legacy
      relation: qa.customer_source
    target:
      connection: warehouse
      relation: qa.customer_target
    checks:
      use:
        - recon_core.basic_equivalence
  - name: broken_contract
    source:
      connection: legacy
      relation: qa.broken_source
    target:
      connection: warehouse
      relation: qa.broken_target
""".lstrip(),
        encoding="utf-8",
    )

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]

    manifest = read_manifest(tmp_path)
    assert list(manifest["contracts"]) == ["customer_revenue"]
    assert manifest["diagnostics"][0]["code"] == "RC_PARSE_MISSING_REQUIRED_FIELD"


def test_parse_service_writes_manifest_for_multi_contract_file_missing_shared_version(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    tmp_path.joinpath("contracts", "grouped.yml").write_text(
        """
contracts:
  - name: customer_revenue
    source:
      connection: legacy
      relation: qa.customer_source
    target:
      connection: warehouse
      relation: qa.customer_target
    checks:
      use:
        - recon_core.basic_equivalence
""".lstrip(),
        encoding="utf-8",
    )

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]

    manifest = read_manifest(tmp_path)
    assert manifest["contracts"] == {}
    assert manifest["diagnostics"][0]["message"] == "Missing required contract field: version"


def test_parse_service_writes_manifest_with_diagnostics_for_invalid_yaml(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    (tmp_path / "contracts" / "broken.yml").write_text("name: [\n", encoding="utf-8")

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_PARSE_INVALID_YAML"]
    assert result.diagnostics[0].path == "contracts/broken.yml"

    manifest = read_manifest(tmp_path)
    assert list(manifest["files"]) == ["contracts/broken.yml"]
    assert manifest["contracts"] == {}
    assert manifest["diagnostics"][0]["code"] == "RC_PARSE_INVALID_YAML"
    assert manifest["diagnostics"][0]["path"] == "contracts/broken.yml"


def test_parse_service_writes_manifest_with_diagnostics_for_non_utf8_yaml(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    (tmp_path / "contracts" / "broken.yml").write_bytes(b"\xff\xfe\xfa")

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_PARSE_FILE_READ_ERROR"]
    assert result.diagnostics[0].path == "contracts/broken.yml"

    manifest = read_manifest(tmp_path)
    assert list(manifest["files"]) == ["contracts/broken.yml"]
    assert manifest["contracts"] == {}
    assert manifest["diagnostics"][0]["code"] == "RC_PARSE_FILE_READ_ERROR"
    assert manifest["diagnostics"][0]["path"] == "contracts/broken.yml"


def test_parse_service_writes_manifest_with_diagnostics_for_missing_contract_path(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, contract_paths=("missing_contracts",), include_contract_dir=False)

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
    ]

    manifest = read_manifest(tmp_path)
    assert manifest["files"] == {}
    assert manifest["contracts"] == {}
    assert manifest["diagnostics"][0]["code"] == "RC_PARSE_RESOURCE_PATH_NOT_FOUND"


def test_parse_service_writes_no_manifest_when_project_root_is_missing(
    tmp_path: Path,
) -> None:
    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_CONFIG_PROJECT_NOT_FOUND"]
    assert not (tmp_path / "target" / "manifest.json").exists()


def test_parse_service_writes_no_manifest_when_project_config_is_invalid(
    tmp_path: Path,
) -> None:
    tmp_path.joinpath("recon_project.yml").write_text("profile: dev\n", encoding="utf-8")

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_INVALID_PROJECT_CONFIG"
    ]
    assert not (tmp_path / "target" / "manifest.json").exists()


def test_parse_service_writes_manifest_with_diagnostics_for_duplicate_contracts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path, "contracts/customer_revenue.yml", name="customer_revenue")
    write_contract(tmp_path, "contracts/duplicate_customer.yml", name="customer_revenue")

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_PARSE_DUPLICATE_CONTRACT"]

    manifest = read_manifest(tmp_path)
    assert list(manifest["contracts"]) == ["customer_revenue"]
    assert manifest["diagnostics"][0]["code"] == "RC_PARSE_DUPLICATE_CONTRACT"


def test_parse_service_returns_runtime_error_when_manifest_cannot_be_written(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    tmp_path.joinpath("target").write_text("not a directory\n", encoding="utf-8")

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Parse completed but manifest could not be written."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MANIFEST_WRITE_FAILED"
    ]
    assert result.diagnostics[0].path == "target"
    assert "Unable to write manifest" in result.diagnostics[0].message


def test_parse_service_rejects_symlinked_target_directory(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    target_path = tmp_path / "target"
    external_path = tmp_path / "external_target"
    external_path.mkdir()
    try:
        target_path.symlink_to(external_path, target_is_directory=True)
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MANIFEST_WRITE_FAILED"
    ]
    assert "symlink" in result.diagnostics[0].message
    assert not (external_path / "manifest.json").exists()


def test_parse_service_rejects_exact_manifest_symlink(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    target_path = tmp_path / "target"
    external_path = tmp_path / "external_manifest.json"
    target_path.mkdir()
    external_path.write_text("external\n", encoding="utf-8")
    try:
        (target_path / "manifest.json").symlink_to(external_path)
    except OSError:
        pytest.skip("Filesystem does not support file symlinks.")

    result = ParseService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MANIFEST_WRITE_FAILED"
    ]
    assert "symlink" in result.diagnostics[0].message
    assert external_path.read_text(encoding="utf-8") == "external\n"
