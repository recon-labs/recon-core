from pathlib import Path

from recon_core.config import PathOrigin
from recon_core.diagnostics import DiagnosticSeverity
from recon_core.parser import (
    LOCAL_RESOURCE_KIND_DEFINITIONS,
    ResourceFile,
    ResourceType,
    discover_contract_files,
    discover_resource_files,
)
from recon_core.project import ResolvedResourcePath


def write_file(path: Path, content: str = "name: customer_revenue\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_discover_contract_files_returns_sorted_yaml_files_with_metadata(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "contracts" / "orders.yml")
    write_file(tmp_path / "contracts" / "customer.yaml")
    write_file(tmp_path / "contracts" / "nested" / "line_items.yml")
    write_file(tmp_path / "contracts" / "README.md", "ignore me\n")

    result = discover_contract_files(tmp_path, (tmp_path / "contracts",))

    assert result.succeeded
    assert result.diagnostics == ()
    assert [resource.relative_path for resource in result.files] == [
        "contracts/customer.yaml",
        "contracts/nested/line_items.yml",
        "contracts/orders.yml",
    ]
    assert {resource.resource_type for resource in result.files} == {ResourceType.CONTRACT}
    assert all(resource.checksum for resource in result.files)


def test_discover_contract_files_allows_empty_existing_contract_directory(
    tmp_path: Path,
) -> None:
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()

    result = discover_contract_files(tmp_path, (contract_dir,))

    assert result.succeeded
    assert result.files == ()
    assert result.diagnostics == ()


def test_discover_contract_files_reports_missing_contract_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "contracts"

    result = discover_contract_files(tmp_path, (missing_path,))

    assert not result.succeeded
    assert result.files == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "contract_path"
    assert diagnostic.path == str(missing_path)
    assert diagnostic.hint == "Create the directory or update `contract-paths`."


def test_discover_contract_files_reports_file_configured_as_contract_path(
    tmp_path: Path,
) -> None:
    contract_file = tmp_path / "contracts.yml"
    contract_file.write_text("name: customer_revenue\n", encoding="utf-8")

    result = discover_contract_files(tmp_path, (contract_file,))

    assert not result.succeeded
    assert result.files == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
    assert diagnostic.path == str(contract_file)
    assert "must be a directory" in diagnostic.message


def test_discover_contract_files_deduplicates_overlapping_contract_paths(
    tmp_path: Path,
) -> None:
    contract_file = tmp_path / "contracts" / "nested" / "customer_revenue.yml"
    write_file(contract_file)

    result = discover_contract_files(
        tmp_path,
        (
            tmp_path / "contracts",
            tmp_path / "contracts" / "nested",
        ),
    )

    assert result.succeeded
    assert [resource.relative_path for resource in result.files] == [
        "contracts/nested/customer_revenue.yml"
    ]


def test_discover_resource_files_indexes_catalog_resources_deterministically(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "contracts" / "orders.yml")
    write_file(tmp_path / "contracts" / "customer.yaml")
    write_file(tmp_path / "check_packs" / "company.yml")
    write_file(tmp_path / "sample_policies" / "stable.yml")
    write_file(tmp_path / "tolerances" / "default.yaml")
    write_file(tmp_path / "schema_policies" / "cdc.yml")
    write_file(tmp_path / "macros" / "normalize.sql", "lower(trim({{ column }}))\n")
    write_file(tmp_path / "macros" / "ignored.yml")
    write_file(tmp_path / "check_packs" / "ignored.txt")

    result = discover_resource_files(
        tmp_path,
        (
            resolved_path("contract-paths", tmp_path / "contracts", PathOrigin.AUTHORED),
            resolved_path("check-pack-paths", tmp_path / "check_packs"),
            resolved_path("sample-policy-paths", tmp_path / "sample_policies"),
            resolved_path("tolerance-policy-paths", tmp_path / "tolerances"),
            resolved_path("schema-policy-paths", tmp_path / "schema_policies"),
            resolved_path("macro-paths", tmp_path / "macros"),
        ),
    )

    assert result.succeeded
    assert result.diagnostics == ()
    assert [(resource.relative_path, resource.resource_type) for resource in result.files] == [
        ("check_packs/company.yml", ResourceType.CHECK_PACK),
        ("contracts/customer.yaml", ResourceType.CONTRACT),
        ("contracts/orders.yml", ResourceType.CONTRACT),
        ("macros/normalize.sql", ResourceType.MACRO_FILE),
        ("sample_policies/stable.yml", ResourceType.SAMPLE_POLICY),
        ("schema_policies/cdc.yml", ResourceType.SCHEMA_POLICY),
        ("tolerances/default.yaml", ResourceType.TOLERANCE_POLICY),
    ]
    assert all(resource.checksum for resource in result.files)


def test_discover_resource_files_skips_missing_default_optional_paths(
    tmp_path: Path,
) -> None:
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()

    result = discover_resource_files(
        tmp_path,
        (
            resolved_path("contract-paths", contract_dir, PathOrigin.DEFAULTED),
            resolved_path("macro-paths", tmp_path / "macros", PathOrigin.DEFAULTED),
        ),
    )

    assert result.succeeded
    assert result.files == ()
    assert result.diagnostics == ()


def test_discover_resource_files_reports_explicit_missing_optional_path(
    tmp_path: Path,
) -> None:
    result = discover_resource_files(
        tmp_path,
        (
            resolved_path(
                "check-pack-paths",
                tmp_path / "custom_packs",
                PathOrigin.AUTHORED,
            ),
        ),
    )

    assert not result.succeeded
    assert result.files == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "check_pack_path"
    assert diagnostic.path == str(tmp_path / "custom_packs")
    assert diagnostic.hint == "Create the directory or update `check-pack-paths`."


def test_discover_resource_files_reports_explicit_file_configured_as_optional_path(
    tmp_path: Path,
) -> None:
    macro_file = tmp_path / "macro.sql"
    macro_file.write_text("select 1\n", encoding="utf-8")

    result = discover_resource_files(
        tmp_path,
        (resolved_path("macro-paths", macro_file, PathOrigin.AUTHORED),),
    )

    assert not result.succeeded
    assert result.files == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
    assert diagnostic.resource_type == "macro_file_path"
    assert diagnostic.path == str(macro_file)
    assert "must be a directory" in diagnostic.message


def test_discover_resource_files_deduplicates_overlapping_resource_paths(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "check_packs" / "nested" / "company.yml")

    result = discover_resource_files(
        tmp_path,
        (
            resolved_path("check-pack-paths", tmp_path / "check_packs"),
            resolved_path("check-pack-paths", tmp_path / "check_packs" / "nested"),
        ),
    )

    assert result.succeeded
    assert [resource.relative_path for resource in result.files] == [
        "check_packs/nested/company.yml"
    ]


def test_discover_resource_files_uses_case_insensitive_suffix_matching(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "contracts" / "CUSTOMER.YML")
    write_file(tmp_path / "macros" / "NORMALIZE.SQL", "lower(trim({{ column }}))\n")

    result = discover_resource_files(
        tmp_path,
        (
            resolved_path("contract-paths", tmp_path / "contracts"),
            resolved_path("macro-paths", tmp_path / "macros"),
        ),
    )

    assert result.succeeded
    assert [(resource.relative_path, resource.resource_type) for resource in result.files] == [
        ("contracts/CUSTOMER.YML", ResourceType.CONTRACT),
        ("macros/NORMALIZE.SQL", ResourceType.MACRO_FILE),
    ]


def test_discover_resource_files_reports_unknown_catalog_path_field(
    tmp_path: Path,
) -> None:
    result = discover_resource_files(
        tmp_path,
        (resolved_path("unknown-paths", tmp_path / "unknown"),),
    )

    assert result.files == ()
    assert result.diagnostics == ()


def test_local_resource_catalog_locks_milestone_4_6_resource_kinds() -> None:
    definitions = {
        definition.resource_type: definition for definition in LOCAL_RESOURCE_KIND_DEFINITIONS
    }

    assert set(definitions) == {
        ResourceType.CONTRACT,
        ResourceType.CHECK_PACK,
        ResourceType.SAMPLE_POLICY,
        ResourceType.TOLERANCE_POLICY,
        ResourceType.SCHEMA_POLICY,
        ResourceType.MACRO_FILE,
    }
    assert definitions[ResourceType.CONTRACT].path_field == "contract-paths"
    assert definitions[ResourceType.CONTRACT].suffixes == frozenset({".yaml", ".yml"})
    assert definitions[ResourceType.CONTRACT].required_by_default is True
    assert definitions[ResourceType.CHECK_PACK].path_field == "check-pack-paths"
    assert definitions[ResourceType.CHECK_PACK].suffixes == frozenset({".yaml", ".yml"})
    assert definitions[ResourceType.SAMPLE_POLICY].path_field == "sample-policy-paths"
    assert definitions[ResourceType.TOLERANCE_POLICY].path_field == "tolerance-policy-paths"
    assert definitions[ResourceType.SCHEMA_POLICY].path_field == "schema-policy-paths"
    assert definitions[ResourceType.MACRO_FILE].path_field == "macro-paths"
    assert definitions[ResourceType.MACRO_FILE].suffixes == frozenset({".sql"})

    optional_definitions = [
        definition
        for definition in definitions.values()
        if definition.resource_type is not ResourceType.CONTRACT
    ]
    assert optional_definitions
    assert all(not definition.required_by_default for definition in optional_definitions)
    assert all(definition.explicit_missing_is_error for definition in definitions.values())
    assert definitions[ResourceType.CONTRACT].handling == "parse"
    assert all(definition.handling == "index" for definition in optional_definitions)


def test_resource_file_serializes_to_dict(tmp_path: Path) -> None:
    path = tmp_path / "contracts" / "customer_revenue.yml"
    resource = ResourceFile(
        path=path,
        relative_path="contracts/customer_revenue.yml",
        resource_type=ResourceType.CONTRACT,
        checksum="abc123",
    )

    assert resource.to_dict() == {
        "path": "contracts/customer_revenue.yml",
        "resource_type": "contract",
        "checksum": "abc123",
    }


def resolved_path(
    field_name: str,
    path: Path,
    origin: PathOrigin = PathOrigin.AUTHORED,
) -> ResolvedResourcePath:
    return ResolvedResourcePath(path=path, origin=origin, field_name=field_name)
