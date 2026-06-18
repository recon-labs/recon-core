"""Shared execution support for check-engine runtime helpers."""

import re
from collections.abc import Mapping
from numbers import Integral
from typing import Any

from recon_core.adapters import ADAPTER_INVALID_RELATION, ConnectionConfig, Relation
from recon_core.adapters.diagnostic_redaction import sanitize_profile_backed_adapter_diagnostics
from recon_core.adapters.lifecycle import ADAPTER_QUERY_FAILED
from recon_core.artifacts import LoadedCompiledCheck, LoadedCompiledContractArtifact
from recon_core.check_engine.models import CheckReason, CheckResult, CheckStatus
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED = "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"

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


def adapter_exception_diagnostic(
    exc: Exception,
    *,
    connection: ConnectionConfig,
    contract: LoadedCompiledContractArtifact,
) -> Diagnostic:
    """Return a sanitized adapter query diagnostic."""
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


def not_executable_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    *,
    reason: CheckReason,
    diagnostic_code: str,
    message: str,
    hint: str,
) -> CheckResult:
    """Return a standard not-executable result for a loaded check."""
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
        identity=identity_label(check),
        message=message,
        diagnostics=check.diagnostics + contract.diagnostics + (diagnostic,),
    )


def error_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    *,
    message: str,
    diagnostics: tuple[Diagnostic, ...],
) -> CheckResult:
    """Return a standard runtime error result for a loaded check."""
    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=CheckStatus.ERROR,
        executed=False,
        identity=identity_label(check),
        message=message,
        diagnostics=check.diagnostics + contract.diagnostics + diagnostics,
    )


def relation_from_name(
    relation_name: str | None,
    *,
    side: str,
    contract_name: str,
) -> tuple[Relation | None, Diagnostic | None]:
    """Parse a compiled relation name into an adapter relation."""
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


def identity_label(check: LoadedCompiledCheck) -> str | None:
    """Return the check identity kind for result display."""
    payload = check.payload
    if payload is None:
        return None
    identity = payload.get("identity")
    if not isinstance(identity, Mapping):
        return None
    kind = identity.get("kind")
    return kind if isinstance(kind, str) else None


def has_reserved_value(value: object) -> bool:
    """Return whether a reserved optional field carries a meaningful value."""
    return value is not None and value != ""


def has_materialization_policy(value: object) -> bool:
    """Return whether materialization policy metadata is unsupported."""
    if not has_reserved_value(value):
        return False
    return not isinstance(value, str) or value not in _EMPTY_MATERIALIZATION_POLICY_VALUES


def strict_int(value: Any) -> int | None:
    """Return an int only for integer values, excluding bool."""
    if isinstance(value, bool) or not isinstance(value, Integral):
        return None
    return int(value)


def same_connection_context(left: ConnectionConfig, right: ConnectionConfig) -> bool:
    """Return whether two profile connections resolve to the same context."""
    return left.type == right.type and left.config == right.config


def safe_string_attribute(instance: object, attribute_name: str) -> str | None:
    """Read a non-empty string attribute without surfacing adapter exceptions."""
    try:
        value = getattr(instance, attribute_name)
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


def exception_hint(prefix: str, exc: Exception) -> str:
    """Return a safe low-level exception hint."""
    return (
        f"{prefix} raised {type(exc).__name__}. Raw adapter, SQL, database error, "
        "and rendered profile text were suppressed."
    )


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
        hint=exception_hint("Adapter", exc),
    )


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
