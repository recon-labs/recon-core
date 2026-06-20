"""Render-SQL orchestration for compile."""

from collections.abc import Mapping
from dataclasses import dataclass

from recon_core.adapters.base import BaseAdapter
from recon_core.adapters.capabilities import ADAPTER_CAPABILITY_UNSUPPORTED
from recon_core.adapters.duckdb import DuckDbSqlRenderer
from recon_core.adapters.registry import resolve_adapter_type
from recon_core.adapters.rendering import RenderedCheckSql, render_check_sql
from recon_core.compiler import ContractCompilationArtifacts
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services._compile_diagnostic_privacy import (
    connection_config_code_tokens,
    connection_config_numeric_field_tokens,
    connection_config_tokens,
    sanitize_profile_backed_adapter_diagnostic,
    sanitize_profile_backed_adapter_diagnostics,
    sanitize_profile_backed_adapter_type,
    sanitize_profile_backed_render_result,
)
from recon_core.services._compile_diagnostics import dedupe_diagnostics
from recon_core.services._compile_rendering_metadata import set_contract_render_block

MIXED_ADAPTER_TYPES_UNSUPPORTED = "RC_ADAPTER_MIXED_ADAPTER_TYPES_UNSUPPORTED"
ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED = "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class RenderSqlCompilationResult:
    """In-memory render-SQL results and diagnostics."""

    results_by_check_id: dict[str, RenderedCheckSql]
    diagnostics: tuple[Diagnostic, ...] = ()


