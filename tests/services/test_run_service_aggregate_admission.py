"""Aggregate admission must fail before profile or adapter work."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from recon_core.adapters import (
    AdapterCapabilities,
    AdapterRegistry,
    AdapterResolutionResult,
    CapabilitySupport,
    ConnectionConfig,
)
from recon_core.adapters._aggregate_runtime import _AggregateQueryResult
from recon_core.adapters.duckdb import AdapterLifecycleError, DuckDbAdapter
from recon_core.artifacts import CompiledContractLoader
from recon_core.check_engine import CheckEngine, CheckStatus, RunResult
from recon_core.cli.main import main
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services import RunService
from recon_core.services.results import ExitCategory
from tests.services._run_service_fixtures import (
    RecordingDuckDbFactory,
    _assert_no_runtime_outputs,
    _compiled_check_payload,
    _duckdb_module,
    _key_safety_payload_for,
    _service_result_text,
    row_count_plan,
    write_compiled_checks,
    write_compiled_contract,
    write_duckdb_row_count_run_inputs,
    write_profiles,
    write_project,
)

_PRIVATE_TOKEN = "private-synthetic-policy-value"


def _aggregate_check(*, grouped: bool = False, tolerance: object = None) -> dict[str, Any]:
    groups = ["customer_id", "month"] if grouped else []
    operation_type = "grouped_aggregate" if grouped else "aggregate"
    check_type = "grouped_aggregate_diff" if grouped else "sum_diff"
    comparison = "compare_grouped_aggregates" if grouped else "compare_aggregates"
    operations: list[dict[str, object]] = [
        {"type": operation_type, "side": side, "aggregate": "sum", "column": "revenue"}
        for side in ("source", "target")
    ]
    if grouped:
        for operation in operations:
            operation["group_by"] = list(groups)
    operations.append({"type": comparison})
    check = _compiled_check_payload(
        check_id=f"check.ecommerce_recon.customer_revenue.{check_type}",
        name=check_type,
        check_type=check_type,
        operations=operations,
        required_capabilities=[operation_type],
    )
    check["origin"] = {"kind": "metric", "name": check_type}
    check["metric"] = {"type": "sum", "column": "revenue", "group_by": groups}
    requirements = check["requirements"]
    assert isinstance(requirements, dict)
    requirements["required_columns"] = ["revenue", *groups]
    requirements["required_metrics"] = [check_type]
    check["tolerance"] = tolerance
    return check


def _run_without_profile(
    path: Path,
    check: dict[str, Any],
    *,
    policies: object = None,
    source_relation: str | None = "qa.source_customers",
    source_query: str | None = None,
    with_profile: bool = False,
) -> Any:
    # A missing profile is deliberate: blocked aggregate checks must not need one.
    write_project(path, profile="local")
    if with_profile:
        write_duckdb_row_count_run_inputs(path, path / "warehouse.duckdb")
    write_compiled_checks(path, checks=[check])
    write_compiled_contract(
        path,
        grain_keys=(),
        source_relation=source_relation,
        source_query=source_query,
    )
    contract_path = path / "target" / "compiled_contracts" / "customer_revenue.yml"
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    if policies is not None:
        payload["policies"] = policies
    contract_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    before = contract_path.read_bytes()
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=path, adapter_registry=registry).execute()
    assert factory.adapters == []
    assert contract_path.read_bytes() == before
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert _PRIVATE_TOKEN not in _service_result_text(result)
    _assert_no_runtime_outputs(path)
    return result


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.parametrize(
    "tolerance",
    [
        pytest.param(-1, id="negative"),
        pytest.param(True, id="boolean"),
        pytest.param(_PRIVATE_TOKEN, id="string"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
        pytest.param({}, id="empty-object"),
        pytest.param({"type": "absolute"}, id="missing-value"),
        pytest.param({"type": "absolute", "value": None}, id="null-value"),
        pytest.param({"type": "absolute", "value": False}, id="boolean-value"),
        pytest.param({"type": "relative", "value": 1}, id="relative"),
        pytest.param({"type": "absolute", "value": 0, "extra": _PRIVATE_TOKEN}, id="extra"),
    ],
)
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_invalid_aggregate_tolerance_blocks_before_profile(
    tmp_path: Path, grouped: bool, tolerance: object
) -> None:
    result = _run_without_profile(tmp_path, _aggregate_check(grouped=grouped, tolerance=tolerance))
    assert "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert "tolerance" in _service_result_text(result).lower()
    assert "non-executable checks" not in result.message


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_unresolved_named_aggregate_policy_blocks_before_profile(
    tmp_path: Path, grouped: bool
) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(grouped=grouped),
        policies={"tolerance_policy": _PRIVATE_TOKEN},
    )
    assert result.message == "Run completed with non-executable checks."
    assert "RC_RUNTIME_AGGREGATE_TOLERANCE_POLICY_UNRESOLVED" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.parametrize(
    "policies",
    [
        pytest.param(_PRIVATE_TOKEN, id="nonmapping"),
        pytest.param({"tolerance_policy": True}, id="boolean-reference"),
        pytest.param({"tolerance_policy": ""}, id="empty-reference"),
        pytest.param({"tolerance_policy": {"value": _PRIVATE_TOKEN}}, id="object-reference"),
    ],
)
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_invalid_named_policy_metadata_errors_before_profile(
    tmp_path: Path, policies: object
) -> None:
    result = _run_without_profile(tmp_path, _aggregate_check(), policies=policies)
    assert "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert "tolerance" in _service_result_text(result).lower()
    assert "non-executable checks" not in result.message


@pytest.mark.parametrize(
    "mutation",
    ("missing_compare", "reversed_sides", "different_column", "different_group_order", "avg"),
)
@pytest.mark.regression_capture("aggregate-admission-typed-plan-boundary")
def test_aggregate_plan_rejects_unsupported_shape_before_profile(
    tmp_path: Path, mutation: str
) -> None:
    check = _aggregate_check(grouped=mutation == "different_group_order")
    operations = check["plan"]["operations"]
    if mutation == "missing_compare":
        operations.pop()
    elif mutation == "reversed_sides":
        operations[0], operations[1] = operations[1], operations[0]
    elif mutation == "different_column":
        operations[1]["column"] = _PRIVATE_TOKEN
    elif mutation == "different_group_order":
        operations[1]["group_by"] = ["month", "customer_id"]
    else:
        for operation in operations[:2]:
            operation["aggregate"] = "avg"
        check["metric"]["type"] = "avg"
    result = _run_without_profile(tmp_path, check)
    assert result.message == "Run completed with non-executable checks."
    assert "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.regression_capture("aggregate-admission-endpoint-precedence")
def test_aggregate_query_endpoint_is_not_executable_before_profile(tmp_path: Path) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(),
        source_relation=None,
        source_query=f"select '{_PRIVATE_TOKEN}'",
    )
    assert result.message == "Run completed with non-executable checks."
    assert "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.regression_capture("aggregate-admission-endpoint-precedence")
def test_aggregate_invalid_relation_errors_before_profile(tmp_path: Path) -> None:
    result = _run_without_profile(
        tmp_path, _aggregate_check(), source_relation=f"qa..{_PRIVATE_TOKEN}"
    )
    assert "RC_ADAPTER_INVALID_RELATION" in {diagnostic.code for diagnostic in result.diagnostics}
    assert "non-executable checks" not in result.message


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.parametrize("tolerance", (0, 0.1, {"type": "absolute", "value": 0.1}))
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_valid_explicit_tolerance_overrides_named_policy_without_execution(
    tmp_path: Path, grouped: bool, tolerance: object
) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(grouped=grouped, tolerance=tolerance),
        policies={"tolerance_policy": _PRIVATE_TOKEN},
        with_profile=True,
    )
    # The policy admits the check; the missing local database still blocks execution.
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED"
    ]


@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_invalid_explicit_override_does_not_fall_back_to_named_policy(tmp_path: Path) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(tolerance=-1),
        policies={"tolerance_policy": _PRIVATE_TOKEN},
    )
    assert "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_malformed_named_metadata_is_not_hidden_by_valid_override(tmp_path: Path) -> None:
    result = _run_without_profile(
        tmp_path,
        _aggregate_check(tolerance=0),
        policies={"tolerance_policy": True},
    )
    assert "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_injected_public_loader_does_not_imply_verified_policy_absence(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(tmp_path, checks=[_aggregate_check(tolerance=0)])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(
        start_path=tmp_path,
        adapter_registry=registry,
        contract_loader=CompiledContractLoader(),
    ).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_AGGREGATE_TOLERANCE_POLICY_UNRESOLVED"
    ]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_mixed_run_preserves_aggregate_policy_error_and_row_count(tmp_path: Path) -> None:
    write_duckdb_row_count_run_inputs(tmp_path, tmp_path / "warehouse.duckdb")
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(operations=row_count_plan()),
            _aggregate_check(tolerance=_PRIVATE_TOKEN),
        ],
    )
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert _PRIVATE_TOKEN not in _service_result_text(result)
    assert len(factory.adapters) == 1
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("fixture", ["missing", "oversized", "wal", "tmp", "view", "missing_table"])
@pytest.mark.regression_capture("aggregate-runtime-scan-preflight")
def test_aggregate_scan_safety_blocks_before_adapter_setup(
    tmp_path: Path, grouped: bool, fixture: str
) -> None:
    database = tmp_path / "warehouse.duckdb"
    if fixture == "oversized":
        with database.open("wb") as stream:
            stream.truncate(65 * 1024 * 1024)
    elif fixture in {"wal", "tmp"}:
        database.touch()
        database.with_name(f"{database.name}.{fixture}").touch()
    elif fixture in {"view", "missing_table"}:
        duckdb = _duckdb_module()
        connection = duckdb.connect(str(database))
        try:
            connection.execute("create schema qa")
            connection.execute(
                "create table qa.target_customers("
                "customer_id integer, month integer, revenue integer)"
            )
            if fixture == "view":
                connection.execute(
                    "create view qa.source_customers as select * from qa.target_customers"
                )
        finally:
            connection.close()

    write_duckdb_row_count_run_inputs(tmp_path, database)
    write_compiled_checks(tmp_path, checks=[_aggregate_check(grouped=grouped)])
    factory = RecordingDuckDbFactory(
        connect_error=RuntimeError("private-aggregate-scan-should-not-open")
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED"
    ]
    assert "aggregate" in result.diagnostics[0].message.lower()
    assert "grain-key" not in _service_result_text(result).lower()
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("target_type", ["duckdb", "warehouse_test"])
@pytest.mark.regression_capture("aggregate-runtime-scan-preflight")
def test_aggregate_service_blocks_cross_context_before_adapter_setup(
    tmp_path: Path, grouped: bool, target_type: str
) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        yaml.safe_dump(
            {
                "profiles": {
                    "local": {
                        "target": "dev",
                        "outputs": {
                            "dev": {
                                "connections": {
                                    "warehouse": {"type": "duckdb", "database": "source.duckdb"},
                                    "replica": {"type": target_type, "database": "target.duckdb"},
                                }
                            }
                        },
                    }
                }
            }
        ),
    )
    write_compiled_checks(tmp_path, checks=[_aggregate_check(grouped=grouped)])
    write_compiled_contract(tmp_path, target_connection="replica")
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"
    ]
    assert "source.duckdb" not in _service_result_text(result)
    assert "target.duckdb" not in _service_result_text(result)
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("missing", ["operation", "cte_support"])
@pytest.mark.regression_capture("aggregate-runtime-capability-isolation")
def test_aggregate_service_requires_capabilities_before_connect(
    tmp_path: Path, grouped: bool, missing: str
) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create schema qa")
        connection.execute(
            "create table qa.source_customers(customer_id integer, month integer, revenue integer)"
        )
        connection.execute("create table qa.target_customers as select * from qa.source_customers")
    finally:
        connection.close()
    write_duckdb_row_count_run_inputs(tmp_path, database)
    write_compiled_checks(tmp_path, checks=[_aggregate_check(grouped=grouped)])
    operation = "grouped_aggregate" if grouped else "aggregate"
    capabilities = AdapterCapabilities(
        {("cte_support" if missing == "operation" else operation): CapabilitySupport.FULL}
    )
    factory = RecordingDuckDbFactory(capabilities=capabilities)
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert "RC_ADAPTER_CAPABILITY_UNSUPPORTED" in {d.code for d in result.diagnostics}
    assert len(factory.adapters) == 1
    assert factory.adapters[0].connect_count == 0
    assert factory.adapters[0].queries == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-runtime-private-routing")
def test_aggregate_service_executes_bounded_same_context(tmp_path: Path, grouped: bool) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create schema qa")
        connection.execute(
            "create table qa.source_customers(customer_id integer, month integer, revenue integer)"
        )
        connection.execute("insert into qa.source_customers values (1, 1, 20), (2, 2, 30)")
        connection.execute("create table qa.target_customers as select * from qa.source_customers")
    finally:
        connection.close()
    write_duckdb_row_count_run_inputs(tmp_path, database)
    write_compiled_checks(tmp_path, checks=[_aggregate_check(grouped=grouped)])
    result = RunService(start_path=tmp_path).execute()
    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == "Run completed with passing checks."
    assert "RC_RUNTIME_BOUNDED_LOCAL_SCAN_ALLOWED" in {d.code for d in result.diagnostics}
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-runtime-capability-isolation")
def test_aggregate_missing_prerequisite_blocks_before_profile(
    tmp_path: Path, grouped: bool
) -> None:
    check = _aggregate_check(grouped=grouped)
    check["prerequisites"] = ["check.ecommerce_recon.customer_revenue.missing"]
    result = _run_without_profile(tmp_path, check)
    assert result.message == "Run completed with blocked checks."
    assert "RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE" in {d.code for d in result.diagnostics}


def _write_bounded_aggregate_inputs(tmp_path: Path, checks: list[dict[str, object]]) -> None:
    duckdb = _duckdb_module()
    database = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create schema qa")
        connection.execute(
            "create table qa.source_customers(customer_id integer, month integer, revenue integer)"
        )
        connection.execute("create table qa.target_customers as select * from qa.source_customers")
    finally:
        connection.close()
    write_duckdb_row_count_run_inputs(tmp_path, database)
    write_compiled_checks(tmp_path, checks=checks)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-runtime-private-routing")
def test_aggregate_service_missing_private_executor_does_not_connect(
    tmp_path: Path, grouped: bool
) -> None:
    _write_bounded_aggregate_inputs(tmp_path, [_aggregate_check(grouped=grouped)])
    operation = "grouped_aggregate" if grouped else "aggregate"
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities(
            {operation: CapabilitySupport.FULL, "cte_support": CapabilitySupport.FULL}
        )
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert "RC_ADAPTER_RENDERER_METADATA_INVALID" in {d.code for d in result.diagnostics}
    assert len(factory.adapters) == 1
    assert factory.adapters[0].connect_count == 0
    assert factory.adapters[0].queries == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize(
    "support",
    [
        CapabilitySupport.UNKNOWN,
        CapabilitySupport.UNSUPPORTED,
        CapabilitySupport.NOT_IMPLEMENTED,
        CapabilitySupport.VERSIONED,
        "full",
    ],
)
@pytest.mark.regression_capture("aggregate-runtime-capability-isolation")
def test_aggregate_capability_blocker_preserves_unrelated_row_count(
    tmp_path: Path, grouped: bool, support: object
) -> None:
    _write_bounded_aggregate_inputs(
        tmp_path,
        [_compiled_check_payload(operations=row_count_plan()), _aggregate_check(grouped=grouped)],
    )
    operation = "grouped_aggregate" if grouped else "aggregate"
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities(
            {
                operation: support,
                "row_count": CapabilitySupport.FULL,
                "cte_support": CapabilitySupport.FULL,
            }
        )
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert "RC_ADAPTER_CAPABILITY_UNSUPPORTED" in {d.code for d in result.diagnostics}
    assert len(factory.adapters) == 1
    adapter = factory.adapters[0]
    assert adapter.connect_count == adapter.close_count == 1
    assert len(adapter.queries) == 1
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("failure", [None, "connect", "close"])
@pytest.mark.regression_capture("aggregate-native-service-lifecycle")
def test_blocked_aggregate_shared_connection_preserves_lifecycle_privacy(
    tmp_path: Path, grouped: bool, failure: str | None
) -> None:
    _write_bounded_aggregate_inputs(
        tmp_path,
        [_compiled_check_payload(operations=row_count_plan()), _aggregate_check(grouped=grouped)],
    )
    diagnostic = Diagnostic(
        code="RC_ADAPTER_CONNECTION_FAILED" if failure == "connect" else "RC_ADAPTER_CLOSE_FAILED",
        severity=DiagnosticSeverity.ERROR,
        message="private-injected-value qa.source_customers private-group-key",
    )
    error = AdapterLifecycleError(diagnostic)
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities(
            {"row_count": CapabilitySupport.FULL, "cte_support": CapabilitySupport.FULL}
        ),
        connect_error=error if failure == "connect" else None,
        close_error=error if failure == "close" else None,
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine, adapter_registry=registry).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert len(factory.adapters) == 1
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == (0 if failure == "connect" else 1)
    assert len(adapter.queries) == (0 if failure == "connect" else 1)
    if failure == "connect":
        assert engine.result is None
    else:
        assert engine.result is not None
        checks = engine.result.contract_results[0].check_results
        assert [(check.status, check.executed) for check in checks] == [
            (CheckStatus.PASS, True),
            (CheckStatus.NOT_EXECUTABLE, False),
        ]
    if failure is not None:
        assert diagnostic.code in {d.code for d in result.diagnostics}
    for token in ("private-injected-value", "qa.source_customers", "private-group-key"):
        assert token not in _service_result_text(result)
    _assert_no_runtime_outputs(tmp_path)


class _CapturingAggregateEngine(CheckEngine):
    result: RunResult | None = None

    def run(self, *args: Any, **kwargs: Any) -> RunResult:
        self.result = super().run(*args, **kwargs)
        return self.result


def _write_native_aggregate_inputs(
    path: Path,
    *,
    source_sql: str,
    target_sql: str,
    grouped: bool,
    tolerance: object = None,
) -> Path:
    duckdb = _duckdb_module()
    database = path / "private-native-aggregate.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create schema qa")
        connection.execute(f"create table qa.source_customers as {source_sql}")
        connection.execute(f"create table qa.target_customers as {target_sql}")
    finally:
        connection.close()
    write_duckdb_row_count_run_inputs(path, database)
    write_compiled_checks(path, checks=[_aggregate_check(grouped=grouped, tolerance=tolerance)])
    return database


def _native_row(value: str, *, key: str = "'private-group-key'", empty: bool = False) -> str:
    where = " where false" if empty else ""
    return f"select {key} as customer_id, 1 as month, {value} as revenue{where}"


def _assert_native_aggregate_result(
    path: Path,
    engine: _CapturingAggregateEngine,
    expected: CheckStatus,
    result: Any,
    *,
    private_tokens: tuple[str, ...] = (),
) -> None:
    expected_exit = {
        CheckStatus.PASS: ExitCategory.SUCCESS,
        CheckStatus.FAIL: ExitCategory.CHECK_FAILURE,
        CheckStatus.ERROR: ExitCategory.RUNTIME_ERROR,
    }
    assert result.exit_category is expected_exit[expected]
    assert engine.result is not None
    assert len(engine.result.contract_results) == 1
    checks = engine.result.contract_results[0].check_results
    assert len(checks) == 1
    check = checks[0]
    assert check.status is expected
    assert check.executed == (expected in (CheckStatus.PASS, CheckStatus.FAIL))
    assert check.source_value is None
    assert check.target_value is None
    assert check.diff_value is None
    assert check.failure_count is None
    assert check.tolerance is None
    assert check.artifact_refs == check.sink_refs == ()
    output = repr(engine.result.to_dict()) + _service_result_text(result)
    for token in (
        "private-group-key",
        "private-native-aggregate.duckdb",
        "qa.source_customers",
        "qa.target_customers",
        *private_tokens,
    ):
        assert token not in output
    _assert_no_runtime_outputs(path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize(
    ("source", "target", "tolerance", "expected"),
    [
        ("9007199254740993::BIGINT", "9007199254740992::BIGINT", 0, CheckStatus.FAIL),
        ("9007199254740993::BIGINT", "9007199254740992::BIGINT", 1, CheckStatus.PASS),
        (
            "'99999999999999999999.01'::DECIMAL(38,2)",
            "'99999999999999999999.00'::DECIMAL(38,2)",
            0.01,
            CheckStatus.PASS,
        ),
        (
            "'99999999999999999999.01'::DECIMAL(38,2)",
            "'99999999999999999999.00'::DECIMAL(38,2)",
            0.009,
            CheckStatus.FAIL,
        ),
        ("0.30000000000000004::DOUBLE", "0.2::DOUBLE", 0.1, CheckStatus.FAIL),
        ("0.30000000000000004::DOUBLE", "0.2::DOUBLE", 0.10000000000000003, CheckStatus.PASS),
        ("0.3::FLOAT", "0.2::FLOAT", 0.11, CheckStatus.PASS),
        ("'NaN'::DOUBLE", "1::DOUBLE", 1, CheckStatus.ERROR),
        ("'Infinity'::DOUBLE", "1::DOUBLE", 1, CheckStatus.ERROR),
        ("'-Infinity'::DOUBLE", "1::DOUBLE", 1, CheckStatus.ERROR),
        ("1e308::DOUBLE", "-1e308::DOUBLE", 1, CheckStatus.ERROR),
        (
            "'private-unsupported-value'::VARCHAR",
            "'private-unsupported-value'::VARCHAR",
            0,
            CheckStatus.ERROR,
        ),
    ],
)
@pytest.mark.regression_capture("aggregate-native-service-numeric-semantics")
def test_native_aggregate_service_numeric_outcomes_and_privacy(
    tmp_path: Path,
    grouped: bool,
    source: str,
    target: str,
    tolerance: object,
    expected: CheckStatus,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row(source),
        target_sql=_native_row(target),
        grouped=grouped,
        tolerance=tolerance,
    )
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    _assert_native_aggregate_result(
        tmp_path,
        engine,
        expected,
        result,
        private_tokens=(
            "9007199254740993",
            "9007199254740992",
            "99999999999999999999",
            "private-unsupported-value",
        ),
    )
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize(
    ("source_value", "source_empty", "target_value", "target_empty", "expected"),
    [
        ("NULL::INTEGER", True, "NULL::INTEGER", True, CheckStatus.PASS),
        ("NULL::INTEGER", False, "NULL::INTEGER", False, CheckStatus.PASS),
        ("NULL::INTEGER", False, "0::INTEGER", False, CheckStatus.FAIL),
        ("NULL::INTEGER", True, "0::INTEGER", False, CheckStatus.FAIL),
        ("0::INTEGER", False, "NULL::INTEGER", True, CheckStatus.FAIL),
    ],
)
@pytest.mark.regression_capture("aggregate-native-service-numeric-semantics")
def test_native_aggregate_service_null_and_empty_outcomes(
    tmp_path: Path,
    grouped: bool,
    source_value: str,
    source_empty: bool,
    target_value: str,
    target_empty: bool,
    expected: CheckStatus,
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row(source_value, key="NULL::VARCHAR", empty=source_empty),
        target_sql=_native_row(target_value, key="NULL::VARCHAR", empty=target_empty),
        grouped=grouped,
    )
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    _assert_native_aggregate_result(tmp_path, engine, expected, result)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.regression_capture("aggregate-native-service-group-presence")
def test_native_grouped_service_distinguishes_absence_from_null(
    tmp_path: Path, reverse: bool
) -> None:
    present = _native_row("NULL::INTEGER")
    absent = _native_row("NULL::INTEGER", empty=True)
    source, target = (absent, present) if reverse else (present, absent)
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=source,
        target_sql=target,
        grouped=True,
        tolerance=999,
    )
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    _assert_native_aggregate_result(tmp_path, engine, CheckStatus.FAIL, result)


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.regression_capture("aggregate-native-service-group-presence")
def test_native_grouped_service_rejects_incompatible_key_types(tmp_path: Path, empty: bool) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER", key="1::INTEGER", empty=empty),
        target_sql=_native_row("1::INTEGER", key="'1'::VARCHAR", empty=empty),
        grouped=True,
    )
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    _assert_native_aggregate_result(tmp_path, engine, CheckStatus.ERROR, result)


@pytest.mark.regression_capture("aggregate-native-service-group-presence")
def test_native_grouped_service_high_cardinality_remains_private(tmp_path: Path) -> None:
    source = (
        "select 'private-group-key-' || i::varchar as customer_id, "
        "1 as month, 123456789012345::bigint as revenue from range(10000) q(i)"
    )
    target = source.replace("range(10000)", "range(9999)")
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=source,
        target_sql=target,
        grouped=True,
        tolerance=999999999999999,
    )
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    _assert_native_aggregate_result(
        tmp_path, engine, CheckStatus.FAIL, result, private_tokens=("123456789012345",)
    )


class _TrackingAggregateAdapter(DuckDbAdapter):
    def __init__(self, *, connection: ConnectionConfig, failure: str | None) -> None:
        super().__init__(connection=connection)
        self.failure = failure
        self.connect_count = 0
        self.close_count = 0
        self.private_columns: list[tuple[str, ...]] = []
        self.public_query_count = 0

    def _injected_failure(self, code: str) -> None:
        raise AdapterLifecycleError(
            Diagnostic(
                code=code,
                severity=DiagnosticSeverity.ERROR,
                message="private-injected-value qa.source_customers private-group-key",
            )
        )

    def connect(self) -> None:
        self.connect_count += 1
        if self.failure == "connect":
            self._injected_failure("RC_ADAPTER_CONNECTION_FAILED")
        super().connect()

    def close(self) -> None:
        self.close_count += 1
        super().close()
        if self.failure == "close":
            self._injected_failure("RC_ADAPTER_CLOSE_FAILED")

    def capabilities(self) -> AdapterCapabilities:
        if self.failure == "invalid_capabilities":
            return "private-injected-value"
        return super().capabilities()

    def execute(self, query: str) -> Any:
        self.public_query_count += 1
        return super().execute(query)

    def _execute_aggregate_query(
        self, query: str, *, expected_columns: tuple[str, ...]
    ) -> _AggregateQueryResult:
        self.private_columns.append(expected_columns)
        if self.failure == "query":
            self._injected_failure("RC_ADAPTER_QUERY_FAILED")
        result = super()._execute_aggregate_query(query, expected_columns=expected_columns)
        if self.failure == "invalid_result" and len(expected_columns) > 1:
            return _AggregateQueryResult(result.columns, result.domains, ())
        return result


class _TrackingAggregateFactory:
    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.adapters: list[_TrackingAggregateAdapter] = []

    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        if self.failure == "setup":
            raise RuntimeError("private-injected-value qa.source_customers private-group-key")
        adapter = _TrackingAggregateAdapter(connection=connection, failure=self.failure)
        self.adapters.append(adapter)
        return AdapterResolutionResult(adapter=adapter)


def _tracking_registry(factory: _TrackingAggregateFactory) -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    return registry


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("failure", [None, "query", "invalid_result", "connect", "close", "setup"])
@pytest.mark.regression_capture("aggregate-native-service-lifecycle")
def test_native_aggregate_lifecycle_and_failure_privacy(
    tmp_path: Path, grouped: bool, failure: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("123456789012345::BIGINT"),
        target_sql=_native_row("123456789012345::BIGINT"),
        grouped=grouped,
    )
    factory = _TrackingAggregateFactory(failure)
    engine = _CapturingAggregateEngine()
    result = RunService(
        start_path=tmp_path, engine=engine, adapter_registry=_tracking_registry(factory)
    ).execute()
    if failure is None:
        _assert_native_aggregate_result(tmp_path, engine, CheckStatus.PASS, result)
    elif failure in ("query", "invalid_result"):
        _assert_native_aggregate_result(tmp_path, engine, CheckStatus.ERROR, result)
    elif failure == "setup":
        assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
        assert engine.result is None
        assert factory.adapters == []
    else:
        assert result.exit_category is ExitCategory.RUNTIME_ERROR
        if failure == "connect":
            assert engine.result is None
        else:
            assert engine.result is not None
    if failure != "setup":
        assert len(factory.adapters) == 1
        adapter = factory.adapters[0]
        assert adapter.connect_count == 1
        assert adapter.close_count == (0 if failure == "connect" else 1)
        assert adapter.public_query_count == 0
        if failure == "connect":
            assert adapter.private_columns == []
        elif failure == "query":
            assert adapter.private_columns == [("type_check",)]
        else:
            assert len(adapter.private_columns) == (4 if grouped else 3)
            assert len(adapter.private_columns[-1]) == (9 if grouped else 3)
    output = _service_result_text(result) + repr(engine.result)
    captured = capsys.readouterr()
    output += captured.out + captured.err
    for token in (
        "private-injected-value",
        "private-group-key",
        "qa.source_customers",
        "123456789012345",
        "private-native-aggregate.duckdb",
    ):
        assert token not in output
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-native-service-lifecycle")
def test_aggregate_invalid_capability_declaration_is_non_executable(
    tmp_path: Path, grouped: bool
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=grouped,
    )
    factory = _TrackingAggregateFactory("invalid_capabilities")
    engine = _CapturingAggregateEngine()
    result = RunService(
        start_path=tmp_path, engine=engine, adapter_registry=_tracking_registry(factory)
    ).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    check = engine.result.contract_results[0].check_results[0]
    assert check.status is CheckStatus.NOT_EXECUTABLE
    assert not check.executed
    assert "RC_ADAPTER_CAPABILITY_DECLARATION_FAILED" in {d.code for d in result.diagnostics}
    assert "private-injected-value" not in _service_result_text(result)
    assert len(factory.adapters) == 1
    assert factory.adapters[0].connect_count == 0
    assert factory.adapters[0].private_columns == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("override", [None, 1])
@pytest.mark.regression_capture("aggregate-native-service-numeric-semantics")
def test_native_aggregate_named_policy_override(
    tmp_path: Path, grouped: bool, override: int | None
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("2::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=grouped,
        tolerance=override,
    )
    contract_path = tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    payload["policies"] = {"tolerance_policy": _PRIVATE_TOKEN}
    contract_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    before = contract_path.read_bytes()
    factory = _TrackingAggregateFactory()
    engine = _CapturingAggregateEngine()
    result = RunService(
        start_path=tmp_path, engine=engine, adapter_registry=_tracking_registry(factory)
    ).execute()
    if override is None:
        assert result.exit_category is ExitCategory.RUNTIME_ERROR
        assert engine.result is not None
        assert (
            engine.result.contract_results[0].check_results[0].status is CheckStatus.NOT_EXECUTABLE
        )
        assert factory.adapters == []
    else:
        _assert_native_aggregate_result(tmp_path, engine, CheckStatus.PASS, result)
        assert len(factory.adapters) == 1
        assert factory.adapters[0].connect_count == factory.adapters[0].close_count == 1
    assert _PRIVATE_TOKEN not in _service_result_text(result)
    assert contract_path.read_bytes() == before
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-native-service-lifecycle")
def test_native_aggregate_same_context_alias_and_mixed_checks(
    tmp_path: Path, grouped: bool
) -> None:
    database = _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("5::INTEGER"),
        target_sql=_native_row("5::INTEGER"),
        grouped=grouped,
    )
    profile_path = tmp_path / "connections" / "profiles.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    connections = profile["profiles"]["local"]["outputs"]["dev"]["connections"]
    connections["replica"] = {"type": "duckdb", "database": str(database)}
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    write_compiled_contract(tmp_path, target_connection="replica")
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(operations=row_count_plan()),
            _key_safety_payload_for("missing_keys"),
            _aggregate_check(grouped=grouped),
        ],
    )
    factory = _TrackingAggregateFactory()
    engine = _CapturingAggregateEngine()
    result = RunService(
        start_path=tmp_path, engine=engine, adapter_registry=_tracking_registry(factory)
    ).execute()
    assert result.exit_category is ExitCategory.SUCCESS
    assert engine.result is not None
    checks = engine.result.contract_results[0].check_results
    assert len(checks) == 3
    assert all(check.status is CheckStatus.PASS and check.executed for check in checks)
    assert len(factory.adapters) == 2
    opened = [adapter for adapter in factory.adapters if adapter.connect_count]
    assert len(opened) == 1
    assert opened[0].connect_count == opened[0].close_count == 1
    assert opened[0].public_query_count == 2
    assert len(opened[0].private_columns) == (4 if grouped else 3)
    assert "private-group-key" not in _service_result_text(result)
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-service-output-privacy")
def test_aggregate_factory_diagnostics_do_not_publish_private_data(
    tmp_path: Path, grouped: bool
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=grouped,
    )

    def factory(connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_ADAPTER_RESOLUTION_FAILED",
                    severity=DiagnosticSeverity.ERROR,
                    message="private-factory-value qa.source_customers",
                    hint="private-group-key",
                    resource_name="private-factory-resource",
                ),
            )
        )

    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()
    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert "RC_ADAPTER_RESOLUTION_FAILED" in {d.code for d in result.diagnostics}
    for token in ("private-factory", "qa.source_customers", "private-group-key"):
        assert token not in _service_result_text(result)
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("distinct_alias", [False, True])
@pytest.mark.regression_capture("aggregate-service-output-privacy")
def test_aggregate_setup_preserves_distinct_connection_failures(
    tmp_path: Path, grouped: bool, distinct_alias: bool
) -> None:
    database = _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=grouped,
    )
    if distinct_alias:
        profile_path = tmp_path / "connections" / "profiles.yml"
        profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        connections = profile["profiles"]["local"]["outputs"]["dev"]["connections"]
        connections["private-replica"] = {"type": "duckdb", "database": str(database)}
        profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
        write_compiled_contract(tmp_path, target_connection="private-replica")

    calls: list[str] = []

    def factory(connection: ConnectionConfig) -> AdapterResolutionResult:
        calls.append(connection.name)
        diagnostic = Diagnostic(
            code="RC_ADAPTER_RESOLUTION_FAILED",
            severity=DiagnosticSeverity.ERROR,
            message="private-factory-value",
            resource_name=connection.name,
        )
        return AdapterResolutionResult(diagnostics=(diagnostic, diagnostic))

    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine, adapter_registry=registry).execute()
    expected = {"warehouse", "private-replica"} if distinct_alias else {"warehouse"}
    assert len(calls) == len(expected)
    assert set(calls) == expected
    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert engine.result is None
    failures = [d for d in result.diagnostics if d.code == "RC_ADAPTER_RESOLUTION_FAILED"]
    assert len(failures) == len(expected)
    assert len({d.hint for d in failures}) == len(expected)
    for token in ("private-replica", "private-factory-value", "warehouse", str(database)):
        assert token not in _service_result_text(result)
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-service-output-privacy")
def test_aggregate_unknown_required_capability_is_sanitized(tmp_path: Path, grouped: bool) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=grouped,
    )
    check = _aggregate_check(grouped=grouped)
    check["plan"]["required_capabilities"].append("private-unknown-capability")
    write_compiled_checks(tmp_path, checks=[check])
    factory = _TrackingAggregateFactory()
    engine = _CapturingAggregateEngine()
    result = RunService(
        start_path=tmp_path, engine=engine, adapter_registry=_tracking_registry(factory)
    ).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    assert engine.result.contract_results[0].check_results[0].status is CheckStatus.NOT_EXECUTABLE
    assert "RC_ADAPTER_CAPABILITY_UNSUPPORTED" in {d.code for d in result.diagnostics}
    assert "private-unknown-capability" not in _service_result_text(result)
    assert "private-unknown-capability" not in repr(engine.result.to_dict())
    assert len(factory.adapters) == 1
    assert factory.adapters[0].connect_count == 0
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("kind", ["HUGEINT", "DECIMAL(38,0)"])
@pytest.mark.parametrize("operation", ["sum", "difference"])
@pytest.mark.regression_capture("aggregate-native-service-numeric-semantics")
def test_native_aggregate_service_exact_overflow(
    tmp_path: Path, grouped: bool, kind: str, operation: str
) -> None:
    maximum = 2**127 - 1 if kind == "HUGEINT" else 10**38 - 1
    source = _native_row(f"'{maximum}'::{kind}")
    if operation == "sum":
        source += " union all " + _native_row(f"1::{kind}")
    target = _native_row(f"'{-maximum if operation == 'difference' else 0}'::{kind}")
    _write_native_aggregate_inputs(tmp_path, source_sql=source, target_sql=target, grouped=grouped)
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    # A version may compute a larger exact native result or reject overflow.
    # Neither may silently wrap, round, or report equivalence.
    assert engine.result is not None
    status = engine.result.contract_results[0].check_results[0].status
    assert status in (CheckStatus.FAIL, CheckStatus.ERROR)
    _assert_native_aggregate_result(
        tmp_path, engine, status, result, private_tokens=(str(maximum),)
    )


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-native-service-numeric-semantics")
def test_native_aggregate_service_arbitrary_integer_availability(
    tmp_path: Path, grouped: bool
) -> None:
    duckdb = _duckdb_module()
    version = tuple(int(part) for part in duckdb.__version__.split(".")[:2])
    if version < (1, 3):
        connection = duckdb.connect()
        try:
            with pytest.raises(duckdb.Error):
                connection.execute("select 1::VARINT")
        finally:
            connection.close()
        return
    kind = "VARINT" if version < (1, 4) else "BIGNUM"
    digits = "1" + "0" * 5000 + "1" if version >= (1, 4) else "1"
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row(f"'{digits}'::{kind}"),
        target_sql=_native_row(f"0::{kind}"),
        grouped=grouped,
    )
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    _assert_native_aggregate_result(
        tmp_path,
        engine,
        CheckStatus.FAIL if version >= (1, 4) else CheckStatus.ERROR,
        result,
        private_tokens=(digits[:30],) if version >= (1, 4) else (),
    )


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize(
    ("target_value", "exit_code"),
    [("123456789012345::BIGINT", 0), ("1::BIGINT", 1), ("'NaN'::DOUBLE", 3)],
)
@pytest.mark.regression_capture("aggregate-service-output-privacy")
def test_native_aggregate_cli_privacy_and_artifact_immutability(
    tmp_path: Path,
    grouped: bool,
    target_value: str,
    exit_code: int,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("123456789012345::BIGINT"),
        target_sql=_native_row(target_value),
        grouped=grouped,
    )
    # A pre-existing compiled SQL artifact is never read or rewritten by run.
    compiled_sql = tmp_path / "target" / "compiled_sql" / "existing.sql"
    compiled_sql.parent.mkdir()
    compiled_sql.write_text("private-existing-compile-sql", encoding="utf-8")
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["run"])
    assert result.exit_code == exit_code
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before
    for token in (
        "private-group-key",
        "private-native-aggregate.duckdb",
        "qa.source_customers",
        "qa.target_customers",
        "123456789012345",
        "private-existing-compile-sql",
    ):
        assert token not in result.output
        assert token not in caplog.text


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("mismatch", ["name", "database", "mutated_database", "malformed"])
@pytest.mark.regression_capture("aggregate-native-service-lifecycle")
def test_aggregate_rejects_wrong_factory_connection_before_open(
    tmp_path: Path, grouped: bool, mixed: bool, mismatch: str
) -> None:
    database = _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=grouped,
    )
    if mixed:
        write_compiled_checks(
            tmp_path,
            checks=[
                _compiled_check_payload(operations=row_count_plan()),
                _aggregate_check(grouped=grouped),
            ],
        )
    wrong_database = tmp_path / "private-unapproved-database.duckdb"
    adapters: list[_TrackingAggregateAdapter] = []

    def factory(connection: ConnectionConfig) -> AdapterResolutionResult:
        wrong_connection = ConnectionConfig(
            name="private-wrong-name" if mismatch == "name" else connection.name,
            type=connection.type,
            config={
                **connection.config,
                "database": str(wrong_database if mismatch == "database" else database),
            },
        )
        if mismatch == "mutated_database":
            connection.config["database"] = str(wrong_database)
            wrong_connection = connection
        adapter = _TrackingAggregateAdapter(connection=wrong_connection, failure=None)
        if mismatch == "malformed":
            adapter.connection = None
        adapters.append(adapter)
        return AdapterResolutionResult(adapter=adapter)

    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine, adapter_registry=registry).execute()
    assert len(adapters) == 1
    adapter = adapters[0]
    assert adapter.connect_count == adapter.close_count == adapter.public_query_count == 0
    assert adapter.private_columns == []
    assert not wrong_database.exists()
    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert engine.result is None
    assert "RC_ADAPTER_METADATA_INVALID" in {d.code for d in result.diagnostics}
    for token in ("private-wrong-name", "private-unapproved-database", str(database)):
        assert token not in _service_result_text(result)
    _assert_no_runtime_outputs(tmp_path)
