"""Stable public identifiers for compiled compiler artifacts."""

import re

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

INVALID_STABLE_ID_PART = "RC_VALIDATE_INVALID_STABLE_ID_PART"
STABLE_ID_PART_HINT = (
    "Use letters, numbers, and underscores. Names must start with a letter or underscore."
)
_STABLE_ID_PART = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def build_contract_id(project_name: str, contract_name: str) -> str:
    """Build a stable compiled contract ID."""
    _validate_stable_id_parts(project_name, contract_name)
    return f"contract.{project_name}.{contract_name}"


def build_check_id(project_name: str, contract_name: str, check_name: str) -> str:
    """Build a stable compiled check ID."""
    _validate_stable_id_parts(project_name, contract_name, check_name)
    return f"check.{project_name}.{contract_name}.{check_name}"


def build_plan_id(project_name: str, contract_name: str, check_name: str) -> str:
    """Build a stable typed check plan ID."""
    _validate_stable_id_parts(project_name, contract_name, check_name)
    return f"plan.{project_name}.{contract_name}.{check_name}"


def is_valid_stable_id_part(part: str) -> bool:
    """Return whether a public stable ID part can be used safely."""
    return bool(_STABLE_ID_PART.fullmatch(part))


def invalid_stable_id_part_diagnostic(
    *,
    resource_type: str,
    resource_name: str,
    value: str,
    path: str | None = None,
) -> Diagnostic:
    """Build a structured diagnostic for invalid stable ID input."""
    return Diagnostic(
        code=INVALID_STABLE_ID_PART,
        severity=DiagnosticSeverity.ERROR,
        message=f"{resource_type.title()} name {value} cannot be used in stable compiled IDs.",
        resource_type=resource_type,
        resource_name=resource_name,
        path=path,
        hint=STABLE_ID_PART_HINT,
    )


def _validate_stable_id_parts(*parts: str) -> None:
    invalid_parts = [part for part in parts if not is_valid_stable_id_part(part)]
    if invalid_parts:
        invalid = ", ".join(repr(part) for part in invalid_parts)
        raise ValueError(
            "Stable ID parts must start with a letter or underscore and contain "
            f"only letters, numbers, and underscores: {invalid}"
        )
