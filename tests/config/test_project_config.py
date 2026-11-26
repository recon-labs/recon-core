from pathlib import Path

import pytest

from recon_core.config import ConfiguredPath, PathOrigin, ProjectConfig, load_project_config
from recon_core.diagnostics import DiagnosticSeverity


def write_project_config(tmp_path: Path, content: str) -> Path:
    project_file = tmp_path / "recon_project.yml"
    project_file.write_text(content, encoding="utf-8")
    return project_file


def test_load_project_config_applies_documented_defaults(tmp_path: Path) -> None:
    project_file = write_project_config(tmp_path, "name: ecommerce_recon\n")

    result = load_project_config(project_file)

    assert result.succeeded
    assert result.diagnostics == ()
    assert result.config == ProjectConfig(
        name="ecommerce_recon",
        version=None,
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


def test_load_project_config_preserves_default_resource_path_origins(
    tmp_path: Path,
) -> None:
    project_file = write_project_config(tmp_path, "name: ecommerce_recon\n")

    result = load_project_config(project_file)

    assert result.succeeded
    assert result.config is not None
    assert result.config.path_entries_for("contract-paths") == (
        ConfiguredPath(
            value="contracts",
            origin=PathOrigin.DEFAULTED,
            field_name="contract-paths",
        ),
    )
    assert result.config.path_entries_for("check-pack-paths") == (
        ConfiguredPath(
            value="check_packs",
            origin=PathOrigin.DEFAULTED,
            field_name="check-pack-paths",
        ),
    )
    assert result.config.path_entries_for("macro-paths") == (
        ConfiguredPath(
            value="macros",
            origin=PathOrigin.DEFAULTED,
            field_name="macro-paths",
        ),
    )


def test_load_project_config_preserves_authored_resource_path_origins(
    tmp_path: Path,
) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: finance_recon
contract-paths:
  - recon_contracts
  - shared/contracts
check-pack-paths:
  - packs
macro-paths:
  - sql_helpers
""".lstrip(),
    )

    result = load_project_config(project_file)

    assert result.succeeded
    assert result.config is not None
    assert result.config.path_entries_for("contract-paths") == (
        ConfiguredPath(
            value="recon_contracts",
            origin=PathOrigin.AUTHORED,
            field_name="contract-paths",
        ),
        ConfiguredPath(
            value="shared/contracts",
            origin=PathOrigin.AUTHORED,
            field_name="contract-paths",
        ),
    )
    assert result.config.path_entries_for("check-pack-paths") == (
        ConfiguredPath(
            value="packs",
            origin=PathOrigin.AUTHORED,
            field_name="check-pack-paths",
        ),
    )
    assert result.config.path_entries_for("sample-policy-paths") == (
        ConfiguredPath(
            value="sample_policies",
            origin=PathOrigin.DEFAULTED,
            field_name="sample-policy-paths",
        ),
    )
    assert result.config.path_entries_for("macro-paths") == (
        ConfiguredPath(
            value="sql_helpers",
            origin=PathOrigin.AUTHORED,
            field_name="macro-paths",
        ),
    )


def test_load_project_config_maps_hyphenated_yaml_keys_to_snake_case_fields(
    tmp_path: Path,
) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: finance_recon
version: 0.2.0
config-version: 1
profile: dev
contract-paths:
  - recon_contracts
sample-policy-paths:
  - policies/samples
tolerance-policy-paths:
  - policies/tolerances
schema-policy-paths:
  - policies/schemas
check-pack-paths:
  - packs
macro-paths:
  - macros
target-path: build/target
report-path: build/reports
state-path: build/state
""".lstrip(),
    )

    result = load_project_config(project_file)

    assert result.succeeded
    assert result.config is not None
    assert result.config.name == "finance_recon"
    assert result.config.version == "0.2.0"
    assert result.config.config_version == 1
    assert result.config.profile == "dev"
    assert result.config.contract_paths == ("recon_contracts",)
    assert result.config.sample_policy_paths == ("policies/samples",)
    assert result.config.tolerance_policy_paths == ("policies/tolerances",)
    assert result.config.schema_policy_paths == ("policies/schemas",)
    assert result.config.check_pack_paths == ("packs",)
    assert result.config.macro_paths == ("macros",)
    assert result.config.target_path == "build/target"
    assert result.config.report_path == "build/reports"
    assert result.config.state_path == "build/state"


