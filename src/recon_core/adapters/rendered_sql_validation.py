"""Validation helpers for rendered SQL step containers."""

from pathlib import Path

from recon_core.adapters.models import RenderedSql


def invalid_rendered_sql_output_reason(rendered_sql: object) -> str | None:
    """Return a human-readable reason when rendered SQL output is malformed."""
    if not isinstance(rendered_sql, tuple):
        return "Rendered SQL output must be a tuple of RenderedSql steps."

    seen_step_names: set[str] = set()
    for index, rendered_step in enumerate(rendered_sql):
        if not isinstance(rendered_step, RenderedSql):
            return f"Rendered SQL output step {index} is not a RenderedSql instance."
        if not isinstance(rendered_step.sql, str) or rendered_step.sql.strip() == "":
            return f"Rendered SQL output step {index} must define non-empty string SQL."
        if (
            not isinstance(rendered_step.operation_type, str)
            or rendered_step.operation_type.strip() == ""
        ):
            return f"Rendered SQL output step {index} must define a non-empty operation type."
        if not isinstance(rendered_step.step_name, str) or rendered_step.step_name.strip() == "":
            return f"Rendered SQL output step {index} must define a non-empty step name."
        if _is_unsafe_rendered_sql_step_name(rendered_step.step_name):
            return f"Rendered SQL output step {index} must define a safe single-segment step name."
        normalized_step_name = rendered_step.step_name.casefold()
        if normalized_step_name in seen_step_names:
            return f"Rendered SQL output step {index} duplicates a rendered SQL step name."
        seen_step_names.add(normalized_step_name)
        if not isinstance(rendered_step.required_capabilities, tuple) or not all(
            isinstance(capability, str) and capability.strip() != ""
            for capability in rendered_step.required_capabilities
        ):
            return (
                f"Rendered SQL output step {index} must define required capabilities as "
                "a tuple of non-empty strings."
            )

    return None


def _is_unsafe_rendered_sql_step_name(step_name: str) -> bool:
    return (
        step_name in {".", ".."}
        or "/" in step_name
        or "\\" in step_name
        or Path(step_name).is_absolute()
    )
