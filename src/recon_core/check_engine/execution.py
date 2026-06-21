"""Execution helpers for the first row-count runtime boundary."""

from collections.abc import Mapping

from recon_core.adapters import (
    ADAPTER_OPERATION_RENDER_FAILED,
    ADAPTER_QUERY_ENDPOINT_UNSUPPORTED,
    ADAPTER_RENDERED_SQL_EMPTY,
    BaseAdapter,
    ConnectionConfig,
    QueryResult,
    Relation,
    SqlRenderer,
)
from recon_core.artifacts import LoadedCompiledCheck, LoadedCompiledContractArtifact
from recon_core.check_engine.dispatch import (
    UNSUPPORTED_CHECK_TYPE,
    UNSUPPORTED_EXECUTION_PLACEMENT,
    UNSUPPORTED_MATERIALIZATION_POLICY,
    UNSUPPORTED_TYPED_OPERATION,
)
from recon_core.check_engine.execution_support import (
    ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED,
    adapter_exception_diagnostic,
    error_result,
    exception_hint,
    has_materialization_policy,
    has_reserved_value,
    missing_sql_renderer_result,
    not_executable_result,
    relation_from_name,
    safe_string_attribute,
    same_connection_context,
    strict_int,
)
from recon_core.check_engine.models import CheckReason, CheckResult, CheckStatus
from recon_core.check_engine.result_metadata import identity_label
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

ROW_COUNT_RESULT_INVALID = "RC_RUNTIME_ROW_COUNT_RESULT_INVALID"

_EXPECTED_ROW_COUNT_PLAN: tuple[dict[str, object], ...] = (
    {"type": "row_count", "side": "source"},
    {"type": "row_count", "side": "target"},
    {"type": "compare_counts"},
)
_EXPECTED_RESULT_COLUMNS = ("source_row_count", "target_row_count", "row_count_diff")


def execute_row_count_check(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    adapter: BaseAdapter,
    *,
    renderer: SqlRenderer | None = None,
    connections_by_name: Mapping[str, ConnectionConfig] | None = None,
) -> CheckResult:
    """Execute one loaded row-count check against an already prepared adapter."""
    if check.check_type != "row_count_diff":
        return not_executable_result(
            check,
            contract,
            reason=CheckReason.UNSUPPORTED_CHECK_TYPE,
            diagnostic_code=UNSUPPORTED_CHECK_TYPE,
            message="Only row-count checks are executable in this runtime boundary.",
            hint="Run a later execution phase after its gate and implementation are complete.",
        )

    metadata_blocker = _reserved_metadata_blocker(check)
    if metadata_blocker is not None:
        return not_executable_result(
            check,
            contract,
            reason=metadata_blocker.reason,
            diagnostic_code=metadata_blocker.diagnostic_code,
            message=metadata_blocker.message,
            hint="Remove unsupported runtime placement or materialization metadata.",
        )

    if not is_supported_row_count_plan_shape(check.plan.operations):
        return not_executable_result(
            check,
            contract,
            reason=CheckReason.UNSUPPORTED_TYPED_OPERATION,
            diagnostic_code=UNSUPPORTED_TYPED_OPERATION,
            message="Row-count execution requires the source count, target count, compare plan.",
            hint="Compile a row-count check plan with the supported typed operation sequence.",
        )

    if contract.source.query is not None or contract.target.query is not None:
        return _query_endpoint_not_executable_result(check, contract)

    context_blocker = _context_blocker(
        check,
        contract,
        adapter,
        connections_by_name=connections_by_name,
    )
    if context_blocker is not None:
        return context_blocker

    source_relation, source_diagnostic = relation_from_name(
        contract.source.relation,
        side="source",
        contract_name=contract.contract_name,
    )
    target_relation, target_diagnostic = relation_from_name(
        contract.target.relation,
        side="target",
        contract_name=contract.contract_name,
    )
    relation_diagnostics = tuple(
        diagnostic
        for diagnostic in (source_diagnostic, target_diagnostic)
        if diagnostic is not None
    )
    if relation_diagnostics:
        return error_result(
            check,
            contract,
            message="Row-count execution could not resolve relation endpoints.",
            diagnostics=relation_diagnostics,
        )
    assert source_relation is not None
    assert target_relation is not None

    renderer_blocker = _renderer_blocker(check, contract, adapter, renderer)
    if renderer_blocker is not None:
        return renderer_blocker
    assert renderer is not None

    rendered_query = _render_compare_counts_query(
        check,
        contract,
        renderer=renderer,
        source_relation=source_relation,
        target_relation=target_relation,
    )
    if isinstance(rendered_query, CheckResult):
        return rendered_query

    try:
        query_result = adapter.execute(rendered_query)
    except Exception as exc:
        diagnostic = adapter_exception_diagnostic(
            exc,
            connection=adapter.connection,
            contract=contract,
        )
        return error_result(
            check,
            contract,
            message="Row-count execution failed before a trustworthy result was produced.",
            diagnostics=(diagnostic,),
        )

    parsed_result = _parse_row_count_result(query_result)
    if isinstance(parsed_result, Diagnostic):
        return error_result(
            check,
            contract,
            message="Row-count execution returned an invalid result shape.",
            diagnostics=(parsed_result,),
        )

    source_count, target_count, diff = parsed_result
    status = CheckStatus.PASS if diff == 0 else CheckStatus.FAIL
    message = "Row-count check passed." if status is CheckStatus.PASS else "Row-count check failed."
    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=status,
        executed=True,
        identity=identity_label(check),
        message=message,
        source_value=source_count,
        target_value=target_count,
        diff_value=diff,
        diagnostics=check.diagnostics + contract.diagnostics,
    )


