from pathlib import Path

import pytest

from recon_core.artifacts import LoadedCompiledContractArtifact, LoadedCompiledEndpoint
from recon_core.config._local_resource_policy import _LocalResourcePolicy
from recon_core.parser.contracts import AuthoredContract, AuthoredEndpoint
from recon_core.parser.models import SourceLocation
from recon_core.profiles import (
    load_selected_profile,
    load_selected_profile_for_connection_names,
    referenced_connection_names_from_compiled_contracts,
)
from recon_core.project import load_project_context


def test_load_selected_profile_for_connection_names_renders_referenced_connections_only(
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
""",
    )
    monkeypatch.setenv("LEGACY_DB", "legacy.duckdb")
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile_for_connection_names(
        context_result.context,
        referenced_connection_names=("legacy", "warehouse"),
    )

    assert result.succeeded
    assert result.profile is not None
    assert result.profile.name == "local"
    assert result.profile.target_name == "dev"
    assert set(result.profile.connections) == {"legacy", "warehouse"}
    assert result.profile.connections["legacy"].config["database"] == "legacy.duckdb"
    assert result.profile.connections["warehouse"].config["database"] == "default.duckdb"
    assert result.diagnostics == ()


def test_load_selected_profile_for_connection_names_reports_referenced_env_var_without_leak(
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

    result = load_selected_profile_for_connection_names(
        context_result.context,
        referenced_connection_names=("legacy", "warehouse"),
    )

    assert not result.succeeded
    assert result.profile is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_PROFILE_ENV_VAR_MISSING"
    ]
    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"
    assert "LEGACY_DB" in diagnostic_text
    assert "safe-default.duckdb" not in diagnostic_text
    assert "WAREHOUSE_DB" not in diagnostic_text


@pytest.mark.parametrize(
    "connection_type",
    [
        pytest.param("\"{{ env_var('RECON_ADAPTER', 'duckdb') }}\"", id="jinja-env-var"),
        pytest.param("env_var('RECON_ADAPTER', 'duckdb')", id="bare-env-var"),
    ],
)
def test_load_selected_profile_for_connection_names_rejects_templated_type(
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

    result = load_selected_profile_for_connection_names(
        context_result.context,
        referenced_connection_names=("legacy", "warehouse"),
    )

    assert result.profile is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_INVALID_PROFILE_CONFIG"
    ]
    assert "Connection `legacy` field `type` must be a literal adapter type." in (
        result.diagnostics[0].message
    )


def test_referenced_connection_names_from_compiled_contracts_uses_loaded_endpoints() -> None:
    names = referenced_connection_names_from_compiled_contracts(
        (
            compiled_contract(
                contract_name="customer_revenue",
                source_connection="legacy",
                target_connection="warehouse",
            ),
            compiled_contract(
                contract_name="orders_revenue",
                source_connection="legacy",
                target_connection="analytics",
            ),
        )
    )

    assert names == ("analytics", "legacy", "warehouse")


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


def test_load_selected_profile_renders_bare_env_var_references(
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
            database: "env_var('LEGACY_DB')"
          warehouse:
            type: duckdb
            database: "env_var('WAREHOUSE_DB', 'default.duckdb')"
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
    assert result.profile.connections["legacy"].config["database"] == "legacy.duckdb"
    assert result.profile.connections["warehouse"].config["database"] == "default.duckdb"
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    "connection_type",
    [
        pytest.param("\"{{ env_var('RECON_ADAPTER', 'duckdb') }}\"", id="jinja-env-var"),
        pytest.param('"{% if true %}duckdb{% endif %}"', id="jinja-statement"),
        pytest.param('"{# duckdb #}"', id="jinja-comment"),
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


@pytest.mark.parametrize(
    "database_value",
    [
        pytest.param('"{% if env %}prod.duckdb{% endif %}"', id="jinja-statement"),
        pytest.param('"{# prod.duckdb #}"', id="jinja-comment"),
    ],
)
def test_load_selected_profile_rejects_unsupported_template_fragments(
    tmp_path: Path,
    database_value: str,
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
            type: duckdb
            database: {database_value}
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
    assert "{%" not in diagnostic_text
    assert "%}" not in diagnostic_text
    assert "{#" not in diagnostic_text
    assert "#}" not in diagnostic_text


@pytest.mark.parametrize(
    "database_value",
    [
        pytest.param(
            "\"{{ env_var('WAREHOUSE_DB', '{{ raw }}') }}\"",
            id="jinja-expression-default",
        ),
        pytest.param(
            "\"{{ env_var('WAREHOUSE_DB', '{% if env %}prod.duckdb{% endif %}') }}\"",
            id="jinja-statement-default",
        ),
        pytest.param(
            "\"{{ env_var('WAREHOUSE_DB', '{# prod.duckdb #}') }}\"",
            id="jinja-comment-default",
        ),
        pytest.param(
            '\'env_var("WAREHOUSE_DB", "{{ raw }}")\'',
            id="bare-template-default",
        ),
        pytest.param(
            "'{{ env_var(\"WAREHOUSE_DB\", \"env_var(''OTHER_DB'')\") }}'",
            id="jinja-embedded-env-var-default",
        ),
        pytest.param(
            "'env_var(\"WAREHOUSE_DB\", \"env_var(''OTHER_DB'')\")'",
            id="bare-embedded-env-var-default",
        ),
    ],
)
def test_load_selected_profile_rejects_unsupported_env_var_defaults(
    tmp_path: Path,
    database_value: str,
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
            type: duckdb
            database: legacy.duckdb
          warehouse:
            type: duckdb
            database: {database_value}
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
    assert "{{ raw }}" not in diagnostic_text
    assert "{% if env %}" not in diagnostic_text
    assert "{# prod.duckdb #}" not in diagnostic_text
    assert "OTHER_DB" not in diagnostic_text


def test_load_selected_profile_rejects_unsupported_bare_env_var_expression(
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
            database: "env_var('MISSING_DB') | lower"
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
    assert "MISSING_DB" not in diagnostic_text
    assert "lower" not in diagnostic_text


@pytest.mark.regression_capture("yaml-diagnostic-redaction")
@pytest.mark.regression_capture("yaml-profile-and-source-privacy")
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


@pytest.mark.regression_capture("yaml-loader-duplicate-key-protection")
@pytest.mark.regression_capture("yaml-profile-and-source-privacy")
def test_load_selected_profile_rejects_duplicate_yaml_keys_without_leak(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    target: prod-secret
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
        "RC_CONFIG_INVALID_PROFILE_YAML"
    ]
    diagnostic = result.diagnostics[0]
    assert diagnostic.message == "Invalid YAML in profile file."
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    diagnostic_text = f"{diagnostic.message} {diagnostic.hint}"
    assert "target" not in diagnostic_text
    assert "prod-secret" not in diagnostic_text


@pytest.mark.regression_capture("yaml-loader-duplicate-key-protection")
@pytest.mark.regression_capture("yaml-profile-and-source-privacy")
def test_load_selected_profile_rejects_unhashable_yaml_mapping_key_without_leak(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_profiles(
        tmp_path,
        """
? [profiles, alias]
: local
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
    diagnostic = result.diagnostics[0]
    assert diagnostic.message == "Invalid YAML in profile file."
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    diagnostic_text = f"{diagnostic.message} {diagnostic.hint}"
    assert "alias" not in diagnostic_text


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


def compiled_contract(
    *,
    contract_name: str,
    source_connection: str,
    target_connection: str,
) -> LoadedCompiledContractArtifact:
    return LoadedCompiledContractArtifact(
        path=Path("target") / "compiled_contracts" / f"{contract_name}.yml",
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contract_id=f"contract.ecommerce_recon.{contract_name}",
        contract_name=contract_name,
        source_file=f"contracts/{contract_name}.yml",
        source=LoadedCompiledEndpoint(
            connection=source_connection,
            relation="qa.source_relation",
        ),
        target=LoadedCompiledEndpoint(
            connection=target_connection,
            relation="qa.target_relation",
        ),
    )


@pytest.mark.parametrize(
    "execution",
    [
        "{adapters: {PRIVATE_SENTINEL: {threads: 2}}}",
        "{adapters: {duckdb: {managed-memory: {percent: 101}}}}",
        "{connections: {missing: {threads: 2}}}",
        "{connections: {legacy: {managed-memory: {percent: 75, mib: 2048}}}}",
        "{connections: {legacy: {threads: PRIVATE_SENTINEL}}}",
        "{connections: {legacy: {threads: '2'}}}",
        "{connections: {legacy: {scratch-directory: null}}}",
        "{connections: {legacy: {spill: {mib: 8796093022208}}}}",
    ],
)
@pytest.mark.regression_capture("local-resource-config-strict-validation")
def test_selected_target_rejects_invalid_operational_policy(tmp_path: Path, execution: str) -> None:
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
            type: duckdb
            database: private.duckdb
        execution: {execution}
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile_for_connection_names(
        context_result.context,
        referenced_connection_names=("legacy",),
        environ={},
    )

    assert not result.succeeded
    assert result.profile is None
    assert result.diagnostics
    assert all(
        diagnostic.code == "RC_CONFIG_INVALID_PROFILE_CONFIG" for diagnostic in result.diagnostics
    )
    assert "PRIVATE_SENTINEL" not in repr(result.diagnostics)
    assert "private.duckdb" not in repr(result.diagnostics)


@pytest.mark.regression_capture("local-resource-config-strict-validation")
def test_selected_target_keeps_operational_policy_out_of_connection_payload(
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
            database: "{{ env_var('DB_PATH') }}"
          warehouse:
            type: duckdb
            database: "{{ env_var('DB_PATH') }}"
          unused:
            type: duckdb
            database: "{{ env_var('UNUSED_DB') }}"
        execution:
          adapters:
            duckdb:
              managed-memory: {mib: 2048}
          connections:
            legacy:
              managed-memory: auto
            warehouse:
              managed-memory: auto
            unused:
              managed-memory: {percent: 999}
      prod:
        connections:
          legacy:
            type: duckdb
            database: "{{ env_var('PROD_DB') }}"
        execution:
          adapters:
            duckdb:
              threads: PRIVATE_SENTINEL
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile_for_connection_names(
        context_result.context,
        referenced_connection_names=("legacy", "warehouse"),
        environ={"DB_PATH": "private.duckdb"},
    )

    assert result.succeeded
    assert result.profile is not None
    assert set(result.profile.connections) == {"legacy", "warehouse"}
    for connection in result.profile.connections.values():
        assert connection.config == {"type": "duckdb", "database": "private.duckdb"}
    assert result.diagnostics == ()


@pytest.mark.regression_capture("local-resource-config-strict-validation")
def test_selected_target_rejects_duckdb_policy_for_non_duckdb_connection(tmp_path: Path) -> None:
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
          warehouse:
            type: snowflake
            account: PRIVATE_SENTINEL
        execution:
          connections:
            warehouse:
              managed-memory: {percent: 75}
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile_for_connection_names(
        context_result.context,
        referenced_connection_names=("warehouse",),
        environ={},
    )

    assert not result.succeeded
    assert result.profile is None
    assert result.diagnostics[0].code == "RC_CONFIG_INVALID_PROFILE_CONFIG"
    assert "PRIVATE_SENTINEL" not in repr(result.diagnostics)


@pytest.mark.regression_capture("local-resource-config-strict-validation")
def test_selected_target_resolves_scoped_resource_policy_precedence(tmp_path: Path) -> None:
    write_project(tmp_path)
    project = tmp_path / "recon_project.yml"
    project.write_text(
        project.read_text(encoding="utf-8")
        + """
execution:
  adapters:
    duckdb:
      managed-memory: {percent: 75}
      spill: {mib: 4096}
      threads: 8
      max-database-mib: 1024
      warn-estimated-input-rows: 50000
""",
        encoding="utf-8",
    )
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy: {type: duckdb, database: private.duckdb}
          warehouse: {type: duckdb, database: private.duckdb}
          other: {type: duckdb, database: other.duckdb}
        execution:
          adapters:
            duckdb:
              managed-memory: {mib: 2048}
              spill: {percent: 80}
          connections:
            legacy:
              managed-memory: auto
              threads: auto
              max-database-mib: none
              warn-estimated-input-rows: none
            warehouse:
              managed-memory: {percent: 60}
              spill: auto
""",
    )
    context_result = load_project_context(tmp_path)
    assert context_result.succeeded
    assert context_result.context is not None

    result = load_selected_profile_for_connection_names(
        context_result.context,
        referenced_connection_names=("legacy", "warehouse", "other"),
        environ={},
    )

    assert result.succeeded
    assert result.profile is not None
    legacy_config = result.profile.connections["legacy"].config
    warehouse_config = result.profile.connections["warehouse"].config
    assert legacy_config == warehouse_config
    policies = result.profile._execution_policies
    assert set(policies) == {"legacy", "warehouse", "other"}

    legacy = policies["legacy"]
    assert legacy.managed_memory_bytes is None
    assert legacy.managed_memory_percent is None
    assert legacy.spill_bytes is None
    assert legacy.spill_percent == 80
    assert legacy.threads is None
    assert legacy.max_database_bytes is None
    assert legacy.warn_estimated_input_rows is None

    warehouse = policies["warehouse"]
    assert warehouse.managed_memory_bytes is None
    assert warehouse.managed_memory_percent == 60
    assert warehouse.spill_bytes is None
    assert warehouse.spill_percent is None
    assert warehouse.threads == 8
    assert warehouse.max_database_bytes == 1024 * (1 << 20)
    assert warehouse.warn_estimated_input_rows == 50000

    other = policies["other"]
    assert other.managed_memory_bytes == 2048 * (1 << 20)
    assert other.managed_memory_percent is None
    assert other.spill_bytes is None
    assert other.spill_percent == 80
    assert other.threads == 8

    def facts(policy: _LocalResourcePolicy) -> dict[str, tuple[str, str, int | None]]:
        return {
            fact.setting: (fact.scope.value, fact.mode.value, fact.requested_value)
            for fact in policy._setting_facts
        }

    assert facts(legacy) == {
        "managed-memory": ("connection", "auto", None),
        "threads": ("connection", "auto", None),
        "spill": ("target", "percent", 80),
        "max-database-mib": ("connection", "none", None),
        "warn-estimated-input-rows": ("connection", "none", None),
        "scratch-directory": ("default", "auto", None),
    }
    assert facts(warehouse)["managed-memory"] == ("connection", "percent", 60)
    assert facts(warehouse)["spill"] == ("connection", "auto", None)
    assert facts(warehouse)["threads"] == ("project", "fixed", 8)
    assert facts(other)["managed-memory"] == ("target", "fixed", 2048 * (1 << 20))
    assert facts(other)["max-database-mib"] == ("project", "fixed", 1024 * (1 << 20))
    assert "private.duckdb" not in repr(legacy._setting_facts)
    assert legacy == _LocalResourcePolicy(spill_percent=80)
