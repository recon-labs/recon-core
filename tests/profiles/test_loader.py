from pathlib import Path

import pytest

from recon_core.parser.contracts import AuthoredContract, AuthoredEndpoint
from recon_core.parser.models import SourceLocation
from recon_core.profiles import load_selected_profile
from recon_core.project import load_project_context


def test_load_selected_profile_renders_referenced_connections_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_project(tmp_path)
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
            database: "{{ env_var('LEGACY_DB') }}"
          warehouse:
            type: duckdb
            database: "{{ env_var('WAREHOUSE_DB', 'default.duckdb') }}"
          unused:
            type: duckdb
            database: "{{ env_var('UNUSED_DB') }}"
      prod:
        connections:
          legacy:
            type: duckdb
            database: "{{ env_var('PROD_LEGACY_DB') }}"
""",
    )
    monkeypatch.setenv("LEGACY_DB", "legacy.duckdb")
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile(
        context_result.context,
        contracts=(contract(source_connection="legacy", target_connection="warehouse"),),
    )

    assert result.succeeded
    assert result.profile is not None
    assert result.profile.name == "local"
    assert result.profile.target_name == "dev"
    assert set(result.profile.connections) == {"legacy", "warehouse"}
    assert result.profile.connections["legacy"].config["database"] == "legacy.duckdb"
    assert result.profile.connections["warehouse"].config["database"] == "default.duckdb"
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    "connection_type",
    [
        pytest.param('"{{ env_var(\'RECON_ADAPTER\', \'duckdb\') }}"', id="jinja-env-var"),
        pytest.param("env_var('RECON_ADAPTER', 'duckdb')", id="bare-env-var"),
    ],
)
def test_load_selected_profile_rejects_templated_connection_type(
    tmp_path: Path,
    connection_type: str,
) -> None:
    write_project(tmp_path)
    write_profiles(
        tmp_path,
        f"""
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: {connection_type}
            database: legacy.duckdb
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile(
        context_result.context,
        contracts=(contract(source_connection="legacy", target_connection="warehouse"),),
    )

    assert result.profile is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_INVALID_PROFILE_CONFIG"
    ]
    assert "Connection `legacy` field `type` must be a literal adapter type." in (
        result.diagnostics[0].message
    )


def test_load_selected_profile_requires_project_profile_for_adapter_aware_compile(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile=None)
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile(
        context_result.context,
        contracts=(contract(source_connection="legacy", target_connection="legacy"),),
    )

    assert not result.succeeded
    assert result.profile is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_PROFILE_NOT_SELECTED"
    ]


def test_load_selected_profile_reports_missing_selected_profile(tmp_path: Path) -> None:
    write_project(tmp_path, profile="missing")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile(
        context_result.context,
        contracts=(contract(source_connection="legacy", target_connection="legacy"),),
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_CONFIG_PROFILE_NOT_FOUND"]
    assert result.diagnostics[0].resource_name == "missing"


def test_load_selected_profile_reports_missing_selected_target(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: missing
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile(
        context_result.context,
        contracts=(contract(source_connection="legacy", target_connection="legacy"),),
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_PROFILE_TARGET_NOT_FOUND"
    ]
    assert result.diagnostics[0].resource_name == "local"


def test_load_selected_profile_reports_missing_referenced_connection(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile(
        context_result.context,
        contracts=(contract(source_connection="legacy", target_connection="warehouse"),),
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_PROFILE_CONNECTION_NOT_FOUND"
    ]
    assert result.diagnostics[0].resource_name == "warehouse"


def test_load_selected_profile_reports_missing_env_var_without_leaking_values(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
            database: "{{ env_var('LEGACY_DB') }}"
          warehouse:
            type: duckdb
            database: "{{ env_var('WAREHOUSE_DB', 'safe-default.duckdb') }}"
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile(
        context_result.context,
        contracts=(contract(source_connection="legacy", target_connection="warehouse"),),
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_PROFILE_ENV_VAR_MISSING"
    ]
    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"
    assert "LEGACY_DB" in diagnostic_text
    assert "safe-default.duckdb" not in diagnostic_text
    assert "WAREHOUSE_DB" not in diagnostic_text


def test_load_selected_profile_rejects_unsupported_template_expression(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
            database: "{{ env_var('MISSING_DB') | lower }}"
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile(
        context_result.context,
        contracts=(contract(source_connection="legacy", target_connection="warehouse"),),
    )

    assert not result.succeeded
    assert result.profile is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_INVALID_PROFILE_CONFIG"
    ]
    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"
    assert "env_var('MISSING_DB') | lower" not in diagnostic_text
    assert "{{" not in diagnostic_text
    assert "}}" not in diagnostic_text


def test_load_selected_profile_sanitizes_invalid_yaml_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
            password: super-secret: invalid
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile(
        context_result.context,
        contracts=(contract(source_connection="legacy", target_connection="legacy"),),
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_INVALID_PROFILE_YAML"
    ]
    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def write_project(tmp_path: Path, *, profile: str | None = "local") -> None:
    profile_yaml = f"profile: {profile}\n" if profile is not None else ""
    tmp_path.joinpath("recon_project.yml").write_text(
        f"""
name: ecommerce_recon
version: 0.1.0
config-version: 1
{profile_yaml}contract-paths:
  - contracts
target-path: target
""".lstrip(),
        encoding="utf-8",
    )


def write_profiles(tmp_path: Path, content: str) -> None:
    profiles_path = tmp_path / "connections" / "profiles.yml"
    profiles_path.parent.mkdir()
    profiles_path.write_text(content.lstrip(), encoding="utf-8")


def contract(
    *,
    source_connection: str,
    target_connection: str,
) -> AuthoredContract:
    return AuthoredContract(
        name="customer_revenue",
        version=1,
        source=AuthoredEndpoint(connection=source_connection, relation="source_table"),
        target=AuthoredEndpoint(connection=target_connection, relation="target_table"),
        source_location=SourceLocation(path="contracts/customer_revenue.yml"),
        checks={"use": ["recon_core.basic_equivalence"]},
    )
