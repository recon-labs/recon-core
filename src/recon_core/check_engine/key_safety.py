"""Execution helpers for relation-backed grain-key safety checks."""

from collections.abc import Mapping
from typing import Final

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
from recon_core.adapters.duckdb import DuckDbSqlRenderer
from recon_core.artifacts import LoadedCompiledCheck, LoadedCompiledContractArtifact
from recon_core.check_engine.dispatch import (
    UNSUPPORTED_CHECK_TYPE,
    UNSUPPORTED_EXECUTION_PLACEMENT,
    UNSUPPORTED_MATERIALIZATION_POLICY,
    UNSUPPORTED_TYPED_OPERATION,
)
from recon_core.check_engine.execution import (
    ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED,
    _adapter_exception_diagnostic,
    _error_result,
    _exception_hint,
    _identity_label,
    _not_executable_result,
    _relation_from_name,
    _safe_string_attribute,
    _same_connection_context,
    _strict_int,
)
from recon_core.check_engine.models import CheckReason, CheckResult, CheckStatus
from recon_core.check_engine.scan_budget import ScanBudgetDecision
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

KEY_SAFETY_RESULT_INVALID: Final = "RC_RUNTIME_KEY_SAFETY_RESULT_INVALID"
NULL_GRAIN_KEYS: Final = "RC_RUNTIME_NULL_GRAIN_KEYS"
DUPLICATE_GRAIN_KEYS: Final = "RC_RUNTIME_DUPLICATE_GRAIN_KEYS"
MISSING_KEYS: Final = "RC_RUNTIME_MISSING_KEYS"
EXTRA_KEYS: Final = "RC_RUNTIME_EXTRA_KEYS"

_EMPTY_MATERIALIZATION_POLICY_VALUES = {"none", "not_applicable"}
_EXPECTED_KEY_OPERATION_BY_CHECK_TYPE: Final[dict[str, dict[str, str]]] = {
    "null_source_keys": {"type": "null_key", "side": "source"},
    "null_target_keys": {"type": "null_key", "side": "target"},
    "duplicate_source_keys": {"type": "duplicate_key", "side": "source"},
    "duplicate_target_keys": {"type": "duplicate_key", "side": "target"},
    "missing_keys": {"type": "key_diff", "direction": "source_minus_target"},
    "extra_keys": {"type": "key_diff", "direction": "target_minus_source"},
}
_FAILURE_DIAGNOSTIC_BY_CHECK_TYPE: Final[dict[str, tuple[str, str]]] = {
    "null_source_keys": (NULL_GRAIN_KEYS, "Null grain-key check failed."),
    "null_target_keys": (NULL_GRAIN_KEYS, "Null grain-key check failed."),
    "duplicate_source_keys": (DUPLICATE_GRAIN_KEYS, "Duplicate grain-key check failed."),
    "duplicate_target_keys": (DUPLICATE_GRAIN_KEYS, "Duplicate grain-key check failed."),
    "missing_keys": (MISSING_KEYS, "Missing key-coverage check failed."),
    "extra_keys": (EXTRA_KEYS, "Extra key-coverage check failed."),
}


