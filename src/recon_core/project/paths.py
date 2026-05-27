"""Project path resolution."""

from dataclasses import dataclass, field
from pathlib import Path

from recon_core.config import ConfiguredPath, PathOrigin, ProjectConfig


@dataclass(frozen=True, slots=True)
class ResolvedResourcePath:
    """Resolved project resource path with authoring origin metadata."""

    path: Path
    origin: PathOrigin
    field_name: str


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
    resource_path_entries: tuple[ResolvedResourcePath, ...] = field(
        default=(),
        compare=False,
        repr=False,
    )

    def path_entries_for(self, field_name: str) -> tuple[ResolvedResourcePath, ...]:
        """Return resolved resource path entries for a project config field."""
        return tuple(
            entry for entry in self.resource_path_entries if entry.field_name == field_name
        )


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
        resource_path_entries=_resolve_resource_path_entries(project_root, config),
    )


def _resolve_path_list(project_root: Path, paths: tuple[str, ...]) -> tuple[Path, ...]:
    return tuple(_resolve_path(project_root, path) for path in paths)


def _resolve_path(project_root: Path, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return project_root / candidate


def _resolve_resource_path_entries(
    project_root: Path,
    config: ProjectConfig,
) -> tuple[ResolvedResourcePath, ...]:
    entries: list[ResolvedResourcePath] = []

    for field_name, values in _resource_path_values(config):
        configured_entries = config.path_entries_for(field_name)
        if not configured_entries:
            configured_entries = tuple(
                ConfiguredPath(
                    value=value,
                    origin=PathOrigin.AUTHORED,
                    field_name=field_name,
                )
                for value in values
            )

        entries.extend(
            ResolvedResourcePath(
                path=_resolve_path(project_root, entry.value),
                origin=entry.origin,
                field_name=entry.field_name,
            )
            for entry in configured_entries
        )

    return tuple(entries)


def _resource_path_values(config: ProjectConfig) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return (
        ("contract-paths", config.contract_paths),
        ("sample-policy-paths", config.sample_policy_paths),
        ("tolerance-policy-paths", config.tolerance_policy_paths),
        ("schema-policy-paths", config.schema_policy_paths),
        ("check-pack-paths", config.check_pack_paths),
        ("macro-paths", config.macro_paths),
    )
