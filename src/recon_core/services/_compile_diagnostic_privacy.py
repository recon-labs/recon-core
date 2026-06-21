"""Profile-backed compile diagnostic privacy helpers."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from recon_core.adapters._diagnostic_redaction_core import sanitize_adapter_diagnostic
from recon_core.adapters._diagnostic_redaction_matching import (
    text_mentions_config_token,
    text_mentions_numeric_config_token,
)
from recon_core.adapters._diagnostic_redaction_tokens import (
    DiagnosticCodeConfigTokens,
)
from recon_core.adapters._diagnostic_redaction_tokens import (
    connection_config_code_tokens as _connection_config_code_tokens,
)
from recon_core.adapters._diagnostic_redaction_tokens import (
    connection_config_numeric_field_tokens as _connection_config_numeric_field_tokens,
)
from recon_core.adapters._diagnostic_redaction_tokens import (
    connection_config_tokens as _connection_config_tokens,
)
from recon_core.adapters.diagnostic_redaction import ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED
from recon_core.adapters.rendering import RenderedCheckSql
from recon_core.diagnostics import Diagnostic
from recon_core.profiles.models import ConnectionConfig


def sanitize_profile_backed_adapter_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    *,
    connection: ConnectionConfig,
    config_tokens: frozenset[str],
    code_config_tokens: DiagnosticCodeConfigTokens,
    numeric_field_tokens: frozenset[int],
) -> tuple[Diagnostic, ...]:
    """Suppress adapter diagnostics that mention rendered profile config."""
    return tuple(
        sanitize_profile_backed_adapter_diagnostic(
            diagnostic,
            connection=connection,
            config_tokens=config_tokens,
            code_config_tokens=code_config_tokens,
            numeric_field_tokens=numeric_field_tokens,
        )
        for diagnostic in diagnostics
    )


def sanitize_profile_backed_render_result(
    render_result: RenderedCheckSql,
    *,
    connection: ConnectionConfig,
    config_tokens: frozenset[str],
    code_config_tokens: DiagnosticCodeConfigTokens,
    numeric_field_tokens: frozenset[int],
) -> RenderedCheckSql:
    """Suppress unsafe profile-backed fields on a rendered-check SQL result."""
    return replace(
        render_result,
        diagnostics=sanitize_profile_backed_adapter_diagnostics(
            render_result.diagnostics,
            connection=connection,
            config_tokens=config_tokens,
            code_config_tokens=code_config_tokens,
            numeric_field_tokens=numeric_field_tokens,
        ),
        adapter_type=sanitize_profile_backed_adapter_type(
            render_result.adapter_type,
            connection=connection,
            config_tokens=config_tokens,
            numeric_field_tokens=numeric_field_tokens,
        ),
    )


def sanitize_profile_backed_adapter_type(
    adapter_type: object | None,
    *,
    connection: ConnectionConfig,
    config_tokens: frozenset[str],
    numeric_field_tokens: frozenset[int],
) -> str | None:
    """Suppress adapter type metadata if it leaks rendered profile config."""
    if not isinstance(adapter_type, str) or adapter_type == "":
        return None
    if not text_mentions_config_token(
        adapter_type,
        config_tokens,
    ) and not text_mentions_numeric_config_token(adapter_type, numeric_field_tokens):
        return adapter_type
    return connection.type


def sanitize_profile_backed_adapter_diagnostic(
    diagnostic: Diagnostic,
    *,
    connection: ConnectionConfig,
    config_tokens: frozenset[str],
    code_config_tokens: DiagnosticCodeConfigTokens,
    numeric_field_tokens: frozenset[int],
) -> Diagnostic:
    """Suppress one adapter diagnostic if it mentions rendered profile config."""
    return sanitize_adapter_diagnostic(
        diagnostic,
        connection_type=connection.type,
        connection_name=connection.name,
        config_tokens=config_tokens,
        code_config_tokens=code_config_tokens,
        numeric_field_tokens=numeric_field_tokens,
        suppressed_code=ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED,
        suppression_reason="profile diagnostics must not expose rendered connection config.",
    )


def connection_config_tokens(
    value: Mapping[str, Any],
    *,
    adapter_type: str,
) -> frozenset[str]:
    """Return string-like rendered profile tokens that diagnostics must not expose."""
    return _connection_config_tokens(value, adapter_type=adapter_type)


def connection_config_numeric_field_tokens(
    value: Mapping[str, Any],
    *,
    adapter_type: str,
) -> frozenset[int]:
    """Return numeric rendered profile tokens that diagnostics must not expose."""
    return _connection_config_numeric_field_tokens(value, adapter_type=adapter_type)


def connection_config_code_tokens(
    value: Mapping[str, Any],
    *,
    adapter_type: str,
) -> DiagnosticCodeConfigTokens:
    """Return rendered profile tokens that diagnostic codes must not expose."""
    return _connection_config_code_tokens(value, adapter_type=adapter_type)
