"""Compile command service."""

from dataclasses import dataclass
from pathlib import Path

from recon_core.adapters.registry import AdapterRegistry
from recon_core.artifacts import (
    COMPILED_CHECKS_DIR_NAME,
    COMPILED_CONTRACTS_DIR_NAME,
    COMPILED_SQL_DIR_NAME,
)
from recon_core.compiler import compile_project
from recon_core.parser import load_parsed_project
from recon_core.profiles import load_selected_profile_for_connection_names
from recon_core.profiles.connection_references import referenced_connection_names
from recon_core.project import load_project_context
from recon_core.services._compile_adapter_setup import resolve_render_sql_adapters
from recon_core.services._compile_artifacts import (
    clear_compiled_artifacts,
    compiled_artifact_runtime_error,
    discard_compiled_sql_artifacts,
    discard_compiled_yaml_artifacts,
    write_compiled_artifacts,
    write_compiled_sql_artifacts,
)
from recon_core.services._compile_diagnostics import dedupe_diagnostics
from recon_core.services._compile_render_sql import render_compiled_sql_in_memory
from recon_core.services._compile_rendering_metadata import (
    apply_compile_diagnostic_render_block_metadata,
    apply_render_failure_metadata,
)
from recon_core.services.results import ExitCategory, ServiceResult


