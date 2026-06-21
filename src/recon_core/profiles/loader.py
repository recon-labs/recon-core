"""Connection profile loading for adapter-aware workflows."""

import os
from collections.abc import Mapping
from pathlib import Path

from recon_core.profiles._diagnostics import (
    INVALID_PROFILE_CONFIG,
    INVALID_PROFILE_YAML,
    PROFILE_CONNECTION_NOT_FOUND,
    PROFILE_ENV_VAR_MISSING,
    PROFILE_FILE_NOT_FOUND,
    PROFILE_NOT_FOUND,
    PROFILE_NOT_SELECTED,
    PROFILE_TARGET_NOT_FOUND,
    profile_diagnostic,
)
from recon_core.profiles._profile_yaml import load_profile_yaml, profiles_mapping
from recon_core.profiles._selection import (
    normalized_connection_names,
    referenced_connections,
    selected_profile_target,
)
from recon_core.profiles.connection_references import (
    ContractConnectionReference,
    connection_names_from_contracts,
)
from recon_core.profiles.models import ProfileLoadResult, SelectedProfile
from recon_core.project import ProjectContext

__all__ = [
    "INVALID_PROFILE_CONFIG",
    "INVALID_PROFILE_YAML",
    "PROFILE_CONNECTION_NOT_FOUND",
    "PROFILE_ENV_VAR_MISSING",
    "PROFILE_FILE_NOT_FOUND",
    "PROFILE_NOT_FOUND",
    "PROFILE_NOT_SELECTED",
    "PROFILE_TARGET_NOT_FOUND",
    "load_selected_profile",
    "load_selected_profile_for_connection_names",
    "referenced_connection_names",
    "referenced_connection_names_from_compiled_contracts",
]

_PROFILES_RELATIVE_PATH = Path("connections") / "profiles.yml"


def load_selected_profile(
    context: ProjectContext,
    *,
    contracts: tuple[ContractConnectionReference, ...],
    environ: Mapping[str, str] | None = None,
) -> ProfileLoadResult:
    """Load the selected profile target and referenced connection configs."""
    return load_selected_profile_for_connection_names(
        context,
        referenced_connection_names=connection_names_from_contracts(contracts),
        environ=environ,
    )


def load_selected_profile_for_connection_names(
    context: ProjectContext,
    *,
    referenced_connection_names: tuple[str, ...],
    environ: Mapping[str, str] | None = None,
) -> ProfileLoadResult:
    """Load the selected profile target and named referenced connections."""
    profile_file = context.project_root / _PROFILES_RELATIVE_PATH
    display_path = _PROFILES_RELATIVE_PATH.as_posix()
    selected_profile_name = context.config.profile

    if selected_profile_name is None:
        return ProfileLoadResult(
            diagnostics=(
                profile_diagnostic(
                    PROFILE_NOT_SELECTED,
                    "Adapter-aware SQL rendering requires `profile` in recon_project.yml.",
                    path=str(context.project_file),
                    resource_type="project_config",
                    hint="Add `profile: <name>` to recon_project.yml.",
                ),
            )
        )

    if not profile_file.is_file():
        return ProfileLoadResult(
            diagnostics=(
                profile_diagnostic(
                    PROFILE_FILE_NOT_FOUND,
                    f"Profile file not found: {display_path}.",
                    path=display_path,
                    resource_type="profile_file",
                    hint="Create connections/profiles.yml for adapter-aware SQL rendering.",
                ),
            )
        )

    load_result = load_profile_yaml(profile_file, display_path)
    if load_result.diagnostics:
        return ProfileLoadResult(diagnostics=load_result.diagnostics)

    raw_profiles = profiles_mapping(load_result.data, display_path)
    if isinstance(raw_profiles, ProfileLoadResult):
        return raw_profiles

    selected_target = selected_profile_target(
        raw_profiles,
        selected_profile_name=selected_profile_name,
        display_path=display_path,
    )
    if isinstance(selected_target, ProfileLoadResult):
        return selected_target

    rendered_connections, diagnostics = referenced_connections(
        selected_target.connections,
        referenced_connection_names=normalized_connection_names(referenced_connection_names),
        profile_name=selected_target.profile_name,
        target_name=selected_target.target_name,
        profile_path=display_path,
        environ=os.environ if environ is None else environ,
    )
    if diagnostics:
        return ProfileLoadResult(diagnostics=tuple(diagnostics))

    return ProfileLoadResult(
        profile=SelectedProfile(
            name=selected_target.profile_name,
            target_name=selected_target.target_name,
            connections=rendered_connections,
        )
    )


def referenced_connection_names(
    contracts: tuple[ContractConnectionReference, ...],
) -> tuple[str, ...]:
    """Return connection names referenced by selected contracts."""
    return connection_names_from_contracts(contracts)


def referenced_connection_names_from_compiled_contracts(
    contracts: tuple[ContractConnectionReference, ...],
) -> tuple[str, ...]:
    """Return connection names referenced by loaded compiled contracts."""
    return connection_names_from_contracts(contracts)
