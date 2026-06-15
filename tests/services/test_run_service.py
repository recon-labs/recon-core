import importlib
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from recon_core.adapters import (
    ADAPTER_API_VERSION,
    AdapterCapabilities,
    AdapterRegistry,
    AdapterResolutionResult,
    BaseAdapter,
    CapabilitySupport,
    ColumnMetadata,
    ConnectionConfig,
    QueryResult,
    Relation,
)
from recon_core.adapters.duckdb import (
    ADAPTER_CLOSE_FAILED,
    ADAPTER_CONNECTION_FAILED,
    ADAPTER_QUERY_FAILED,
)
from recon_core.artifacts import LoadedCompiledChecksArtifact
from recon_core.check_engine import (
    CheckExecutionContext,
    CheckResult,
    CheckStatus,
    ContractResult,
    RunResult,
)
from recon_core.services import RunService
from recon_core.services.results import ExitCategory


def test_run_service_reports_missing_compiled_artifacts(tmp_path: Path) -> None:
    write_project(tmp_path)

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compiled-check artifacts could not be loaded."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND"
    ]
    assert not (tmp_path / "target" / "run_results.json").exists()
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "state").exists()


def test_run_service_loads_compiled_checks_and_returns_not_executable_status(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MISSING_ENGINE_CAPABILITY"
    ]
    assert "row_count" in result.diagnostics[0].message
    assert not (tmp_path / "target" / "run_results.json").exists()
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "state").exists()


def test_run_service_does_not_mutate_preexisting_run_outputs(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    output_contents = {
        tmp_path / "target" / "run_results.json": '{"status":"stale"}\n',
        tmp_path / "target" / "failures" / "existing.csv": "id\n1\n",
        tmp_path / "reports" / "existing.md": "# stale report\n",
        tmp_path / "state" / "existing.json": '{"watermark":"stale"}\n',
    }
    for path, content in output_contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    for path, content in output_contents.items():
        assert path.read_text(encoding="utf-8") == content


def test_run_service_uses_compiled_artifacts_without_parsing_authored_contracts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)
    contract_path = tmp_path / "contracts" / "customer_revenue.yml"
    contract_path.parent.mkdir()
    contract_path.write_text(
        "version: 1\nsource:\n  query: select * from t where ssn: secret\n",
        encoding="utf-8",
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MISSING_ENGINE_CAPABILITY"
    ]
    assert "secret" not in "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )


def test_run_service_reports_empty_compiled_check_scope(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path, checks=[])

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "No compiled checks are available."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_NO_COMPILED_CHECKS"
    ]


def test_run_service_runs_valid_artifacts_when_another_artifact_has_empty_checks(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path, contract_name="valid_contract")
    write_compiled_contract(tmp_path, contract_name="valid_contract")
    write_compiled_checks(
        tmp_path,
        contract_name="empty_contract",
        checks=[],
        diagnostics=[
            {
                "code": "RC_VALIDATE_NO_COMPILED_CHECKS",
                "severity": "error",
                "message": "Contract does not compile into any checks.",
                "resource_type": "contract",
                "resource_name": "empty_contract",
                "path": "contracts/empty_contract.yml",
                "line": None,
                "column": None,
                "hint": "Add a supported check pack or metric.",
            }
        ],
    )
    write_compiled_contract(tmp_path, contract_name="empty_contract")

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_NO_COMPILED_CHECKS",
        "RC_RUNTIME_MISSING_ENGINE_CAPABILITY",
    ]


def test_run_service_maps_engine_check_failure_to_check_failure_exit(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)

    result = RunService(start_path=tmp_path, engine=_FailingEngine()).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert result.message == "Run completed with failing checks."
    assert result.diagnostics == ()


def test_run_service_sanitizes_engine_boundary_exception(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_compiled_checks(tmp_path)
    write_compiled_contract(tmp_path)

    result = RunService(start_path=tmp_path, engine=_RaisingEngine()).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during check-engine evaluation."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR"
    ]
    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )
    assert "super-secret" not in diagnostic_text
    assert "traceback" not in diagnostic_text.lower()


