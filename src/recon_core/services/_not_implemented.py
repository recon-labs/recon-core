"""Helpers for command services that are not implemented yet."""

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services.results import ExitCategory, ServiceResult


def not_implemented_result(command_name: str, service_name: str) -> ServiceResult:
    message = f"recon {command_name} is not implemented yet."
    return ServiceResult(
        exit_category=ExitCategory.RUNTIME_ERROR,
        message=message,
        diagnostics=(
            Diagnostic(
                code="RC_RUNTIME_NOT_IMPLEMENTED",
                severity=DiagnosticSeverity.ERROR,
                message=message,
                hint=f"Implement {service_name} in a later milestone.",
            ),
        ),
    )
