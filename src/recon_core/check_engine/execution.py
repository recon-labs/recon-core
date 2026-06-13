"""Execution helpers for the first row-count runtime boundary."""

import re
from collections.abc import Mapping
from numbers import Integral
from typing import Any

from recon_core.adapters import (
    ADAPTER_INVALID_RELATION,
    ADAPTER_OPERATION_RENDER_FAILED,
    ADAPTER_QUERY_ENDPOINT_UNSUPPORTED,
    ADAPTER_RENDERED_SQL_EMPTY,
    BaseAdapter,
    ConnectionConfig,
    QueryResult,
    Relation,
    SqlRenderer,
)
from recon_core.adapters.diagnostic_redaction import sanitize_profile_backed_adapter_diagnostics
from recon_core.adapters.duckdb import ADAPTER_QUERY_FAILED, DuckDbSqlRenderer
from recon_core.artifacts import LoadedCompiledCheck, LoadedCompiledContractArtifact
from recon_core.check_engine.dispatch import (
    UNSUPPORTED_CHECK_TYPE,
    UNSUPPORTED_EXECUTION_PLACEMENT,
    UNSUPPORTED_MATERIALIZATION_POLICY,
    UNSUPPORTED_TYPED_OPERATION,
)
from recon_core.check_engine.models import CheckReason, CheckResult, CheckStatus
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED = "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"
ROW_COUNT_RESULT_INVALID = "RC_RUNTIME_ROW_COUNT_RESULT_INVALID"

_EXPECTED_ROW_COUNT_PLAN: tuple[dict[str, object], ...] = (
    {"type": "row_count", "side": "source"},
    {"type": "row_count", "side": "target"},
    {"type": "compare_counts"},
)
_EXPECTED_RESULT_COLUMNS = ("source_row_count", "target_row_count", "row_count_diff")
_EMPTY_MATERIALIZATION_POLICY_VALUES = {"none", "not_applicable"}
_UNSAFE_QUERY_TEXT_PATTERN = re.compile(
    r"\bselect\s+|\bwith\s+|\bfrom\s+|\bwhere\s+|\bjoin\s+|\bcount\s*\(",
    re.IGNORECASE,
)
_UNSAFE_DATABASE_ERROR_PATTERN = re.compile(
    r"\b(?:catalog|binder|parser|syntax|transaction|connection|io)\s+error\b|"
    r"\b(?:sql|operational|programming)error\b|traceback",
    re.IGNORECASE,
)


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
        return _not_executable_result(
            check,
            contract,
            reason=CheckReason.UNSUPPORTED_CHECK_TYPE,
            diagnostic_code=UNSUPPORTED_CHECK_TYPE,
            message="Only row-count checks are executable in this runtime boundary.",
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

    if check.plan.operations != _EXPECTED_ROW_COUNT_PLAN:
        return _not_executable_result(
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
            message="Row-count execution could not resolve relation endpoints.",
            diagnostics=relation_diagnostics,
        )
    assert source_relation is not None
    assert target_relation is not None

    resolved_renderer = renderer if renderer is not None else DuckDbSqlRenderer()
    renderer_blocker = _renderer_blocker(check, contract, adapter, resolved_renderer)
    if renderer_blocker is not None:
        return renderer_blocker

    rendered_query = _render_compare_counts_query(
        check,
        contract,
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
            message="Row-count execution failed before a trustworthy result was produced.",
            diagnostics=(diagnostic,),
        )

    parsed_result = _parse_row_count_result(query_result)
    if isinstance(parsed_result, Diagnostic):
        return _error_result(
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
        identity=_identity_label(check),
        message=message,
        source_value=source_count,
        target_value=target_count,
        diff_value=diff,
        diagnostics=check.diagnostics + contract.diagnostics,
    )


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
                message="Row-count execution placement metadata is not supported.",
            )
        materialization_policy = operation.get("materialization_policy")
        if _has_materialization_policy(materialization_policy):
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
    return _not_executable_result(
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
        message="Row-count execution requires one adapter connection context.",
        hint="Run this check only when source and target resolve to the same adapter context.",
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
        return _error_result(
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
                    hint=_exception_hint("Renderer", exc),
                ),
            ),
        )

    compare_step = rendered_steps[-1] if rendered_steps else None
    if compare_step is None or compare_step.operation_type != "compare_counts":
        return _error_result(
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
        return _error_result(
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

    source_count = _strict_int(row[0])
    target_count = _strict_int(row[1])
    diff = _strict_int(row[2])
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


def _adapter_exception_diagnostic(
    exc: Exception,
    *,
    connection: ConnectionConfig,
    contract: LoadedCompiledContractArtifact,
) -> Diagnostic:
    diagnostic = getattr(exc, "diagnostic", None)
    if isinstance(diagnostic, Diagnostic):
        if (
            _is_known_sanitized_adapter_query_diagnostic(diagnostic)
            and not _diagnostic_mentions_runtime_sensitive_text(
                diagnostic,
                contract=contract,
            )
            and not _diagnostic_mentions_connection_config_values(
                diagnostic,
                connection=connection,
            )
        ):
            return diagnostic
        sanitized = sanitize_profile_backed_adapter_diagnostics(
            (diagnostic,),
            connection=connection,
        )[0]
        if sanitized != diagnostic or _diagnostic_mentions_runtime_sensitive_text(
            sanitized,
            contract=contract,
        ):
            return _fallback_adapter_query_diagnostic(exc, connection=connection)
        return sanitized
    return _fallback_adapter_query_diagnostic(exc, connection=connection)


def _fallback_adapter_query_diagnostic(
    exc: Exception,
    *,
    connection: ConnectionConfig,
) -> Diagnostic:
    return Diagnostic(
        code=ADAPTER_QUERY_FAILED,
        severity=DiagnosticSeverity.ERROR,
        message="Adapter query execution failed.",
        resource_type="adapter",
        resource_name=connection.type,
        hint=_exception_hint("Adapter", exc),
    )


def _not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    *,
    reason: CheckReason,
    diagnostic_code: str,
    message: str,
    hint: str,
) -> CheckResult:
    diagnostic = Diagnostic(
        code=diagnostic_code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="compiled_check",
        resource_name=f"{check.contract_name}.{check.name}",
        hint=hint,
    )
    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=CheckStatus.NOT_EXECUTABLE,
        executed=False,
        reason_code=reason,
        identity=_identity_label(check),
        message=message,
        diagnostics=check.diagnostics + contract.diagnostics + (diagnostic,),
    )


