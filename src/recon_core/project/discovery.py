"""Project root discovery."""

from pathlib import Path

PROJECT_FILE_NAME = "recon_project.yml"


def find_project_root(start_path: Path | None = None) -> Path | None:
    """Search upward from a file or directory for a Recon project marker."""
    start = Path.cwd() if start_path is None else Path(start_path)
    candidate = start.resolve()

    if candidate.is_file():
        candidate = candidate.parent

    for directory in (candidate, *candidate.parents):
        if (directory / PROJECT_FILE_NAME).is_file():
            return directory

    return None
