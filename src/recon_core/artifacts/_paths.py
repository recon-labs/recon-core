"""Filesystem safeguards for generated artifact writers."""

from pathlib import Path


def ensure_safe_artifact_write(output_path: Path, *, overwrite: bool) -> None:
    """Reject unintentional overwrites and case-insensitive path collisions."""
    output_dir = output_path.parent
    output_name_key = output_path.name.casefold()

    if not output_dir.exists():
        return

    for existing_path in output_dir.iterdir():
        if existing_path.name.casefold() != output_name_key:
            continue

        if existing_path.name == output_path.name:
            if overwrite:
                return
            raise FileExistsError(f"Artifact already exists: {output_path}")

        raise FileExistsError(
            f"Artifact filename {output_path.name} has a case-insensitive collision "
            f"with existing artifact {existing_path.name} under {output_dir}."
        )
