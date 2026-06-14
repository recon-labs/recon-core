"""Adapter diagnostic redaction for profile-backed setup paths."""

import re
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, unquote, urlsplit

from recon_core.diagnostics import Diagnostic
from recon_core.profiles import ConnectionConfig

ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED = "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED"

_NUMERIC_LITERAL_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_CONNECTION_STRING_COMPONENT_SPLIT_PATTERN = re.compile(r"[^A-Za-z0-9_.+-]+")


@dataclass(frozen=True, slots=True)
class _DiagnosticCodeConfigTokens:
    boundary_tokens: frozenset[str]
    embedded_tokens: frozenset[str]


def sanitize_profile_backed_adapter_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    *,
    connection: ConnectionConfig,
) -> tuple[Diagnostic, ...]:
    """Suppress rendered connection config from adapter-provided diagnostics."""
    config_tokens = _connection_config_tokens(
        connection.config,
        adapter_type=connection.type,
    )
    code_config_tokens = _connection_config_code_tokens(
        connection.config,
        adapter_type=connection.type,
    )
    numeric_field_tokens = _connection_config_numeric_field_tokens(
        connection.config,
        adapter_type=connection.type,
    )
    return tuple(
        _sanitize_profile_backed_adapter_diagnostic(
            diagnostic,
            connection=connection,
            config_tokens=config_tokens,
            code_config_tokens=code_config_tokens,
            numeric_field_tokens=numeric_field_tokens,
        )
        for diagnostic in diagnostics
    )


def _sanitize_profile_backed_adapter_diagnostic(
    diagnostic: Diagnostic,
    *,
    connection: ConnectionConfig,
    config_tokens: frozenset[str],
    code_config_tokens: _DiagnosticCodeConfigTokens,
    numeric_field_tokens: frozenset[int],
) -> Diagnostic:
    code_mentions_config_token = _diagnostic_code_mentions_config_token(
        diagnostic,
        code_config_tokens,
        numeric_field_tokens,
    )
    if not code_mentions_config_token and not _diagnostic_mentions_config_token(
        diagnostic,
        config_tokens,
        numeric_field_tokens,
    ):
        return diagnostic

    return Diagnostic(
        code=(
            ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED if code_mentions_config_token else diagnostic.code
        ),
        severity=diagnostic.severity,
        message=(
            f"Adapter `{connection.type}` reported a diagnostic for "
            f"connection `{connection.name}`; adapter diagnostic text was suppressed "
            "because runtime adapter diagnostics must not expose rendered connection config."
        ),
        resource_type="adapter",
        resource_name=connection.type,
        hint=(
            "Fix the adapter configuration or inspect the adapter locally without exposing secrets."
        ),
    )


def _connection_config_tokens(
    value: Mapping[str, object],
    *,
    adapter_type: str,
) -> frozenset[str]:
    tokens: set[str] = set()
    _collect_connection_config_tokens(value, adapter_type=adapter_type, tokens=tokens)
    return frozenset(tokens)


def _connection_config_code_tokens(
    value: Mapping[str, object],
    *,
    adapter_type: str,
) -> _DiagnosticCodeConfigTokens:
    boundary_tokens: set[str] = set()
    embedded_tokens: set[str] = set()
    _collect_connection_config_code_tokens(
        value,
        adapter_type=adapter_type,
        boundary_tokens=boundary_tokens,
        embedded_tokens=embedded_tokens,
    )
    return _DiagnosticCodeConfigTokens(
        boundary_tokens=frozenset(boundary_tokens),
        embedded_tokens=frozenset(embedded_tokens),
    )


def _connection_config_numeric_field_tokens(
    value: Mapping[str, object],
    *,
    adapter_type: str,
) -> frozenset[int]:
    tokens: set[int] = set()
    _collect_connection_config_numeric_field_tokens(
        value,
        adapter_type=adapter_type,
        tokens=tokens,
    )
    return frozenset(tokens)


def _collect_connection_config_tokens(
    value: object,
    *,
    adapter_type: str,
    tokens: set[str],
    current_key: str | None = None,
) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            key_text = key if isinstance(key, str) else None
            if key_text is not None and key_text.casefold() != "type":
                tokens.add(key_text)
            _collect_connection_config_tokens(
                nested_value,
                adapter_type=adapter_type,
                tokens=tokens,
                current_key=key_text,
            )
        return

    if isinstance(value, str):
        if value != "" and value.casefold() != adapter_type.casefold():
            tokens.add(value)
        for token in _connection_string_component_tokens(value):
            if token.casefold() != adapter_type.casefold():
                tokens.add(token)
        return

    if isinstance(value, list | tuple):
        for item in value:
            _collect_connection_config_tokens(
                item,
                adapter_type=adapter_type,
                tokens=tokens,
                current_key=current_key,
            )
        return

    if value is None or isinstance(value, bool):
        return

    token = str(value)
    if token != "" and (
        len(token) >= 3 or (current_key is not None and _is_secret_like_config_key(current_key))
    ):
        tokens.add(token)


