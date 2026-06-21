from pathlib import Path

import pytest

import recon_core.adapters.duckdb.runtime_scan_guard as duckdb_scan_guard_module
from recon_core.adapters import (
    AdapterCapabilities,
    AdapterRegistry,
    CapabilitySupport,
    QueryResult,
)
from recon_core.adapters.duckdb import (
    ADAPTER_QUERY_FAILED,
)
from recon_core.services import RunService
from recon_core.services.results import ExitCategory
from tests.services._run_service_fixtures import (
    BOUNDED_LOCAL_SCAN_ALLOWED,
    BOUNDED_LOCAL_SCAN_REQUIRED,
    RecordingDuckDbFactory,
    RecordingWarehouseFactory,
    _all_key_safety_checks,
    _assert_no_runtime_outputs,
    _compiled_check_payload,
    _duckdb_module,
    _duplicate_key_operation,
    _key_diff_operation,
    _key_safety_check_payload,
    _key_safety_payload_for,
    _service_result_text,
    _write_duckdb_key_safety_tables,
    _write_duckdb_row_count_tables,
    _write_mixed_case_duckdb_key_safety_tables,
    row_count_plan,
    write_bounded_local_duckdb_fixture,
    write_compiled_checks,
    write_compiled_contract,
    write_duckdb_key_safety_run_inputs,
    write_duckdb_row_count_run_inputs,
    write_profiles,
    write_project,
)


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


