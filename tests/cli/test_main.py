import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from recon_core import __version__
from recon_core.cli.main import main
from recon_core.services import (
    CompileService,
    ExitCategory,
    InitService,
    ParseService,
    RunService,
    ServiceResult,
)


def test_cli_version_outputs_package_version() -> None:
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_help_lists_core_commands() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    for command in ("init", "parse", "compile", "run"):
        assert command in result.output


def test_run_command_reports_missing_compiled_artifacts() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_project()

        result = runner.invoke(main, ["run"])

    assert result.exit_code == 3
    assert "Error: Compiled-check artifacts could not be loaded." in result.output
    assert "Code: RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND" in result.output
    assert "Hint: Run `recon compile` before `recon run`." in result.output


@pytest.mark.parametrize(
    ("command", "service_cls"),
    [
        ("parse", ParseService),
        ("compile", CompileService),
        ("run", RunService),
    ],
)
def test_cli_commands_delegate_to_services(
    command: str,
    service_cls: type[InitService | ParseService | CompileService | RunService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def execute(self: InitService | ParseService | CompileService | RunService) -> ServiceResult:
        nonlocal calls
        calls += 1
        return ServiceResult(exit_category=ExitCategory.RUNTIME_ERROR)

    monkeypatch.setattr(service_cls, "execute", execute)

    result = CliRunner().invoke(main, [command])

    assert result.exit_code != 0
    assert calls == 1


@pytest.mark.parametrize(
    ("args", "expected_render_sql"),
    [
        (["compile"], False),
        (["compile", "--render-sql"], True),
    ],
)
def test_compile_command_passes_render_sql_flag(
    args: list[str],
    expected_render_sql: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def execute(self: CompileService) -> ServiceResult:
        calls.append(self.render_sql)
        return ServiceResult.success("ok")

    monkeypatch.setattr(CompileService, "execute", execute)

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 0
    assert calls == [expected_render_sql]


def test_parse_command_writes_manifest_for_project() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_project()
        _write_contract()

        result = runner.invoke(main, ["parse"])

        assert result.exit_code == 0
        assert "Parsed 1 contract. Wrote manifest to" in result.output

        manifest = json.loads(_manifest_path().read_text(encoding="utf-8"))
        assert list(manifest["contracts"]) == ["customer_revenue"]
        assert manifest["diagnostics"] == []


def test_compile_command_writes_compiled_artifacts_for_project() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_project()
        _write_contract()

        result = runner.invoke(main, ["compile"])

        assert result.exit_code == 0
        assert "Compiled 1 contract. Wrote artifacts to" in result.output

        checks = _read_yaml(_compiled_checks_path())
        assert isinstance(checks, dict)
        assert checks["artifact_type"] == "compiled_checks"
        assert [check["name"] for check in checks["checks"]] == [
            "row_count_diff",
            "missing_keys",
            "extra_keys",
            "null_source_keys",
            "null_target_keys",
            "duplicate_source_keys",
            "duplicate_target_keys",
            "total_revenue",
        ]


def test_compile_render_sql_prints_diagnostic_message_for_profile_errors() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_project(profile="local")
        _write_contract()
        _write_profiles_with_missing_env_var()

        result = runner.invoke(main, ["compile", "--render-sql"])

        assert result.exit_code == 4
        assert "Error: SQL rendering profile configuration failed." in result.output
        assert "Code: RC_CONFIG_PROFILE_ENV_VAR_MISSING" in result.output
        assert (
            "Message: Connection `legacy` references missing environment variable `MISSING_DB`."
            in result.output
        )
        assert "Hint: Set the environment variable or provide an env_var default." in result.output


def test_parse_command_does_not_print_raw_yaml_snippets_for_invalid_contract() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_project()
        _contract_path().write_text(
            """
version: 1
name: customer_revenue
source:
  connection: legacy
  query: select * from customers where ssn: secret-ssn
target:
  connection: warehouse
  relation: qa.customer_target
checks:
  use:
    - recon_core.basic_equivalence
""".lstrip(),
            encoding="utf-8",
        )

        result = runner.invoke(main, ["parse"])

        assert result.exit_code == 2
        assert "Code: RC_PARSE_INVALID_YAML" in result.output
        assert "Message: Invalid YAML in resource file." in result.output
        assert "secret-ssn" not in result.output
        assert "select * from customers" not in result.output


def test_parse_command_returns_validation_error_and_writes_manifest() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        _write_project()
        _contract_path().write_text(
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

        result = runner.invoke(main, ["parse"])

        assert result.exit_code == 2
        assert "Error: Parse completed with 1 diagnostic." in result.output
        assert "Code: RC_PARSE_MISSING_REQUIRED_FIELD" in result.output

        manifest = json.loads(_manifest_path().read_text(encoding="utf-8"))
        assert manifest["contracts"] == {}
        assert manifest["diagnostics"][0]["code"] == "RC_PARSE_MISSING_REQUIRED_FIELD"


def test_init_command_creates_project() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "ecommerce_recon"])

        assert result.exit_code == 0
        assert "Created Recon project at" in result.output
        assert "ecommerce_recon" in result.output
        assert "Error:" not in result.output

        project_dir = Path("ecommerce_recon")
        assert (project_dir / "check_packs").is_dir()
        assert (project_dir / "macros").is_dir()

        config = yaml.safe_load((project_dir / "recon_project.yml").read_text(encoding="utf-8"))
        assert config["check-pack-paths"] == ["check_packs"]
        assert config["macro-paths"] == ["macros"]


def test_init_command_requires_project_name() -> None:
    result = CliRunner().invoke(main, ["init"])

    assert result.exit_code != 0
    assert "Missing argument 'PROJECT_NAME'" in result.output


def test_init_command_existing_path_reports_configuration_error() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "ecommerce_recon"])
        assert result.exit_code == 0

        result = runner.invoke(main, ["init", "ecommerce_recon"])

        assert result.exit_code == 4
        assert "Error: Path already exists:" in result.output
        assert "Code: RC_CONFIG_INIT_PATH_EXISTS" in result.output
        assert "Path: " in result.output
        assert "ecommerce_recon" in result.output
        assert "Hint: Choose a new project name or remove the existing path." in result.output


