"""Compiled artifact publication helpers for compile."""

import shutil
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

from recon_core.artifacts import (
    COMPILED_CHECKS_DIR_NAME,
    COMPILED_CONTRACTS_DIR_NAME,
    COMPILED_SQL_DIR_NAME,
    CompiledCheckWriter,
    CompiledContractWriter,
    CompiledSqlWriter,
    CompiledSqlWriteRequest,
)
from recon_core.artifacts._paths import (
    ensure_real_artifact_directory,
    reject_symlinked_path_components,
)
from recon_core.compiler import ContractCompilationArtifacts
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services._compile_rendering_metadata import (
    RenderedCheckSqlResult,
    apply_rendered_sql_metadata,
)
from recon_core.services.results import ExitCategory, ServiceResult

COMPILED_ARTIFACT_WRITE_FAILED = "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"


def clear_compiled_artifacts(target_path: Path) -> None:
    """Remove stale compiled YAML and SQL outputs before compile starts."""
    _clear_compiled_artifact_directory(target_path / COMPILED_CONTRACTS_DIR_NAME)
    _clear_compiled_artifact_directory(target_path / COMPILED_CHECKS_DIR_NAME)
    _clear_compiled_sql_artifact_directory(target_path / COMPILED_SQL_DIR_NAME)


def write_compiled_artifacts(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    target_path: Path,
) -> None:
    """Write compiled contract and compiled check YAML artifacts."""
    contract_writer = CompiledContractWriter()
    check_writer = CompiledCheckWriter()
    _ensure_compiled_artifact_directory(target_path / COMPILED_CONTRACTS_DIR_NAME)
    _ensure_compiled_artifact_directory(target_path / COMPILED_CHECKS_DIR_NAME)

    for compiled_contract in compiled_contracts:
        contract_writer.write(compiled_contract.contract_artifact, target_path, overwrite=True)
        check_writer.write(compiled_contract.checks_artifact, target_path, overwrite=True)


def write_compiled_sql_artifacts(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    *,
    render_results_by_check_id: Mapping[str, RenderedCheckSqlResult],
    target_path: Path,
) -> tuple[ContractCompilationArtifacts, ...]:
    """Write compiled SQL files and return contracts with rendered metadata."""
    sql_writer = CompiledSqlWriter()
    write_requests: list[CompiledSqlWriteRequest] = []

    for compiled_contract in compiled_contracts:
        for check in compiled_contract.checks_artifact.checks:
            render_result = render_results_by_check_id.get(check.id)
            if render_result is None:
                continue
            write_requests.append(
                CompiledSqlWriteRequest(
                    contract_name=compiled_contract.contract_artifact.contract.name,
                    check_id=check.id,
                    rendered_sql=render_result.sql,
                )
            )

    write_results = sql_writer.write_batch(
        requests=tuple(write_requests),
        target_path=target_path,
        overwrite=True,
    )
    sql_paths_by_check_id = {
        write_result.check_id: write_result.sql_paths for write_result in write_results
    }
    return apply_rendered_sql_metadata(
        compiled_contracts,
        render_results_by_check_id=render_results_by_check_id,
        sql_paths_by_check_id=sql_paths_by_check_id,
    )


def discard_compiled_sql_artifacts(output_dir: Path) -> None:
    """Best-effort discard of compiled SQL output after failed publication."""
    with suppress(OSError, ValueError):
        _clear_compiled_sql_artifact_directory(output_dir)


def discard_compiled_yaml_artifacts(target_path: Path) -> None:
    """Best-effort discard of compiled YAML output after failed publication."""
    for directory_name in (COMPILED_CONTRACTS_DIR_NAME, COMPILED_CHECKS_DIR_NAME):
        with suppress(OSError, ValueError):
            _clear_compiled_artifact_directory(target_path / directory_name)


def compiled_artifact_runtime_error(
    exc: OSError | ValueError,
    *,
    target_path: Path,
    project_root: Path,
) -> ServiceResult:
    """Build the existing service-level artifact write failure result."""
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


def _clear_compiled_artifact_directory(output_dir: Path) -> None:
    reject_symlinked_path_components(output_dir)

    if not output_dir.exists():
        return
    if not output_dir.is_dir():
        raise NotADirectoryError(f"Compiled artifact output path is not a directory: {output_dir}")

    for output_path in output_dir.glob("*.yml"):
        if output_path.is_file() or output_path.is_symlink():
            output_path.unlink()
    with suppress(OSError):
        output_dir.rmdir()


def _clear_compiled_sql_artifact_directory(output_dir: Path) -> None:
    reject_symlinked_path_components(output_dir)

    if not output_dir.exists():
        return
    if not output_dir.is_dir():
        raise NotADirectoryError(f"Compiled SQL output path is not a directory: {output_dir}")

    shutil.rmtree(output_dir)


def _ensure_compiled_artifact_directory(output_dir: Path) -> None:
    ensure_real_artifact_directory(output_dir)


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
