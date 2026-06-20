"""Adapter/profile preparation for compile SQL rendering."""

from dataclasses import dataclass

from recon_core.adapters.base import BaseAdapter
from recon_core.adapters.default_registry import default_adapter_registry
from recon_core.adapters.registry import (
    AdapterRegistry,
    resolve_adapter_type,
    validate_adapter_api_compatibility,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles.models import ConnectionConfig, SelectedProfile
from recon_core.services._compile_diagnostic_privacy import (
    connection_config_code_tokens,
    connection_config_numeric_field_tokens,
    connection_config_tokens,
    sanitize_profile_backed_adapter_diagnostics,
)
from recon_core.services._compile_diagnostics import dedupe_diagnostics

ADAPTER_TYPE_MISMATCH = "RC_ADAPTER_TYPE_MISMATCH"


@dataclass(frozen=True, slots=True)
class RenderSqlAdapterResolution:
    """Prepared adapters and diagnostics for render-SQL."""

    adapters_by_connection: dict[str, BaseAdapter]
    diagnostics_by_connection: dict[str, tuple[Diagnostic, ...]]
    diagnostics: tuple[Diagnostic, ...] = ()


def resolve_render_sql_adapters(
    profile: SelectedProfile,
    *,
    registry: AdapterRegistry | None,
) -> RenderSqlAdapterResolution:
    """Resolve profile connections into render-SQL adapter instances."""
    resolved_registry = default_adapter_registry() if registry is None else registry
    diagnostics: list[Diagnostic] = []
    adapters_by_connection: dict[str, BaseAdapter] = {}
    diagnostics_by_connection: dict[str, tuple[Diagnostic, ...]] = {}

    for connection in profile.connections.values():
        config_tokens = connection_config_tokens(connection.config, adapter_type=connection.type)
        code_config_tokens = connection_config_code_tokens(
            connection.config,
            adapter_type=connection.type,
        )
        numeric_field_tokens = connection_config_numeric_field_tokens(
            connection.config,
            adapter_type=connection.type,
        )
        connection_diagnostics: list[Diagnostic] = []
        resolution = resolved_registry.resolve(connection)
        resolution_diagnostics = _connection_scoped_adapter_setup_diagnostics(
            sanitize_profile_backed_adapter_diagnostics(
                resolution.diagnostics,
                connection=connection,
                config_tokens=config_tokens,
                code_config_tokens=code_config_tokens,
                numeric_field_tokens=numeric_field_tokens,
            ),
            connection=connection,
        )
        connection_diagnostics.extend(resolution_diagnostics)
        if resolution_diagnostics or resolution.adapter is None:
            diagnostics.extend(connection_diagnostics)
            if connection_diagnostics:
                diagnostics_by_connection[connection.name] = dedupe_diagnostics(
                    tuple(connection_diagnostics)
                )
            continue
        metadata_resolution = resolve_adapter_type(resolution.adapter)
        metadata_diagnostics = _connection_scoped_adapter_setup_diagnostics(
            sanitize_profile_backed_adapter_diagnostics(
                metadata_resolution.diagnostics,
                connection=connection,
                config_tokens=config_tokens,
                code_config_tokens=code_config_tokens,
                numeric_field_tokens=numeric_field_tokens,
            ),
            connection=connection,
        )
        connection_diagnostics.extend(metadata_diagnostics)
        if metadata_diagnostics:
            diagnostics.extend(connection_diagnostics)
            diagnostics_by_connection[connection.name] = dedupe_diagnostics(
                tuple(connection_diagnostics)
            )
            continue
        assert metadata_resolution.adapter_type is not None
        if metadata_resolution.adapter_type != connection.type:
            type_mismatch_diagnostics = _connection_scoped_adapter_setup_diagnostics(
                sanitize_profile_backed_adapter_diagnostics(
                    (_adapter_type_mismatch_diagnostic(connection),),
                    connection=connection,
                    config_tokens=config_tokens,
                    code_config_tokens=code_config_tokens,
                    numeric_field_tokens=numeric_field_tokens,
                ),
                connection=connection,
            )
            connection_diagnostics.extend(type_mismatch_diagnostics)
            diagnostics.extend(connection_diagnostics)
            diagnostics_by_connection[connection.name] = dedupe_diagnostics(
                tuple(connection_diagnostics)
            )
            continue
        api_diagnostics = _connection_scoped_adapter_setup_diagnostics(
            sanitize_profile_backed_adapter_diagnostics(
                validate_adapter_api_compatibility(resolution.adapter),
                connection=connection,
                config_tokens=config_tokens,
                code_config_tokens=code_config_tokens,
                numeric_field_tokens=numeric_field_tokens,
            ),
            connection=connection,
        )
        connection_diagnostics.extend(api_diagnostics)
        diagnostics.extend(connection_diagnostics)
        if api_diagnostics:
            diagnostics_by_connection[connection.name] = dedupe_diagnostics(
                tuple(connection_diagnostics)
            )
            continue
        adapters_by_connection[connection.name] = resolution.adapter

    return RenderSqlAdapterResolution(
        adapters_by_connection=adapters_by_connection,
        diagnostics_by_connection=diagnostics_by_connection,
        diagnostics=dedupe_diagnostics(tuple(diagnostics)),
    )


def _connection_scoped_adapter_setup_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    *,
    connection: ConnectionConfig,
) -> tuple[Diagnostic, ...]:
    return tuple(
        _connection_scoped_adapter_setup_diagnostic(diagnostic, connection=connection)
        for diagnostic in diagnostics
    )


def _connection_scoped_adapter_setup_diagnostic(
    diagnostic: Diagnostic,
    *,
    connection: ConnectionConfig,
) -> Diagnostic:
    connection_marker = f"connection `{connection.name}`".casefold()
    if connection_marker in diagnostic.message.casefold():
        return diagnostic
    return Diagnostic(
        code=diagnostic.code,
        severity=diagnostic.severity,
        message=f"Connection `{connection.name}`: {diagnostic.message}",
        resource_type=diagnostic.resource_type,
        resource_name=diagnostic.resource_name,
        path=diagnostic.path,
        line=diagnostic.line,
        column=diagnostic.column,
        hint=diagnostic.hint,
    )


def _adapter_type_mismatch_diagnostic(connection: ConnectionConfig) -> Diagnostic:
    return Diagnostic(
        code=ADAPTER_TYPE_MISMATCH,
        severity=DiagnosticSeverity.ERROR,
        message=(
            f"Adapter factory for profile type `{connection.type}` returned adapter "
            "metadata that does not match the profile connection type."
        ),
        resource_type="adapter",
        resource_name=connection.type,
        hint=(
            "Register the adapter under its declared adapter type or update the "
            "adapter's `adapter_type` metadata to match the profile `type`."
        ),
    )
