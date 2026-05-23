"""Stable public identifiers for compiled compiler artifacts."""

import re

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


def _validate_stable_id_parts(*parts: str) -> None:
    invalid_parts = [part for part in parts if not _STABLE_ID_PART.fullmatch(part)]
    if invalid_parts:
        invalid = ", ".join(repr(part) for part in invalid_parts)
        raise ValueError(
            "Stable ID parts must start with a letter or underscore and contain "
            f"only letters, numbers, and underscores: {invalid}"
        )
