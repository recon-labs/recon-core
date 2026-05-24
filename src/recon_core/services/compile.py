"""Compile command service."""

from dataclasses import dataclass, replace
from pathlib import Path

from recon_core.artifacts import (
    COMPILED_CHECKS_DIR_NAME,
    COMPILED_CONTRACTS_DIR_NAME,
    CompiledCheckWriter,
    CompiledContractWriter,
)
from recon_core.compiler import ContractCompilationArtifacts, compile_project
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser import (
    AuthoredContract,
    ResourceFile,
    discover_contract_files,
    load_yaml_file,
    parse_contract_resource,
)
from recon_core.project import load_project_context
from recon_core.services.results import ExitCategory, ServiceResult

COMPILED_ARTIFACT_WRITE_FAILED = "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"


@dataclass(frozen=True, slots=True)
class CompileService:
    """Service boundary for recon compile."""

    start_path: Path | None = None

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

        discovery_result = discover_contract_files(
            context.project_root,
            context.paths.contract_paths,
        )
        diagnostics = list(discovery_result.diagnostics)
        contracts = _parse_contract_files(discovery_result.files, diagnostics)
        if diagnostics:
            return ServiceResult(
                exit_category=ExitCategory.VALIDATION_ERROR,
                message="Compile failed during project parsing.",
                diagnostics=tuple(diagnostics),
            )

        compilation = compile_project(
            project_name=context.config.name,
            project_version=context.config.version,
            contracts=tuple(contracts),
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

        try:
            _write_compiled_artifacts(compilation.contracts, context.paths.target_path)
        except OSError as exc:
            target_path = _display_path(context.paths.target_path, context.project_root)
            return ServiceResult(
                exit_category=ExitCategory.RUNTIME_ERROR,
                message="Compile completed but artifacts could not be written.",
                diagnostics=(
                    Diagnostic(
                        code=COMPILED_ARTIFACT_WRITE_FAILED,
                        severity=DiagnosticSeverity.ERROR,
                        message=f"Unable to write compiled artifacts under {target_path}: {exc}",
                        resource_type="compiled_artifacts",
                        path=target_path,
                        hint=(
                            "Check that target-path is a writable directory "
                            "or update target-path in recon_project.yml."
                        ),
                    ),
                ),
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


def _parse_contract_files(
    resource_files: tuple[ResourceFile, ...],
    diagnostics: list[Diagnostic],
) -> list[AuthoredContract]:
    contracts: list[AuthoredContract] = []

    for resource_file in resource_files:
        yaml_result = load_yaml_file(resource_file.path)
        diagnostics.extend(_resource_relative_diagnostics(yaml_result.diagnostics, resource_file))
        if not yaml_result.succeeded:
            continue

        contract_result = parse_contract_resource(resource_file, yaml_result.data)
        diagnostics.extend(contract_result.diagnostics)
        contracts.extend(contract_result.contracts)

    return contracts


def _write_compiled_artifacts(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    target_path: Path,
) -> None:
    contract_writer = CompiledContractWriter()
    check_writer = CompiledCheckWriter()
    _prepare_compiled_artifact_directory(target_path / COMPILED_CONTRACTS_DIR_NAME)
    _prepare_compiled_artifact_directory(target_path / COMPILED_CHECKS_DIR_NAME)

    for compiled_contract in compiled_contracts:
        contract_writer.write(compiled_contract.contract_artifact, target_path, overwrite=True)
        check_writer.write(compiled_contract.checks_artifact, target_path, overwrite=True)


def _prepare_compiled_artifact_directory(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for output_path in output_dir.glob("*.yml"):
        if output_path.is_file() or output_path.is_symlink():
            output_path.unlink()


def _resource_relative_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    resource_file: ResourceFile,
) -> tuple[Diagnostic, ...]:
    return tuple(
        replace(diagnostic, path=resource_file.relative_path) for diagnostic in diagnostics
    )


def _pluralize(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
