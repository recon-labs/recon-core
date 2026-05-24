"""Filesystem safeguards for generated artifact writers."""

from pathlib import Path


def ensure_real_artifact_directory(output_dir: Path) -> None:
    """Create an artifact directory after rejecting symlinked path components."""
    reject_symlinked_path_components(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reject_symlinked_path_components(output_dir)


def reject_symlinked_path_components(path: Path) -> None:
    """Reject a path if any existing component is a symlink."""
    current_path = Path(path.anchor) if path.is_absolute() else Path()
    parts = path.parts[1:] if path.is_absolute() else path.parts

    for part in parts:
        current_path = current_path / part
        if current_path.is_symlink():
            raise FileExistsError(f"Artifact path contains a symlink: {current_path}")


def artifact_output_path(output_dir: Path, artifact_name: str) -> Path:
    """Build an artifact path from a safe filename stem."""
    _validate_artifact_filename_stem(artifact_name)
    return output_dir / f"{artifact_name}.yml"


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


def _validate_artifact_filename_stem(artifact_name: str) -> None:
    if (
        not artifact_name
        or artifact_name in {".", ".."}
        or "/" in artifact_name
        or "\\" in artifact_name
        or Path(artifact_name).is_absolute()
    ):
        raise ValueError(f"Artifact name {artifact_name!r} is not a safe artifact filename stem.")