def test_run_service_executes_row_count_with_runtime_profile_and_adapter_context(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
          unused:
            type: duckdb
            database: "{{ env_var('UNUSED_DB') }}"
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        result=QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((12, 12, 0),),
            row_count=1,
        )
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert result.diagnostics == ()
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    assert not (tmp_path / "target" / "run_results.json").exists()
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize(
    ("rendering_status", "diagnostic_code"),
    [
        ("blocked", "RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS"),
        ("failed", "RC_ADAPTER_OPERATION_RENDER_FAILED"),
    ],
)
def test_run_service_blocks_row_count_with_blocked_or_failed_compiled_rendering_status(
    tmp_path: Path,
    rendering_status: str,
    diagnostic_code: str,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(
                operations=row_count_plan(),
                rendering={"status": rendering_status, "sql_paths": []},
                diagnostics=[
                    {
                        "code": diagnostic_code,
                        "severity": "error",
                        "message": (
                            f"SQL rendering for check `row_count_diff` was {rendering_status}."
                        ),
                        "resource_type": "compiled_check",
                        "resource_name": "check.ecommerce_recon.customer_revenue.row_count_diff",
                        "path": None,
                        "line": None,
                        "column": None,
                        "hint": (
                            "Fix the compile diagnostics and rerun `recon compile --render-sql`."
                        ),
                    }
                ],
            )
        ],
    )
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during check-engine evaluation."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [diagnostic_code]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize(
    ("rendering_status", "diagnostic_code"),
    [
        ("blocked", "RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS"),
        ("failed", "RC_ADAPTER_OPERATION_RENDER_FAILED"),
    ],
)
def test_run_service_blocks_key_safety_with_blocked_or_failed_compiled_rendering_status(
    tmp_path: Path,
    rendering_status: str,
    diagnostic_code: str,
) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(
        tmp_path,
        checks=[
            _key_safety_check_payload(
                rendering={"status": rendering_status, "sql_paths": []},
                diagnostics=[
                    {
                        "code": diagnostic_code,
                        "severity": "error",
                        "message": (
                            f"SQL rendering for check `missing_keys` was {rendering_status}."
                        ),
                        "resource_type": "compiled_check",
                        "resource_name": "check.ecommerce_recon.customer_revenue.missing_keys",
                        "path": None,
                        "line": None,
                        "column": None,
                        "hint": (
                            "Fix the compile diagnostics and rerun `recon compile --render-sql`."
                        ),
                    }
                ],
            )
        ],
    )
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during check-engine evaluation."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [diagnostic_code]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_row_count_with_actual_duckdb_relations_pass(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_row_count_tables(
        duckdb,
        database,
        source_rows=((1,), (2,), (3,)),
        target_rows=((10,), (20,), (30,)),
    )
    write_duckdb_row_count_run_inputs(tmp_path, database)

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert result.diagnostics == ()
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_row_count_with_actual_duckdb_relations_fail(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_row_count_tables(
        duckdb,
        database,
        source_rows=((1,), (2,)),
        target_rows=((10,), (20,), (30,)),
    )
    write_duckdb_row_count_run_inputs(tmp_path, database)

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert result.message == "Run completed with failing checks."
    assert result.diagnostics == ()
    public_text = _service_result_text(result)
    assert "2" not in public_text
    assert "3" not in public_text
    assert "-1" not in public_text
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_sanitizes_actual_duckdb_execution_failure(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_row_count_tables(
        duckdb,
        database,
        source_rows=((1,),),
        target_rows=(),
        create_target=False,
    )
    write_duckdb_row_count_run_inputs(tmp_path, database)

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during check-engine evaluation."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [ADAPTER_QUERY_FAILED]
    public_text = _service_result_text(result)
    assert "DuckDB query execution failed." in public_text
    assert "target_customers" not in public_text
    assert "source_customers" not in public_text
    assert "select" not in public_text.lower()
    assert "count" not in public_text.lower()
    assert "Catalog Error" not in public_text
    assert str(database) not in public_text
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_key_safety_with_runtime_profile_and_adapter_context(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
          unused:
            type: duckdb
            database: "{{ env_var('UNUSED_DB') }}"
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        result=QueryResult(columns=("failure_count",), rows=((0,),), row_count=1)
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert result.diagnostics == ()
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    assert "failure_count" in adapter.queries[0]
    assert "UNUSED_DB" not in _service_result_text(result)
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_key_safety_failure_without_raw_key_output(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(
        tmp_path,
        checks=[
            _key_safety_check_payload(
                check_id="check.ecommerce_recon.customer_revenue.duplicate_source_keys",
                name="duplicate_source_keys",
                check_type="duplicate_source_keys",
                operations=[_duplicate_key_operation("source")],
                required_capabilities=["duplicate_key"],
            )
        ],
    )
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        result=QueryResult(columns=("failure_count",), rows=((2,),), row_count=1)
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert result.message == "Run completed with failing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_DUPLICATE_GRAIN_KEYS"
    ]
    public_text = _service_result_text(result)
    assert "customer_id" not in public_text
    assert "raw key" in public_text.lower()
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_blocks_query_endpoints_before_adapter_execution(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(
        tmp_path,
        source_relation=None,
        source_query="select * from source_customers where ssn = 'secret-ssn'",
    )
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"
    ]
    public_text = _service_result_text(result)
    assert "secret-ssn" not in public_text
    assert "select * from source_customers" not in public_text
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_blocks_key_safety_query_endpoints_before_adapter_query(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(
        tmp_path,
        source_relation=None,
        source_query="select customer_id from source_customers where ssn = 'secret-ssn'",
    )
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"
    ]
    public_text = _service_result_text(result)
    assert "secret-ssn" not in public_text
    assert "select customer_id" not in public_text
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_blocks_cross_context_duckdb_execution_without_bridge_or_fallback(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: source.duckdb
          replica:
            type: duckdb
            database: target.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(
        tmp_path,
        source_connection="warehouse",
        target_connection="replica",
    )
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"
    ]
    public_text = _service_result_text(result)
    assert "source.duckdb" not in public_text
    assert "target.duckdb" not in public_text
    assert len(factory.adapters) == 2
    assert [adapter.connect_count for adapter in factory.adapters] == [0, 0]
    assert [adapter.queries for adapter in factory.adapters] == [[], []]
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_blocks_key_safety_cross_context_without_bridge_or_fallback(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: source.duckdb
          replica:
            type: duckdb
            database: target.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(
        tmp_path,
        source_connection="warehouse",
        target_connection="replica",
    )
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"
    ]
    public_text = _service_result_text(result)
    assert "source.duckdb" not in public_text
    assert "target.duckdb" not in public_text
    assert len(factory.adapters) == 2
    assert [adapter.connect_count for adapter in factory.adapters] == [0, 0]
    assert [adapter.queries for adapter in factory.adapters] == [[], []]
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_blocks_different_adapter_types_without_bridge_or_fallback(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
          replica:
            type: warehouse_test
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(
        tmp_path,
        source_connection="warehouse",
        target_connection="replica",
    )
    duckdb_factory = RecordingDuckDbFactory()
    other_factory = RecordingWarehouseFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", duckdb_factory)
    registry.register("warehouse_test", other_factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"
    ]
    assert len(duckdb_factory.adapters) == 1
    assert len(other_factory.adapters) == 1
    assert duckdb_factory.adapters[0].connect_count == 0
    assert other_factory.adapters[0].connect_count == 0
    assert duckdb_factory.adapters[0].queries == []
    assert other_factory.adapters[0].queries == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_row_count_for_same_context_duckdb_aliases(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
          replica:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(
        tmp_path,
        source_connection="warehouse",
        target_connection="replica",
    )
    factory = RecordingDuckDbFactory(
        result=QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((12, 12, 0),),
            row_count=1,
        )
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert result.diagnostics == ()
    assert sum(adapter.connect_count for adapter in factory.adapters) == 1
    assert sum(adapter.close_count for adapter in factory.adapters) == 1
    assert sum(len(adapter.queries) for adapter in factory.adapters) == 1
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_row_count_with_explicit_no_materialization_policy(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    operations = [
        {"type": "row_count", "side": "source", "materialization_policy": "none"},
        {"type": "row_count", "side": "target", "materialization_policy": "none"},
        {"type": "compare_counts", "materialization_policy": "none"},
    ]
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=operations)])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert result.diagnostics == ()
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize(
    ("operations", "diagnostic_code"),
    [
        (
            [
                {"type": "row_count", "side": "source", "execution_placement": "source"},
                {"type": "row_count", "side": "target"},
                {"type": "compare_counts"},
            ],
            "RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT",
        ),
        (
            [
                {
                    "type": "row_count",
                    "side": "source",
                    "materialization_policy": "temporary_table",
                },
                {"type": "row_count", "side": "target"},
                {"type": "compare_counts"},
            ],
            "RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY",
        ),
    ],
)
def test_run_service_blocks_unsupported_placement_or_materialization_before_adapter_setup(
    tmp_path: Path,
    operations: list[dict[str, object]],
    diagnostic_code: str,
) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=operations)])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [diagnostic_code]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_valid_row_count_and_key_safety_checks(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(operations=row_count_plan()),
            _key_safety_check_payload(),
        ],
    )
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        results=(
            QueryResult(
                columns=("source_row_count", "target_row_count", "row_count_diff"),
                rows=((4, 4, 0),),
                row_count=1,
            ),
            QueryResult(columns=("failure_count",), rows=((0,),), row_count=1),
        )
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert result.diagnostics == ()
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 2
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_does_not_mutate_stale_outputs_during_executable_row_count(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    output_contents = {
        tmp_path / "target" / "run_results.json": '{"status":"stale"}\n',
        tmp_path / "target" / "failures" / "existing.csv": "id\n1\n",
        tmp_path / "target" / "compiled_sql" / "existing.sql": "select 1;\n",
        tmp_path / "reports" / "existing.md": "# stale report\n",
        tmp_path / "state" / "existing.json": '{"watermark":"stale"}\n',
    }
    for path, content in output_contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert result.diagnostics == ()
    for path, content in output_contents.items():
        assert path.read_text(encoding="utf-8") == content


def test_run_service_reports_missing_compiled_contract_before_profile_or_adapter_work(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compiled-contract artifacts could not be loaded."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND"
    ]
    assert factory.adapters == []


def test_run_service_reports_referenced_profile_diagnostic_before_adapter_resolution(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: "{{ env_var('WAREHOUSE_DB') }}"
          unused:
            type: duckdb
            database: "{{ env_var('UNUSED_DB') }}"
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run profile configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_PROFILE_ENV_VAR_MISSING"
    ]
    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"
    assert "WAREHOUSE_DB" in diagnostic_text
    assert "UNUSED_DB" not in diagnostic_text
    assert factory.adapters == []


def test_run_service_ignores_unsupported_later_phase_contract_profile_env(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
          later_phase:
            type: duckdb
            database: "{{ env_var('LATER_PHASE_DB') }}"
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    write_compiled_checks(
        tmp_path,
        contract_name="later_phase_contract",
        checks=[
            _compiled_check_payload(
                check_id="check.ecommerce_recon.later_phase_contract.sum_diff",
                name="sum_diff",
                check_type="sum_diff",
                operations=[
                    {
                        "type": "aggregate",
                        "side": "source",
                        "aggregate": "sum",
                        "column": "revenue",
                    },
                    {
                        "type": "aggregate",
                        "side": "target",
                        "aggregate": "sum",
                        "column": "revenue",
                    },
                    {"type": "compare_aggregates"},
                ],
                required_capabilities=[],
            )
        ],
    )
    write_compiled_contract(
        tmp_path,
        contract_name="later_phase_contract",
        source_connection="later_phase",
        target_connection="later_phase",
    )
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_CHECK_NOT_EXECUTABLE"
    ]
    assert "LATER_PHASE_DB" not in _service_result_text(result)
    assert len(factory.adapters) == 1
    adapter = factory.adapters[0]
    assert adapter.connection.name == "warehouse"
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_requires_key_safety_capability_before_connect(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities({"cte_support": CapabilitySupport.FULL})
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "key_diff" in result.diagnostics[0].message
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []


def test_run_service_blocks_key_safety_scan_budget_for_non_local_adapter(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: warehouse_test
            database: warehouse
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path)
    factory = RecordingWarehouseFactory(
        capabilities=AdapterCapabilities(
            {
                "key_diff": CapabilitySupport.FULL,
                "cte_support": CapabilitySupport.FULL,
            }
        )
    )
    registry = AdapterRegistry()
    registry.register("warehouse_test", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_SCAN_ESTIMATE_UNKNOWN"
    ]
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_reports_adapter_setup_failure_before_connect(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities({"row_count": CapabilitySupport.FULL})
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "cte_support" in result.diagnostics[0].message
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []


def test_run_service_requires_row_count_capability_even_if_compiled_artifact_omits_it(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(
        tmp_path,
        checks=[_compiled_check_payload(operations=row_count_plan(), required_capabilities=[])],
    )
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities({"cte_support": CapabilitySupport.FULL})
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "row_count" in result.diagnostics[0].message
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []


def test_run_service_reports_connect_failure_without_engine_execution(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
            password: super-secret
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        connect_error=RuntimeError("password=super-secret database=warehouse.duckdb")
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run adapter connection failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [ADAPTER_CONNECTION_FAILED]
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 0
    assert adapter.queries == []


def test_run_service_reports_close_failure_after_success(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
            password: super-secret
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(close_error=RuntimeError("close leaked password=super-secret"))
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during adapter lifecycle cleanup."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [ADAPTER_CLOSE_FAILED]
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1


def test_run_service_preserves_execution_failure_when_close_also_fails(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
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
            type: duckdb
            database: warehouse.duckdb
            password: super-secret
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        execute_error=RuntimeError("query leaked password=super-secret"),
        close_error=RuntimeError("close leaked password=super-secret"),
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during check-engine evaluation."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        ADAPTER_QUERY_FAILED,
        ADAPTER_CLOSE_FAILED,
    ]
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1


def write_project(path: Path, *, profile: str | None = None) -> None:
    profile_line = f"profile: {profile}\n" if profile is not None else ""
    (path / "recon_project.yml").write_text(
        f"""
name: ecommerce_recon
version: 0.1.0
config-version: 1
{profile_line}\
contract-paths:
  - contracts
target-path: target
report-path: reports
state-path: state
""".lstrip(),
        encoding="utf-8",
    )


def write_profiles(path: Path, content: str) -> None:
    profiles_path = path / "connections" / "profiles.yml"
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_path.write_text(content.lstrip(), encoding="utf-8")


def write_duckdb_row_count_run_inputs(path: Path, database: Path) -> None:
    write_project(path, profile="local")
    write_profiles(
        path,
        yaml.safe_dump(
            {
                "profiles": {
                    "local": {
                        "target": "dev",
                        "outputs": {
                            "dev": {
                                "connections": {
                                    "warehouse": {
                                        "type": "duckdb",
                                        "database": str(database),
                                    }
                                }
                            }
                        },
                    }
                }
            },
            sort_keys=False,
        ),
    )
    write_compiled_checks(path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(path)


def write_compiled_checks(
    path: Path,
    *,
    contract_name: str = "customer_revenue",
    checks: list[dict[str, object]] | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> None:
    artifact_path = path / "target" / "compiled_checks" / f"{contract_name}.yml"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        yaml.safe_dump(
            _compiled_checks_payload(
                contract_name=contract_name,
                checks=checks,
                diagnostics=diagnostics,
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_compiled_contract(
    path: Path,
    *,
    contract_name: str = "customer_revenue",
    source_connection: str = "warehouse",
    target_connection: str = "warehouse",
    source_relation: str | None = "qa.source_customers",
    target_relation: str | None = "qa.target_customers",
    source_query: str | None = None,
    target_query: str | None = None,
) -> None:
    artifact_path = path / "target" / "compiled_contracts" / f"{contract_name}.yml"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        yaml.safe_dump(
            _compiled_contract_payload(
                contract_name=contract_name,
                source_connection=source_connection,
                target_connection=target_connection,
                source_relation=source_relation,
                target_relation=target_relation,
                source_query=source_query,
                target_query=target_query,
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )


class _FailingEngine:
    def run(
        self,
        artifacts: tuple[LoadedCompiledChecksArtifact, ...],
        *,
        run_id: str,
        started_at: str,
        finished_at: str,
        project_name: str | None = None,
        execution_context: CheckExecutionContext | None = None,
    ) -> RunResult:
        check_result = CheckResult(
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            name="row_count_diff",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=CheckStatus.FAIL,
            executed=True,
            source_value=10,
            target_value=11,
        )
        contract_result = ContractResult.from_check_results(
            contract_name="customer_revenue",
            check_results=(check_result,),
        )
        return RunResult.from_contract_results(
            run_id=run_id,
            project_name=project_name or artifacts[0].project_name,
            started_at=started_at,
            finished_at=finished_at,
            contract_results=(contract_result,),
        )


class _RaisingEngine:
    def run(
        self,
        artifacts: tuple[LoadedCompiledChecksArtifact, ...],
        *,
        run_id: str,
        started_at: str,
        finished_at: str,
        project_name: str | None = None,
        execution_context: CheckExecutionContext | None = None,
    ) -> RunResult:
        raise RuntimeError("super-secret database error")


def _compiled_checks_payload(
    *,
    contract_name: str = "customer_revenue",
    checks: list[dict[str, object]] | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "artifact_type": "compiled_checks",
        "artifact_version": 1,
        "recon_version": "0.0.test",
        "generated_at": "2026-05-23T12:00:00Z",
        "invocation_id": "01JTESTINVOCATION0000000000",
        "project": {"name": "ecommerce_recon", "version": "0.1.0"},
        "contract": {
            "id": f"contract.ecommerce_recon.{contract_name}",
            "name": contract_name,
            "source_file": f"contracts/{contract_name}.yml",
        },
        "checks": checks if checks is not None else [_compiled_check_payload()],
        "diagnostics": diagnostics if diagnostics is not None else [],
    }


def _compiled_check_payload(
    *,
    check_id: str = "check.ecommerce_recon.customer_revenue.row_count_diff",
    name: str = "row_count_diff",
    check_type: str = "row_count_diff",
    operations: list[dict[str, object]] | None = None,
    required_capabilities: list[str] | None = None,
    rendering: dict[str, object] | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    resolved_required_capabilities = (
        required_capabilities if required_capabilities is not None else ["row_count"]
    )
    return {
        "id": check_id,
        "name": name,
        "type": check_type,
        "origin": {"kind": "check_pack", "name": "recon_core.basic_equivalence"},
        "identity": {"kind": "none", "keys": []},
        "requirements": {
            "requires_grain_keys": False,
            "requires_non_null_grain": False,
            "requires_unique_grain": False,
            "requires_cdc_keys": False,
            "required_columns": [],
            "required_metrics": [],
            "required_capabilities": resolved_required_capabilities,
        },
        "sampling": {"mode": "full"},
        "tolerance": None,
        "prerequisites": [],
        "blocking_policy": {"on_prerequisite_failure": "skipped"},
        "plan": {
            "id": f"plan.ecommerce_recon.customer_revenue.{name}",
            "operations": operations
            if operations is not None
            else [{"type": "row_count", "side": "source"}],
            "required_capabilities": resolved_required_capabilities,
        },
        "rendering": rendering
        if rendering is not None
        else {"status": "not_rendered", "sql_paths": []},
        "diagnostics": diagnostics if diagnostics is not None else [],
    }


def _compiled_contract_payload(
    *,
    contract_name: str,
    source_connection: str,
    target_connection: str,
    source_relation: str | None,
    target_relation: str | None,
    source_query: str | None = None,
    target_query: str | None = None,
) -> dict[str, object]:
    source: dict[str, object] = {"connection": source_connection}
    if source_relation is not None:
        source["relation"] = source_relation
    if source_query is not None:
        source["query"] = source_query
    target: dict[str, object] = {"connection": target_connection}
    if target_relation is not None:
        target["relation"] = target_relation
    if target_query is not None:
        target["query"] = target_query
    return {
        "artifact_type": "compiled_contract",
        "artifact_version": 1,
        "recon_version": "0.0.test",
        "generated_at": "2026-05-23T12:00:00Z",
        "invocation_id": "01JTESTINVOCATION0000000000",
        "project": {"name": "ecommerce_recon", "version": "0.1.0"},
        "contract": {
            "id": f"contract.ecommerce_recon.{contract_name}",
            "name": contract_name,
            "source_file": f"contracts/{contract_name}.yml",
        },
        "identity": {"grain": {"keys": []}, "cdc": {"keys": []}},
        "source": source,
        "target": target,
        "columns": [],
        "metrics": [],
        "checks": [],
        "diagnostics": [],
    }


def row_count_plan() -> list[dict[str, object]]:
    return [
        {"type": "row_count", "side": "source"},
        {"type": "row_count", "side": "target"},
        {"type": "compare_counts"},
    ]


def _key_safety_check_payload(
    *,
    check_id: str = "check.ecommerce_recon.customer_revenue.missing_keys",
    name: str = "missing_keys",
    check_type: str = "missing_keys",
    operations: list[dict[str, object]] | None = None,
    required_capabilities: list[str] | None = None,
    rendering: dict[str, object] | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    resolved_operations = (
        operations
        if operations is not None
        else [_key_diff_operation("source_minus_target")]
    )
    resolved_required_capabilities = (
        required_capabilities if required_capabilities is not None else ["key_diff"]
    )
    return _compiled_check_payload(
        check_id=check_id,
        name=name,
        check_type=check_type,
        operations=resolved_operations,
        required_capabilities=resolved_required_capabilities,
        rendering=rendering,
        diagnostics=diagnostics,
    )


def _key_diff_operation(direction: str) -> dict[str, object]:
    return {
        "type": "key_diff",
        "direction": direction,
        "identity": {"kind": "grain", "keys": ["customer_id"]},
    }


def _duplicate_key_operation(side: str) -> dict[str, object]:
    return {
        "type": "duplicate_key",
        "side": side,
        "identity": {"kind": "grain", "keys": ["customer_id"]},
    }


def _duckdb_module() -> Any:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            return importlib.import_module("duckdb")
        except ImportError:
            pytest.fail(
                "DuckDB run-service execution tests are required in this environment. "
                "Install with `.[dev,duckdb]`.",
                pytrace=False,
            )

    return pytest.importorskip("duckdb")


def _write_duckdb_row_count_tables(
    duckdb: Any,
    database: Path,
    *,
    source_rows: tuple[tuple[int], ...],
    target_rows: tuple[tuple[int], ...],
    create_target: bool = True,
) -> None:
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create schema qa")
        connection.execute("create table qa.source_customers(id integer)")
        if source_rows:
            connection.executemany("insert into qa.source_customers values (?)", source_rows)
        if create_target:
            connection.execute("create table qa.target_customers(id integer)")
            if target_rows:
                connection.executemany("insert into qa.target_customers values (?)", target_rows)
    finally:
        connection.close()


def _assert_no_runtime_outputs(path: Path) -> None:
    assert not (path / "target" / "run_results.json").exists()
    assert not (path / "target" / "failures").exists()
    assert not (path / "target" / "compiled_sql").exists()
    assert not (path / "reports").exists()
    assert not (path / "state").exists()


def _service_result_text(result: object) -> str:
    fields: list[str] = []
    message = getattr(result, "message", None)
    if message is not None:
        fields.append(str(message))
    for diagnostic in getattr(result, "diagnostics", ()):
        fields.extend(
            str(value)
            for value in (
                diagnostic.code,
                diagnostic.message,
                diagnostic.hint,
                diagnostic.resource_type,
                diagnostic.resource_name,
                diagnostic.path,
                diagnostic.line,
                diagnostic.column,
            )
            if value is not None
        )
    return "\n".join(fields)


class RecordingDuckDbFactory:
    def __init__(
        self,
        *,
        result: QueryResult | None = None,
        results: tuple[QueryResult, ...] | None = None,
        capabilities: AdapterCapabilities | None = None,
        connect_error: Exception | None = None,
        execute_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.result = result
        self.results = results
        self.capabilities = capabilities
        self.connect_error = connect_error
        self.execute_error = execute_error
        self.close_error = close_error
        self.adapters: list[RecordingDuckDbAdapter] = []

    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        adapter = RecordingDuckDbAdapter(
            connection=connection,
            result=self.result,
            results=self.results,
            capabilities=self.capabilities,
            connect_error=self.connect_error,
            execute_error=self.execute_error,
            close_error=self.close_error,
        )
        self.adapters.append(adapter)
        return AdapterResolutionResult(adapter=adapter)


class RecordingWarehouseFactory:
    def __init__(self, *, capabilities: AdapterCapabilities | None = None) -> None:
        self.capabilities = capabilities
        self.adapters: list[RecordingWarehouseAdapter] = []

    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        adapter = RecordingWarehouseAdapter(
            connection=connection,
            result=None,
            results=None,
            capabilities=self.capabilities,
            connect_error=None,
            execute_error=None,
            close_error=None,
        )
        self.adapters.append(adapter)
        return AdapterResolutionResult(adapter=adapter)


class RecordingDuckDbAdapter(BaseAdapter):
    adapter_type = "duckdb"
    adapter_version = "test"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def __init__(
        self,
        *,
        connection: ConnectionConfig,
        result: QueryResult | None,
        results: tuple[QueryResult, ...] | None,
        capabilities: AdapterCapabilities | None,
        connect_error: Exception | None,
        execute_error: Exception | None,
        close_error: Exception | None,
    ) -> None:
        super().__init__(connection=connection)
        default_result = result or QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((1, 1, 0),),
            row_count=1,
        )
        self.results = list(results) if results is not None else [default_result]
        self._capabilities = capabilities or AdapterCapabilities(
            {
                "row_count": CapabilitySupport.FULL,
                "cte_support": CapabilitySupport.FULL,
                "key_diff": CapabilitySupport.FULL,
                "null_key": CapabilitySupport.FULL,
                "duplicate_key": CapabilitySupport.FULL,
            }
        )
        self.connect_error = connect_error
        self.execute_error = execute_error
        self.close_error = close_error
        self.connect_count = 0
        self.close_count = 0
        self.connected = False
        self.queries: list[str] = []

    def connect(self) -> None:
        self.connect_count += 1
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True

    def close(self) -> None:
        self.close_count += 1
        if self.close_error is not None:
            raise self.close_error
        self.connected = False

    def execute(self, query: str) -> QueryResult:
        self.queries.append(query)
        if self.execute_error is not None:
            raise self.execute_error
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]

    def relation_exists(self, relation: Relation) -> bool:
        return False

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        return ()

    def capabilities(self) -> AdapterCapabilities:
        return self._capabilities


class RecordingWarehouseAdapter(RecordingDuckDbAdapter):
    adapter_type = "warehouse_test"
