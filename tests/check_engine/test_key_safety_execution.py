from pathlib import Path
from typing import Any

import pytest

from recon_core.adapters import (
    ADAPTER_API_VERSION,
    AdapterCapabilities,
    BaseAdapter,
    CapabilitySupport,
    ColumnMetadata,
    ConnectionConfig,
    QueryResult,
    Relation,
    RenderedSql,
)
from recon_core.adapters.duckdb import (
    ADAPTER_QUERY_FAILED,
    AdapterLifecycleError,
    DuckDbSqlRenderer,
)
from recon_core.artifacts import (
    LoadedCheckPlan,
    LoadedCompiledCheck,
    LoadedCompiledContractArtifact,
    LoadedCompiledEndpoint,
)
from recon_core.check_engine import CheckReason, CheckStatus
from recon_core.check_engine.key_safety import (
    DUPLICATE_GRAIN_KEYS,
    EXTRA_KEYS,
    KEY_SAFETY_RESULT_INVALID,
    MISSING_KEYS,
    NULL_GRAIN_KEYS,
    execute_key_safety_check,
)
from recon_core.check_engine.scan_budget import (
    BOUNDED_LOCAL_SCAN_ALLOWED,
    BOUNDED_LOCAL_SCAN_REQUIRED,
    SCAN_BUDGET_EXCEEDED,
    SCAN_ESTIMATE_UNKNOWN,
    SCAN_ESTIMATE_UNSUPPORTED,
    UNSAFE_SCAN_PREFLIGHT,
    ScanBudgetContext,
    ScanBudgetDecision,
    ScanEstimateState,
    ScanExecutionEnvironment,
    classify_scan_budget,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


def test_scan_budget_allows_explicit_bounded_local_relation_backed_context() -> None:
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.LOCAL_DEV,
            relation_backed=True,
            bounded=True,
        )
    )

    assert decision.allowed
    assert decision.reason is None
    assert decision.classification == "bounded_local"
    assert decision.message == "Bounded local/dev relation-backed scan may execute."
    assert [diagnostic.code for diagnostic in decision.diagnostics] == [BOUNDED_LOCAL_SCAN_ALLOWED]
    assert decision.diagnostics[0].severity is DiagnosticSeverity.INFO


@pytest.mark.parametrize(
    ("relation_backed", "bounded"),
    [
        (False, True),
        (True, False),
        (False, False),
    ],
)
def test_scan_budget_requires_local_relation_backed_bounded_classification(
    relation_backed: bool,
    bounded: bool,
) -> None:
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.LOCAL_DEV,
            relation_backed=relation_backed,
            bounded=bounded,
        )
    )

    assert not decision.allowed
    assert decision.reason is CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED
    assert decision.classification == "not_executable"
    assert [diagnostic.code for diagnostic in decision.diagnostics] == [BOUNDED_LOCAL_SCAN_REQUIRED]
    assert "internal bounded local/dev" in decision.diagnostics[0].message
    assert "internal local/dev scan guard" in (decision.diagnostics[0].hint or "")