def _error_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    *,
    message: str,
    diagnostics: tuple[Diagnostic, ...],
) -> CheckResult:
    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=CheckStatus.ERROR,
        executed=False,
        identity=_identity_label(check),
        message=message,
        diagnostics=check.diagnostics + contract.diagnostics + diagnostics,
    )


def _relation_from_name(
    relation_name: str | None,
    *,
    side: str,
    contract_name: str,
) -> tuple[Relation | None, Diagnostic | None]:
    if relation_name is None:
        return None, _invalid_relation_diagnostic(
            contract_name=contract_name,
            side=side,
            message="Relation endpoint is missing.",
        )

    raw_parts = relation_name.split(".")
    parts = tuple(part for part in raw_parts if part)
    if len(parts) not in {1, 2, 3} or len(parts) != len(raw_parts):
        return None, _invalid_relation_diagnostic(
            contract_name=contract_name,
            side=side,
            message="Relation endpoint must have one to three non-empty identifier parts.",
        )

    if len(parts) == 1:
        return Relation(identifier=parts[0]), None
    if len(parts) == 2:
        return Relation(schema=parts[0], identifier=parts[1]), None
    return Relation(catalog=parts[0], schema=parts[1], identifier=parts[2]), None


def _invalid_relation_diagnostic(
    *,
    contract_name: str,
    side: str,
    message: str,
) -> Diagnostic:
    return Diagnostic(
        code=ADAPTER_INVALID_RELATION,
        severity=DiagnosticSeverity.ERROR,
        message=f"Contract `{contract_name}` {side} endpoint is not executable. {message}",
        resource_type="contract_endpoint",
        resource_name=contract_name,
        hint="Use relation, schema.relation, or catalog.schema.relation.",
    )


def _identity_label(check: LoadedCompiledCheck) -> str | None:
    payload = check.payload
    if payload is None:
        return None
    identity = payload.get("identity")
    if not isinstance(identity, Mapping):
        return None
    kind = identity.get("kind")
    return kind if isinstance(kind, str) else None