def render_compiled_sql_in_memory(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    *,
    adapters_by_connection: dict[str, BaseAdapter],
    adapter_diagnostics_by_connection: Mapping[str, tuple[Diagnostic, ...]] | None = None,
) -> RenderSqlCompilationResult:
    """Render compiled checks to in-memory SQL without writing artifacts."""
    diagnostics: list[Diagnostic] = []
    results_by_check_id: dict[str, RenderedCheckSql] = {}
    connection_diagnostics = adapter_diagnostics_by_connection or {}

    for compiled_contract in compiled_contracts:
        source_connection = compiled_contract.contract_artifact.source.connection
        target_connection = compiled_contract.contract_artifact.target.connection
        adapter_diagnostics = _adapter_diagnostics_for_contract_connections(
            source_connection,
            target_connection,
            diagnostics_by_connection=connection_diagnostics,
        )
        if adapter_diagnostics:
            diagnostics.extend(adapter_diagnostics)
            set_contract_render_block(
                results_by_check_id,
                compiled_contract=compiled_contract,
                diagnostics=adapter_diagnostics,
            )
            continue

        source_adapter = adapters_by_connection.get(source_connection)
        target_adapter = adapters_by_connection.get(target_connection)
        if source_adapter is None or target_adapter is None:
            continue
        source_config_tokens = connection_config_tokens(
            source_adapter.connection.config,
            adapter_type=source_adapter.connection.type,
        )
        source_code_config_tokens = connection_config_code_tokens(
            source_adapter.connection.config,
            adapter_type=source_adapter.connection.type,
        )
        source_numeric_field_tokens = connection_config_numeric_field_tokens(
            source_adapter.connection.config,
            adapter_type=source_adapter.connection.type,
        )
        target_config_tokens = connection_config_tokens(
            target_adapter.connection.config,
            adapter_type=target_adapter.connection.type,
        )
        target_code_config_tokens = connection_config_code_tokens(
            target_adapter.connection.config,
            adapter_type=target_adapter.connection.type,
        )
        target_numeric_field_tokens = connection_config_numeric_field_tokens(
            target_adapter.connection.config,
            adapter_type=target_adapter.connection.type,
        )
        source_adapter_type_resolution = resolve_adapter_type(source_adapter)
        target_adapter_type_resolution = resolve_adapter_type(target_adapter)
        source_metadata_diagnostics = sanitize_profile_backed_adapter_diagnostics(
            source_adapter_type_resolution.diagnostics,
            connection=source_adapter.connection,
            config_tokens=source_config_tokens,
            code_config_tokens=source_code_config_tokens,
            numeric_field_tokens=source_numeric_field_tokens,
        )
        target_metadata_diagnostics = sanitize_profile_backed_adapter_diagnostics(
            target_adapter_type_resolution.diagnostics,
            connection=target_adapter.connection,
            config_tokens=target_config_tokens,
            code_config_tokens=target_code_config_tokens,
            numeric_field_tokens=target_numeric_field_tokens,
        )
        metadata_diagnostics = source_metadata_diagnostics + target_metadata_diagnostics
        if metadata_diagnostics:
            diagnostics.extend(metadata_diagnostics)
            set_contract_render_block(
                results_by_check_id,
                compiled_contract=compiled_contract,
                diagnostics=metadata_diagnostics,
            )
            continue
        assert source_adapter_type_resolution.adapter_type is not None
        assert target_adapter_type_resolution.adapter_type is not None
        source_adapter_type = sanitize_profile_backed_adapter_type(
            source_adapter_type_resolution.adapter_type,
            connection=source_adapter.connection,
            config_tokens=source_config_tokens,
            numeric_field_tokens=source_numeric_field_tokens,
        )
        if (
            source_adapter_type_resolution.adapter_type
            != target_adapter_type_resolution.adapter_type
        ):
            diagnostic = Diagnostic(
                code=MIXED_ADAPTER_TYPES_UNSUPPORTED,
                severity=DiagnosticSeverity.ERROR,
                message=(
                    "Milestone 6 SQL rendering requires source and target "
                    "connections to use the same adapter type."
                ),
                resource_type="compiled_contract",
                resource_name=compiled_contract.contract_artifact.contract.name,
                hint="Use relation endpoints on a single adapter type for this milestone.",
            )
            diagnostics.append(diagnostic)
            set_contract_render_block(
                results_by_check_id,
                compiled_contract=compiled_contract,
                diagnostics=(diagnostic,),
            )
            continue
        if not _same_connection_context(source_adapter, target_adapter):
            diagnostic = Diagnostic(
                code=ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED,
                severity=DiagnosticSeverity.ERROR,
                message=(
                    "Milestone 6 SQL rendering requires source and target "
                    "connections to resolve to the same adapter connection context."
                ),
                resource_type="compiled_contract",
                resource_name=compiled_contract.contract_artifact.contract.name,
                hint=(
                    "Use the same DuckDB database profile config for source and target, "
                    "or wait for explicit cross-connection rendering support."
                ),
            )
            diagnostics.append(diagnostic)
            set_contract_render_block(
                results_by_check_id,
                compiled_contract=compiled_contract,
                diagnostics=(diagnostic,),
                adapter_type=source_adapter_type,
            )
            continue

        renderer = _renderer_for_adapter_type(source_adapter_type_resolution.adapter_type)
        if renderer is None:
            diagnostic = Diagnostic(
                code=ADAPTER_CAPABILITY_UNSUPPORTED,
                severity=DiagnosticSeverity.ERROR,
                message=(
                    f"Adapter `{source_adapter_type_resolution.adapter_type}` "
                    "does not have a SQL renderer."
                ),
                resource_type="adapter",
                resource_name=source_adapter_type_resolution.adapter_type,
                hint="Use an adapter with a SQL renderer.",
            )
            diagnostic = sanitize_profile_backed_adapter_diagnostic(
                diagnostic,
                connection=source_adapter.connection,
                config_tokens=source_config_tokens,
                code_config_tokens=source_code_config_tokens,
                numeric_field_tokens=source_numeric_field_tokens,
            )
            diagnostics.append(diagnostic)
            set_contract_render_block(
                results_by_check_id,
                compiled_contract=compiled_contract,
                diagnostics=(diagnostic,),
                adapter_type=source_adapter_type,
            )
            continue

        for check in compiled_contract.checks_artifact.checks:
            render_result = render_check_sql(
                contract=compiled_contract.contract_artifact,
                check=check,
                adapter=source_adapter,
                renderer=renderer,
            )
            render_result = sanitize_profile_backed_render_result(
                render_result,
                connection=source_adapter.connection,
                config_tokens=source_config_tokens,
                code_config_tokens=source_code_config_tokens,
                numeric_field_tokens=source_numeric_field_tokens,
            )
            results_by_check_id[check.id] = render_result
            diagnostics.extend(render_result.diagnostics)

    return RenderSqlCompilationResult(
        results_by_check_id=results_by_check_id,
        diagnostics=dedupe_diagnostics(tuple(diagnostics)),
    )


def _adapter_diagnostics_for_contract_connections(
    source_connection: str,
    target_connection: str,
    *,
    diagnostics_by_connection: Mapping[str, tuple[Diagnostic, ...]],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen_connections: set[str] = set()

    for connection_name in (source_connection, target_connection):
        if connection_name in seen_connections:
            continue
        seen_connections.add(connection_name)
        diagnostics.extend(diagnostics_by_connection.get(connection_name, ()))

    return dedupe_diagnostics(tuple(diagnostics))


def _same_connection_context(source_adapter: BaseAdapter, target_adapter: BaseAdapter) -> bool:
    return (
        source_adapter.connection.type == target_adapter.connection.type
        and source_adapter.connection.config == target_adapter.connection.config
    )


def _renderer_for_adapter_type(adapter_type: str) -> DuckDbSqlRenderer | None:
    if adapter_type == "duckdb":
        return DuckDbSqlRenderer()
    return None
