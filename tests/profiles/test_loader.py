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