def is_supported_row_count_plan_shape(operations: tuple[dict[str, object], ...]) -> bool:
    """Return whether operations match the 7.2 executable row-count plan shape."""
    if len(operations) != len(_EXPECTED_ROW_COUNT_PLAN):
        return False
    return all(
        _operation_matches_row_count_shape(operation, expected_operation)
        for operation, expected_operation in zip(operations, _EXPECTED_ROW_COUNT_PLAN, strict=True)
    )


def row_count_query_endpoint_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    """Return the row-count query-endpoint blocker without requiring an adapter."""
    return _query_endpoint_not_executable_result(check, contract)


def _operation_matches_row_count_shape(
    operation: Mapping[str, object],
    expected_operation: Mapping[str, object],
) -> bool:
    for key, expected_value in expected_operation.items():
        if operation.get(key) != expected_value:
            return False
    if any(
        has_reserved_value(operation.get(key))
        for key in ("execution_placement", "comparison_location")
    ):
        return False
    if has_materialization_policy(operation.get("materialization_policy")):
        return False

    allowed_fields = set(expected_operation) | {
        "execution_placement",
        "comparison_location",
        "materialization_policy",
    }
    return set(operation).issubset(allowed_fields)


class _ReservedMetadataBlocker:
    def __init__(
        self,
        *,
        reason: CheckReason,
        diagnostic_code: str,
        message: str,
    ) -> None:
        self.reason = reason
        self.diagnostic_code = diagnostic_code
        self.message = message


def _reserved_metadata_blocker(check: LoadedCompiledCheck) -> _ReservedMetadataBlocker | None:
    for operation in check.plan.operations:
        if any(
            has_reserved_value(operation.get(key))
            for key in ("execution_placement", "comparison_location")
        ):
            return _ReservedMetadataBlocker(
                reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
                diagnostic_code=UNSUPPORTED_EXECUTION_PLACEMENT,
                message="Row-count execution placement metadata is not supported.",
            )
        materialization_policy = operation.get("materialization_policy")
        if has_materialization_policy(materialization_policy):
            return _ReservedMetadataBlocker(
                reason=CheckReason.UNSUPPORTED_MATERIALIZATION_POLICY,
                diagnostic_code=UNSUPPORTED_MATERIALIZATION_POLICY,
                message="Row-count execution materialization policy is not supported.",
            )
    return None


def _query_endpoint_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    return not_executable_result(
        check,
        contract,
        reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
        diagnostic_code=ADAPTER_QUERY_ENDPOINT_UNSUPPORTED,
        message="Row-count execution supports relation endpoints only.",
        hint="Use relation endpoints for row-count execution.",
    )


def _context_blocker(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    adapter: BaseAdapter,
    *,
    connections_by_name: Mapping[str, ConnectionConfig] | None = None,
) -> CheckResult | None:
    if contract.source.connection == contract.target.connection:
        if adapter.connection.name != contract.source.connection:
            return _connection_context_not_executable_result(check, contract)
        return None

    if connections_by_name is None:
        return _connection_context_not_executable_result(check, contract)

    source_connection = connections_by_name.get(contract.source.connection)
    target_connection = connections_by_name.get(contract.target.connection)
    if source_connection is None or target_connection is None:
        return _connection_context_not_executable_result(check, contract)
    if not same_connection_context(source_connection, target_connection):
        return _connection_context_not_executable_result(check, contract)
    if not same_connection_context(adapter.connection, source_connection):
        return _connection_context_not_executable_result(check, contract)
    return None


