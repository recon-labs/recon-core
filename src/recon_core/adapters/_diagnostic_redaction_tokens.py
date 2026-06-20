"""Private rendered-profile token extraction for adapter diagnostic redaction."""

import re
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, unquote, urlsplit

_CONNECTION_STRING_COMPONENT_SPLIT_PATTERN = re.compile(r"[^A-Za-z0-9_.+-]+")


@dataclass(frozen=True, slots=True)
class DiagnosticCodeConfigTokens:
    """Connection config tokens for diagnostic code redaction checks."""

    boundary_tokens: frozenset[str]
    embedded_tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class AdapterDiagnosticConfigTokens:
    """Rendered connection config tokens for adapter diagnostic redaction."""

    config_tokens: frozenset[str]
    code_config_tokens: DiagnosticCodeConfigTokens
    numeric_field_tokens: frozenset[int]


def adapter_diagnostic_config_tokens(
    value: Mapping[str, object],
    *,
    adapter_type: str,
) -> AdapterDiagnosticConfigTokens:
    """Return all token groups needed for adapter diagnostic redaction."""
    return AdapterDiagnosticConfigTokens(
        config_tokens=connection_config_tokens(value, adapter_type=adapter_type),
        code_config_tokens=connection_config_code_tokens(value, adapter_type=adapter_type),
        numeric_field_tokens=connection_config_numeric_field_tokens(
            value,
            adapter_type=adapter_type,
        ),
    )


def connection_config_tokens(
    value: Mapping[str, object],
    *,
    adapter_type: str,
) -> frozenset[str]:
    """Return string-like rendered profile tokens that diagnostics must not expose."""
    tokens: set[str] = set()
    _collect_connection_config_tokens(value, adapter_type=adapter_type, tokens=tokens)
    return frozenset(tokens)


def connection_config_code_tokens(
    value: Mapping[str, object],
    *,
    adapter_type: str,
) -> DiagnosticCodeConfigTokens:
    """Return rendered profile tokens that diagnostic codes must not expose."""
    boundary_tokens: set[str] = set()
    embedded_tokens: set[str] = set()
    _collect_connection_config_code_tokens(
        value,
        adapter_type=adapter_type,
        boundary_tokens=boundary_tokens,
        embedded_tokens=embedded_tokens,
    )
    return DiagnosticCodeConfigTokens(
        boundary_tokens=frozenset(boundary_tokens),
        embedded_tokens=frozenset(embedded_tokens),
    )


def connection_config_numeric_field_tokens(
    value: Mapping[str, object],
    *,
    adapter_type: str,
) -> frozenset[int]:
    """Return numeric rendered profile tokens that diagnostics must not expose."""
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