@pytest.mark.parametrize(
    ("estimate_state", "reason", "diagnostic_code"),
    [
        (
            ScanEstimateState.PRESENT,
            CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED,
            BOUNDED_LOCAL_SCAN_REQUIRED,
        ),
        (
            ScanEstimateState.UNKNOWN,
            CheckReason.SCAN_ESTIMATE_UNKNOWN,
            SCAN_ESTIMATE_UNKNOWN,
        ),
        (
            ScanEstimateState.UNAVAILABLE,
            CheckReason.SCAN_ESTIMATE_UNSUPPORTED,
            SCAN_ESTIMATE_UNSUPPORTED,
        ),
        (
            ScanEstimateState.UNSUPPORTED,
            CheckReason.SCAN_ESTIMATE_UNSUPPORTED,
            SCAN_ESTIMATE_UNSUPPORTED,
        ),
        (
            ScanEstimateState.MALFORMED,
            CheckReason.SCAN_ESTIMATE_UNSUPPORTED,
            SCAN_ESTIMATE_UNSUPPORTED,
        ),
        (
            ScanEstimateState.OVER_BUDGET,
            CheckReason.SCAN_BUDGET_EXCEEDED,
            SCAN_BUDGET_EXCEEDED,
        ),
        (
            ScanEstimateState.UNSAFE_PREFLIGHT,
            CheckReason.UNSAFE_SCAN_PREFLIGHT,
            UNSAFE_SCAN_PREFLIGHT,
        ),
    ],
)
def test_scan_budget_fail_closed_paths_are_not_executable(
    estimate_state: ScanEstimateState,
    reason: CheckReason,
    diagnostic_code: str,
) -> None:
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.PRODUCTION,
            relation_backed=True,
            bounded=False,
            estimate_state=estimate_state,
        )
    )

    assert not decision.allowed
    assert decision.reason is reason
    assert decision.classification == "not_executable"
    assert len(decision.diagnostics) == 1
    diagnostic = decision.diagnostics[0]
    assert diagnostic.code == diagnostic_code
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert "not executable" in diagnostic.message
    if diagnostic_code == SCAN_ESTIMATE_UNKNOWN:
        assert "internal local/dev scan guard" in (diagnostic.hint or "")


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "select",
        "customer_id",
        "source_table",
        "target_table",
        "password",
    ],
)
def test_scan_budget_diagnostics_do_not_include_source_target_details(
    unsafe_text: str,
) -> None:
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.PRODUCTION,
            relation_backed=True,
            bounded=False,
            estimate_state=ScanEstimateState.OVER_BUDGET,
        )
    )

    diagnostic_text = " ".join(
        part
        for diagnostic in decision.diagnostics
        for part in (diagnostic.code, diagnostic.message, diagnostic.hint or "")
    ).lower()
    assert unsafe_text not in diagnostic_text


_IDENTITY: dict[str, object] = {
    "kind": "grain",
    "keys": ["customer_id", "month"],
}

_KEY_CHECK_OPERATIONS: tuple[tuple[str, dict[str, object]], ...] = (
    ("null_source_keys", {"type": "null_key", "side": "source", "identity": _IDENTITY}),
    ("null_target_keys", {"type": "null_key", "side": "target", "identity": _IDENTITY}),
    (
        "duplicate_source_keys",
        {"type": "duplicate_key", "side": "source", "identity": _IDENTITY},
    ),
    (
        "duplicate_target_keys",
        {"type": "duplicate_key", "side": "target", "identity": _IDENTITY},
    ),
    (
        "missing_keys",
        {"type": "key_diff", "direction": "source_minus_target", "identity": _IDENTITY},
    ),
    (
        "extra_keys",
        {"type": "key_diff", "direction": "target_minus_source", "identity": _IDENTITY},
    ),
)


@pytest.mark.parametrize(("check_type", "operation"), _KEY_CHECK_OPERATIONS)
def test_execute_key_safety_check_passes_without_violations(
    check_type: str,
    operation: dict[str, object],
) -> None:
    adapter = _duckdb_adapter()
    _create_key_tables(
        adapter,
        source_rows=((1, "2026-01"), (2, "2026-02")),
        target_rows=((1, "2026-01"), (2, "2026-02")),
    )

    result = execute_key_safety_check(
        _key_check(check_type, operation),
        _contract(),
        adapter,
        scan_budget_decision=_allowed_scan_budget(),
    )

    assert result.status is CheckStatus.PASS
    assert result.executed
    assert result.reason_code is None
    assert result.failure_count == 0
    assert result.artifact_refs == ()
    assert result.sink_refs == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [BOUNDED_LOCAL_SCAN_ALLOWED]
    assert len(adapter.queries) == 1
    assert adapter.queries[0].startswith("select count(*) as failure_count\nfrom (")
    assert "recon_key_safety_failures" in adapter.queries[0]


