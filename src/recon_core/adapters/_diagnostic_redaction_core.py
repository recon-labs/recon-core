"""Private adapter diagnostic redaction core helpers."""

from recon_core.adapters._diagnostic_redaction_matching import (
    diagnostic_code_mentions_config_token,
    diagnostic_mentions_config_token,
)
from recon_core.adapters._diagnostic_redaction_tokens import DiagnosticCodeConfigTokens
from recon_core.diagnostics import Diagnostic


def sanitize_adapter_diagnostic(
    diagnostic: Diagnostic,
    *,
    connection_type: str,
    connection_name: str,
    config_tokens: frozenset[str],
    code_config_tokens: DiagnosticCodeConfigTokens,
    numeric_field_tokens: frozenset[int],
    suppressed_code: str,
    suppression_reason: str,
) -> Diagnostic:
    """Suppress one adapter diagnostic if it mentions rendered profile config."""
    code_mentions_config_token = diagnostic_code_mentions_config_token(
        diagnostic,
        code_config_tokens,
        numeric_field_tokens,
    )
    if not code_mentions_config_token and not diagnostic_mentions_config_token(
        diagnostic,
        config_tokens,
        numeric_field_tokens,
    ):
        return diagnostic

    return Diagnostic(
        code=suppressed_code if code_mentions_config_token else diagnostic.code,
        severity=diagnostic.severity,
        message=(
            f"Adapter `{connection_type}` reported a diagnostic for "
            f"connection `{connection_name}`; adapter diagnostic text was suppressed "
            f"because {suppression_reason}"
        ),
        resource_type="adapter",
        resource_name=connection_type,
        hint=(
            "Fix the adapter configuration or inspect the adapter locally without exposing secrets."
        ),
    )