def execute_key_safety_check(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    adapter: BaseAdapter,
    *,
    scan_budget_decision: ScanBudgetDecision,
    renderer: SqlRenderer | None = None,
    connections_by_name: Mapping[str, ConnectionConfig] | None = None,
) -> CheckResult:
    """Execute one loaded grain-key safety check through a bounded count query."""
    if check.check_type not in _EXPECTED_KEY_OPERATION_BY_CHECK_TYPE:
        return _not_executable_result(
            check,
            contract,
            reason=CheckReason.UNSUPPORTED_CHECK_TYPE,
            diagnostic_code=UNSUPPORTED_CHECK_TYPE,
            message="Only grain-key safety checks are executable in this runtime boundary.",
            hint="Run a later execution phase after its gate and implementation are complete.",
        )

    metadata_blocker = _reserved_metadata_blocker(check)
    if metadata_blocker is not None:
        return _not_executable_result(
            check,
            contract,
            reason=metadata_blocker.reason,
            diagnostic_code=metadata_blocker.diagnostic_code,
            message=metadata_blocker.message,
            hint="Remove unsupported runtime placement or materialization metadata.",
        )

    if not is_supported_key_safety_plan_shape(check.check_type, check.plan.operations):
        return _unsupported_plan_shape_not_executable_result(check, contract)

    if not key_safety_identity_matches_contract(check, contract):
        return _identity_mismatch_not_executable_result(check, contract)

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

    source_relation, source_diagnostic = _relation_from_name(
        contract.source.relation,
        side="source",
        contract_name=contract.contract_name,
    )
    target_relation, target_diagnostic = _relation_from_name(
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
        return _error_result(
            check,
            contract,
            message="Key-safety execution could not resolve relation endpoints.",
            diagnostics=relation_diagnostics,
        )
    assert source_relation is not None
    assert target_relation is not None

    if not scan_budget_decision.allowed:
        return _scan_budget_not_executable_result(check, contract, scan_budget_decision)

    resolved_renderer = renderer if renderer is not None else DuckDbSqlRenderer()
    renderer_blocker = _renderer_blocker(check, contract, adapter, resolved_renderer)
    if renderer_blocker is not None:
        return renderer_blocker

    operation = check.plan.operations[0]
    rendered_query = _render_key_safety_count_query(
        check,
        contract,
        operation=operation,
        renderer=resolved_renderer,
        source_relation=source_relation,
        target_relation=target_relation,
    )
    if isinstance(rendered_query, CheckResult):
        return rendered_query

    try:
        query_result = adapter.execute(rendered_query)
    except Exception as exc:
        diagnostic = _adapter_exception_diagnostic(
            exc,
            connection=adapter.connection,
            contract=contract,
        )
        return _error_result(
            check,
            contract,
            message="Key-safety execution failed before a trustworthy result was produced.",
            diagnostics=(diagnostic,),
        )

    parsed_result = _parse_key_safety_count_result(query_result)
    if isinstance(parsed_result, Diagnostic):
        return _error_result(
            check,
            contract,
            message="Key-safety execution returned an invalid result shape.",
            diagnostics=(parsed_result,),
        )

    status = CheckStatus.PASS if parsed_result == 0 else CheckStatus.FAIL
    message = (
        "Key-safety check passed." if status is CheckStatus.PASS else "Key-safety check failed."
    )
    diagnostics = check.diagnostics + contract.diagnostics
    if status is CheckStatus.FAIL:
        diagnostics = diagnostics + (_failure_diagnostic(check),)
    diagnostics = diagnostics + scan_budget_decision.diagnostics

    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=status,
        executed=True,
        identity=_identity_label(check),
        message=message,
        failure_count=parsed_result,
        diagnostics=diagnostics,
    )


def is_supported_key_safety_plan_shape(
    check_type: str,
    operations: tuple[dict[str, object], ...],
) -> bool:
    """Return whether operations match a supported grain-key safety plan shape."""
    expected_operation = _EXPECTED_KEY_OPERATION_BY_CHECK_TYPE.get(check_type)
    if expected_operation is None or len(operations) != 1:
        return False
    return _operation_matches_key_safety_shape(operations[0], expected_operation)


def is_key_safety_check_type(check_type: str) -> bool:
    """Return whether a check type belongs to the grain-key safety family."""
    return check_type in _EXPECTED_KEY_OPERATION_BY_CHECK_TYPE


def key_safety_query_endpoint_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    """Return the key-safety query-endpoint blocker without requiring an adapter."""
    return _query_endpoint_not_executable_result(check, contract)