def test_run_service_executes_actual_duckdb_key_safety_all_checks_pass(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=((1, "north"), (2, "south")),
        target_rows=((1, "north"), (2, "south")),
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=_all_key_safety_checks(keys=("customer_id", "region")),
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_ALLOWED]
    public_text = _service_result_text(result)
    assert "north" not in public_text
    assert "south" not in public_text
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("key-safety-duckdb-local-database-filename-suffix")
def test_run_service_allows_key_safety_duckdb_local_database_without_duckdb_suffix(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.db"
    _write_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=((1, "north"), (2, "south")),
        target_rows=((1, "north"), (2, "south")),
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=_all_key_safety_checks(keys=("customer_id", "region")),
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_ALLOWED]
    public_text = _service_result_text(result)
    assert "north" not in public_text
    assert "south" not in public_text
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("key-safety-duckdb-identifier-case-metadata")
def test_run_service_allows_key_safety_duckdb_base_table_metadata_case_mismatch(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_mixed_case_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=((1, "north"),),
        target_rows=((1, "north"),),
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=_all_key_safety_checks(keys=("customer_id", "region")),
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_ALLOWED]
    public_text = _service_result_text(result)
    assert "north" not in public_text
    assert "Source_Customers" not in public_text
    assert "Target_Customers" not in public_text
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("duckdb-view-external-scan-guard")
def test_run_service_blocks_key_safety_duckdb_view_over_external_file_before_adapter_setup(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    external_source = tmp_path / "external_source.csv"
    external_source.write_text("customer_id,region\n1,secret-external\n", encoding="utf-8")
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create schema qa")
        escaped_external_source = external_source.as_posix().replace("'", "''")
        connection.execute(
            "create view qa.source_customers as "
            f"select * from read_csv_auto('{escaped_external_source}')"
        )
        connection.execute("create table qa.target_customers(customer_id integer, region varchar)")
    finally:
        connection.close()
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=[_key_safety_payload_for("missing_keys", keys=("customer_id", "region"))],
    )
    factory = RecordingDuckDbFactory(
        result=QueryResult(columns=("failure_count",), rows=((0,),), row_count=1)
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_REQUIRED]
    public_text = _service_result_text(result)
    assert "secret-external" not in public_text
    assert "external_source" not in public_text
    assert "source_customers" not in public_text
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("duckdb-wal-sidecar-scan-guard")
def test_run_service_blocks_key_safety_duckdb_wal_sidecar_before_adapter_setup(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    live_directory = tmp_path / "live"
    live_directory.mkdir()
    live_database = live_directory / "warehouse.duckdb"
    database = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(live_database))
    try:
        connection.execute("set checkpoint_threshold='1GB'")
        connection.execute("create schema qa")
        connection.execute(
            "create table qa.source_customers as "
            "select i as customer_id, 'secret-wal' as region from range(1000) tbl(i)"
        )
        connection.execute(
            "create table qa.target_customers as "
            "select i as customer_id, 'secret-wal' as region from range(1000) tbl(i)"
        )
        for sidecar_source in live_directory.iterdir():
            (tmp_path / sidecar_source.name).write_bytes(sidecar_source.read_bytes())
    finally:
        connection.close()
    assert database.stat().st_size <= duckdb_scan_guard_module._MAX_BOUNDED_LOCAL_DUCKDB_BYTES
    assert (tmp_path / "warehouse.duckdb.wal").is_file()
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=[_key_safety_payload_for("missing_keys", keys=("customer_id", "region"))],
    )
    factory = RecordingDuckDbFactory(
        result=QueryResult(columns=("failure_count",), rows=((0,),), row_count=1)
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_REQUIRED]
    public_text = _service_result_text(result)
    assert "secret-wal" not in public_text
    assert "warehouse.duckdb.wal" not in public_text
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize(
    (
        "check_type",
        "source_rows",
        "target_rows",
        "expected_diagnostic",
        "forbidden_tokens",
    ),
    [
        (
            "null_source_keys",
            ((None, "secret-source-null"), (1, "shared")),
            ((1, "shared"),),
            "RC_RUNTIME_NULL_GRAIN_KEYS",
            ("secret-source-null", "customer_id", "region"),
        ),
        (
            "null_target_keys",
            ((1, "shared"),),
            ((None, "secret-target-null"), (1, "shared")),
            "RC_RUNTIME_NULL_GRAIN_KEYS",
            ("secret-target-null", "customer_id", "region"),
        ),
        (
            "duplicate_source_keys",
            ((7, "secret-source-duplicate"), (7, "secret-source-duplicate")),
            ((7, "secret-source-duplicate"),),
            "RC_RUNTIME_DUPLICATE_GRAIN_KEYS",
            ("secret-source-duplicate", "customer_id", "region"),
        ),
        (
            "duplicate_target_keys",
            ((8, "secret-target-duplicate"),),
            ((8, "secret-target-duplicate"), (8, "secret-target-duplicate")),
            "RC_RUNTIME_DUPLICATE_GRAIN_KEYS",
            ("secret-target-duplicate", "customer_id", "region"),
        ),
        (
            "missing_keys",
            ((11, "secret-source-only"), (11, "secret-source-only"), (None, "null-left")),
            ((12, "target-only"),),
            "RC_RUNTIME_MISSING_KEYS",
            ("secret-source-only", "null-left", "target-only", "customer_id", "region"),
        ),
        (
            "extra_keys",
            ((13, "source-only"),),
            ((14, "secret-target-only"), (14, "secret-target-only"), (None, "null-right")),
            "RC_RUNTIME_EXTRA_KEYS",
            ("source-only", "secret-target-only", "null-right", "customer_id", "region"),
        ),
    ],
)
def test_run_service_executes_actual_duckdb_key_safety_failures_without_raw_output(
    tmp_path: Path,
    check_type: str,
    source_rows: tuple[tuple[object, ...], ...],
    target_rows: tuple[tuple[object, ...], ...],
    expected_diagnostic: str,
    forbidden_tokens: tuple[str, ...],
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=source_rows,
        target_rows=target_rows,
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=[_key_safety_payload_for(check_type, keys=("customer_id", "region"))],
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert result.message == "Run completed with failing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        expected_diagnostic,
        BOUNDED_LOCAL_SCAN_ALLOWED,
    ]
    public_text = _service_result_text(result)
    for token in forbidden_tokens:
        assert token not in public_text
    assert "select" not in public_text.lower()
    assert "source_customers" not in public_text
    assert "target_customers" not in public_text
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_actual_duckdb_duplicate_plus_null_signals(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=(
            (None, "secret-null-candidate"),
            (None, "secret-null-candidate"),
            (21, "secret-duplicate"),
            (21, "secret-duplicate"),
        ),
        target_rows=((21, "secret-duplicate"),),
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=[
            _key_safety_payload_for("null_source_keys", keys=("customer_id", "region")),
            _key_safety_payload_for(
                "duplicate_source_keys",
                keys=("customer_id", "region"),
            ),
        ],
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert result.message == "Run completed with failing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_NULL_GRAIN_KEYS",
        BOUNDED_LOCAL_SCAN_ALLOWED,
        "RC_RUNTIME_DUPLICATE_GRAIN_KEYS",
    ]
    public_text = _service_result_text(result)
    assert "secret-null-candidate" not in public_text
    assert "secret-duplicate" not in public_text
    assert "customer_id" not in public_text
    assert "region" not in public_text
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize(
    ("source_rows", "target_rows", "expected_exit", "expected_diagnostics"),
    [
        ((), (), ExitCategory.SUCCESS, (BOUNDED_LOCAL_SCAN_ALLOWED,)),
        (
            (),
            ((31, "target-only"),),
            ExitCategory.CHECK_FAILURE,
            (BOUNDED_LOCAL_SCAN_ALLOWED, "RC_RUNTIME_EXTRA_KEYS"),
        ),
        (
            ((32, "source-only"),),
            (),
            ExitCategory.CHECK_FAILURE,
            (BOUNDED_LOCAL_SCAN_ALLOWED, "RC_RUNTIME_MISSING_KEYS"),
        ),
    ],
)
def test_run_service_executes_actual_duckdb_key_safety_empty_side_cases(
    tmp_path: Path,
    source_rows: tuple[tuple[object, ...], ...],
    target_rows: tuple[tuple[object, ...], ...],
    expected_exit: ExitCategory,
    expected_diagnostics: tuple[str, ...],
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=source_rows,
        target_rows=target_rows,
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=_all_key_safety_checks(keys=("customer_id", "region")),
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is expected_exit
    assert [diagnostic.code for diagnostic in result.diagnostics] == list(expected_diagnostics)
    public_text = _service_result_text(result)
    assert "source-only" not in public_text
    assert "target-only" not in public_text
    assert "failure_count" not in public_text
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_actual_duckdb_row_count_and_key_safety_together(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=((41, "shared"), (42, "also-shared")),
        target_rows=((41, "shared"), (42, "also-shared")),
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=[
            _compiled_check_payload(operations=row_count_plan()),
            _key_safety_payload_for("missing_keys", keys=("customer_id", "region")),
        ],
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_ALLOWED]
    public_text = _service_result_text(result)
    assert "shared" not in public_text
    assert "also-shared" not in public_text
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("key-safety-shape-blocker-precedence")
def test_run_service_preserves_key_safety_shape_blocker_in_mixed_runtime_run(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=((41, "shared"),),
        target_rows=((41, "shared"),),
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=[
            _compiled_check_payload(operations=row_count_plan()),
            _key_safety_check_payload(
                operations=[_key_diff_operation("target_minus_source")],
                required_capabilities=["key_diff"],
            ),
        ],
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
    ]
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_preserves_key_safety_shape_blocker_when_it_is_the_only_check(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(
        tmp_path,
        checks=[
            _key_safety_check_payload(
                operations=[_key_diff_operation("target_minus_source")],
                required_capabilities=["key_diff"],
            ),
        ],
    )
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
    ]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_preserves_key_safety_shape_blocker_for_query_endpoint_contract(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(
        tmp_path,
        checks=[
            _key_safety_check_payload(
                operations=[_key_diff_operation("target_minus_source")],
                required_capabilities=["key_diff"],
            ),
        ],
    )
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
        "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
    ]
    public_text = _service_result_text(result)
    assert "secret-ssn" not in public_text
    assert "select customer_id" not in public_text
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("key-safety-invalid-relation-diagnostic-precedence")
def test_run_service_preserves_key_safety_invalid_relation_before_profile_loading(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="missing_profile")
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path, source_relation="bad..name")
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during check-engine evaluation."
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_ADAPTER_INVALID_RELATION"]
    assert "RC_CONFIG" not in _service_result_text(result)
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_does_not_mutate_stale_outputs_during_actual_key_safety(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=((51, "secret-stale-output"),),
        target_rows=(),
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=[_key_safety_payload_for("missing_keys", keys=("customer_id", "region"))],
    )
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

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MISSING_KEYS",
        BOUNDED_LOCAL_SCAN_ALLOWED,
    ]
    assert "secret-stale-output" not in _service_result_text(result)
    for path, content in output_contents.items():
        assert path.read_text(encoding="utf-8") == content