@dataclass(frozen=True, slots=True)
class CompileService:
    """Service boundary for recon compile."""

    start_path: Path | None = None
    render_sql: bool = False
    adapter_registry: AdapterRegistry | None = None

    def execute(self) -> ServiceResult:
        context_result = load_project_context(self.start_path)
        if not context_result.succeeded:
            return ServiceResult(
                exit_category=ExitCategory.CONFIGURATION_ERROR,
                message="Project configuration failed.",
                diagnostics=context_result.diagnostics,
            )

        assert context_result.context is not None
        context = context_result.context

        try:
            clear_compiled_artifacts(context.paths.target_path)
        except OSError as exc:
            return compiled_artifact_runtime_error(
                exc,
                target_path=context.paths.target_path,
                project_root=context.project_root,
            )

        parsed_project = load_parsed_project(context)
        if parsed_project.diagnostics:
            return ServiceResult(
                exit_category=ExitCategory.VALIDATION_ERROR,
                message="Compile failed during project parsing.",
                diagnostics=parsed_project.diagnostics,
            )

        compilation = compile_project(
            project_name=context.config.name,
            project_version=context.config.version,
            contracts=parsed_project.contracts,
        )

        if compilation.diagnostics and not compilation.contracts:
            return ServiceResult(
                exit_category=ExitCategory.VALIDATION_ERROR,
                message=(
                    "Compile failed with "
                    f"{_pluralize(len(compilation.diagnostics), 'diagnostic')}. "
                    "Wrote no compiled artifacts."
                ),
                diagnostics=compilation.diagnostics,
            )

        if self.render_sql:
            if not compilation.succeeded:
                compiled_contracts = apply_compile_diagnostic_render_block_metadata(
                    compilation.contracts
                )
                try:
                    write_compiled_artifacts(compiled_contracts, context.paths.target_path)
                except (OSError, ValueError) as exc:
                    discard_compiled_yaml_artifacts(context.paths.target_path)
                    return compiled_artifact_runtime_error(
                        exc,
                        target_path=context.paths.target_path,
                        project_root=context.project_root,
                    )
                return ServiceResult(
                    exit_category=ExitCategory.VALIDATION_ERROR,
                    message=(
                        f"Compile completed with "
                        f"{_pluralize(len(compilation.diagnostics), 'diagnostic')}. "
                        "Wrote compiled artifacts for "
                        f"{_pluralize(len(compilation.contracts), 'contract')}."
                    ),
                    diagnostics=compilation.diagnostics,
                )

            profile_result = load_selected_profile_for_connection_names(
                context,
                referenced_connection_names=referenced_connection_names(parsed_project.contracts),
            )
            if not profile_result.succeeded:
                return ServiceResult(
                    exit_category=ExitCategory.CONFIGURATION_ERROR,
                    message="SQL rendering profile configuration failed.",
                    diagnostics=profile_result.diagnostics,
                )

            assert profile_result.profile is not None
            adapter_resolution = resolve_render_sql_adapters(
                profile_result.profile,
                registry=self.adapter_registry,
            )
            if adapter_resolution.diagnostics:
                render_result = render_compiled_sql_in_memory(
                    compilation.contracts,
                    adapters_by_connection=adapter_resolution.adapters_by_connection,
                    adapter_diagnostics_by_connection=(
                        adapter_resolution.diagnostics_by_connection
                    ),
                )
                compiled_contracts = apply_render_failure_metadata(
                    compilation.contracts,
                    render_results_by_check_id=render_result.results_by_check_id,
                )
                try:
                    write_compiled_artifacts(compiled_contracts, context.paths.target_path)
                except (OSError, ValueError) as exc:
                    discard_compiled_yaml_artifacts(context.paths.target_path)
                    return compiled_artifact_runtime_error(
                        exc,
                        target_path=context.paths.target_path,
                        project_root=context.project_root,
                    )
                return ServiceResult(
                    exit_category=ExitCategory.CONFIGURATION_ERROR,
                    message="SQL rendering adapter configuration failed.",
                    diagnostics=dedupe_diagnostics(
                        adapter_resolution.diagnostics + render_result.diagnostics
                    ),
                )

            render_result = render_compiled_sql_in_memory(
                compilation.contracts,
                adapters_by_connection=adapter_resolution.adapters_by_connection,
            )
            if render_result.diagnostics:
                compiled_contracts = apply_render_failure_metadata(
                    compilation.contracts,
                    render_results_by_check_id=render_result.results_by_check_id,
                )
                try:
                    write_compiled_artifacts(compiled_contracts, context.paths.target_path)
                except (OSError, ValueError) as exc:
                    discard_compiled_yaml_artifacts(context.paths.target_path)
                    return compiled_artifact_runtime_error(
                        exc,
                        target_path=context.paths.target_path,
                        project_root=context.project_root,
                    )
                return ServiceResult(
                    exit_category=ExitCategory.CONFIGURATION_ERROR,
                    message="SQL rendering failed.",
                    diagnostics=compilation.diagnostics + render_result.diagnostics,
                )

            try:
                compiled_contracts = write_compiled_sql_artifacts(
                    compilation.contracts,
                    render_results_by_check_id=render_result.results_by_check_id,
                    target_path=context.paths.target_path,
                )
                write_compiled_artifacts(compiled_contracts, context.paths.target_path)
            except (OSError, ValueError) as exc:
                discard_compiled_sql_artifacts(context.paths.target_path / COMPILED_SQL_DIR_NAME)
                discard_compiled_yaml_artifacts(context.paths.target_path)
                return compiled_artifact_runtime_error(
                    exc,
                    target_path=context.paths.target_path,
                    project_root=context.project_root,
                )

            if compilation.succeeded:
                return ServiceResult.success(
                    message=(
                        f"Compiled {_pluralize(len(compilation.contracts), 'contract')}. "
                        f"Wrote artifacts to "
                        f"{context.paths.target_path / COMPILED_CONTRACTS_DIR_NAME}, "
                        f"{context.paths.target_path / COMPILED_CHECKS_DIR_NAME}, and "
                        f"{context.paths.target_path / COMPILED_SQL_DIR_NAME}."
                    )
                )

            return ServiceResult(
                exit_category=ExitCategory.VALIDATION_ERROR,
                message=(
                    f"Compile completed with "
                    f"{_pluralize(len(compilation.diagnostics), 'diagnostic')}. "
                    "Wrote compiled artifacts for "
                    f"{_pluralize(len(compilation.contracts), 'contract')}."
                ),
                diagnostics=compilation.diagnostics,
            )

        try:
            write_compiled_artifacts(compilation.contracts, context.paths.target_path)
        except (OSError, ValueError) as exc:
            discard_compiled_yaml_artifacts(context.paths.target_path)
            return compiled_artifact_runtime_error(
                exc,
                target_path=context.paths.target_path,
                project_root=context.project_root,
            )

        if compilation.succeeded:
            return ServiceResult.success(
                message=(
                    f"Compiled {_pluralize(len(compilation.contracts), 'contract')}. "
                    f"Wrote artifacts to {context.paths.target_path / COMPILED_CONTRACTS_DIR_NAME} "
                    f"and {context.paths.target_path / COMPILED_CHECKS_DIR_NAME}."
                )
            )

        return ServiceResult(
            exit_category=ExitCategory.VALIDATION_ERROR,
            message=(
                f"Compile completed with {_pluralize(len(compilation.diagnostics), 'diagnostic')}. "
                "Wrote compiled artifacts for "
                f"{_pluralize(len(compilation.contracts), 'contract')}."
            ),
            diagnostics=compilation.diagnostics,
        )


def _pluralize(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"
