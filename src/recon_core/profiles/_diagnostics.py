"""Profile loading diagnostics."""

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles.models import ProfileLoadResult

PROFILE_FILE_NOT_FOUND = "RC_CONFIG_PROFILE_FILE_NOT_FOUND"
INVALID_PROFILE_YAML = "RC_CONFIG_INVALID_PROFILE_YAML"
INVALID_PROFILE_CONFIG = "RC_CONFIG_INVALID_PROFILE_CONFIG"
PROFILE_NOT_SELECTED = "RC_CONFIG_PROFILE_NOT_SELECTED"
PROFILE_NOT_FOUND = "RC_CONFIG_PROFILE_NOT_FOUND"
PROFILE_TARGET_NOT_FOUND = "RC_CONFIG_PROFILE_TARGET_NOT_FOUND"
PROFILE_CONNECTION_NOT_FOUND = "RC_CONFIG_PROFILE_CONNECTION_NOT_FOUND"
PROFILE_ENV_VAR_MISSING = "RC_CONFIG_PROFILE_ENV_VAR_MISSING"


def invalid_profile_result(
    path: str,
    message: str,
    *,
    resource_name: str | None = None,
) -> ProfileLoadResult:
    return ProfileLoadResult(
        diagnostics=(
            profile_diagnostic(
                INVALID_PROFILE_CONFIG,
                message,
                path=path,
                resource_type="profile",
                resource_name=resource_name,
                hint="Use the documented connections/profiles.yml structure.",
            ),
        )
    )


def profile_diagnostic(
    code: str,
    message: str,
    *,
    path: str,
    resource_type: str,
    resource_name: str | None = None,
    line: int | None = None,
    column: int | None = None,
    hint: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type=resource_type,
        resource_name=resource_name,
        path=path,
        line=line,
        column=column,
        hint=hint,
    )
