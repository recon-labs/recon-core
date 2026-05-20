from pathlib import Path

from recon_core.config import ProjectConfig
from recon_core.project import ProjectPaths, resolve_project_paths


def make_project_config(**overrides: object) -> ProjectConfig:
    values: dict[str, object] = {
        "name": "ecommerce_recon",
        "version": None,
        "config_version": 1,
        "profile": None,
        "contract_paths": ("contracts",),
        "sample_policy_paths": ("sample_policies",),
        "tolerance_policy_paths": ("tolerances",),
        "schema_policy_paths": ("schema_policies",),
        "check_pack_paths": ("check_packs",),
        "macro_paths": ("macros",),
        "target_path": "target",
        "report_path": "reports",
        "state_path": "state",
    }
    values.update(overrides)
    return ProjectConfig(**values)  # type: ignore[arg-type]


def test_resolve_project_paths_resolves_relative_paths_from_project_root(
    tmp_path: Path,
) -> None:
    config = make_project_config(
        contract_paths=("contracts", "shared/contracts"),
        sample_policy_paths=("sample_policies", "shared/sample_policies"),
        tolerance_policy_paths=("tolerances", "shared/tolerances"),
        schema_policy_paths=("schema_policies", "shared/schema_policies"),
        check_pack_paths=("check_packs", "shared/check_packs"),
        macro_paths=("macros", "shared/macros"),
        target_path="build/target",
        report_path="build/reports",
        state_path="build/state",
    )

    paths = resolve_project_paths(tmp_path, config)

    assert paths == ProjectPaths(
        contract_paths=(tmp_path / "contracts", tmp_path / "shared/contracts"),
        sample_policy_paths=(
            tmp_path / "sample_policies",
            tmp_path / "shared/sample_policies",
        ),
        tolerance_policy_paths=(tmp_path / "tolerances", tmp_path / "shared/tolerances"),
        schema_policy_paths=(
            tmp_path / "schema_policies",
            tmp_path / "shared/schema_policies",
        ),
        check_pack_paths=(tmp_path / "check_packs", tmp_path / "shared/check_packs"),
        macro_paths=(tmp_path / "macros", tmp_path / "shared/macros"),
        target_path=tmp_path / "build/target",
        report_path=tmp_path / "build/reports",
        state_path=tmp_path / "build/state",
    )


def test_resolve_project_paths_preserves_absolute_paths(tmp_path: Path) -> None:
    external_root = tmp_path / "external"
    config = make_project_config(
        contract_paths=(str(external_root / "contracts"),),
        sample_policy_paths=(str(external_root / "sample_policies"),),
        tolerance_policy_paths=(str(external_root / "tolerances"),),
        schema_policy_paths=(str(external_root / "schema_policies"),),
        check_pack_paths=(str(external_root / "check_packs"),),
        macro_paths=(str(external_root / "macros"),),
        target_path=str(external_root / "target"),
        report_path=str(external_root / "reports"),
        state_path=str(external_root / "state"),
    )

    paths = resolve_project_paths(tmp_path / "project", config)

    assert paths.contract_paths == (external_root / "contracts",)
    assert paths.sample_policy_paths == (external_root / "sample_policies",)
    assert paths.tolerance_policy_paths == (external_root / "tolerances",)
    assert paths.schema_policy_paths == (external_root / "schema_policies",)
    assert paths.check_pack_paths == (external_root / "check_packs",)
    assert paths.macro_paths == (external_root / "macros",)
    assert paths.target_path == external_root / "target"
    assert paths.report_path == external_root / "reports"
    assert paths.state_path == external_root / "state"


def test_resolve_project_paths_resolves_default_generated_paths(tmp_path: Path) -> None:
    paths = resolve_project_paths(tmp_path, make_project_config())

    assert paths.target_path == tmp_path / "target"
    assert paths.report_path == tmp_path / "reports"
    assert paths.state_path == tmp_path / "state"
