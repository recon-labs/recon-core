from pathlib import Path

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
)
from recon_core.adapters.duckdb import ADAPTER_QUERY_FAILED, AdapterLifecycleError
from recon_core.artifacts import (
    LoadedCheckPlan,
    LoadedCompiledCheck,
    LoadedCompiledContractArtifact,
    LoadedCompiledEndpoint,
)
from recon_core.check_engine import CheckReason, CheckStatus, execute_row_count_check
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


def test_execute_row_count_check_passes_with_equal_counts() -> None:
    adapter = RecordingAdapter(
        result=QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((7, 7, 0),),
            row_count=1,
        )
    )

    result = execute_row_count_check(_row_count_check(), _contract(), adapter)

    assert result.status is CheckStatus.PASS
    assert result.executed
    assert result.reason_code is None
    assert result.source_value == 7
    assert result.target_value == 7
    assert result.diff_value == 0
    assert result.artifact_refs == ()
    assert result.sink_refs == ()
    assert result.diagnostics == ()
    assert len(adapter.queries) == 1
    assert "source_row_count" in adapter.queries[0]
    assert "target_row_count" in adapter.queries[0]
    assert "row_count_diff" in adapter.queries[0]
    assert "cross join" in adapter.queries[0]


def test_execute_row_count_check_fails_with_unequal_counts() -> None:
    adapter = RecordingAdapter(
        result=QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((7, 9, -2),),
            row_count=1,
        )
    )

    result = execute_row_count_check(_row_count_check(), _contract(), adapter)

    assert result.status is CheckStatus.FAIL
    assert result.executed
    assert result.reason_code is None
    assert result.source_value == 7
    assert result.target_value == 9
    assert result.diff_value == -2
    assert result.artifact_refs == ()
    assert result.sink_refs == ()
    assert len(adapter.queries) == 1


@pytest.mark.parametrize(
    "query_result",
    [
        QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=(),
            row_count=0,
        ),
        QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((7, 7, 0), (8, 8, 0)),
            row_count=2,
        ),
        QueryResult(
            columns=("source_row_count", "target_row_count"),
            rows=((7, 7),),
            row_count=1,
        ),
        QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=(("7", 7, 0),),
            row_count=1,
        ),
        QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((7, 9, 0),),
            row_count=1,
        ),
    ],
)
def test_execute_row_count_check_reports_malformed_result_shape(query_result: QueryResult) -> None:
    adapter = RecordingAdapter(result=query_result)

    result = execute_row_count_check(_row_count_check(), _contract(), adapter)

    assert result.status is CheckStatus.ERROR
    assert not result.executed
    assert result.source_value is None
    assert result.target_value is None
    assert result.diff_value is None
    assert result.artifact_refs == ()
    assert result.sink_refs == ()
    assert result.diagnostics[0].code == "RC_RUNTIME_ROW_COUNT_RESULT_INVALID"
    assert len(adapter.queries) == 1


def test_execute_row_count_check_preserves_sanitized_adapter_query_error() -> None:
    adapter = RecordingAdapter(
        error=AdapterLifecycleError(
            Diagnostic(
                code=ADAPTER_QUERY_FAILED,
                severity=DiagnosticSeverity.ERROR,
                message="DuckDB query execution failed.",
                resource_type="adapter",
                resource_name="duckdb",
                hint=(
                    "DuckDB raised RuntimeError. Raw adapter, SQL, database error, and "
                    "rendered profile text were suppressed."
                ),
            )
        )
    )

    result = execute_row_count_check(_row_count_check(), _contract(), adapter)

    assert result.status is CheckStatus.ERROR
    assert not result.executed
    assert result.diagnostics[0].code == ADAPTER_QUERY_FAILED
    assert "RuntimeError" in _diagnostic_text(result.diagnostics)
    assert "super-secret" not in _diagnostic_text(result.diagnostics)
    assert "select" not in _diagnostic_text(result.diagnostics).lower()


def test_execute_row_count_check_blocks_other_check_types_before_adapter_execution() -> None:
    adapter = RecordingAdapter()

    result = execute_row_count_check(
        _row_count_check(check_type="key_diff"),
        _contract(),
        adapter,
    )

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.reason_code is CheckReason.UNSUPPORTED_CHECK_TYPE
    assert result.diagnostics[0].code == "RC_RUNTIME_UNSUPPORTED_CHECK_TYPE"
    assert adapter.queries == []


