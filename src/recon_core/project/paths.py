"""Project path resolution."""

from dataclasses import dataclass
from pathlib import Path

from recon_core.config import ProjectConfig


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    """Resolved project paths."""

    contract_paths: tuple[Path, ...]
    sample_policy_paths: tuple[Path, ...]
    tolerance_policy_paths: tuple[Path, ...]
    schema_policy_paths: tuple[Path, ...]
    check_pack_paths: tuple[Path, ...]
    macro_paths: tuple[Path, ...]
    target_path: Path
    report_path: Path
    state_path: Path


def resolve_project_paths(project_root: Path, config: ProjectConfig) -> ProjectPaths:
    """Resolve project config paths against the project root."""
    return ProjectPaths(
        contract_paths=_resolve_path_list(project_root, config.contract_paths),
        sample_policy_paths=_resolve_path_list(project_root, config.sample_policy_paths),
        tolerance_policy_paths=_resolve_path_list(project_root, config.tolerance_policy_paths),
        schema_policy_paths=_resolve_path_list(project_root, config.schema_policy_paths),
        check_pack_paths=_resolve_path_list(project_root, config.check_pack_paths),
        macro_paths=_resolve_path_list(project_root, config.macro_paths),
        target_path=_resolve_path(project_root, config.target_path),
        report_path=_resolve_path(project_root, config.report_path),
        state_path=_resolve_path(project_root, config.state_path),
    )


def _resolve_path_list(project_root: Path, paths: tuple[str, ...]) -> tuple[Path, ...]:
    return tuple(_resolve_path(project_root, path) for path in paths)


def _resolve_path(project_root: Path, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return project_root / candidate