def test_run_service_sanitizes_actual_duckdb_key_safety_type_mismatch(
    tmp_path: Path,
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    _write_duckdb_key_safety_tables(
        duckdb,
        database,
        source_rows=((61, "secret-type-source"),),
        target_rows=(("61", "secret-type-target"),),
        target_column_definitions=("customer_id varchar", "region varchar"),
    )
    write_duckdb_key_safety_run_inputs(
        tmp_path,
        database,
        checks=[_key_safety_payload_for("missing_keys")],
    )

    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during check-engine evaluation."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [ADAPTER_QUERY_FAILED]
    public_text = _service_result_text(result)
    assert "DuckDB query execution failed." in public_text
    assert "Recon DuckDB key_diff key type mismatch." not in public_text
    assert "secret-type-source" not in public_text
    assert "secret-type-target" not in public_text
    assert "source_customers" not in public_text
    assert "target_customers" not in public_text
    assert "select" not in public_text.lower()
    assert str(database) not in public_text
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_key_safety_with_runtime_profile_and_adapter_context(
    tmp_path: Path,
) -> None:
    write_bounded_local_duckdb_fixture(tmp_path)
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
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_ALLOWED]
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    assert "failure_count" in adapter.queries[0]
    assert "UNUSED_DB" not in _service_result_text(result)
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("key-safety-duckdb-relative-path-project-root")
def test_run_service_resolves_relative_duckdb_profile_paths_from_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_path = tmp_path / "project"
    process_cwd = tmp_path / "process-cwd"
    project_path.mkdir()
    process_cwd.mkdir()
    duckdb = _duckdb_module()
    _write_duckdb_key_safety_tables(
        duckdb,
        project_path / "warehouse.duckdb",
        source_rows=((1, "north"),),
        target_rows=(),
    )
    _write_duckdb_key_safety_tables(
        duckdb,
        process_cwd / "warehouse.duckdb",
        source_rows=(),
        target_rows=(),
    )
    write_project(project_path, profile="local")
    write_profiles(
        project_path,
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
    write_compiled_checks(project_path, checks=[_key_safety_payload_for("missing_keys")])
    write_compiled_contract(project_path)
    monkeypatch.chdir(process_cwd)

    result = RunService(start_path=project_path).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert result.message == "Run completed with failing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MISSING_KEYS",
        BOUNDED_LOCAL_SCAN_ALLOWED,
    ]
    assert "warehouse.duckdb" not in _service_result_text(result)
    _assert_no_runtime_outputs(project_path)