def test_init_command_rejects_path_like_project_name() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "../outside"])

        assert result.exit_code == 4
        assert "Error: Invalid project name: ../outside" in result.output
        assert "Code: RC_CONFIG_INIT_INVALID_PROJECT_NAME" in result.output
        assert "Hint: Use a single directory name." in result.output
        assert "Names must start with a letter or underscore." in result.output


def test_init_command_rejects_project_name_that_cannot_be_stable_id() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "ecommerce-recon"])

        assert result.exit_code == 4
        assert "Error: Invalid project name: ecommerce-recon" in result.output
        assert "Code: RC_CONFIG_INIT_INVALID_PROJECT_NAME" in result.output
        assert "Names must start with a letter or underscore." in result.output


def _write_project(*, profile: str | None = None) -> None:
    _contract_path().parent.mkdir()
    _manifest_path().parent.mkdir()
    profile_yaml = f"profile: {profile}\n" if profile is not None else ""
    _project_path().write_text(
        f"""
name: ecommerce_recon
version: 0.1.0
config-version: 1
{profile_yaml}\
contract-paths:
  - contracts
target-path: target
""".lstrip(),
        encoding="utf-8",
    )


def _write_contract() -> None:
    _contract_path().write_text(
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
    - month
metrics:
  - name: total_revenue
    type: sum
    column: revenue
checks:
  use:
    - recon_core.basic_equivalence
""".lstrip(),
        encoding="utf-8",
    )


def _write_profiles_with_missing_env_var() -> None:
    profiles_path = Path("connections/profiles.yml")
    profiles_path.parent.mkdir()
    profiles_path.write_text(
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
            database: "{{ env_var('MISSING_DB') }}"
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""".lstrip(),
        encoding="utf-8",
    )


def _project_path() -> Path:
    return Path("recon_project.yml")


def _contract_path() -> Path:
    return Path("contracts/customer_revenue.yml")


def _manifest_path() -> Path:
    return Path("target/manifest.json")


def _compiled_checks_path() -> Path:
    return Path("target/compiled_checks/customer_revenue.yml")


def _read_yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