@pytest.mark.regression_capture("yaml-diagnostic-redaction")
def test_load_project_config_reports_invalid_yaml(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path, "name: ecommerce_recon\nprofile: local: secret-profile\n"
    )

    result = load_project_config(project_file)

    assert not result.succeeded
    assert result.config is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_YAML"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.message == "Invalid YAML in project config."
    assert diagnostic.path == str(project_file)
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    assert diagnostic.hint is not None
    assert "secret-profile" not in diagnostic.message


@pytest.mark.regression_capture("yaml-loader-duplicate-key-protection")
def test_load_project_config_reports_duplicate_yaml_keys(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: ecommerce_recon
name: finance_recon
""".lstrip(),
    )

    result = load_project_config(project_file)

    assert not result.succeeded
    assert result.config is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_YAML"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == str(project_file)
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    assert diagnostic.message == "Invalid YAML in project config: duplicate YAML key."


@pytest.mark.regression_capture("yaml-loader-duplicate-key-protection")
def test_load_project_config_reports_unhashable_yaml_mapping_key(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path,
        """
? [name, alias]
: ecommerce_recon
""".lstrip(),
    )

    result = load_project_config(project_file)

    assert not result.succeeded
    assert result.config is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_YAML"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == str(project_file)
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    assert diagnostic.message == "Invalid YAML in project config: unsupported YAML mapping key."


def test_load_project_config_reports_non_mapping_yaml(tmp_path: Path) -> None:
    project_file = write_project_config(tmp_path, "- ecommerce_recon\n")

    result = load_project_config(project_file)

    diagnostic = result.diagnostics[0]
    assert not result.succeeded
    assert result.config is None
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.path == str(project_file)
    assert "top-level mapping" in diagnostic.message


def test_load_project_config_reports_unreadable_config_path(tmp_path: Path) -> None:
    result = load_project_config(tmp_path)

    assert not result.succeeded
    assert result.config is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == str(tmp_path)
    assert "Could not read project config file" in diagnostic.message
    assert diagnostic.hint is not None


def test_load_project_config_reports_missing_required_name(tmp_path: Path) -> None:
    project_file = write_project_config(tmp_path, "profile: dev\n")

    result = load_project_config(project_file)

    diagnostic = result.diagnostics[0]
    assert not result.succeeded
    assert result.config is None
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.path == str(project_file)
    assert "name" in diagnostic.message


def test_load_project_config_reports_wrong_field_type(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: ecommerce_recon
contract-paths: contracts
""".lstrip(),
    )

    result = load_project_config(project_file)

    diagnostic = result.diagnostics[0]
    assert not result.succeeded
    assert result.config is None
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.path == str(project_file)
    assert "contract-paths" in diagnostic.message
    assert diagnostic.hint is not None