def key_safety_identity_matches_contract(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> bool:
    """Return whether one key-safety operation uses the compiled grain identity."""
    if not is_key_safety_check_type(check.check_type) or len(check.plan.operations) != 1:
        return False
    return _operation_identity_matches_contract(check.plan.operations[0], contract)


def key_safety_identity_mismatch_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    """Return the key-safety identity mismatch blocker without requiring an adapter."""
    return _identity_mismatch_not_executable_result(check, contract)


def key_safety_unsupported_plan_shape_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    """Return the key-safety typed-plan shape blocker without requiring an adapter."""
    return _unsupported_plan_shape_not_executable_result(check, contract)


def key_safety_connection_context_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    """Return the key-safety connection-context blocker without requiring an adapter."""
    return _connection_context_not_executable_result(check, contract)


def key_safety_scan_budget_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    decision: ScanBudgetDecision,
) -> CheckResult:
    """Return the key-safety scan-budget blocker without requiring an adapter."""
    return _scan_budget_not_executable_result(check, contract, decision)


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
            _has_reserved_value(operation.get(key))
            for key in ("execution_placement", "comparison_location")
        ):
            return _ReservedMetadataBlocker(
                reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
                diagnostic_code=UNSUPPORTED_EXECUTION_PLACEMENT,
                message="Key-safety execution placement metadata is not supported.",
            )
        materialization_policy = operation.get("materialization_policy")
        if _has_materialization_policy(materialization_policy):
            return _ReservedMetadataBlocker(
                reason=CheckReason.UNSUPPORTED_MATERIALIZATION_POLICY,
                diagnostic_code=UNSUPPORTED_MATERIALIZATION_POLICY,
                message="Key-safety execution materialization policy is not supported.",
            )
    return None


def _operation_matches_key_safety_shape(
    operation: Mapping[str, object],
    expected_operation: Mapping[str, str],
) -> bool:
    for key, expected_value in expected_operation.items():
        if operation.get(key) != expected_value:
            return False
    identity = operation.get("identity")
    if not _has_identity_keys(identity):
        return False
    if any(
        _has_reserved_value(operation.get(key))
        for key in ("execution_placement", "comparison_location")
    ):
        return False
    if _has_materialization_policy(operation.get("materialization_policy")):
        return False

    allowed_fields = set(expected_operation) | {
        "identity",
        "execution_placement",
        "comparison_location",
        "materialization_policy",
    }
    return set(operation).issubset(allowed_fields)


def _has_identity_keys(identity: object) -> bool:
    if not isinstance(identity, Mapping):
        return False
    if identity.get("kind") != "grain":
        return False
    keys = identity.get("keys")
    return isinstance(keys, list) and all(isinstance(key, str) and key for key in keys)


def _operation_identity_matches_contract(
    operation: Mapping[str, object],
    contract: LoadedCompiledContractArtifact,
) -> bool:
    identity = operation.get("identity")
    if not isinstance(identity, Mapping) or identity.get("kind") != "grain":
        return False
    keys = identity.get("keys")
    if not isinstance(keys, list):
        return False
    return tuple(keys) == contract.grain_keys


def _identity_mismatch_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    return _not_executable_result(
        check,
        contract,
        reason=CheckReason.UNSUPPORTED_TYPED_OPERATION,
        diagnostic_code=UNSUPPORTED_TYPED_OPERATION,
        message=(
            "Key-safety typed operation identity must match the compiled contract grain identity."
        ),
        hint="Recompile the contract so key-safety checks use the contract grain keys.",
    )


def _unsupported_plan_shape_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    return _not_executable_result(
        check,
        contract,
        reason=CheckReason.UNSUPPORTED_TYPED_OPERATION,
        diagnostic_code=UNSUPPORTED_TYPED_OPERATION,
        message="Key-safety execution requires one supported key-safety typed operation.",
        hint="Compile a key-safety check plan with the supported typed operation shape.",
    )


def _query_endpoint_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    return _not_executable_result(
        check,
        contract,
        reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
        diagnostic_code=ADAPTER_QUERY_ENDPOINT_UNSUPPORTED,
        message="Key-safety execution supports relation endpoints only.",
        hint="Use relation endpoints for key-safety execution.",
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
    if not _same_connection_context(source_connection, target_connection):
        return _connection_context_not_executable_result(check, contract)
    if not _same_connection_context(adapter.connection, source_connection):
        return _connection_context_not_executable_result(check, contract)
    return None


def _connection_context_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
) -> CheckResult:
    return _not_executable_result(
        check,
        contract,
        reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
        diagnostic_code=ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED,
        message="Key-safety execution requires one adapter connection context.",
        hint="Run this check only when source and target resolve to the same adapter context.",
    )


def _scan_budget_not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    decision: ScanBudgetDecision,
) -> CheckResult:
    reason = decision.reason or CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED
    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=CheckStatus.NOT_EXECUTABLE,
        executed=False,
        reason_code=reason,
        identity=_identity_label(check),
        message=decision.message,
        diagnostics=check.diagnostics + contract.diagnostics + decision.diagnostics,
    )


