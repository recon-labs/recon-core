from pathlib import Path

from recon_core.diagnostics import DiagnosticSeverity
from recon_core.parser import ResourceFile, ResourceType, discover_contract_files


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