def _collect_connection_config_code_tokens(
    value: object,
    *,
    adapter_type: str,
    boundary_tokens: set[str],
    embedded_tokens: set[str],
    current_key: str | None = None,
) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            key_text = key if isinstance(key, str) else None
            if (
                key_text is not None
                and key_text.casefold() != "type"
                and _is_secret_like_config_key(key_text)
            ):
                boundary_tokens.add(key_text)
                embedded_tokens.add(key_text)
            _collect_connection_config_code_tokens(
                nested_value,
                adapter_type=adapter_type,
                boundary_tokens=boundary_tokens,
                embedded_tokens=embedded_tokens,
                current_key=key_text,
            )
        return

    if isinstance(value, str):
        if value != "" and value.casefold() != adapter_type.casefold():
            boundary_tokens.add(value)
            embedded_tokens.add(value)
        for token in _connection_string_component_tokens(value):
            if token.casefold() == adapter_type.casefold():
                continue
            boundary_tokens.add(token)
            embedded_tokens.add(token)
        return

    if isinstance(value, list | tuple):
        for item in value:
            _collect_connection_config_code_tokens(
                item,
                adapter_type=adapter_type,
                boundary_tokens=boundary_tokens,
                embedded_tokens=embedded_tokens,
                current_key=current_key,
            )
        return

    if value is None or isinstance(value, bool):
        return

    token = str(value)
    if token != "" and (
        len(token) >= 3 or (current_key is not None and _is_secret_like_config_key(current_key))
    ):
        boundary_tokens.add(token)
        embedded_tokens.add(token)


def _collect_connection_config_numeric_field_tokens(
    value: object,
    *,
    adapter_type: str,
    tokens: set[int],
) -> None:
    if isinstance(value, Mapping):
        for nested_value in value.values():
            _collect_connection_config_numeric_field_tokens(
                nested_value,
                adapter_type=adapter_type,
                tokens=tokens,
            )
        return

    if isinstance(value, list | tuple):
        for item in value:
            _collect_connection_config_numeric_field_tokens(
                item,
                adapter_type=adapter_type,
                tokens=tokens,
            )
        return

    if isinstance(value, str):
        if value.casefold() == adapter_type.casefold():
            return
        for token in _connection_string_component_tokens(value):
            numeric_value = _integer_like_value(token)
            if numeric_value is not None:
                tokens.add(numeric_value)

    numeric_value = _integer_like_value(value)
    if numeric_value is not None:
        tokens.add(numeric_value)


def _connection_string_component_tokens(value: str) -> frozenset[str]:
    tokens: set[str] = set()
    stripped = value.strip()
    if stripped == "":
        return frozenset()

    with suppress(ValueError):
        parsed = urlsplit(stripped)
        if parsed.scheme and (parsed.netloc or parsed.path):
            _add_connection_string_component_token(parsed.username, tokens=tokens)
            _add_connection_string_component_token(
                parsed.password,
                tokens=tokens,
                allow_short=True,
            )
            _add_connection_string_component_token(parsed.hostname, tokens=tokens)
            with suppress(ValueError):
                port = parsed.port
                if port is not None:
                    tokens.add(str(port))
            for segment in parsed.path.split("/"):
                _add_connection_string_component_token(segment, tokens=tokens)
            for key, query_value in parse_qsl(parsed.query, keep_blank_values=False):
                secret_query_key = _is_secret_like_config_key(key)
                if secret_query_key:
                    _add_connection_string_component_token(key, tokens=tokens)
                _add_connection_string_component_token(
                    query_value,
                    tokens=tokens,
                    allow_short=secret_query_key,
                )

    if "://" in stripped or "@" in stripped or ";" in stripped:
        for component in _CONNECTION_STRING_COMPONENT_SPLIT_PATTERN.split(stripped):
            _add_connection_string_component_token(component, tokens=tokens)

    return frozenset(tokens)


def _add_connection_string_component_token(
    component: str | None,
    *,
    tokens: set[str],
    allow_short: bool = False,
) -> None:
    if component is None:
        return

    raw_component = component.strip()
    decoded_component = unquote(raw_component).strip()
    seen_components: set[str] = set()
    for candidate in (raw_component, decoded_component):
        if candidate in seen_components:
            continue
        seen_components.add(candidate)
        if candidate != "" and (allow_short or len(candidate) >= 3):
            tokens.add(candidate)


def _is_secret_like_config_key(key: str) -> bool:
    normalized_key = key.casefold()
    return any(
        secret_word in normalized_key
        for secret_word in (
            "password",
            "passwd",
            "pwd",
            "secret",
            "token",
            "credential",
            "key",
        )
    )


