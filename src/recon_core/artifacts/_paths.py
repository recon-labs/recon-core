"""Filesystem safeguards for generated artifact writers."""

from pathlib import Path


def ensure_safe_artifact_write(output_path: Path, *, overwrite: bool) -> None:
    """Reject unintentional overwrites and case-insensitive path collisions."""
    output_dir = output_path.parent
    output_name_key = output_path.name.casefold()

    if not output_dir.exists():
        return

    matching_paths = tuple(
        existing_path
        for existing_path in output_dir.iterdir()
        if existing_path.name.casefold() == output_name_key
    )
    case_collisions = tuple(
        existing_path for existing_path in matching_paths if existing_path.name != output_path.name
    )

    if case_collisions:
        colliding_names = ", ".join(path.name for path in case_collisions)
        raise FileExistsError(
            f"Artifact filename {output_path.name} has a case-insensitive collision "
            f"with existing artifact {colliding_names} under {output_dir}."
        )

    if matching_paths and not overwrite:
        raise FileExistsError(f"Artifact already exists: {output_path}")
