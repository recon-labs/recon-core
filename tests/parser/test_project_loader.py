from pathlib import Path

from recon_core.config import ProjectConfig
from recon_core.diagnostics import DiagnosticSeverity
from recon_core.parser import ParsedProject, load_parsed_project
from recon_core.project import ProjectContext, load_project_context, resolve_project_paths


def write_project(
    project_root: Path,
    *,
    contract_paths: tuple[str, ...] = ("contracts",),
    check_pack_paths: tuple[str, ...] | None = None,
    target_path: str = "target",
    include_contract_dir: bool = True,
    include_check_pack_paths: bool = False,
) -> None:
    contract_paths_yaml = "\n".join(f"  - {contract_path}" for contract_path in contract_paths)
    check_pack_paths_yaml = _path_list_yaml("check-pack-paths", check_pack_paths)
    project_root.joinpath("recon_project.yml").write_text(
        f"""
name: ecommerce_recon
version: 0.1.0
config-version: 1
contract-paths:
{contract_paths_yaml}
{check_pack_paths_yaml}
target-path: {target_path}
""".lstrip(),
        encoding="utf-8",
    )
    if include_contract_dir:
        for contract_path in contract_paths:
            (project_root / contract_path).mkdir(parents=True, exist_ok=True)
    if include_check_pack_paths and check_pack_paths is not None:
        for check_pack_path in check_pack_paths:
            (project_root / check_pack_path).mkdir(parents=True, exist_ok=True)


def _path_list_yaml(field_name: str, paths: tuple[str, ...] | None) -> str:
    if paths is None:
        return ""
    path_items = "\n".join(f"  - {path}" for path in paths)
    return f"{field_name}:\n{path_items}"


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


def test_load_parsed_project_indexes_non_contract_files_without_parsing_them(
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
    (tmp_path / "tolerances" / "default.yaml").write_text(
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
    context = load_context(tmp_path)

    parsed_project = load_parsed_project(context)

    assert parsed_project.succeeded
    assert [
        (resource.relative_path, resource.resource_type.value) for resource in parsed_project.files
    ] == [
        ("check_packs/company.yml", "check_pack"),
        ("contracts/customer_revenue.yml", "contract"),
        ("macros/normalize.sql", "macro_file"),
        ("sample_policies/stable.yml", "sample_policy"),
        ("schema_policies/cdc.yml", "schema_policy"),
        ("tolerances/default.yaml", "tolerance_policy"),
    ]
    assert [contract.name for contract in parsed_project.contracts] == ["customer_revenue"]
    assert parsed_project.diagnostics == ()


def test_load_parsed_project_reports_explicit_missing_non_contract_path(
    tmp_path: Path,
) -> None:
    write_project(
        tmp_path,
        check_pack_paths=("custom_packs",),
        include_check_pack_paths=False,
    )
    write_contract(tmp_path)
    context = load_context(tmp_path)

    parsed_project = load_parsed_project(context)

    assert not parsed_project.succeeded
    assert [resource.relative_path for resource in parsed_project.files] == [
        "contracts/customer_revenue.yml"
    ]
    assert [contract.name for contract in parsed_project.contracts] == ["customer_revenue"]
    assert len(parsed_project.diagnostics) == 1

    diagnostic = parsed_project.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
    assert diagnostic.resource_type == "check_pack_path"
    assert diagnostic.path == str(tmp_path / "custom_packs")


def test_load_parsed_project_skips_missing_default_optional_paths_for_manual_config(
    tmp_path: Path,
) -> None:
    (tmp_path / "contracts").mkdir()
    write_contract(tmp_path)
    config = ProjectConfig(
        name="ecommerce_recon",
        version="0.1.0",
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
    context = ProjectContext(
        project_root=tmp_path,
        project_file=tmp_path / "recon_project.yml",
        config=config,
        paths=resolve_project_paths(tmp_path, config),
        profile_paths=(),
    )

    parsed_project = load_parsed_project(context)

    assert parsed_project.succeeded
    assert [resource.relative_path for resource in parsed_project.files] == [
        "contracts/customer_revenue.yml"
    ]
    assert [contract.name for contract in parsed_project.contracts] == ["customer_revenue"]
    assert parsed_project.diagnostics == ()


def test_load_parsed_project_reports_ambiguous_cross_kind_resource_file(
    tmp_path: Path,
) -> None:
    write_project(
        tmp_path,
        contract_paths=("resources",),
        check_pack_paths=("resources",),
        include_check_pack_paths=True,
    )
    (tmp_path / "resources" / "company.yml").write_text(
        "this is not valid: [\n",
        encoding="utf-8",
    )
    context = load_context(tmp_path)

    parsed_project = load_parsed_project(context)

    assert not parsed_project.succeeded
    assert parsed_project.files == ()
    assert parsed_project.contracts == ()
    assert [diagnostic.code for diagnostic in parsed_project.diagnostics] == [
        "RC_PARSE_AMBIGUOUS_RESOURCE_FILE"
    ]
    assert parsed_project.diagnostics[0].path == "resources/company.yml"


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
    assert [resource.relative_path for resource in parsed_project.files] == ["contracts/broken.yml"]
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