def _renderer_blocker(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    adapter: BaseAdapter,
    renderer: SqlRenderer,
) -> CheckResult | None:
    adapter_type = _safe_string_attribute(adapter, "adapter_type")
    renderer_adapter_type = _safe_string_attribute(renderer, "adapter_type")
    if adapter_type == "duckdb" and renderer_adapter_type == "duckdb":
        return None
    return _not_executable_result(
        check,
        contract,
        reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
        diagnostic_code=UNSUPPORTED_EXECUTION_PLACEMENT,
        message="Key-safety execution currently supports DuckDB adapter execution only.",
        hint="Use a DuckDB adapter and DuckDB SQL renderer for this execution phase.",
    )


def _render_key_safety_count_query(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    *,
    operation: Mapping[str, object],
    renderer: SqlRenderer,
    source_relation: Relation,
    target_relation: Relation,
) -> str | CheckResult:
    try:
        rendered_step = renderer.render_operation(
            operation,
            source_relation=source_relation,
            target_relation=target_relation,
        )
    except Exception as exc:
        return _error_result(
            check,
            contract,
            message="Key-safety execution could not render a SQL query.",
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_OPERATION_RENDER_FAILED,
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter SQL rendering failed for key-safety execution.",
                    resource_type="compiled_check",
                    resource_name=f"{check.contract_name}.{check.name}",
                    hint=_exception_hint("Renderer", exc),
                ),
            ),
        )

    expected_operation_type = operation.get("type")
    if rendered_step.operation_type != expected_operation_type:
        return _error_result(
            check,
            contract,
            message="Key-safety execution did not receive a key-safety SQL step.",
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_OPERATION_RENDER_FAILED,
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter SQL rendering returned an invalid key-safety plan.",
                    resource_type="compiled_check",
                    resource_name=f"{check.contract_name}.{check.name}",
                    hint="The rendered key-safety step must match the typed operation.",
                ),
            ),
        )
    rendered_sql = rendered_step.sql.strip()
    if rendered_sql == "":
        return _error_result(
            check,
            contract,
            message="Key-safety execution did not receive a SQL query.",
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_RENDERED_SQL_EMPTY,
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter SQL rendering returned empty SQL for key-safety execution.",
                    resource_type="compiled_check",
                    resource_name=f"{check.contract_name}.{check.name}",
                    hint="The rendered key-safety step must include SQL.",
                ),
            ),
        )

    return (
        f"select count(*) as failure_count\nfrom (\n{rendered_sql}\n) as recon_key_safety_failures"
    )


def _parse_key_safety_count_result(result: QueryResult) -> int | Diagnostic:
    if result.columns != ("failure_count",):
        return _invalid_result_diagnostic("Key-safety query returned unexpected columns.")
    if len(result.rows) != 1:
        return _invalid_result_diagnostic("Key-safety query must return exactly one row.")

    row = result.rows[0]
    if len(row) != 1:
        return _invalid_result_diagnostic("Key-safety query returned an unexpected row shape.")

    failure_count = _strict_int(row[0])
    if failure_count is None:
        return _invalid_result_diagnostic("Key-safety query returned a non-integer count.")
    if failure_count < 0:
        return _invalid_result_diagnostic("Key-safety query returned a negative count.")
    return failure_count


def _invalid_result_diagnostic(message: str) -> Diagnostic:
    return Diagnostic(
        code=KEY_SAFETY_RESULT_INVALID,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="runtime_result",
        hint="The adapter result was rejected before producing evidence.",
    )


def _failure_diagnostic(check: LoadedCompiledCheck) -> Diagnostic:
    code, message = _FAILURE_DIAGNOSTIC_BY_CHECK_TYPE[check.check_type]
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="compiled_check",
        resource_name=f"{check.contract_name}.{check.name}",
        hint="Raw key values and failure details are not emitted by this execution phase.",
    )


def _has_reserved_value(value: object) -> bool:
    return value is not None and value != ""


def _has_materialization_policy(value: object) -> bool:
    if not _has_reserved_value(value):
        return False
    return not isinstance(value, str) or value not in _EMPTY_MATERIALIZATION_POLICY_VALUES
