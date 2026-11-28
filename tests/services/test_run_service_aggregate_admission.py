"""Aggregate admission must fail before profile or adapter work."""

from pathlib import Path
from types import SimpleNamespace
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
from recon_core.adapters._project_binding import _BoundSessionError
from recon_core.adapters.duckdb import AdapterLifecycleError, DuckDbAdapter
from recon_core.adapters.duckdb import _bound_execution as binding
from recon_core.adapters.models import QueryResult
from recon_core.artifacts import CompiledContractLoader
from recon_core.check_engine import CheckEngine, CheckStatus, RunResult
from recon_core.cli.main import main
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services import RunService
from recon_core.services.results import ExitCategory
from tests.services._run_service_fixtures import (
    RecordingDuckDbFactory,
    _all_key_safety_checks,
    _assert_no_runtime_outputs,
    _compiled_check_payload,
    _duckdb_module,
    _key_safety_payload_for,
    _service_result_text,
    _without_scope_advisory,
    row_count_plan,
    write_compiled_checks,
    write_compiled_contract,
    write_duckdb_row_count_run_inputs,
    write_profiles,
    write_project,
)

_PRIVATE_TOKEN = "private-synthetic-policy-value"


class _NativeSessionTrace:
    """Trace actual owned-session reads; inject failures at the new private boundary."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.sessions: list[binding._OwnedDuckDbSession] = []
        self.closes: list[binding._OwnedDuckDbSession] = []
        self.aggregate_columns: list[tuple[str, ...]] = []
        self.row_queries: list[str] = []
        self.failures: dict[int, str] = {}
        original_open = binding._OwnedDuckDbSession.open
        original_close = binding._OwnedDuckDbSession.close
        original_aggregate = binding._OwnedDuckDbSession._read_bound_aggregate
        original_row = binding._OwnedDuckDbSession._read_bound_query

        def open_session(session: binding._OwnedDuckDbSession) -> None:
            self.sessions.append(session)
            if self.failures.get(len(self.sessions)) == "connect":
                raise _BoundSessionError(
                    "RC_ADAPTER_CONNECTION_FAILED",
                    "Read-only execution session could not be opened.",
                )
            original_open(session)

        def close_session(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
            self.closes.append(session)
            diagnostics = original_close(session)
            index = self.sessions.index(session) + 1
            if self.failures.get(index) == "close":
                # Simulate failed rollback with confirmed release, not a leaked handle.
                return diagnostics + (
                    Diagnostic(
                        code="RC_ADAPTER_CLOSE_FAILED",
                        severity=DiagnosticSeverity.ERROR,
                        message="Read-only transaction cleanup failed.",
                    ),
                )
            return diagnostics

        def aggregate(
            session: binding._OwnedDuckDbSession,
            lease: binding._BindingLease,
            scope: binding._BindingScope,
            query: str,
            *,
            expected_columns: tuple[str, ...],
        ) -> _AggregateQueryResult:
            self.aggregate_columns.append(expected_columns)
            failure = self.failures.get(self.sessions.index(session) + 1)
            if failure == "query":
                raise RuntimeError("private-injected-value qa.source_customers private-group-key")
            result = original_aggregate(
                session, lease, scope, query, expected_columns=expected_columns
            )
            if failure == "invalid_result" and len(expected_columns) > 1:
                return _AggregateQueryResult(result.columns, result.domains, ())
            return result

        def row(
            session: binding._OwnedDuckDbSession,
            lease: binding._BindingLease,
            scope: binding._BindingScope,
            query: str,
        ) -> QueryResult:
            self.row_queries.append(query)
            return original_row(session, lease, scope, query)

        monkeypatch.setattr(binding._OwnedDuckDbSession, "open", open_session)
        monkeypatch.setattr(binding._OwnedDuckDbSession, "close", close_session)
        monkeypatch.setattr(binding._OwnedDuckDbSession, "_read_bound_aggregate", aggregate)
        monkeypatch.setattr(binding._OwnedDuckDbSession, "_read_bound_query", row)


@pytest.fixture
def session_trace(monkeypatch: pytest.MonkeyPatch) -> _NativeSessionTrace:
    return _NativeSessionTrace(monkeypatch)


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
def test_mixed_run_preserves_aggregate_policy_error_and_row_count(
    tmp_path: Path, session_trace: _NativeSessionTrace
) -> None:
    _write_bounded_aggregate_inputs(
        tmp_path, [_compiled_check_payload(operations=row_count_plan())]
    )
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
    assert adapter.connect_count == adapter.close_count == 0
    assert adapter.queries == []
    assert len(session_trace.sessions) == len(session_trace.closes) == 1
    assert len(session_trace.row_queries) == 1
    assert session_trace.aggregate_columns == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("fixture", ["missing", "oversized", "wal", "tmp", "view", "missing_table"])
@pytest.mark.regression_capture("aggregate-runtime-scan-preflight")
def test_aggregate_scan_safety_blocks_before_adapter_setup(
    tmp_path: Path, grouped: bool, fixture: str, session_trace: _NativeSessionTrace
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
    if fixture == "oversized":
        _set_project_duckdb_execution(tmp_path, {"max-database-mib": 64})
    write_compiled_checks(tmp_path, checks=[_aggregate_check(grouped=grouped)])
    factory = _TrackingAggregateFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    expected_code = (
        "RC_RUNTIME_SCAN_BUDGET_EXCEEDED"
        if fixture == "oversized"
        else "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED"
    )
    diagnostics = (
        _without_scope_advisory(result.diagnostics)
        if fixture in {"view", "missing_table"}
        else result.diagnostics
    )
    assert [diagnostic.code for diagnostic in diagnostics] == [expected_code]
    assert "grain-key" not in _service_result_text(result).lower()
    count = 1 if fixture in {"view", "missing_table"} else 0
    assert len(factory.adapters) == count
    assert all(adapter.connect_count == 0 for adapter in factory.adapters)
    assert len(session_trace.sessions) == len(session_trace.closes) == count
    assert session_trace.aggregate_columns == session_trace.row_queries == []
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
    tmp_path: Path, grouped: bool, support: object, session_trace: _NativeSessionTrace
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
    invocation = RunService(start_path=tmp_path, adapter_registry=registry)._execute_invocation()
    result = invocation.service_result
    first, second = invocation.resource_facts
    assert first.capability_admitted is True and first.admission.value == "verified"
    assert second.capability_admitted is None and second.admission.value == "not_reached"
    assert second.native is None
    assert invocation.run_result is not None
    reason = invocation.run_result.contract_results[0].check_results[1].reason_code
    assert reason is not None and reason.value == "missing_engine_capability"
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert "RC_ADAPTER_CAPABILITY_UNSUPPORTED" in {d.code for d in result.diagnostics}
    assert len(factory.adapters) == 1
    adapter = factory.adapters[0]
    assert adapter.connect_count == adapter.close_count == 0
    assert adapter.queries == []
    assert len(session_trace.sessions) == len(session_trace.closes) == 1
    assert len(session_trace.row_queries) == 1
    assert session_trace.aggregate_columns == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("failure", [None, "connect", "close"])
@pytest.mark.regression_capture("aggregate-native-service-lifecycle")
def test_blocked_aggregate_shared_connection_preserves_lifecycle_privacy(
    tmp_path: Path, grouped: bool, failure: str | None, session_trace: _NativeSessionTrace
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
    if failure is not None:
        session_trace.failures[1] = failure
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities(
            {"row_count": CapabilitySupport.FULL, "cte_support": CapabilitySupport.FULL}
        ),
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine, adapter_registry=registry).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert len(factory.adapters) == 1
    adapter = factory.adapters[0]
    assert adapter.connect_count == adapter.close_count == 0
    assert adapter.queries == []
    assert len(session_trace.sessions) == len(session_trace.closes) == 1
    assert len(session_trace.row_queries) == (0 if failure == "connect" else 1)
    assert session_trace.aggregate_columns == []
    assert engine.result is not None
    checks = engine.result.contract_results[0].check_results
    assert [(check.status, check.executed) for check in checks] == [
        (CheckStatus.PASS, True) if failure is None else (CheckStatus.ERROR, False),
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
@pytest.mark.regression_capture("duckdb-worker-lossless-result-transport")
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
@pytest.mark.parametrize(
    ("source_key", "target_key"),
    [
        ("1::INTEGER", "'1'::VARCHAR"),
        ("1::INTEGER", "1::BIGINT"),
        ("1::INTEGER", "1::UINTEGER"),
        ("1::DECIMAL(10,2)", "1::DECIMAL(10,3)"),
    ],
)
@pytest.mark.regression_capture("aggregate-native-service-group-presence")
def test_native_grouped_service_rejects_incompatible_key_types(
    tmp_path: Path, empty: bool, source_key: str, target_key: str
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER", key=source_key, empty=empty),
        target_sql=_native_row("1::INTEGER", key=target_key, empty=empty),
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
    tmp_path: Path,
    grouped: bool,
    failure: str | None,
    capsys: pytest.CaptureFixture[str],
    session_trace: _NativeSessionTrace,
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("123456789012345::BIGINT"),
        target_sql=_native_row("123456789012345::BIGINT"),
        grouped=grouped,
    )
    factory = _TrackingAggregateFactory("setup" if failure == "setup" else None)
    if failure is not None:
        session_trace.failures[1] = failure
    engine = _CapturingAggregateEngine()
    result = RunService(
        start_path=tmp_path, engine=engine, adapter_registry=_tracking_registry(factory)
    ).execute()
    if failure is None:
        _assert_native_aggregate_result(tmp_path, engine, CheckStatus.PASS, result)
    elif failure == "setup":
        assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
        assert engine.result is None
        assert factory.adapters == []
        assert session_trace.sessions == []
    else:
        _assert_native_aggregate_result(tmp_path, engine, CheckStatus.ERROR, result)
        expected = {
            "query": "RC_ADAPTER_QUERY_FAILED",
            "invalid_result": "RC_RUNTIME_AGGREGATE_RESULT_INVALID",
            "connect": "RC_ADAPTER_CONNECTION_FAILED",
            "close": "RC_ADAPTER_CLOSE_FAILED",
        }
        assert expected[failure] in {d.code for d in result.diagnostics}
    if failure != "setup":
        assert len(factory.adapters) == 1
        adapter = factory.adapters[0]
        assert adapter.connect_count == adapter.close_count == 0
        assert adapter.public_query_count == 0
        assert adapter.private_columns == []
        assert len(session_trace.sessions) == len(session_trace.closes) == 1
        if failure == "connect":
            assert session_trace.aggregate_columns == []
        elif failure == "query":
            assert session_trace.aggregate_columns == [("type_check",)]
        else:
            assert len(session_trace.aggregate_columns) == (4 if grouped else 3)
            assert len(session_trace.aggregate_columns[-1]) == (9 if grouped else 3)
        assert session_trace.row_queries == []
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
@pytest.mark.parametrize("failure", ["one_close", "both_close", "connect_and_close"])
@pytest.mark.regression_capture("aggregate-native-service-lifecycle")
def test_aggregate_lifecycle_preserves_distinct_connection_failures(
    tmp_path: Path, grouped: bool, failure: str, session_trace: _NativeSessionTrace
) -> None:
    database = _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=grouped,
    )
    profile_path = tmp_path / "connections" / "profiles.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    connections = profile["profiles"]["local"]["outputs"]["dev"]["connections"]
    connections["private-replica"] = {"type": "duckdb", "database": str(database)}
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    check = _aggregate_check(grouped=grouped)
    check["id"] = check["id"].replace("customer_revenue", "other_revenue")
    check["plan"]["id"] = check["plan"]["id"].replace("customer_revenue", "other_revenue")
    write_compiled_checks(tmp_path, contract_name="other_revenue", checks=[check])
    write_compiled_contract(
        tmp_path,
        contract_name="other_revenue",
        source_connection="private-replica",
        target_connection="private-replica",
    )
    adapters: dict[str, _TrackingAggregateAdapter] = {}

    def factory(connection: ConnectionConfig) -> AdapterResolutionResult:
        adapter = _TrackingAggregateAdapter(connection=connection, failure=None)
        adapters[connection.name] = adapter
        return AdapterResolutionResult(adapter=adapter)

    session_trace.failures = {2: "close"}
    if failure == "both_close":
        session_trace.failures[1] = "close"
    elif failure == "connect_and_close":
        session_trace.failures[1] = "connect"
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    engine = _CapturingAggregateEngine()
    result = RunService(start_path=tmp_path, engine=engine, adapter_registry=registry).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert set(adapters) == {"warehouse", "private-replica"}
    assert all(adapter.connect_count == adapter.close_count == 0 for adapter in adapters.values())
    assert len(session_trace.sessions) == len(session_trace.closes) == 2
    assert engine.result is not None
    assert len(engine.result.contract_results) == 2
    checks = [contract.check_results[0] for contract in engine.result.contract_results]
    assert sum(check.status is CheckStatus.ERROR for check in checks) == (
        1 if failure == "one_close" else 2
    )
    assert all(not check.executed for check in checks if check.status is CheckStatus.ERROR)
    if failure == "connect_and_close":
        assert sum(d.code == "RC_ADAPTER_CONNECTION_FAILED" for d in result.diagnostics) == 1
    failures = [d for d in result.diagnostics if d.code == "RC_ADAPTER_CLOSE_FAILED"]
    assert len(failures) == (2 if failure == "both_close" else 1)
    for token in ("private-replica", "private-injected-value", "qa.source_customers"):
        assert token not in _service_result_text(result)
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
    tmp_path: Path, grouped: bool, override: int | None, session_trace: _NativeSessionTrace
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
        assert session_trace.sessions == []
    else:
        _assert_native_aggregate_result(tmp_path, engine, CheckStatus.PASS, result)
        assert len(factory.adapters) == 1
        assert factory.adapters[0].connect_count == factory.adapters[0].close_count == 0
        assert len(session_trace.sessions) == len(session_trace.closes) == 1
        assert len(session_trace.aggregate_columns) == (4 if grouped else 3)
    assert _PRIVATE_TOKEN not in _service_result_text(result)
    assert contract_path.read_bytes() == before
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-native-service-lifecycle")
def test_native_aggregate_same_context_alias_and_mixed_checks(
    tmp_path: Path, grouped: bool, session_trace: _NativeSessionTrace
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
    assert all(adapter.connect_count == adapter.close_count == 0 for adapter in factory.adapters)
    assert all(adapter.public_query_count == 0 for adapter in factory.adapters)
    assert all(not adapter.private_columns for adapter in factory.adapters)
    assert len(session_trace.sessions) == len(session_trace.closes) == 3
    assert len(session_trace.row_queries) == 2
    assert len(session_trace.aggregate_columns) == (4 if grouped else 3)
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


def _set_project_duckdb_execution(path: Path, settings: dict[str, object]) -> None:
    project_path = path / "recon_project.yml"
    project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    project["execution"] = {"adapters": {"duckdb": settings}}
    project_path.write_text(yaml.safe_dump(project, sort_keys=False), encoding="utf-8")


@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("family", range(9))
@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_explicit_footprint_policy(
    tmp_path: Path, offset: int, family: int, session_trace: _NativeSessionTrace
) -> None:
    database = tmp_path / "warehouse.duckdb"
    with database.open("wb") as stream:
        stream.truncate(64 * 1024 * 1024 + offset)
    write_duckdb_row_count_run_inputs(tmp_path, database)
    _set_project_duckdb_execution(tmp_path, {"max-database-mib": 64})
    payloads = [
        _compiled_check_payload(operations=row_count_plan()),
        *_all_key_safety_checks(),
        _aggregate_check(),
        _aggregate_check(grouped=True),
    ]
    write_compiled_checks(tmp_path, checks=[payloads[family]])
    # A sparse file supplies only size evidence; no data read is possible.
    session_trace.failures[1] = "connect"
    engine = _CapturingAggregateEngine()
    invocation = RunService(
        start_path=tmp_path,
        engine=engine,
        adapter_registry=_tracking_registry(_TrackingAggregateFactory()),
    )._execute_invocation()
    result = invocation.service_result
    facts = invocation.resource_facts[0]
    assert facts.preliminary_allowed is (offset <= 0)
    assert (facts.native is None) is (offset > 0)
    assert facts.admission.value == ("not_reached" if offset > 0 else "unverified")
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    check = engine.result.contract_results[0].check_results[0]
    if offset > 0:
        assert check.status is CheckStatus.NOT_EXECUTABLE
        assert "RC_RUNTIME_SCAN_BUDGET_EXCEEDED" in {d.code for d in check.diagnostics}
        assert session_trace.sessions == []
    else:
        assert check.status is CheckStatus.ERROR
        assert "RC_ADAPTER_CONNECTION_FAILED" in {d.code for d in check.diagnostics}
        assert len(session_trace.sessions) == len(session_trace.closes) == 1
    assert not check.executed
    assert session_trace.aggregate_columns == session_trace.row_queries == []


@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_large_native_database_without_default_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, session_trace: _NativeSessionTrace
) -> None:
    database = _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=False,
    )
    duckdb = _duckdb_module()
    writer = duckdb.connect(str(database))
    try:
        # High-entropy synthetic padding makes the file exceed the old cap.
        columns = ", ".join(f"hash(i * 10 + {j}) as c{j}" for j in range(10))
        writer.execute(f"create table padding as select {columns} from range(1250000) r(i)")
    finally:
        writer.close()
    assert database.stat().st_size > 64 * 1024 * 1024
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(operations=row_count_plan()),
            *_all_key_safety_checks(),
            _aggregate_check(),
            _aggregate_check(grouped=True),
        ],
    )
    before = database.stat()
    engine = _CapturingAggregateEngine()
    invocation = RunService(start_path=tmp_path, engine=engine)._execute_invocation()
    result = invocation.service_result
    assert len(invocation.resource_facts) == 9
    assert all(
        fact.admission.value == "verified"
        and fact.capability_admitted is True
        and fact.native is not None
        and fact.native.readback_verified
        for fact in invocation.resource_facts
    )
    assert result.exit_category is ExitCategory.SUCCESS
    assert engine.result is not None
    checks = engine.result.contract_results[0].check_results
    assert len(checks) == 9
    assert all(check.status is CheckStatus.PASS and check.executed for check in checks)
    assert checks[0].source_value == checks[0].target_value == 1
    assert len(session_trace.sessions) == len(session_trace.closes) == 9
    monkeypatch.chdir(tmp_path)
    assert CliRunner().invoke(main, ["run"]).exit_code == 0
    assert len(session_trace.sessions) == len(session_trace.closes) == 18

    _set_project_duckdb_execution(tmp_path, {"max-database-mib": 64})
    blocked = RunService(start_path=tmp_path, engine=engine)._execute_invocation()
    result = blocked.service_result
    assert len(blocked.resource_facts) == 9
    assert all(
        fact.preliminary_allowed is False
        and fact.admission.value == "not_reached"
        and fact.native is None
        for fact in blocked.resource_facts
    )
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    checks = engine.result.contract_results[0].check_results
    assert all(
        check.status is CheckStatus.NOT_EXECUTABLE and not check.executed for check in checks
    )
    assert all(
        "RC_RUNTIME_SCAN_BUDGET_EXCEEDED" in {d.code for d in check.diagnostics} for check in checks
    )
    cli = CliRunner().invoke(main, ["run"])
    assert cli.exit_code == 3 and "RC_RUNTIME_SCAN_BUDGET_EXCEEDED" in cli.output
    assert len(session_trace.sessions) == len(session_trace.closes) == 18
    assert database.stat().st_size == before.st_size
    assert database.stat().st_mtime_ns == before.st_mtime_ns
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("local-adaptive-resource-targets")
@pytest.mark.parametrize("threshold", [1, 2, 3])
@pytest.mark.parametrize("same_relation", [False, True])
def test_optional_native_input_row_estimate_is_role_summed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, threshold: int, same_relation: bool
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=False,
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    if same_relation:
        write_compiled_contract(tmp_path, target_relation="qa.source_customers")
    _set_project_duckdb_execution(tmp_path, {"warn-estimated-input-rows": threshold})
    invocation = RunService(start_path=tmp_path)._execute_invocation()
    result = invocation.service_result
    native = invocation.resource_facts[0].native
    assert native is not None and native.estimate is not None
    assert native.estimate.value == ("exceeds_advisory" if threshold < 2 else "within_advisory")
    assert result.exit_category is ExitCategory.SUCCESS
    warnings = [
        d for d in result.diagnostics if d.code == "RC_RUNTIME_ESTIMATED_INPUT_ROWS_ADVISORY"
    ]
    assert bool(warnings) is (threshold < 2)
    assert all(d.severity is DiagnosticSeverity.WARNING for d in warnings)
    monkeypatch.chdir(tmp_path)
    cli = CliRunner().invoke(main, ["run"])
    assert cli.exit_code == 0
    assert ("RC_RUNTIME_ESTIMATED_INPUT_ROWS_ADVISORY" in cli.output) is (threshold < 2)
    assert "qa.source_customers" not in cli.output
    assert "qa.target_customers" not in cli.output
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("duckdb-owned-project-binding")
@pytest.mark.regression_capture("duckdb-worker-bound-session-scope")
def test_all_nine_checks_use_owned_transaction_and_qualified_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("5::INTEGER"),
        target_sql=_native_row("5::INTEGER"),
        grouped=False,
    )
    duckdb = _duckdb_module()
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(operations=row_count_plan()),
            *_all_key_safety_checks(),
            _aggregate_check(),
            _aggregate_check(grouped=True),
        ],
    )
    native = duckdb.connect(str(database), read_only=True)
    try:
        catalog = native.execute("pragma database_list").fetchall()[0][1]
    finally:
        native.close()
    before = database.read_bytes()
    sessions: list[list[str]] = []
    guards: list[list[str]] = []
    closures: list[str] = []
    scratch_paths: list[Path] = []

    class Connection:
        def __init__(self, connection: Any, *, actor: bool) -> None:
            self.connection = connection
            self.actor = actor
            self.statements: list[str] = []
            (sessions if actor else guards).append(self.statements)

        def execute(self, query: str, *args: Any, **kwargs: Any) -> Any:
            self.statements.append(query)
            return self.connection.execute(query, *args, **kwargs)

        def close(self) -> None:
            self.connection.close()
            self.statements.append("CLOSE")
            closures.append("actor" if self.actor else "guard")

    def connect(
        path: str, *, read_only: bool = False, config: dict[str, str] | None = None
    ) -> Connection:
        if path == ":memory:":
            assert not read_only and config is not None
            scratch = Path(config["temp_directory"])
            assert scratch.is_dir()
            scratch_paths.append(scratch)
            return Connection(duckdb.connect(path, config=config), actor=True)
        assert path == str(database)
        assert read_only is True and config is None
        return Connection(duckdb.connect(path, read_only=read_only), actor=False)

    monkeypatch.setattr(binding, "import_module", lambda name: SimpleNamespace(connect=connect))
    invocation = RunService(start_path=tmp_path)._execute_invocation()
    assert invocation.service_result.exit_category is ExitCategory.SUCCESS
    assert invocation.run_result is not None
    checks = invocation.run_result.contract_results[0].check_results
    assert invocation.scope_facts.complete is True
    facts = invocation.execution_facts
    assert facts.attempted_check_count == 9
    assert facts.peak_active_native_checks == 1
    comparison_attempts = 0
    assert len(checks) == len(sessions) == len(guards) == 9
    assert all(check.status is CheckStatus.PASS and check.executed for check in checks)
    monkeypatch.chdir(tmp_path)
    cli = CliRunner().invoke(main, ["run"])
    assert cli.exit_code == 0
    assert len(sessions) == len(guards) == len(scratch_paths) == 18
    assert len(set(scratch_paths)) == 18
    assert all(not path.exists() for path in scratch_paths)
    assert closures == ["actor", "guard"] * 18
    assert str(database) not in cli.output and str(tmp_path) not in cli.output
    for index, (check, statements, guard) in enumerate(
        zip(checks * 2, sessions, guards, strict=True)
    ):
        assert guard[-1] == "CLOSE" and "BEGIN TRANSACTION" not in guard
        start = statements.index("BEGIN TRANSACTION")
        assert any("ATTACH " in statement for statement in statements[:start])
        assert any(
            "current_setting('temp_directory')" in statement for statement in statements[:start]
        )
        statements = statements[start:]
        assert statements[-2:] == ["ROLLBACK", "CLOSE"]
        assert statements[1] == statements[3] == "pragma database_list"
        assert all("information_schema.tables" in statements[i] for i in (2, 4))
        if index < 9:
            native = invocation.resource_facts[index].native
            assert native is not None
            assert invocation.resource_facts[index].check_id == check.check_id
            assert native.execute_attempts == native.fetch_attempts == len(statements[5:-2])
            comparison_attempts += len(statements[5:-2])
        queries = [query for query in statements[5:-2] if not query.startswith("DESCRIBE ")]
        assert len(queries) == {"sum_diff": 3, "grouped_aggregate_diff": 4}.get(check.check_type, 1)
        assert all(f'"{catalog}"."qa".' in query for query in queries)
        assert all(query.lower().split(maxsplit=1)[0] in {"select", "with"} for query in queries)
        if check.check_type == "grouped_aggregate_diff":
            assert "typeof(s.group_key_" not in queries[-1]
            assert "s.group_key_0 is not distinct from t.group_key_0" in queries[-1]
            assert "s.group_key_1 is not distinct from t.group_key_1" in queries[-1]
    assert facts.native_execute_attempts == facts.native_fetch_attempts == comparison_attempts
    assert database.read_bytes() == before
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_binding_drift_between_aggregate_guards_stops_final_read(
    tmp_path: Path, grouped: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("5::INTEGER"),
        target_sql=_native_row("5::INTEGER"),
        grouped=grouped,
    )
    original = binding._OwnedDuckDbSession._read_bound_aggregate
    attempted: list[tuple[str, ...]] = []
    completed: list[tuple[str, ...]] = []
    sidecar = database.with_name(f"{database.name}.tmp")

    def read(
        session: binding._OwnedDuckDbSession,
        lease: binding._BindingLease,
        scope: binding._BindingScope,
        query: str,
        *,
        expected_columns: tuple[str, ...],
    ) -> _AggregateQueryResult:
        attempted.append(expected_columns)
        result = original(session, lease, scope, query, expected_columns=expected_columns)
        completed.append(expected_columns)
        if expected_columns == ("numeric_domain",):
            sidecar.touch()
        return result

    monkeypatch.setattr(binding._OwnedDuckDbSession, "_read_bound_aggregate", read)
    engine = _CapturingAggregateEngine()
    try:
        result = RunService(start_path=tmp_path, engine=engine).execute()
        _assert_native_aggregate_result(tmp_path, engine, CheckStatus.ERROR, result)
        assert "RC_RUNTIME_BINDING_PROOF_FAILED" in {d.code for d in result.diagnostics}
        assert completed == [("type_check",)] * (2 if grouped else 1) + [("numeric_domain",)]
        assert attempted[:-1] == completed
        assert len(attempted[-1]) == (9 if grouped else 3)
    finally:
        sidecar.unlink(missing_ok=True)
    writer = _duckdb_module().connect(str(database))
    writer.close()


@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_unavailable_catalog_estimate_is_advisory_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("1::INTEGER"),
        target_sql=_native_row("1::INTEGER"),
        grouped=False,
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    _set_project_duckdb_execution(tmp_path, {"warn-estimated-input-rows": 1})
    monkeypatch.setattr(binding, "_catalog_estimated_rows", lambda connection, relation: None)
    engine = _CapturingAggregateEngine()
    invocation = RunService(start_path=tmp_path, engine=engine)._execute_invocation()
    result = invocation.service_result
    native = invocation.resource_facts[0].native
    assert native is not None and native.estimate is not None
    assert native.estimate.value == "unknown"
    assert "RC_RUNTIME_ESTIMATED_INPUT_ROWS_UNKNOWN" in native.advisory_codes
    assert result.exit_category is ExitCategory.SUCCESS
    assert engine.result is not None
    check = engine.result.contract_results[0].check_results[0]
    assert check.status is CheckStatus.PASS and check.executed
    assert check.source_value == check.target_value == 1
    codes = {d.code for d in result.diagnostics}
    assert "RC_RUNTIME_ESTIMATED_INPUT_ROWS_ADVISORY" not in codes
    unknown = [d for d in result.diagnostics if d.code == "RC_RUNTIME_ESTIMATED_INPUT_ROWS_UNKNOWN"]
    assert len(unknown) == 1
    assert unknown[0].severity is DiagnosticSeverity.WARNING and unknown[0].hint
    monkeypatch.chdir(tmp_path)
    cli = CliRunner().invoke(main, ["run"])
    assert cli.exit_code == 0
    assert "RC_RUNTIME_ESTIMATED_INPUT_ROWS_UNKNOWN" in cli.output
    assert "RC_RUNTIME_ESTIMATED_INPUT_ROWS_ADVISORY" not in cli.output
    assert "qa.source_customers" not in cli.output and str(tmp_path) not in cli.output


@pytest.mark.regression_capture("local-adaptive-resource-targets")
@pytest.mark.parametrize("mode", ["auto", "percent", "fixed", "auto-threads"])
def test_fresh_native_targets_for_each_check_and_both_invocation_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from fractions import Fraction

    from recon_core.adapters._local_resource_observation import (
        _LinuxConstraints,
        _LocalObservation,
    )
    from recon_core.adapters.duckdb._native_resource_controls import _parse_native_size

    database = _write_native_aggregate_inputs(
        tmp_path,
        source_sql=_native_row("5::INTEGER"),
        target_sql=_native_row("5::INTEGER"),
        grouped=False,
    )
    duckdb = _duckdb_module()
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(operations=row_count_plan()),
            _aggregate_check(),
            _aggregate_check(grouped=True),
        ],
    )
    scratch = tmp_path / "private-scratch"
    scratch.mkdir()
    settings: dict[str, object] = {"scratch-directory": "private-scratch", "threads": 1}
    if mode == "auto-threads":
        settings.pop("threads")
    if mode == "percent":
        settings.update({"managed-memory": {"percent": 75}, "spill": {"percent": 75}})
    elif mode == "fixed":
        settings.update({"managed-memory": {"mib": 192}, "spill": {"mib": 192}})
    _set_project_duckdb_execution(tmp_path, settings)
    capacities = [(256, 512), (1024 if mode == "auto-threads" else 512, 1024), (128, 128)]
    observations: list[Path] = []
    observed_targets: list[tuple[int, int]] = []
    observed_threads: list[int] = []

    def observe(path: Path) -> _LocalObservation:
        memory, disk = capacities[len(observations) % len(capacities)]
        assert path.parent == scratch.resolve() and path.is_dir()
        observations.append(path)
        return _LocalObservation(
            host_available_bytes=2048 << 20,
            platform_cpu_count=8,
            affinity_count=4,
            linux_constraints=_LinuxConstraints(
                memory_headroom_bytes=memory << 20,
                cpu_capacity=Fraction(3, 2),
                memory_incomplete=False,
                cpu_incomplete=False,
            ),
            scratch_free_bytes=disk << 20,
            scratch_memory_backed=False,
            platform="linux",
        )

    original_open = binding._OwnedDuckDbSession.open
    original_recommendations = binding._read_native_recommendations

    def recommendations(native: Any) -> Any:
        # Deterministic native recommendation clamp; actual setting application
        # and actual project query execution are not mocked.
        actual = original_recommendations(native)
        if mode == "auto-threads":
            return type(actual)(memory_bytes=800 << 20, threads=4)
        return type(actual)(memory_bytes=200 << 20, threads=actual.threads)

    def open_session(session: binding._OwnedDuckDbSession) -> None:
        original_open(session)
        request = session._native_controls
        assert request is not None
        assert request.memory_bytes is not None and request.spill_bytes is not None
        native = session._connection
        memory = _parse_native_size(
            native.execute("SELECT current_setting('memory_limit')").fetchone()[0]
        )
        spill = _parse_native_size(
            native.execute("SELECT current_setting('max_temp_directory_size')").fetchone()[0]
        )
        assert memory is not None and memory.contains(request.memory_bytes)
        assert spill is not None and spill.contains(request.spill_bytes)
        assert request.threads is not None
        assert native.execute("SELECT current_setting('threads')").fetchone() == (request.threads,)
        observed_threads.append(request.threads)
        observed_targets.append((request.memory_bytes, request.spill_bytes))

    monkeypatch.setattr(binding, "_observe_local_resources", observe)
    monkeypatch.setattr(binding, "_read_native_recommendations", recommendations)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", open_session)
    observer = duckdb.connect(str(database), read_only=True)
    query = (
        "SELECT current_setting('memory_limit'), current_setting('threads'), "
        "current_setting('temp_directory'), current_setting('max_temp_directory_size')"
    )
    before = observer.execute(query).fetchone()
    try:
        engine = _CapturingAggregateEngine()
        result = RunService(start_path=tmp_path, engine=engine).execute()
        assert result.exit_category is ExitCategory.SUCCESS
        assert engine.result is not None
        checks = engine.result.contract_results[0].check_results
        assert len(checks) == 3
        assert all(check.status is CheckStatus.PASS and check.executed for check in checks)
        assert any("controller scope is incomplete" in d.message for d in result.diagnostics)
        parallelism = [d for d in result.diagnostics if "Automatic threads reduced" in d.message]
        assert len(parallelism) == (1 if mode == "auto-threads" else 0)
        assert all(d.severity is DiagnosticSeverity.WARNING and d.hint for d in parallelism)
        monkeypatch.chdir(tmp_path)
        cli = CliRunner().invoke(main, ["run"])
        assert cli.exit_code == 0
        assert "controller scope is incomplete" in cli.output
        assert ("Automatic threads reduced" in cli.output) is (mode == "auto-threads")
        assert observer.execute(query).fetchone() == before
        assert observer.execute("SELECT count(*) FROM qa.source_customers").fetchone() == (1,)
    finally:
        observer.close()
    mib = 1 << 20
    expected = {
        "auto": [
            (128 * mib, 512 * mib * 9 // 10),
            (200 * mib, 1024 * mib * 9 // 10),
            (64 * mib, 128 * mib * 9 // 10),
        ],
        "percent": [(192 * mib, 384 * mib), (384 * mib, 768 * mib), (96 * mib, 96 * mib)],
        "fixed": [(192 * mib, 192 * mib), (192 * mib, 192 * mib), (128 * mib, 128 * mib)],
        "auto-threads": [
            (128 * mib, 512 * mib * 9 // 10),
            (512 * mib, 1024 * mib * 9 // 10),
            (64 * mib, 128 * mib * 9 // 10),
        ],
    }[mode]
    assert observed_targets == expected * 2
    assert observed_threads == ([1, 2, 1] if mode == "auto-threads" else [1, 1, 1]) * 2
    assert len(set(observations)) == 6
    assert not list(scratch.iterdir())
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
@pytest.mark.parametrize("mode", ["embedded", "cli"])
def test_actual_run_service_cancels_active_native_spill(tmp_path: Path, mode: str) -> None:
    """Observe real spill, request caller cancellation, and prove native stop and release."""
    _duckdb_module()
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        import os
        import signal
        import threading
        import time
        from pathlib import Path
        import sys

        import duckdb
        from click.testing import CliRunner
        from recon_core.cli.main import main
        from recon_core.adapters.duckdb import _bound_execution as binding
        from recon_core.services import RunService
        from tests.services._run_service_fixtures import (
            write_duckdb_row_count_run_inputs, write_compiled_checks, row_count_plan,
            _compiled_check_payload, _assert_no_runtime_outputs,
        )
        from tests.services.test_run_service_aggregate_admission import (
            _aggregate_check, _set_project_duckdb_execution,
        )

        base = Path(sys.argv[1]).resolve()
        mode = sys.argv[2]
        database = base / "private-spill.duckdb"
        writer = duckdb.connect(str(database), config={"threads": "2", "memory_limit": "768MiB"})
        try:
            writer.execute("CREATE SCHEMA qa")
            writer.execute(
                "CREATE TABLE qa.source_customers AS "
                "SELECT i customer_id, 5::bigint revenue FROM range(3000000) t(i)"
            )
            writer.execute("CREATE TABLE qa.target_customers AS SELECT * FROM qa.source_customers")
        finally:
            writer.close()
        write_duckdb_row_count_run_inputs(base, database)
        grouped = _aggregate_check(grouped=True)
        grouped["metric"]["group_by"] = ["customer_id"]
        grouped["requirements"]["required_columns"] = ["revenue", "customer_id"]
        for op in grouped["plan"]["operations"]:
            if "group_by" in op:
                op["group_by"] = ["customer_id"]
        write_compiled_checks(base, checks=[grouped, _compiled_check_payload(
            operations=row_count_plan()
        )])
        scratch = base / "scratch"
        scratch.mkdir()
        _set_project_duckdb_execution(base, {
            "managed-memory": {"mib": 128}, "threads": 1,
            "spill": {"mib": 1024}, "scratch-directory": "scratch",
        })
        observer = duckdb.connect(str(database), read_only=True)
        setting_sql = (
            "SELECT current_setting('memory_limit'), current_setting('threads'), "
            "current_setting('temp_directory'), current_setting('max_temp_directory_size')"
        )
        before = observer.execute(setting_sql).fetchone()
        event = threading.Event()
        active = threading.Event()
        sessions = []
        native_interrupted = []
        native_errors = []
        final_calls = []
        spill_files = []
        closed = []
        outcomes = []
        original_open = binding._OwnedDuckDbSession.open
        original_close = binding._OwnedDuckDbSession.close

        class ObservedActor:
            def __init__(self, native):
                self.native = native
            def __getattr__(self, name):
                return getattr(self.native, name)
            def execute(self, statement, *args):
                # The final comparison (not setup, type guard or DESCRIBE).
                is_final = "total_group_count" in statement.lower() and not (
                    statement.lstrip().upper().startswith("DESCRIBE")
                )
                if is_final:
                    # The private scratch base was initially empty; setup and guards
                    # must not supply the positive file evidence for this comparison.
                    assert not any(
                        item.is_file() and item.stat().st_size > 0
                        for item in scratch.rglob("*")
                    ), "Spill evidence must start empty before final comparison."
                    final_calls.append(1)
                    active.set()
                try:
                    return self.native.execute(statement, *args)
                except duckdb.Error as error:
                    if is_final:
                        native_interrupted.append("interrupt" in str(error).lower())
                        native_errors.append(type(error).__name__)
                    raise
                finally:
                    if is_final:
                        active.clear()

        def open_session(session):
            original_open(session)
            sessions.append(session)
            session._connection = ObservedActor(session._connection)

        def close_session(session):
            diagnostics = original_close(session)
            closed.append(session.released)
            return diagnostics

        binding._OwnedDuckDbSession.open = open_session
        binding._OwnedDuckDbSession.close = close_session

        original_execute = RunService._execute_invocation

        def capture_invocation(self, **kwargs):
            outcome = original_execute(self, **kwargs)
            outcomes.append(outcome)
            return outcome

        RunService._execute_invocation = capture_invocation
        seen = threading.Event()
        done = threading.Event()
        failures = []
        previous = signal.getsignal(signal.SIGINT)

        def request_after_spill():
            try:
                deadline = time.monotonic() + 45
                while not done.is_set() and time.monotonic() < deadline:
                    if active.is_set():
                        for entry in scratch.rglob("*"):
                            try:
                                if entry.is_file() and entry.stat().st_size > 0:
                                    spill_files.append(entry.name)
                                    seen.set()
                                    break
                            except FileNotFoundError:
                                continue
                    if seen.is_set():
                        assert active.is_set(), "Spill was no longer active."
                        if mode == "cli":
                            signal.raise_signal(signal.SIGINT)
                        else:
                            event.set()
                        return
                    time.sleep(0.005)
                raise AssertionError("No active native spill observed.")
            except BaseException as error:
                failures.append(error)
                event.set()

        watcher = threading.Thread(target=request_after_spill, daemon=False)
        watcher.start()
        try:
            if mode == "cli":
                os.chdir(base)
                result = CliRunner().invoke(main, ["run", "--timeout-seconds", "60"])
                assert result.exit_code == 3, result.output
                assert "RC_RUNTIME_RUN_CANCELLED" in result.output
                assert signal.getsignal(signal.SIGINT) == previous
            else:
                RunService(start_path=base).execute(timeout_seconds=60, cancel_event=event)
            done.set()
            watcher.join(20)
            assert not watcher.is_alive()
            assert not failures and seen.is_set(), (
                f"failures={failures!r}; final_calls={final_calls!r}; "
                f"spill_files={spill_files!r}; native_errors={native_errors!r}; "
                f"results={[o.service_result.to_dict() for o in outcomes]!r}"
            )
            assert final_calls == [1]
            assert native_interrupted == [True]
            assert len(sessions) == 1 and closed == [True]
            assert len(outcomes) == 1
            outcome = outcomes[0]
            assert outcome.service_result.exit_category.value == "runtime_error"
            assert outcome.stop_cause.value == "run_cancelled"
            assert outcome.scope_facts.complete is True
            checks = outcome.run_result.contract_results[0].check_results
            assert checks[0].status.value == "error" and not checks[0].executed
            assert checks[0].source_value is None and checks[0].target_value is None
            assert checks[1].reason_code.value == "run_cancelled"
            assert not checks[1].executed
            assert observer.execute(setting_sql).fetchone() == before
            assert observer.execute("SELECT 42").fetchone() == (42,)
            assert not list(scratch.iterdir())
            assert not any(
                t.name in ("recon-run-control", "recon-cli-run") for t in threading.enumerate()
            )
            _assert_no_runtime_outputs(base)
        finally:
            event.set()
            done.set()
            watcher.join(20)
            observer.close()
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path.resolve()), mode],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