@pytest.mark.parametrize(
    ("check_type", "operation", "source_rows", "target_rows", "failure_count", "code"),
    [
        (
            "null_source_keys",
            {"type": "null_key", "side": "source", "identity": _IDENTITY},
            ((None, "2026-01"), (1, "2026-02")),
            ((1, "2026-02"),),
            1,
            NULL_GRAIN_KEYS,
        ),
        (
            "null_target_keys",
            {"type": "null_key", "side": "target", "identity": _IDENTITY},
            ((1, "2026-02"),),
            ((None, "2026-01"), (1, "2026-02")),
            1,
            NULL_GRAIN_KEYS,
        ),
        (
            "duplicate_source_keys",
            {"type": "duplicate_key", "side": "source", "identity": _IDENTITY},
            (
                (None, "2026-01"),
                (None, "2026-01"),
                (2, "2026-02"),
                (2, "2026-02"),
            ),
            ((2, "2026-02"),),
            1,
            DUPLICATE_GRAIN_KEYS,
        ),
        (
            "duplicate_target_keys",
            {"type": "duplicate_key", "side": "target", "identity": _IDENTITY},
            ((2, "2026-02"),),
            (
                (None, "2026-01"),
                (None, "2026-01"),
                (2, "2026-02"),
                (2, "2026-02"),
            ),
            1,
            DUPLICATE_GRAIN_KEYS,
        ),
        (
            "missing_keys",
            {"type": "key_diff", "direction": "source_minus_target", "identity": _IDENTITY},
            ((1, "2026-01"), (1, "2026-01"), (2, "2026-02"), (None, "2026-03")),
            ((1, "2026-01"),),
            1,
            MISSING_KEYS,
        ),
        (
            "extra_keys",
            {"type": "key_diff", "direction": "target_minus_source", "identity": _IDENTITY},
            ((1, "2026-01"),),
            ((1, "2026-01"), (2, "2026-02"), (2, "2026-02"), (None, "2026-03")),
            1,
            EXTRA_KEYS,
        ),
    ],
)
def test_execute_key_safety_check_fails_with_count_only(
    check_type: str,
    operation: dict[str, object],
    source_rows: tuple[tuple[int | None, str | None], ...],
    target_rows: tuple[tuple[int | None, str | None], ...],
    failure_count: int,
    code: str,
) -> None:
    adapter = _duckdb_adapter()
    _create_key_tables(adapter, source_rows=source_rows, target_rows=target_rows)

    result = execute_key_safety_check(
        _key_check(check_type, operation),
        _contract(),
        adapter,
        scan_budget_decision=_allowed_scan_budget(),
    )

    diagnostic_text = _diagnostic_text(result.diagnostics)

    assert result.status is CheckStatus.FAIL
    assert result.executed
    assert result.failure_count == failure_count
    assert result.source_value is None
    assert result.target_value is None
    assert result.artifact_refs == ()
    assert result.sink_refs == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        code,
        BOUNDED_LOCAL_SCAN_ALLOWED,
    ]
    assert "2026" not in diagnostic_text
    assert "customer_id" not in diagnostic_text
    assert "source_table" not in diagnostic_text
    assert "target_table" not in diagnostic_text


@pytest.mark.parametrize(("check_type", "operation"), _KEY_CHECK_OPERATIONS)
def test_execute_key_safety_check_passes_on_empty_sides(
    check_type: str,
    operation: dict[str, object],
) -> None:
    adapter = _duckdb_adapter()
    _create_key_tables(adapter, source_rows=(), target_rows=())

    result = execute_key_safety_check(
        _key_check(check_type, operation),
        _contract(),
        adapter,
        scan_budget_decision=_allowed_scan_budget(),
    )

    assert result.status is CheckStatus.PASS
    assert result.failure_count == 0


@pytest.mark.parametrize(
    "query_result",
    [
        QueryResult(columns=("failure_count",), rows=(), row_count=0),
        QueryResult(columns=("failure_count",), rows=((0,), (1,)), row_count=2),
        QueryResult(columns=("unexpected",), rows=((0,),), row_count=1),
        QueryResult(columns=("failure_count",), rows=(("0",),), row_count=1),
        QueryResult(columns=("failure_count",), rows=((-1,),), row_count=1),
    ],
)
def test_execute_key_safety_check_reports_malformed_count_result(
    query_result: QueryResult,
) -> None:
    adapter = RecordingAdapter(result=query_result)

    result = execute_key_safety_check(
        _key_check("missing_keys", _KEY_CHECK_OPERATIONS[4][1]),
        _contract(),
        adapter,
        scan_budget_decision=_allowed_scan_budget(),
    )

    assert result.status is CheckStatus.ERROR
    assert not result.executed
    assert result.failure_count is None
    assert result.artifact_refs == ()
    assert result.sink_refs == ()
    assert result.diagnostics[0].code == KEY_SAFETY_RESULT_INVALID
    assert len(adapter.queries) == 1


