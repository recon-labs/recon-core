"""Private adapter diagnostic redaction matching helpers."""

import re

from recon_core.adapters._diagnostic_redaction_tokens import (
    DiagnosticCodeConfigTokens,
    _integer_like_numeric_literal,
    _integer_like_value,
)
from recon_core.diagnostics import Diagnostic

_NUMERIC_LITERAL_PATTERN = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def diagnostic_code_mentions_config_token(
    diagnostic: Diagnostic,
    code_config_tokens: DiagnosticCodeConfigTokens,
    numeric_field_tokens: frozenset[int],
) -> bool:
    """Return whether a diagnostic code includes rendered profile config."""
    return (
        _code_mentions_config_token(
            diagnostic.code,
            code_config_tokens.boundary_tokens,
        )
        or text_mentions_config_token(
            diagnostic.code,
            code_config_tokens.embedded_tokens,
        )
        or _code_mentions_numeric_config_token(diagnostic.code, numeric_field_tokens)
    )


def diagnostic_mentions_config_token(
    diagnostic: Diagnostic,
    config_tokens: frozenset[str],
    numeric_field_tokens: frozenset[int],
) -> bool:
    """Return whether a diagnostic field includes rendered profile config."""
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
    return text_mentions_config_token(
        diagnostic_text,
        config_tokens,
    ) or text_mentions_numeric_config_token(diagnostic_text, numeric_field_tokens)


def text_mentions_config_token(text: str, config_tokens: frozenset[str]) -> bool:
    """Return whether text includes a rendered profile token."""
    normalized_text = text.casefold()
    return any(token.casefold() in normalized_text for token in config_tokens)


def text_mentions_numeric_config_token(
    text: str,
    numeric_field_tokens: frozenset[int],
) -> bool:
    """Return whether text includes a rendered numeric profile token."""
    return any(
        _text_mentions_numeric_token(text, numeric_token) for numeric_token in numeric_field_tokens
    )


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
