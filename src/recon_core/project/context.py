"""Project context loading."""

from dataclasses import dataclass
from pathlib import Path

from recon_core.config import ProjectConfig, load_project_config
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.project.discovery import PROJECT_FILE_NAME, find_project_root
from recon_core.project.paths import ProjectPaths, resolve_project_paths


@dataclass(frozen=True, slots=True)
class ProjectContext:
    """Loaded project context."""

    project_root: Path
    project_file: Path
    config: ProjectConfig
    paths: ProjectPaths
    profile_paths: tuple[Path, ...]


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

    project_file = project_root / PROJECT_FILE_NAME
    config_result = load_project_config(project_file)
    if not config_result.succeeded:
        return ProjectContextLoadResult(diagnostics=config_result.diagnostics)

    assert config_result.config is not None
    paths = resolve_project_paths(project_root, config_result.config)

    return ProjectContextLoadResult(
        context=ProjectContext(
            project_root=project_root,
            project_file=project_file,
            config=config_result.config,
            paths=paths,
            profile_paths=_profile_paths(project_root),
        )
    )


def _profile_paths(project_root: Path) -> tuple[Path, ...]:
    connections_dir = project_root / "connections"
    return (
        connections_dir / "profiles.yml.example",
        connections_dir / "profiles.yml",
    )