def test_load_project_config_reports_unsupported_config_version(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: ecommerce_recon
config-version: 2
""".lstrip(),
    )

    result = load_project_config(project_file)

    diagnostic = result.diagnostics[0]
    assert not result.succeeded
    assert result.config is None
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.path == str(project_file)
    assert "config-version" in diagnostic.message
    assert "1" in diagnostic.message
    assert diagnostic.hint is not None


def test_load_project_config_reports_unknown_field(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path,
        """
name: ecommerce_recon
unexpected-setting: true
""".lstrip(),
    )

    result = load_project_config(project_file)

    diagnostic = result.diagnostics[0]
    assert not result.succeeded
    assert result.config is None
    assert diagnostic.code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert diagnostic.path == str(project_file)
    assert "unexpected-setting" in diagnostic.message


@pytest.mark.parametrize(
    "settings",
    [
        "",
        "execution: {}\n",
        "execution:\n  scan-budget: {}\n",
        "execution:\n  scan-budget:\n    local: {}\n",
    ],
)
def test_local_resource_policy_defaults(tmp_path: Path, settings: str) -> None:
    result = load_project_config(write_project_config(tmp_path, "name: recon\n" + settings))
    baseline = load_project_config(write_project_config(tmp_path, "name: recon\n"))
    assert result.succeeded
    assert result.config == baseline.config
    assert result.config is not None
    policy = result.config._local_resource_policy
    assert policy.max_database_bytes is None
    assert policy.warn_estimated_input_rows is None
    assert policy.managed_memory_bytes is None
    assert policy.threads is None
    assert policy.spill_bytes is None
    assert policy.memory_reserve_bytes is None
    assert policy.disk_reserve_bytes is None
    assert policy.scratch_directory is None


@pytest.mark.regression_capture("local-resource-config-strict-validation")
def test_local_resource_policy_values(tmp_path: Path) -> None:
    project_file = write_project_config(
        tmp_path,
        """name: recon
execution:
  scan-budget:
    local:
      max-database-mib: 8796093022207
      warn-estimated-input-rows: 9223372036854775807
      managed-memory-mib: 8192
      threads: 8
      spill-mib: 20480
      memory-reserve-mib: 2048
      disk-reserve-mib: 4096
      scratch-directory: private-scratch
""",
    )
    result = load_project_config(project_file)
    assert result.succeeded
    assert result.config is not None
    policy = result.config._local_resource_policy
    mib = 1 << 20
    assert policy.max_database_bytes == 8796093022207 * mib
    assert policy.warn_estimated_input_rows == (1 << 63) - 1
    assert policy.managed_memory_bytes == 8192 * mib
    assert policy.threads == 8
    assert policy.spill_bytes == 20480 * mib
    assert policy.memory_reserve_bytes == 2048 * mib
    assert policy.disk_reserve_bytes == 4096 * mib
    assert policy.scratch_directory == "private-scratch"
    assert not (tmp_path / "private-scratch").exists()
    assert "private-scratch" not in repr(result.config)


@pytest.mark.parametrize(
    "field",
    [
        "max-database-mib",
        "warn-estimated-input-rows",
        "managed-memory-mib",
        "threads",
        "spill-mib",
        "memory-reserve-mib",
        "disk-reserve-mib",
    ],
)
@pytest.mark.parametrize("value", ["0", "-1", "true", "1.0", "'1'", "null", "9223372036854775808"])
def test_local_resource_policy_invalid_integer(tmp_path: Path, field: str, value: str) -> None:
    project_file = write_project_config(
        tmp_path, f"name: recon\nexecution:\n  scan-budget:\n    local:\n      {field}: {value}\n"
    )
    result = load_project_config(project_file)
    assert not result.succeeded
    assert result.config is None
    assert result.diagnostics[0].code == "RC_CONFIG_INVALID_PROJECT_CONFIG"


@pytest.mark.parametrize(
    "field",
    [
        "max-database-mib",
        "managed-memory-mib",
        "spill-mib",
        "memory-reserve-mib",
        "disk-reserve-mib",
    ],
)
@pytest.mark.regression_capture("local-resource-config-strict-validation")
def test_local_resource_policy_mib_overflow(tmp_path: Path, field: str) -> None:
    project_file = write_project_config(
        tmp_path,
        f"name: recon\nexecution:\n  scan-budget:\n    local:\n      {field}: 8796093022208\n",
    )
    assert not load_project_config(project_file).succeeded


@pytest.mark.parametrize(
    "settings",
    [
        "execution: null\n",
        "execution: []\n",
        "execution: {PRIVATE_SENTINEL: true}\n",
        "execution: {1: true}\n",
        "execution: {scan-budget: null}\n",
        "execution: {scan-budget: []}\n",
        "execution: {scan-budget: {PRIVATE_SENTINEL: true}}\n",
        "execution: {scan-budget: {local: null}}\n",
        "execution: {scan-budget: {local: []}}\n",
        "execution: {scan-budget: {local: {PRIVATE_SENTINEL: true}}}\n",
        "execution: {scan-budget: {local: {1: true}}}\n",
        "execution: {scan-budget: {local: {scratch-directory: null}}}\n",
        "execution: {scan-budget: {local: {scratch-directory: 1}}}\n",
        "execution: {scan-budget: {local: {scratch-directory: ''}}}\n",
        "execution: {scan-budget: {local: {scratch-directory: '   '}}}\n",
        "execution: {scan-budget: {local: {scratch-directory: [PRIVATE_SENTINEL]}}}\n",
        "execution: {scan-budget: {local: {threads: PRIVATE_SENTINEL}}}\n",
    ],
)
@pytest.mark.regression_capture("local-resource-config-strict-validation")
def test_local_resource_policy_invalid_mapping(tmp_path: Path, settings: str) -> None:
    result = load_project_config(write_project_config(tmp_path, "name: recon\n" + settings))
    assert not result.succeeded
    assert result.config is None
    assert result.diagnostics[0].code == "RC_CONFIG_INVALID_PROJECT_CONFIG"
    assert "PRIVATE_SENTINEL" not in repr(result.diagnostics)


@pytest.mark.regression_capture("yaml-loader-duplicate-key-protection")
def test_local_resource_policy_duplicate_key(tmp_path: Path) -> None:
    result = load_project_config(
        write_project_config(
            tmp_path,
            "name: recon\nexecution: {scan-budget: {local: {threads: 1, threads: 2}}}\n",
        )
    )
    assert not result.succeeded
    assert result.diagnostics[0].code == "RC_CONFIG_INVALID_PROJECT_YAML"
