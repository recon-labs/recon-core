"""Project context loading."""

from dataclasses import dataclass
from pathlib import Path

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.project.discovery import PROJECT_FILE_NAME, find_project_root


@dataclass(frozen=True, slots=True)
class ProjectContext:
    """Minimal project context discovered from the filesystem."""

    project_root: Path
    project_file: Path


@dataclass(frozen=True, slots=True)
class ProjectContextLoadResult:
    """Result for project context loading."""

    context: ProjectContext | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.context is not None and not self.diagnostics


def load_project_context(start_path: Path | None = None) -> ProjectContextLoadResult:
    """Discover the Recon project context from a start path."""
    start = Path.cwd() if start_path is None else Path(start_path)
    project_root = find_project_root(start)

    if project_root is None:
        return ProjectContextLoadResult(
            diagnostics=(
                Diagnostic(
                    code="RC_CONFIG_PROJECT_NOT_FOUND",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"No {PROJECT_FILE_NAME} found from {start}.",
                    resource_type="project",
                    path=str(start),
                    hint=(
                        "Run this command from a Recon project directory, "
                        "or create one with `recon init <project_name>`."
                    ),
                ),
            )
        )

    return ProjectContextLoadResult(
        context=ProjectContext(
            project_root=project_root,
            project_file=project_root / PROJECT_FILE_NAME,
        )
    )