def _connection_context_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    return not_executable_result(
        check,
        contract,
        reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
        diagnostic_code=ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED,
        message="Row-count execution requires one adapter connection context.",
        hint="Run this check only when source and target resolve to the same adapter context.",
    )


def _renderer_blocker(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    adapter: BaseAdapter,
    renderer: SqlRenderer | None,
) -> CheckResult | None:
    adapter_type = safe_string_attribute(adapter, "adapter_type")
    if renderer is None:
        if adapter_type == "duckdb":
            return missing_sql_renderer_result(
                check,
                contract,
                execution_label="Row-count",
            )
        return not_executable_result(
            check,
            contract,
            reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
            diagnostic_code=UNSUPPORTED_EXECUTION_PLACEMENT,
            message="Row-count execution currently supports DuckDB adapter execution only.",
            hint="Use a DuckDB adapter and DuckDB SQL renderer for this execution phase.",
        )

    renderer_adapter_type = safe_string_attribute(renderer, "adapter_type")
    if adapter_type == "duckdb" and renderer_adapter_type == "duckdb":
        return None
    return not_executable_result(
        check,
        contract,
        reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
        diagnostic_code=UNSUPPORTED_EXECUTION_PLACEMENT,
        message="Row-count execution currently supports DuckDB adapter execution only.",
        hint="Use a DuckDB adapter and DuckDB SQL renderer for this execution phase.",
    )


def _render_compare_counts_query(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    *,
    renderer: SqlRenderer,
    source_relation: Relation,
    target_relation: Relation,
) -> str | CheckResult:
    try:
        rendered_steps = renderer.render_plan(
            tuple(check.plan.operations),
            source_relation=source_relation,
            target_relation=target_relation,
        )
    except Exception as exc:
        return error_result(
            check,
            contract,
            message="Row-count execution could not render a SQL query.",
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_OPERATION_RENDER_FAILED,
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter SQL rendering failed for row-count execution.",
                    resource_type="compiled_check",
                    resource_name=f"{check.contract_name}.{check.name}",
                    hint=exception_hint("Renderer", exc),
                ),
            ),
        )

    compare_step = rendered_steps[-1] if rendered_steps else None
    if compare_step is None or compare_step.operation_type != "compare_counts":
        return error_result(
            check,
            contract,
            message="Row-count execution did not receive a compare-counts SQL step.",
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_OPERATION_RENDER_FAILED,
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter SQL rendering returned an invalid row-count plan.",
                    resource_type="compiled_check",
                    resource_name=f"{check.contract_name}.{check.name}",
                    hint="The final rendered row-count step must be a compare_counts operation.",
                ),
            ),
        )
    if compare_step.sql == "":
        return error_result(
            check,
            contract,
            message="Row-count execution did not receive a SQL query.",
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_RENDERED_SQL_EMPTY,
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter SQL rendering returned empty SQL for row-count execution.",
                    resource_type="compiled_check",
                    resource_name=f"{check.contract_name}.{check.name}",
                    hint="The final rendered row-count compare step must include SQL.",
                ),
            ),
        )

    return compare_step.sql


def _parse_row_count_result(result: QueryResult) -> tuple[int, int, int] | Diagnostic:
    if result.columns != _EXPECTED_RESULT_COLUMNS:
        return _invalid_result_diagnostic("Row-count query returned unexpected columns.")
    if len(result.rows) != 1:
        return _invalid_result_diagnostic("Row-count query must return exactly one row.")

    row = result.rows[0]
    if len(row) != 3:
        return _invalid_result_diagnostic("Row-count query returned an unexpected row shape.")

    source_count = strict_int(row[0])
    target_count = strict_int(row[1])
    diff = strict_int(row[2])
    if source_count is None or target_count is None or diff is None:
        return _invalid_result_diagnostic("Row-count query returned non-integer values.")
    if diff != source_count - target_count:
        return _invalid_result_diagnostic("Row-count query returned an inconsistent diff.")
    return source_count, target_count, diff


def _invalid_result_diagnostic(message: str) -> Diagnostic:
    return Diagnostic(
        code=ROW_COUNT_RESULT_INVALID,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="runtime_result",
        hint="The adapter result was rejected before producing evidence.",
    )