def test_execute_key_safety_check_reports_renderer_failure_without_querying_adapter() -> None:
    adapter = RecordingAdapter()

    result = execute_key_safety_check(
        _key_check("missing_keys", _KEY_CHECK_OPERATIONS[4][1]),
        _contract(),
        adapter,
        renderer=RaisingRenderer(),
        scan_budget_decision=_allowed_scan_budget(),
    )

    diagnostic_text = _diagnostic_text(result.diagnostics)

    assert result.status is CheckStatus.ERROR
    assert not result.executed
    assert result.diagnostics[0].code == "RC_ADAPTER_OPERATION_RENDER_FAILED"
    assert "select" not in diagnostic_text.lower()
    assert adapter.queries == []


def test_execute_key_safety_check_suppresses_leaky_adapter_query_diagnostic() -> None:
    adapter = RecordingAdapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="duckdb",
            config={"database": "warehouse.duckdb", "password": "super-secret"},
        ),
        error=AdapterLifecycleError(
            Diagnostic(
                code="RC_CUSTOM_QUERY_FAILED",
                severity=DiagnosticSeverity.ERROR,
                message=(
                    "select customer_id from source_table failed with "
                    "Catalog Error: missing target_table"
                ),
                resource_type="adapter",
                resource_name="source_table",
                path="duckdb://warehouse.duckdb",
                hint="password=super-secret",
            )
        ),
    )

    result = execute_key_safety_check(
        _key_check("missing_keys", _KEY_CHECK_OPERATIONS[4][1]),
        _contract(),
        adapter,
        scan_budget_decision=_allowed_scan_budget(),
    )

    diagnostic_text = _diagnostic_text(result.diagnostics)

    assert result.status is CheckStatus.ERROR
    assert result.diagnostics[0].code == ADAPTER_QUERY_FAILED
    assert "super-secret" not in diagnostic_text
    assert "warehouse.duckdb" not in diagnostic_text
    assert "select" not in diagnostic_text.lower()
    assert "Catalog Error" not in diagnostic_text
    assert "source_table" not in diagnostic_text
    assert "target_table" not in diagnostic_text


def test_execute_key_safety_check_blocks_scan_budget_before_adapter_query() -> None:
    adapter = RecordingAdapter()

    result = execute_key_safety_check(
        _key_check("missing_keys", _KEY_CHECK_OPERATIONS[4][1]),
        _contract(),
        adapter,
        scan_budget_decision=classify_scan_budget(
            ScanBudgetContext(
                environment=ScanExecutionEnvironment.PRODUCTION,
                relation_backed=True,
                bounded=False,
                estimate_state=ScanEstimateState.UNKNOWN,
            )
        ),
    )

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert not result.executed
    assert result.reason_code is CheckReason.SCAN_ESTIMATE_UNKNOWN
    assert adapter.queries == []


def test_execute_key_safety_check_rejects_non_grain_identity_before_adapter_query() -> None:
    adapter = RecordingAdapter()

    result = execute_key_safety_check(
        _key_check(
            "missing_keys",
            {
                "type": "key_diff",
                "direction": "source_minus_target",
                "identity": {"kind": "cdc", "keys": ["customer_id", "month"]},
            },
        ),
        _contract(),
        adapter,
        scan_budget_decision=_allowed_scan_budget(),
    )

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert not result.executed
    assert result.reason_code is CheckReason.UNSUPPORTED_TYPED_OPERATION
    assert result.diagnostics[0].code == "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
    assert adapter.queries == []


def test_execute_key_safety_check_rejects_identity_keys_that_do_not_match_contract() -> None:
    adapter = RecordingAdapter()

    result = execute_key_safety_check(
        _key_check(
            "missing_keys",
            {
                "type": "key_diff",
                "direction": "source_minus_target",
                "identity": {"kind": "grain", "keys": ["cdc_id"]},
            },
        ),
        _contract(),
        adapter,
        scan_budget_decision=_allowed_scan_budget(),
    )

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert not result.executed
    assert result.reason_code is CheckReason.UNSUPPORTED_TYPED_OPERATION
    assert result.diagnostics[0].code == "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
    assert adapter.queries == []


def _duckdb_adapter() -> "DuckDbExecutionAdapter":
    duckdb = pytest.importorskip("duckdb")
    return DuckDbExecutionAdapter(duckdb.connect(database=":memory:"))