def _has_reserved_value(value: object) -> bool:
    return value is not None and value != ""


def _has_materialization_policy(value: object) -> bool:
    if not _has_reserved_value(value):
        return False
    return not isinstance(value, str) or value not in _EMPTY_MATERIALIZATION_POLICY_VALUES


def _strict_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, Integral):
        return None
    return int(value)


def _same_connection_context(left: ConnectionConfig, right: ConnectionConfig) -> bool:
    return left.type == right.type and left.config == right.config


def _safe_string_attribute(instance: object, attribute_name: str) -> str | None:
    try:
        value = getattr(instance, attribute_name)
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


def _exception_hint(prefix: str, exc: Exception) -> str:
    return (
        f"{prefix} raised {type(exc).__name__}. Raw adapter, SQL, database error, "
        "and rendered profile text were suppressed."
    )


def _diagnostic_mentions_runtime_sensitive_text(
    diagnostic: Diagnostic,
    *,
    contract: LoadedCompiledContractArtifact,
) -> bool:
    diagnostic_text = "\n".join(_diagnostic_text_values(diagnostic))
    if _UNSAFE_QUERY_TEXT_PATTERN.search(diagnostic_text):
        return True
    if _UNSAFE_DATABASE_ERROR_PATTERN.search(diagnostic_text):
        return True

    folded_text = diagnostic_text.casefold()
    return any(token.casefold() in folded_text for token in _contract_sensitive_tokens(contract))


def _is_known_sanitized_adapter_query_diagnostic(diagnostic: Diagnostic) -> bool:
    return (
        diagnostic.code == ADAPTER_QUERY_FAILED
        and diagnostic.resource_type == "adapter"
        and diagnostic.message.endswith("query execution failed.")
        and diagnostic.hint is not None
        and "suppressed" in diagnostic.hint.casefold()
    )


def _diagnostic_mentions_connection_config_values(
    diagnostic: Diagnostic,
    *,
    connection: ConnectionConfig,
) -> bool:
    diagnostic_text = "\n".join(_diagnostic_text_values(diagnostic)).casefold()
    return any(
        token.casefold() in diagnostic_text
        for token in _connection_config_value_tokens(
            connection.config,
            adapter_type=connection.type,
        )
    )


def _diagnostic_text_values(diagnostic: Diagnostic) -> tuple[str, ...]:
    return tuple(
        str(value)
        for value in (
            diagnostic.code,
            diagnostic.message,
            diagnostic.resource_type,
            diagnostic.resource_name,
            diagnostic.path,
            diagnostic.line,
            diagnostic.column,
            diagnostic.hint,
        )
        if value is not None
    )


def _contract_sensitive_tokens(
    contract: LoadedCompiledContractArtifact,
) -> frozenset[str]:
    tokens: set[str] = set()
    for endpoint in (contract.source, contract.target):
        tokens.add(endpoint.connection)
        if endpoint.relation is not None:
            tokens.add(endpoint.relation)
            tokens.update(part for part in endpoint.relation.split(".") if len(part) >= 4)
        if endpoint.query is not None:
            tokens.add(endpoint.query)
    return frozenset(token for token in tokens if token)


def _connection_config_value_tokens(
    value: object,
    *,
    adapter_type: str,
) -> frozenset[str]:
    tokens: set[str] = set()
    _collect_connection_config_value_tokens(value, adapter_type=adapter_type, tokens=tokens)
    return frozenset(tokens)


def _collect_connection_config_value_tokens(
    value: object,
    *,
    adapter_type: str,
    tokens: set[str],
) -> None:
    if isinstance(value, Mapping):
        for nested_value in value.values():
            _collect_connection_config_value_tokens(
                nested_value,
                adapter_type=adapter_type,
                tokens=tokens,
            )
        return

    if isinstance(value, str):
        if value and value.casefold() != adapter_type.casefold():
            tokens.add(value)
        for token in re.split(r"[^A-Za-z0-9_.+-]+", value):
            if len(token) >= 3 and token.casefold() != adapter_type.casefold():
                tokens.add(token)
        return

    if isinstance(value, list | tuple):
        for item in value:
            _collect_connection_config_value_tokens(
                item,
                adapter_type=adapter_type,
                tokens=tokens,
            )
        return

    if value is not None and not isinstance(value, bool):
        tokens.add(str(value))
