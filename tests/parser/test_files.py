from pathlib import Path

from recon_core.diagnostics import DiagnosticSeverity
from recon_core.parser import (
    LOCAL_RESOURCE_KIND_DEFINITIONS,
    ResourceFile,
    ResourceType,
    discover_contract_files,
)


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