@pytest.mark.parametrize(
    "operations",
    [
        ({"type": "row_count", "side": "source"}, {"type": "compare_counts"}),
        (
            {"type": "row_count", "side": "target"},
            {"type": "row_count", "side": "source"},
            {"type": "compare_counts"},
        ),
        (
            {"type": "row_count", "side": "source"},
            {"type": "row_count", "side": "target"},
            {"type": "future_operation"},
        ),
    ],
)
def test_execute_row_count_check_blocks_unsupported_plan_shape_before_adapter_execution(
    operations: tuple[dict[str, object], ...],
) -> None:
    adapter = RecordingAdapter()

    result = execute_row_count_check(_row_count_check(operations=operations), _contract(), adapter)

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.reason_code is CheckReason.UNSUPPORTED_TYPED_OPERATION
    assert result.diagnostics[0].code == "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
    assert adapter.queries == []


@pytest.mark.parametrize(
    ("operation", "reason", "diagnostic_code"),
    [
        (
            {"type": "row_count", "side": "source", "execution_placement": "source"},
            CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
            "RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT",
        ),
        (
            {"type": "row_count", "side": "source", "comparison_location": "source"},
            CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
            "RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT",
        ),
        (
            {"type": "row_count", "side": "source", "materialization_policy": "temporary_table"},
            CheckReason.UNSUPPORTED_MATERIALIZATION_POLICY,
            "RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY",
        ),
    ],
)
def test_execute_row_count_check_blocks_reserved_runtime_metadata_before_adapter_execution(
    operation: dict[str, object],
    reason: CheckReason,
    diagnostic_code: str,
) -> None:
    adapter = RecordingAdapter()
    operations = (
        operation,
        {"type": "row_count", "side": "target"},
        {"type": "compare_counts"},
    )

    result = execute_row_count_check(_row_count_check(operations=operations), _contract(), adapter)

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.reason_code is reason
    assert result.diagnostics[0].code == diagnostic_code
    assert adapter.queries == []


def test_execute_row_count_check_blocks_query_endpoints_before_adapter_execution() -> None:
    adapter = RecordingAdapter()

    result = execute_row_count_check(
        _row_count_check(),
        _contract(source_relation=None, source_query="select * from super_secret_table"),
        adapter,
    )

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.reason_code is CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT
    assert result.diagnostics[0].code == "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"
    assert "super_secret_table" not in _diagnostic_text(result.diagnostics)
    assert adapter.queries == []


def test_execute_row_count_check_blocks_cross_context_before_adapter_execution() -> None:
    adapter = RecordingAdapter()

    result = execute_row_count_check(
        _row_count_check(),
        _contract(source_connection="legacy", target_connection="warehouse"),
        adapter,
    )

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.reason_code is CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT
    assert result.diagnostics[0].code == "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"
    assert "legacy" not in _diagnostic_text(result.diagnostics)
    assert "warehouse" not in _diagnostic_text(result.diagnostics)
    assert adapter.queries == []


class RecordingAdapter(BaseAdapter):
    adapter_type = "duckdb"
    adapter_version = "test"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def __init__(
        self,
        *,
        result: QueryResult | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(connection=ConnectionConfig(name="warehouse", type="duckdb"))
        self.result = result or QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((1, 1, 0),),
            row_count=1,
        )
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
        return AdapterCapabilities(
            {
                "relations": CapabilitySupport.FULL,
                "queries": CapabilitySupport.UNSUPPORTED,
                "cte_support": CapabilitySupport.FULL,
                "row_count": CapabilitySupport.FULL,
            }
        )


def _row_count_check(
    *,
    check_type: str = "row_count_diff",
    operations: tuple[dict[str, object], ...] | None = None,
) -> LoadedCompiledCheck:
    return LoadedCompiledCheck(
        id="check.ecommerce_recon.customer_revenue.row_count_diff",
        name="row_count_diff",
        check_type=check_type,
        contract_name="customer_revenue",
        plan=LoadedCheckPlan(
            id="plan.ecommerce_recon.customer_revenue.row_count_diff",
            operations=operations
            or (
                {"type": "row_count", "side": "source"},
                {"type": "row_count", "side": "target"},
                {"type": "compare_counts"},
            ),
            required_capabilities=("row_count", "cte_support"),
        ),
        payload={"identity": {"kind": "none", "keys": []}},
    )


def _contract(
    *,
    source_connection: str = "warehouse",
    target_connection: str = "warehouse",
    source_relation: str | None = "qa.source_customers",
    target_relation: str | None = "qa.target_customers",
    source_query: str | None = None,
    target_query: str | None = None,
) -> LoadedCompiledContractArtifact:
    return LoadedCompiledContractArtifact(
        path=Path("target/compiled_contracts/customer_revenue.yml"),
        project_name="ecommerce_recon",
        project_version=None,
        contract_id="contract.ecommerce_recon.customer_revenue",
        contract_name="customer_revenue",
        source_file="recon.yml",
        source=LoadedCompiledEndpoint(
            connection=source_connection,
            relation=source_relation,
            query=source_query,
        ),
        target=LoadedCompiledEndpoint(
            connection=target_connection,
            relation=target_relation,
            query=target_query,
        ),
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
