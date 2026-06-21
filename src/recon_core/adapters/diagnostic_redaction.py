"""Adapter diagnostic redaction for profile-backed setup paths."""

from recon_core.adapters._diagnostic_redaction_core import sanitize_adapter_diagnostic
from recon_core.adapters._diagnostic_redaction_tokens import adapter_diagnostic_config_tokens
from recon_core.diagnostics import Diagnostic
from recon_core.profiles import ConnectionConfig

ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED = "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED"


def sanitize_profile_backed_adapter_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    *,
    connection: ConnectionConfig,
) -> tuple[Diagnostic, ...]:
    """Suppress rendered connection config from adapter-provided diagnostics."""
    token_context = adapter_diagnostic_config_tokens(
        connection.config,
        adapter_type=connection.type,
    )
    return tuple(
        sanitize_adapter_diagnostic(
            diagnostic,
            connection_type=connection.type,
            connection_name=connection.name,
            config_tokens=token_context.config_tokens,
            code_config_tokens=token_context.code_config_tokens,
            numeric_field_tokens=token_context.numeric_field_tokens,
            suppressed_code=ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED,
            suppression_reason=(
                "runtime adapter diagnostics must not expose rendered connection config."
            ),
        )
        for diagnostic in diagnostics
    )


__all__ = [
    "ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    "sanitize_profile_backed_adapter_diagnostics",
]
