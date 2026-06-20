"""Selected profile and referenced connection resolution."""

from collections.abc import Mapping
from dataclasses import dataclass

from recon_core.diagnostics import Diagnostic
from recon_core.profiles._diagnostics import (
    INVALID_PROFILE_CONFIG,
    PROFILE_CONNECTION_NOT_FOUND,
    PROFILE_NOT_FOUND,
    PROFILE_TARGET_NOT_FOUND,
    invalid_profile_result,
    profile_diagnostic,
)
from recon_core.profiles._rendering import connection_type_uses_template, render_profile_value
from recon_core.profiles.models import ConnectionConfig, ProfileLoadResult


@dataclass(frozen=True, slots=True)
class SelectedProfileTarget:
    profile_name: str
    target_name: str
    connections: Mapping[object, object]


def normalized_connection_names(names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(names)))


def selected_profile_target(
    raw_profiles: Mapping[object, object],
    *,
    selected_profile_name: str,
    display_path: str,
) -> SelectedProfileTarget | ProfileLoadResult:
    raw_profile = raw_profiles.get(selected_profile_name)
    if not isinstance(raw_profile, Mapping):
        return ProfileLoadResult(
            diagnostics=(
                profile_diagnostic(
                    PROFILE_NOT_FOUND,
                    f"Selected profile `{selected_profile_name}` was not found.",
                    path=display_path,
                    resource_type="profile",
                    resource_name=selected_profile_name,
                    hint=(
                        "Add the profile under `profiles` or update `profile` in "
                        "recon_project.yml."
                    ),
                ),
            )
        )

    raw_target_name = raw_profile.get("target")
    if not isinstance(raw_target_name, str) or raw_target_name == "":
        return invalid_profile_result(
            display_path,
            "Selected profile must define a non-empty string `target`.",
            resource_name=selected_profile_name,
        )

    raw_outputs = raw_profile.get("outputs")
    if not isinstance(raw_outputs, Mapping):
        return invalid_profile_result(
            display_path,
            "Selected profile must define an `outputs` mapping.",
            resource_name=selected_profile_name,
        )

    raw_target = raw_outputs.get(raw_target_name)
    if not isinstance(raw_target, Mapping):
        return ProfileLoadResult(
            diagnostics=(
                profile_diagnostic(
                    PROFILE_TARGET_NOT_FOUND,
                    (
                        f"Selected target `{raw_target_name}` was not found for "
                        f"profile `{selected_profile_name}`."
                    ),
                    path=display_path,
                    resource_type="profile_target",
                    resource_name=selected_profile_name,
                    hint="Add the target under `outputs` or update the profile `target`.",
                ),
            )
        )

    raw_connections = raw_target.get("connections")
    if not isinstance(raw_connections, Mapping):
        return invalid_profile_result(
            display_path,
            "Selected profile target must define a `connections` mapping.",
            resource_name=selected_profile_name,
        )

    return SelectedProfileTarget(
        profile_name=selected_profile_name,
        target_name=raw_target_name,
        connections=raw_connections,
    )


def referenced_connections(
    raw_connections: Mapping[object, object],
    *,
    referenced_connection_names: tuple[str, ...],
    profile_name: str,
    target_name: str,
    profile_path: str,
    environ: Mapping[str, str],
) -> tuple[dict[str, ConnectionConfig], list[Diagnostic]]:
    rendered_connections: dict[str, ConnectionConfig] = {}
    diagnostics: list[Diagnostic] = []

    for connection_name in referenced_connection_names:
        raw_connection = raw_connections.get(connection_name)
        if not isinstance(raw_connection, Mapping):
            diagnostics.append(
                profile_diagnostic(
                    PROFILE_CONNECTION_NOT_FOUND,
                    (
                        f"Connection `{connection_name}` referenced by selected contracts "
                        f"was not found in profile `{profile_name}` target `{target_name}`."
                    ),
                    path=profile_path,
                    resource_type="profile_connection",
                    resource_name=connection_name,
                    hint="Add the named connection or update the contract endpoint connection.",
                )
            )
            continue

        raw_connection_type = raw_connection.get("type")
        if not isinstance(raw_connection_type, str) or raw_connection_type == "":
            diagnostics.append(
                profile_diagnostic(
                    INVALID_PROFILE_CONFIG,
                    f"Connection `{connection_name}` must define a non-empty string `type`.",
                    path=profile_path,
                    resource_type="profile_connection",
                    resource_name=connection_name,
                    hint="Set the adapter type for this connection.",
                )
            )
            continue
        if connection_type_uses_template(raw_connection_type):
            diagnostics.append(
                profile_diagnostic(
                    INVALID_PROFILE_CONFIG,
                    f"Connection `{connection_name}` field `type` must be a literal adapter type.",
                    path=profile_path,
                    resource_type="profile_connection",
                    resource_name=connection_name,
                    hint=(
                        "Set `type` to a literal adapter type such as `duckdb`; use "
                        "`env_var(...)` only for non-routing connection config values."
                    ),
                )
            )
            continue

        rendered_config = render_profile_value(
            dict(raw_connection),
            connection_name=connection_name,
            profile_path=profile_path,
            environ=environ,
            diagnostics=diagnostics,
        )
        if isinstance(rendered_config, dict):
            connection_type = rendered_config.get("type")
            if not isinstance(connection_type, str) or connection_type == "":
                diagnostics.append(
                    profile_diagnostic(
                        INVALID_PROFILE_CONFIG,
                        f"Connection `{connection_name}` must define a non-empty string `type`.",
                        path=profile_path,
                        resource_type="profile_connection",
                        resource_name=connection_name,
                        hint="Set the adapter type for this connection.",
                    )
                )
                continue
            rendered_connections[connection_name] = ConnectionConfig(
                name=connection_name,
                type=connection_type,
                config=rendered_config,
            )

    return rendered_connections, diagnostics