def test_run_service_executes_key_safety_failure_without_raw_key_output(
    tmp_path: Path,
) -> None:
    write_bounded_local_duckdb_fixture(tmp_path)
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
        "RC_RUNTIME_DUPLICATE_GRAIN_KEYS",
        BOUNDED_LOCAL_SCAN_ALLOWED,
    ]
    public_text = _service_result_text(result)
    assert "customer_id" not in public_text
    assert "raw key" in public_text.lower()
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_key_safety_with_named_sampling_metadata(
    tmp_path: Path,
) -> None:
    write_bounded_local_duckdb_fixture(tmp_path)
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
    sampled_key_check = _key_safety_payload_for("null_source_keys")
    sampled_key_check["sampling"] = {"policy": "stable_hash_5_percent"}
    write_compiled_checks(tmp_path, checks=[sampled_key_check])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        result=QueryResult(columns=("failure_count",), rows=((1,),), row_count=1)
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CHECK_FAILURE
    assert result.message == "Run completed with failing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_NULL_GRAIN_KEYS",
        BOUNDED_LOCAL_SCAN_ALLOWED,
    ]
    public_text = _service_result_text(result)
    assert "stable_hash_5_percent" not in public_text
    assert "customer_id" not in public_text
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_blocks_query_endpoints_before_adapter_execution(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_blocks_key_safety_query_endpoints_before_adapter_query(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
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
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_ignores_query_endpoint_profile_when_relation_backed_check_executes(
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
    write_compiled_checks(
        tmp_path,
        contract_name="query_endpoint_contract",
        checks=[
            _key_safety_check_payload(
                check_id="check.ecommerce_recon.query_endpoint_contract.missing_keys"
            )
        ],
    )
    write_compiled_contract(
        tmp_path,
        contract_name="query_endpoint_contract",
        source_connection="unused_query_connection",
        target_connection="unused_query_connection",
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
    assert "unused_query_connection" not in public_text
    assert "secret-ssn" not in public_text
    assert "select customer_id" not in public_text
    adapter = factory.adapters[0]
    assert adapter.connection.name == "warehouse"
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
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
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("hidden-bounded-local-fixture-marker-removed")
def test_run_service_blocks_key_safety_same_context_duckdb_without_local_fixture(
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
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        connect_error=RuntimeError("opened unbounded key-safety adapter")
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_REQUIRED]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("hidden-bounded-local-fixture-marker-removed")
def test_run_service_scan_safety_blocks_key_safety_with_full_capabilities(
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
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities(
            {
                "key_diff": CapabilitySupport.FULL,
                "null_key": CapabilitySupport.FULL,
                "duplicate_key": CapabilitySupport.FULL,
                "cte_support": CapabilitySupport.FULL,
            }
        ),
        connect_error=RuntimeError("opened adapter before scan safety allowed execution"),
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_REQUIRED]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("hidden-bounded-local-fixture-marker-removed")
def test_run_service_blocks_key_safety_same_context_duckdb_oversized_local_fixture(
    tmp_path: Path,
) -> None:
    with (tmp_path / "warehouse.duckdb").open("wb") as database:
        database.truncate(65 * 1024 * 1024)
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
        connect_error=RuntimeError("opened oversized key-safety adapter")
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_REQUIRED]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_key_safety_for_same_context_duckdb_aliases(
    tmp_path: Path,
) -> None:
    write_bounded_local_duckdb_fixture(tmp_path)
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
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(
        tmp_path,
        source_connection="warehouse",
        target_connection="replica",
    )
    factory = RecordingDuckDbFactory(
        result=QueryResult(columns=("failure_count",), rows=((0,),), row_count=1)
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_ALLOWED]
    assert len(factory.adapters) == 2
    assert sum(adapter.connect_count for adapter in factory.adapters) == 1
    assert sum(adapter.close_count for adapter in factory.adapters) == 1
    assert sum(len(adapter.queries) for adapter in factory.adapters) == 1
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


def test_run_service_blocks_key_safety_different_adapter_types_without_bridge_or_fallback(
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
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
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
    assert duckdb_factory.adapters == []
    assert other_factory.adapters == []
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


@pytest.mark.parametrize(
    ("operation", "diagnostic_code"),
    [
        (
            {
                "type": "key_diff",
                "direction": "source_minus_target",
                "identity": {"kind": "grain", "keys": ["customer_id"]},
                "execution_placement": "source",
            },
            "RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT",
        ),
        (
            {
                "type": "key_diff",
                "direction": "source_minus_target",
                "identity": {"kind": "grain", "keys": ["customer_id"]},
                "materialization_policy": "temporary_table",
            },
            "RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY",
        ),
    ],
)
def test_run_service_blocks_key_safety_unsupported_runtime_metadata_before_adapter_setup(
    tmp_path: Path,
    operation: dict[str, object],
    diagnostic_code: str,
) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(
        tmp_path,
        checks=[_key_safety_check_payload(operations=[operation])],
    )
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


def test_run_service_rejects_key_safety_identity_mismatch_before_profile_or_adapter_setup(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(
        tmp_path,
        checks=[
            _key_safety_check_payload(
                operations=[
                    {
                        "type": "key_diff",
                        "direction": "source_minus_target",
                        "identity": {"kind": "grain", "keys": ["cdc_id"]},
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
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
    ]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_executes_valid_row_count_and_key_safety_checks(
    tmp_path: Path,
) -> None:
    write_bounded_local_duckdb_fixture(tmp_path)
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
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_ALLOWED]
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
