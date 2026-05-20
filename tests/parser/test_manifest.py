from pathlib import Path

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser import (
    AuthoredContract,
    AuthoredEndpoint,
    ManifestProject,
    ResourceFile,
    ResourceType,
    build_manifest,
)
from recon_core.parser.manifest import DUPLICATE_CONTRACT
from recon_core.parser.models import SourceLocation


def make_resource_file(
    tmp_path: Path, relative_path: str = "contracts/customer.yml", checksum: str = "abc123"
) -> ResourceFile:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("name: placeholder\n", encoding="utf-8")
    return ResourceFile(
        path=path,
        relative_path=relative_path,
        resource_type=ResourceType.CONTRACT,
        checksum=checksum,
    )


def make_contract(
    name: str = "customer_revenue",
    path: str = "contracts/customer.yml",
    source_relation: str = "qa.customer_source",
    target_relation: str = "qa.customer_target",
    tags: tuple[str, ...] = ("finance",),
) -> AuthoredContract:
    return AuthoredContract(
        name=name,
        version=1,
        source=AuthoredEndpoint(connection="legacy", relation=source_relation),
        target=AuthoredEndpoint(connection="warehouse", relation=target_relation),
        checks={"use": ["recon_core.basic_equivalence"]},
        source_location=SourceLocation(path=path),
        tags=tags,
    )


def test_build_manifest_serializes_project_files_contracts_and_diagnostics(
    tmp_path: Path,
) -> None:
    first_file = make_resource_file(tmp_path, "contracts/orders.yml", "orders-checksum")
    second_file = make_resource_file(tmp_path, "contracts/customer.yml", "customer-checksum")
    diagnostic = Diagnostic(
        code="RC_PARSE_INVALID_YAML",
        severity=DiagnosticSeverity.ERROR,
        message="Invalid YAML in contract resource.",
        resource_type="contract",
        path="contracts/broken.yml",
    )

    manifest = build_manifest(
        project=ManifestProject(name="ecommerce_recon", config_version=1, version="0.1.0"),
        files=(first_file, second_file),
        contracts=(
            make_contract(name="orders", path="contracts/orders.yml", tags=("orders",)),
            make_contract(),
        ),
        diagnostics=(diagnostic,),
        recon_version="0.0.test",
        generated_at="2026-05-20T12:00:00Z",
    )

    assert not manifest.succeeded
    assert manifest.to_dict() == {
        "artifact_type": "manifest",
        "artifact_version": 1,
        "recon_version": "0.0.test",
        "generated_at": "2026-05-20T12:00:00Z",
        "project": {
            "name": "ecommerce_recon",
            "config_version": 1,
            "version": "0.1.0",
        },
        "files": {
            "contracts/customer.yml": {
                "path": "contracts/customer.yml",
                "resource_type": "contract",
                "checksum": "customer-checksum",
            },
            "contracts/orders.yml": {
                "path": "contracts/orders.yml",
                "resource_type": "contract",
                "checksum": "orders-checksum",
            },
        },
        "contracts": {
            "customer_revenue": {
                "name": "customer_revenue",
                "version": 1,
                "path": "contracts/customer.yml",
                "tags": ["finance"],
                "source": {
                    "connection": "legacy",
                    "relation": "qa.customer_source",
                    "query": None,
                },
                "target": {
                    "connection": "warehouse",
                    "relation": "qa.customer_target",
                    "query": None,
                },
            },
            "orders": {
                "name": "orders",
                "version": 1,
                "path": "contracts/orders.yml",
                "tags": ["orders"],
                "source": {
                    "connection": "legacy",
                    "relation": "qa.customer_source",
                    "query": None,
                },
                "target": {
                    "connection": "warehouse",
                    "relation": "qa.customer_target",
                    "query": None,
                },
            },
        },
        "diagnostics": [diagnostic.to_dict()],
    }


def test_build_manifest_detects_duplicate_contract_names(tmp_path: Path) -> None:
    manifest = build_manifest(
        project=ManifestProject(name="ecommerce_recon", config_version=1),
        files=(
            make_resource_file(tmp_path, "contracts/customer.yml"),
            make_resource_file(tmp_path, "contracts/duplicate.yml"),
        ),
        contracts=(
            make_contract(path="contracts/customer.yml", source_relation="qa.first_source"),
            make_contract(path="contracts/duplicate.yml", source_relation="qa.second_source"),
        ),
        recon_version="0.0.test",
        generated_at="2026-05-20T12:00:00Z",
    )

    assert not manifest.succeeded
    assert list(manifest.contracts) == ["customer_revenue"]
    assert manifest.contracts["customer_revenue"].source.to_dict()["relation"] == "qa.first_source"
    assert len(manifest.diagnostics) == 1

    diagnostic = manifest.diagnostics[0]
    assert diagnostic.code == DUPLICATE_CONTRACT
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "contract"
    assert diagnostic.resource_name == "customer_revenue"
    assert diagnostic.path == "contracts/duplicate.yml"
    assert diagnostic.hint == "First definition was found at contracts/customer.yml."


def test_build_manifest_orders_files_and_contracts_by_key(tmp_path: Path) -> None:
    manifest = build_manifest(
        project=ManifestProject(name="ecommerce_recon", config_version=1),
        files=(
            make_resource_file(tmp_path, "contracts/z.yml"),
            make_resource_file(tmp_path, "contracts/a.yml"),
        ),
        contracts=(
            make_contract(name="z_contract", path="contracts/z.yml"),
            make_contract(name="a_contract", path="contracts/a.yml"),
        ),
        recon_version="0.0.test",
        generated_at="2026-05-20T12:00:00Z",
    )

    manifest_dict = manifest.to_dict()

    assert list(manifest_dict["files"]) == ["contracts/a.yml", "contracts/z.yml"]
    assert list(manifest_dict["contracts"]) == ["a_contract", "z_contract"]
