"""Compile command service."""

from dataclasses import dataclass
from pathlib import Path

from recon_core.adapters import default_adapter_registry, validate_adapter_api_compatibility
from recon_core.artifacts import (
    COMPILED_CHECKS_DIR_NAME,
    COMPILED_CONTRACTS_DIR_NAME,
    CompiledCheckWriter,
    CompiledContractWriter,
)
from recon_core.artifacts._paths import (
    ensure_real_artifact_directory,
    reject_symlinked_path_components,
)
from recon_core.compiler import ContractCompilationArtifacts, compile_project
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser import load_parsed_project
from recon_core.profiles import load_selected_profile
from recon_core.profiles.models import SelectedProfile
from recon_core.project import load_project_context
from recon_core.services.results import ExitCategory, ServiceResult

COMPILED_ARTIFACT_WRITE_FAILED = "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
RENDER_SQL_NOT_IMPLEMENTED = "RC_RUNTIME_RENDER_SQL_NOT_IMPLEMENTED"


@dataclass(frozen=True, slots=True)
class CompileService:
    """Service boundary for recon compile."""

    start_path: Path | None = None
    render_sql: bool = False

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
            _clear_compiled_artifacts(context.paths.target_path)
        except OSError as exc:
            return _compiled_artifact_runtime_error(
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
            profile_result = load_selected_profile(context, contracts=parsed_project.contracts)
            if not profile_result.succeeded:
                return ServiceResult(
                    exit_category=ExitCategory.CONFIGURATION_ERROR,
                    message="SQL rendering profile configuration failed.",
                    diagnostics=profile_result.diagnostics,
                )

            assert profile_result.profile is not None
            adapter_diagnostics = _resolve_render_sql_adapters(profile_result.profile)
            if adapter_diagnostics:
                return ServiceResult(
                    exit_category=ExitCategory.CONFIGURATION_ERROR,
                    message="SQL rendering adapter configuration failed.",
                    diagnostics=adapter_diagnostics,
                )

            return _render_sql_not_implemented()

        try:
            _write_compiled_artifacts(compilation.contracts, context.paths.target_path)
        except OSError as exc:
            return _compiled_artifact_runtime_error(
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


def _write_compiled_artifacts(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    target_path: Path,
) -> None:
    contract_writer = CompiledContractWriter()
    check_writer = CompiledCheckWriter()
    _ensure_compiled_artifact_directory(target_path / COMPILED_CONTRACTS_DIR_NAME)
    _ensure_compiled_artifact_directory(target_path / COMPILED_CHECKS_DIR_NAME)

    for compiled_contract in compiled_contracts:
        contract_writer.write(compiled_contract.contract_artifact, target_path, overwrite=True)
        check_writer.write(compiled_contract.checks_artifact, target_path, overwrite=True)


def _clear_compiled_artifacts(target_path: Path) -> None:
    _clear_compiled_artifact_directory(target_path / COMPILED_CONTRACTS_DIR_NAME)
    _clear_compiled_artifact_directory(target_path / COMPILED_CHECKS_DIR_NAME)


def _clear_compiled_artifact_directory(output_dir: Path) -> None:
    reject_symlinked_path_components(output_dir)

    if not output_dir.is_dir():
        return

    for output_path in output_dir.glob("*.yml"):
        if output_path.is_file() or output_path.is_symlink():
            output_path.unlink()


def _ensure_compiled_artifact_directory(output_dir: Path) -> None:
    ensure_real_artifact_directory(output_dir)


def _compiled_artifact_runtime_error(
    exc: OSError,
    *,
    target_path: Path,
    project_root: Path,
) -> ServiceResult:
    display_path = _display_path(target_path, project_root)
    return ServiceResult(
        exit_category=ExitCategory.RUNTIME_ERROR,
        message="Compile completed but artifacts could not be written.",
        diagnostics=(
            Diagnostic(
                code=COMPILED_ARTIFACT_WRITE_FAILED,
                severity=DiagnosticSeverity.ERROR,
                message=f"Unable to write compiled artifacts under {display_path}: {exc}",
                resource_type="compiled_artifacts",
                path=display_path,
                hint=(
                    "Check that target-path is a writable directory "
                    "or update target-path in recon_project.yml."
                ),
            ),
        ),
    )


def _resolve_render_sql_adapters(profile: SelectedProfile) -> tuple[Diagnostic, ...]:
    registry = default_adapter_registry()
    diagnostics: list[Diagnostic] = []

    for connection in profile.connections.values():
        resolution = registry.resolve(connection)
        diagnostics.extend(resolution.diagnostics)
        if resolution.adapter is None:
            continue
        diagnostics.extend(validate_adapter_api_compatibility(resolution.adapter))

    return tuple(diagnostics)


def _render_sql_not_implemented() -> ServiceResult:
    return ServiceResult(
        exit_category=ExitCategory.RUNTIME_ERROR,
        message="SQL rendering is not implemented yet.",
        diagnostics=(
            Diagnostic(
                code=RENDER_SQL_NOT_IMPLEMENTED,
                severity=DiagnosticSeverity.ERROR,
                message=(
                    "`recon compile --render-sql` loaded project profiles, "
                    "but adapter-aware SQL rendering is not implemented yet."
                ),
                resource_type="compiled_sql",
                hint="Continue Milestone 6 Phase 2 before using rendered SQL output.",
            ),
        ),
    )


def _pluralize(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