def _diagnostic_code_mentions_config_token(
    diagnostic: Diagnostic,
    code_config_tokens: _DiagnosticCodeConfigTokens,
    numeric_field_tokens: frozenset[int],
) -> bool:
    return (
        _code_mentions_config_token(
            diagnostic.code,
            code_config_tokens.boundary_tokens,
        )
        or _text_mentions_config_token(
            diagnostic.code,
            code_config_tokens.embedded_tokens,
        )
        or _code_mentions_numeric_config_token(diagnostic.code, numeric_field_tokens)
    )


def _diagnostic_mentions_config_token(
    diagnostic: Diagnostic,
    config_tokens: frozenset[str],
    numeric_field_tokens: frozenset[int],
) -> bool:
    if _diagnostic_numeric_fields_match_config_token(diagnostic, numeric_field_tokens):
        return True

    if not config_tokens and not numeric_field_tokens:
        return False

    diagnostic_text = "\n".join(
        str(value)
        for value in (
            diagnostic.message,
            diagnostic.hint,
            diagnostic.path,
            diagnostic.resource_type,
            diagnostic.resource_name,
            diagnostic.line,
            diagnostic.column,
        )
        if value is not None
    )
    return _text_mentions_config_token(
        diagnostic_text,
        config_tokens,
    ) or _text_mentions_numeric_config_token(diagnostic_text, numeric_field_tokens)


def _diagnostic_numeric_fields_match_config_token(
    diagnostic: Diagnostic,
    numeric_field_tokens: frozenset[int],
) -> bool:
    if not numeric_field_tokens:
        return False

    return any(
        numeric_value in numeric_field_tokens
        for numeric_value in (
            _integer_like_value(diagnostic.line),
            _integer_like_value(diagnostic.column),
        )
        if numeric_value is not None
    )


def _text_mentions_config_token(text: str, config_tokens: frozenset[str]) -> bool:
    normalized_text = text.casefold()
    return any(token.casefold() in normalized_text for token in config_tokens)


def _text_mentions_numeric_config_token(
    text: str,
    numeric_field_tokens: frozenset[int],
) -> bool:
    return any(
        _text_mentions_numeric_token(text, numeric_token) for numeric_token in numeric_field_tokens
    )


def _code_mentions_config_token(text: str, config_tokens: frozenset[str]) -> bool:
    normalized_text = text.casefold()
    return any(
        _code_mentions_token(normalized_text, token.casefold())
        for token in config_tokens
        if token != ""
    )


def _code_mentions_token(normalized_text: str, token: str) -> bool:
    start = normalized_text.find(token)
    while start != -1:
        end = start + len(token)
        if _code_token_has_text_boundaries(normalized_text, start, end):
            return True
        start = normalized_text.find(token, start + 1)
    return False


def _code_mentions_numeric_config_token(
    text: str,
    numeric_field_tokens: frozenset[int],
) -> bool:
    return any(
        _code_mentions_numeric_token(text, numeric_token) for numeric_token in numeric_field_tokens
    )


def _code_mentions_numeric_token(text: str, token: int) -> bool:
    for match in _NUMERIC_LITERAL_PATTERN.finditer(text):
        if _integer_like_numeric_literal(match.group(0)) == token:
            return True
    return False


def _code_token_has_text_boundaries(text: str, start: int, end: int) -> bool:
    previous_char = text[start - 1] if start > 0 else ""
    next_char = text[end] if end < len(text) else ""
    return not previous_char.isalnum() and not next_char.isalnum()


def _text_mentions_numeric_token(text: str, token: int) -> bool:
    for match in _NUMERIC_LITERAL_PATTERN.finditer(text):
        if not _numeric_literal_has_text_boundaries(text, match.start(), match.end()):
            continue
        if _integer_like_numeric_literal(match.group(0)) == token:
            return True
    return False


def _numeric_literal_has_text_boundaries(text: str, start: int, end: int) -> bool:
    previous_previous_char = text[start - 2] if start > 1 else ""
    previous_char = text[start - 1] if start > 0 else ""
    next_char = text[end] if end < len(text) else ""
    next_next_char = text[end + 1] if end + 1 < len(text) else ""

    if previous_char.isalnum() or previous_char in {"_", "+", "-"}:
        return False
    if previous_char == "." and previous_previous_char.isdecimal():
        return False
    if next_char.isalnum() or next_char == "_":
        return False
    return not (next_char == "." and next_next_char.isdecimal())


def _integer_like_numeric_literal(value: str) -> int | None:
    try:
        numeric_value = Decimal(value)
    except InvalidOperation:
        return None
    if not numeric_value.is_finite():
        return None
    integer_value = numeric_value.to_integral_value()
    if numeric_value != integer_value:
        return None
    return int(integer_value)


def _integer_like_value(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        return _integer_like_numeric_literal(stripped)
    return None


__all__ = [
    "ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    "sanitize_profile_backed_adapter_diagnostics",
]
