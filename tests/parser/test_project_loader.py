from pathlib import Path

from recon_core.diagnostics import DiagnosticSeverity
from recon_core.parser import ParsedProject, load_parsed_project
from recon_core.project import ProjectContext, load_project_context


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
  relation: qa.{name}_source
target:
  connection: warehouse
  relation: qa.{name}_target
checks:
  use:
    - recon_core.basic_equivalence
tags:
  - finance
""".lstrip(),
        encoding="utf-8",
    )
    return contract_path


def load_context(project_root: Path) -> ProjectContext:
    context_result = load_project_context(project_root)

    assert context_result.succeeded
    assert context_result.context is not None
    return context_result.context


def test_load_parsed_project_returns_context_files_contracts_and_no_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path, "contracts/orders.yml", name="orders")
    write_contract(tmp_path, "contracts/customer_revenue.yml")
    context = load_context(tmp_path)

    parsed_project = load_parsed_project(context)

    assert isinstance(parsed_project, ParsedProject)
    assert parsed_project.succeeded
    assert parsed_project.context is context
    assert parsed_project.diagnostics == ()
    assert [resource.relative_path for resource in parsed_project.files] == [
        "contracts/customer_revenue.yml",
        "contracts/orders.yml",
    ]
    assert [contract.name for contract in parsed_project.contracts] == [
        "customer_revenue",
        "orders",
    ]
    assert [contract.source_location.path for contract in parsed_project.contracts] == [
        "contracts/customer_revenue.yml",
        "contracts/orders.yml",
    ]


def test_load_parsed_project_reports_missing_contract_path(tmp_path: Path) -> None:
    write_project(tmp_path, include_contract_dir=False)
    context = load_context(tmp_path)

    parsed_project = load_parsed_project(context)

    assert not parsed_project.succeeded
    assert parsed_project.context is context
    assert parsed_project.files == ()
    assert parsed_project.contracts == ()
    assert len(parsed_project.diagnostics) == 1

    diagnostic = parsed_project.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "contract_path"
    assert diagnostic.path == str(tmp_path / "contracts")


def test_load_parsed_project_rewrites_yaml_diagnostics_to_resource_relative_path(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    broken_contract = tmp_path / "contracts" / "broken.yml"
    broken_contract.write_text("name: [\n", encoding="utf-8")
    context = load_context(tmp_path)

    parsed_project = load_parsed_project(context)

    assert not parsed_project.succeeded
    assert [resource.relative_path for resource in parsed_project.files] == [
        "contracts/broken.yml"
    ]
    assert parsed_project.contracts == ()
    assert len(parsed_project.diagnostics) == 1

    diagnostic = parsed_project.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_INVALID_YAML"
    assert diagnostic.path == "contracts/broken.yml"
    assert diagnostic.line is not None
    assert diagnostic.column is not None


def test_load_parsed_project_preserves_valid_contracts_with_parse_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path, "contracts/customer_revenue.yml")
    (tmp_path / "contracts" / "broken.yml").write_text(
        """
version: 1
name: broken_contract
source:
  connection: legacy
  relation: qa.broken_source
target:
  connection: warehouse
  relation: qa.broken_target
""".lstrip(),
        encoding="utf-8",
    )
    context = load_context(tmp_path)

    parsed_project = load_parsed_project(context)

    assert not parsed_project.succeeded
    assert [resource.relative_path for resource in parsed_project.files] == [
        "contracts/broken.yml",
        "contracts/customer_revenue.yml",
    ]
    assert [contract.name for contract in parsed_project.contracts] == ["customer_revenue"]
    assert [diagnostic.code for diagnostic in parsed_project.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]
    assert parsed_project.diagnostics[0].path == "contracts/broken.yml"


def test_load_parsed_project_has_no_artifact_side_effects(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    context = load_context(tmp_path)

    parsed_project = load_parsed_project(context)

    assert parsed_project.succeeded
    assert not (tmp_path / "target").exists()