class DuckDbExecutionAdapter(BaseAdapter):
    adapter_type = "duckdb"
    adapter_version = "test"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def __init__(self, connection_handle: Any) -> None:
        super().__init__(connection=ConnectionConfig(name="warehouse", type="duckdb"))
        self.connection_handle = connection_handle
        self.queries: list[str] = []

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def execute(self, query: str) -> QueryResult:
        self.queries.append(query)
        cursor = self.connection_handle.execute(query)
        columns = tuple(column[0] for column in cursor.description or ())
        rows = tuple(tuple(row) for row in cursor.fetchall())
        return QueryResult(columns=columns, rows=rows, row_count=len(rows))

    def relation_exists(self, relation: Relation) -> bool:
        return False

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        return ()

    def capabilities(self) -> AdapterCapabilities:
        return _key_safety_capabilities()


class RecordingAdapter(BaseAdapter):
    adapter_type = "duckdb"
    adapter_version = "test"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def __init__(
        self,
        *,
        connection: ConnectionConfig | None = None,
        result: QueryResult | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(connection=connection or ConnectionConfig(name="warehouse", type="duckdb"))
        self.result = result or QueryResult(columns=("failure_count",), rows=((0,),), row_count=1)
        self.error = error
        self.queries: list[str] = []

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def execute(self, query: str) -> QueryResult:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return self.result

    def relation_exists(self, relation: Relation) -> bool:
        return False

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        return ()

    def capabilities(self) -> AdapterCapabilities:
        return _key_safety_capabilities()


class RaisingRenderer(DuckDbSqlRenderer):
    def render_operation(
        self,
        operation: dict[str, Any],
        *,
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        raise RuntimeError("select customer_id from source_table failed")


def _key_safety_capabilities() -> AdapterCapabilities:
    return AdapterCapabilities(
        {
            "relations": CapabilitySupport.FULL,
            "queries": CapabilitySupport.UNSUPPORTED,
            "cte_support": CapabilitySupport.FULL,
            "key_diff": CapabilitySupport.FULL,
            "null_key": CapabilitySupport.FULL,
            "duplicate_key": CapabilitySupport.FULL,
        }
    )


def _create_key_tables(
    adapter: DuckDbExecutionAdapter,
    *,
    source_rows: tuple[tuple[int | None, str | None], ...],
    target_rows: tuple[tuple[int | None, str | None], ...],
) -> None:
    adapter.connection_handle.execute(
        "create table source_table (customer_id integer, month varchar)"
    )
    adapter.connection_handle.execute(
        "create table target_table (customer_id integer, month varchar)"
    )
    if source_rows:
        adapter.connection_handle.executemany(
            "insert into source_table values (?, ?)",
            source_rows,
        )
    if target_rows:
        adapter.connection_handle.executemany(
            "insert into target_table values (?, ?)",
            target_rows,
        )


def _key_check(
    check_type: str,
    operation: dict[str, object],
) -> LoadedCompiledCheck:
    return LoadedCompiledCheck(
        id=f"check.ecommerce_recon.customer_revenue.{check_type}",
        name=check_type,
        check_type=check_type,
        contract_name="customer_revenue",
        plan=LoadedCheckPlan(
            id=f"plan.ecommerce_recon.customer_revenue.{check_type}",
            operations=(operation,),
            required_capabilities=("cte_support",),
        ),
        payload={"identity": _IDENTITY},
    )


def _contract() -> LoadedCompiledContractArtifact:
    return LoadedCompiledContractArtifact(
        path=Path("target/compiled_contracts/customer_revenue.yml"),
        project_name="ecommerce_recon",
        project_version=None,
        contract_id="contract.ecommerce_recon.customer_revenue",
        contract_name="customer_revenue",
        source_file="recon.yml",
        source=LoadedCompiledEndpoint(
            connection="warehouse",
            relation="source_table",
        ),
        target=LoadedCompiledEndpoint(
            connection="warehouse",
            relation="target_table",
        ),
        grain_keys=("customer_id", "month"),
    )


def _allowed_scan_budget() -> ScanBudgetDecision:
    return classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.LOCAL_DEV,
            relation_backed=True,
            bounded=True,
        )
    )


def _diagnostic_text(diagnostics: tuple[Diagnostic, ...]) -> str:
    fields: list[str] = []
    for diagnostic in diagnostics:
        fields.extend(
            str(value)
            for value in (
                diagnostic.message,
                diagnostic.hint,
                diagnostic.resource_name,
                diagnostic.path,
            )
            if value is not None
        )
    return " ".join(fields)
