"""Compile command service."""

import shutil
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from recon_core.adapters import (
    ADAPTER_CAPABILITY_UNSUPPORTED,
    ADAPTER_OPERATION_RENDER_FAILED,
    ADAPTER_RENDERED_SQL_EMPTY,
    AdapterRegistry,
    BaseAdapter,
    RenderedCheckSql,
    default_adapter_registry,
    render_check_sql,
    validate_adapter_api_compatibility,
)
from recon_core.adapters.duckdb import DuckDbSqlRenderer
from recon_core.adapters.registry import resolve_adapter_type
from recon_core.artifacts import (
    COMPILED_CHECKS_DIR_NAME,
    COMPILED_CONTRACTS_DIR_NAME,
    COMPILED_SQL_DIR_NAME,
    CompiledCheckWriter,
    CompiledContractWriter,
    CompiledSqlWriter,
)
from recon_core.artifacts._paths import (
    ensure_real_artifact_directory,
    reject_symlinked_path_components,
)
from recon_core.compiler import (
    CompiledCheck,
    ContractCompilationArtifacts,
    Rendering,
    RenderingStatus,
    compile_project,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser import load_parsed_project
from recon_core.profiles import load_selected_profile
from recon_core.profiles.models import ConnectionConfig, SelectedProfile
from recon_core.project import load_project_context
from recon_core.services.results import ExitCategory, ServiceResult

COMPILED_ARTIFACT_WRITE_FAILED = "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
MIXED_ADAPTER_TYPES_UNSUPPORTED = "RC_ADAPTER_MIXED_ADAPTER_TYPES_UNSUPPORTED"
ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED = "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"
ADAPTER_RENDERING_OUTPUT_SUPPRESSED = "RC_ADAPTER_RENDERING_OUTPUT_SUPPRESSED"
ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS = (
    "RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS"
)


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
            if not compilation.succeeded:
                compiled_contracts = _apply_compile_diagnostic_render_block_metadata(
                    compilation.contracts
                )
                try:
                    _write_compiled_artifacts(compiled_contracts, context.paths.target_path)
                except (OSError, ValueError) as exc:
                    _discard_compiled_yaml_artifacts(context.paths.target_path)
                    return _compiled_artifact_runtime_error(
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

            profile_result = load_selected_profile(context, contracts=parsed_project.contracts)
            if not profile_result.succeeded:
                return ServiceResult(
                    exit_category=ExitCategory.CONFIGURATION_ERROR,
                    message="SQL rendering profile configuration failed.",
                    diagnostics=profile_result.diagnostics,
                )

            assert profile_result.profile is not None
            adapter_resolution = _resolve_render_sql_adapters(
                profile_result.profile,
                registry=self.adapter_registry,
            )
            if adapter_resolution.diagnostics:
                render_result = _render_compiled_sql_in_memory(
                    compilation.contracts,
                    adapters_by_connection=adapter_resolution.adapters_by_connection,
                    adapter_diagnostics_by_connection=(
                        adapter_resolution.diagnostics_by_connection
                    ),
                )
                compiled_contracts = _apply_render_failure_metadata(
                    compilation.contracts,
                    render_results_by_check_id=render_result.results_by_check_id,
                )
                try:
                    _write_compiled_artifacts(compiled_contracts, context.paths.target_path)
                except (OSError, ValueError) as exc:
                    _discard_compiled_yaml_artifacts(context.paths.target_path)
                    return _compiled_artifact_runtime_error(
                        exc,
                        target_path=context.paths.target_path,
                        project_root=context.project_root,
                    )
                return ServiceResult(
                    exit_category=ExitCategory.CONFIGURATION_ERROR,
                    message="SQL rendering adapter configuration failed.",
                    diagnostics=adapter_resolution.diagnostics,
                )

            render_result = _render_compiled_sql_in_memory(
                compilation.contracts,
                adapters_by_connection=adapter_resolution.adapters_by_connection,
            )
            if render_result.diagnostics:
                compiled_contracts = _apply_render_failure_metadata(
                    compilation.contracts,
                    render_results_by_check_id=render_result.results_by_check_id,
                )
                try:
                    _write_compiled_artifacts(compiled_contracts, context.paths.target_path)
                except (OSError, ValueError) as exc:
                    _discard_compiled_yaml_artifacts(context.paths.target_path)
                    return _compiled_artifact_runtime_error(
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
                compiled_contracts = _write_compiled_sql_artifacts(
                    compilation.contracts,
                    render_results_by_check_id=render_result.results_by_check_id,
                    target_path=context.paths.target_path,
                )
                _write_compiled_artifacts(compiled_contracts, context.paths.target_path)
            except (OSError, ValueError) as exc:
                _discard_compiled_sql_artifacts(context.paths.target_path / COMPILED_SQL_DIR_NAME)
                _discard_compiled_yaml_artifacts(context.paths.target_path)
                return _compiled_artifact_runtime_error(
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
            _write_compiled_artifacts(compilation.contracts, context.paths.target_path)
        except (OSError, ValueError) as exc:
            _discard_compiled_yaml_artifacts(context.paths.target_path)
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


def _write_compiled_sql_artifacts(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    *,
    render_results_by_check_id: dict[str, RenderedCheckSql],
    target_path: Path,
) -> tuple[ContractCompilationArtifacts, ...]:
    sql_writer = CompiledSqlWriter()
    rendered_contracts: list[ContractCompilationArtifacts] = []

    for compiled_contract in compiled_contracts:
        rendered_checks = []
        for check in compiled_contract.checks_artifact.checks:
            render_result = render_results_by_check_id.get(check.id)
            if render_result is None:
                rendered_checks.append(check)
                continue
            sql_paths = sql_writer.write(
                contract_name=compiled_contract.contract_artifact.contract.name,
                check_id=check.id,
                rendered_sql=render_result.sql,
                target_path=target_path,
                overwrite=True,
            )
            rendered_checks.append(
                replace(
                    check,
                    rendering=Rendering(
                        status=RenderingStatus.RENDERED,
                        sql_paths=sql_paths,
                        adapter_type=render_result.adapter_type,
                    ),
                )
            )

        rendered_contracts.append(
            replace(
                compiled_contract,
                checks_artifact=replace(
                    compiled_contract.checks_artifact,
                    checks=tuple(rendered_checks),
                ),
            )
        )

    return tuple(rendered_contracts)


def _apply_render_failure_metadata(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    *,
    render_results_by_check_id: dict[str, RenderedCheckSql],
) -> tuple[ContractCompilationArtifacts, ...]:
    rendered_contracts: list[ContractCompilationArtifacts] = []

    for compiled_contract in compiled_contracts:
        rendered_checks = []
        for check in compiled_contract.checks_artifact.checks:
            render_result = render_results_by_check_id.get(check.id)
            if render_result is None:
                rendered_checks.append(
                    _with_blocked_rendering(
                        check,
                        diagnostics=(_rendering_output_suppressed_diagnostic(check),),
                    )
                )
                continue
            if not render_result.diagnostics:
                rendered_checks.append(
                    _with_blocked_rendering(
                        check,
                        diagnostics=(_rendering_output_suppressed_diagnostic(check),),
                        adapter_type=render_result.adapter_type,
                    )
                )
                continue
            rendered_checks.append(
                replace(
                    check,
                    rendering=Rendering(
                        status=_render_failure_status(render_result.diagnostics),
                        sql_paths=(),
                        adapter_type=render_result.adapter_type,
                    ),
                    diagnostics=check.diagnostics + render_result.diagnostics,
                )
            )

        rendered_contracts.append(
            replace(
                compiled_contract,
                checks_artifact=replace(
                    compiled_contract.checks_artifact,
                    checks=tuple(rendered_checks),
                ),
            )
        )

    return tuple(rendered_contracts)


def _with_blocked_rendering(
    check: CompiledCheck,
    *,
    diagnostics: tuple[Diagnostic, ...] = (),
    adapter_type: str | None = None,
) -> CompiledCheck:
    return replace(
        check,
        rendering=Rendering(
            status=RenderingStatus.BLOCKED,
            sql_paths=(),
            adapter_type=adapter_type,
        ),
        diagnostics=check.diagnostics + diagnostics,
    )


def _rendering_output_suppressed_diagnostic(check: CompiledCheck) -> Diagnostic:
    return Diagnostic(
        code=ADAPTER_RENDERING_OUTPUT_SUPPRESSED,
        severity=DiagnosticSeverity.ERROR,
        message=(
            f"SQL output for check `{check.id}` was suppressed because another check in "
            "the same render-sql invocation produced a rendering diagnostic."
        ),
        resource_type="compiled_check",
        resource_name=check.id,
        hint="Fix the rendering diagnostics and rerun `recon compile --render-sql`.",
    )


def _apply_compile_diagnostic_render_block_metadata(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
) -> tuple[ContractCompilationArtifacts, ...]:
    rendered_contracts: list[ContractCompilationArtifacts] = []

    for compiled_contract in compiled_contracts:
        rendered_checks = tuple(
            _with_blocked_rendering(
                check,
                diagnostics=(_rendering_blocked_by_compile_diagnostic(check),),
            )
            for check in compiled_contract.checks_artifact.checks
        )
        rendered_contracts.append(
            replace(
                compiled_contract,
                checks_artifact=replace(
                    compiled_contract.checks_artifact,
                    checks=rendered_checks,
                ),
            )
        )

    return tuple(rendered_contracts)


def _rendering_blocked_by_compile_diagnostic(check: CompiledCheck) -> Diagnostic:
    return Diagnostic(
        code=ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS,
        severity=DiagnosticSeverity.ERROR,
        message=(
            f"SQL rendering for check `{check.id}` was blocked because compile "
            "validation produced diagnostics before adapter rendering could start."
        ),
        resource_type="compiled_check",
        resource_name=check.id,
        hint="Fix the compile diagnostics and rerun `recon compile --render-sql`.",
    )


def _render_failure_status(diagnostics: tuple[Diagnostic, ...]) -> RenderingStatus:
    if any(
        diagnostic.code in {ADAPTER_OPERATION_RENDER_FAILED, ADAPTER_RENDERED_SQL_EMPTY}
        for diagnostic in diagnostics
    ):
        return RenderingStatus.FAILED
    return RenderingStatus.BLOCKED


def _dedupe_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> tuple[Diagnostic, ...]:
    unique: list[Diagnostic] = []
    seen: set[tuple[object, ...]] = set()
    for diagnostic in diagnostics:
        key = (
            diagnostic.code,
            diagnostic.severity,
            diagnostic.message,
            diagnostic.resource_type,
            diagnostic.resource_name,
            diagnostic.path,
            diagnostic.line,
            diagnostic.column,
            diagnostic.hint,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(diagnostic)
    return tuple(unique)


def _dedupe_adapter_setup_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
) -> tuple[Diagnostic, ...]:
    unique: list[Diagnostic] = []
    seen: set[tuple[object, ...]] = set()
    for diagnostic in diagnostics:
        key = (
            diagnostic.code,
            diagnostic.severity,
            diagnostic.message,
            diagnostic.resource_type,
            diagnostic.resource_name,
            diagnostic.path,
            diagnostic.line,
            diagnostic.column,
            diagnostic.hint,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(diagnostic)
    return tuple(unique)


def _clear_compiled_artifacts(target_path: Path) -> None:
    _clear_compiled_artifact_directory(target_path / COMPILED_CONTRACTS_DIR_NAME)
    _clear_compiled_artifact_directory(target_path / COMPILED_CHECKS_DIR_NAME)
    _clear_compiled_sql_artifact_directory(target_path / COMPILED_SQL_DIR_NAME)


def _clear_compiled_artifact_directory(output_dir: Path) -> None:
    reject_symlinked_path_components(output_dir)

    if not output_dir.exists():
        return
    if not output_dir.is_dir():
        raise NotADirectoryError(f"Compiled artifact output path is not a directory: {output_dir}")

    for output_path in output_dir.glob("*.yml"):
        if output_path.is_file() or output_path.is_symlink():
            output_path.unlink()


def _clear_compiled_sql_artifact_directory(output_dir: Path) -> None:
    reject_symlinked_path_components(output_dir)

    if not output_dir.exists():
        return
    if not output_dir.is_dir():
        raise NotADirectoryError(f"Compiled SQL output path is not a directory: {output_dir}")

    shutil.rmtree(output_dir)


def _ensure_compiled_artifact_directory(output_dir: Path) -> None:
    ensure_real_artifact_directory(output_dir)


def _compiled_artifact_runtime_error(
    exc: OSError | ValueError,
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


@dataclass(frozen=True, slots=True)
class _RenderSqlAdapterResolution:
    adapters_by_connection: dict[str, BaseAdapter]
    diagnostics_by_connection: dict[str, tuple[Diagnostic, ...]]
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class _RenderSqlCompilationResult:
    results_by_check_id: dict[str, RenderedCheckSql]
    diagnostics: tuple[Diagnostic, ...] = ()


def _resolve_render_sql_adapters(
    profile: SelectedProfile,
    *,
    registry: AdapterRegistry | None,
) -> _RenderSqlAdapterResolution:
    resolved_registry = default_adapter_registry() if registry is None else registry
    diagnostics: list[Diagnostic] = []
    adapters_by_connection: dict[str, BaseAdapter] = {}
    diagnostics_by_connection: dict[str, tuple[Diagnostic, ...]] = {}

    for connection in profile.connections.values():
        config_tokens = _connection_config_tokens(connection.config, adapter_type=connection.type)
        numeric_field_tokens = _connection_config_numeric_field_tokens(
            connection.config,
            adapter_type=connection.type,
        )
        connection_diagnostics: list[Diagnostic] = []
        resolution = resolved_registry.resolve(connection)
        resolution_diagnostics = _connection_scoped_adapter_setup_diagnostics(
            _sanitize_profile_backed_adapter_diagnostics(
                resolution.diagnostics,
                connection=connection,
                config_tokens=config_tokens,
                numeric_field_tokens=numeric_field_tokens,
            ),
            connection=connection,
        )
        connection_diagnostics.extend(resolution_diagnostics)
        if resolution_diagnostics or resolution.adapter is None:
            diagnostics.extend(connection_diagnostics)
            if connection_diagnostics:
                diagnostics_by_connection[connection.name] = _dedupe_diagnostics(
                    tuple(connection_diagnostics)
                )
            continue
        metadata_diagnostics = _connection_scoped_adapter_setup_diagnostics(
            _sanitize_profile_backed_adapter_diagnostics(
                resolve_adapter_type(resolution.adapter).diagnostics,
                connection=connection,
                config_tokens=config_tokens,
                numeric_field_tokens=numeric_field_tokens,
            ),
            connection=connection,
        )
        connection_diagnostics.extend(metadata_diagnostics)
        if metadata_diagnostics:
            diagnostics.extend(connection_diagnostics)
            diagnostics_by_connection[connection.name] = _dedupe_diagnostics(
                tuple(connection_diagnostics)
            )
            continue
        api_diagnostics = _connection_scoped_adapter_setup_diagnostics(
            _sanitize_profile_backed_adapter_diagnostics(
                validate_adapter_api_compatibility(resolution.adapter),
                connection=connection,
                config_tokens=config_tokens,
                numeric_field_tokens=numeric_field_tokens,
            ),
            connection=connection,
        )
        connection_diagnostics.extend(api_diagnostics)
        diagnostics.extend(connection_diagnostics)
        if api_diagnostics:
            diagnostics_by_connection[connection.name] = _dedupe_diagnostics(
                tuple(connection_diagnostics)
            )
            continue
        adapters_by_connection[connection.name] = resolution.adapter

    return _RenderSqlAdapterResolution(
        adapters_by_connection=adapters_by_connection,
        diagnostics_by_connection=diagnostics_by_connection,
        diagnostics=_dedupe_adapter_setup_diagnostics(tuple(diagnostics)),
    )


def _sanitize_profile_backed_adapter_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    *,
    connection: ConnectionConfig,
    config_tokens: frozenset[str],
    numeric_field_tokens: frozenset[int],
) -> tuple[Diagnostic, ...]:
    return tuple(
        _sanitize_profile_backed_adapter_diagnostic(
            diagnostic,
            connection=connection,
            config_tokens=config_tokens,
            numeric_field_tokens=numeric_field_tokens,
        )
        for diagnostic in diagnostics
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
    return replace(diagnostic, message=f"Connection `{connection.name}`: {diagnostic.message}")


def _sanitize_profile_backed_render_result(
    render_result: RenderedCheckSql,
    *,
    connection: ConnectionConfig,
    config_tokens: frozenset[str],
    numeric_field_tokens: frozenset[int],
) -> RenderedCheckSql:
    return replace(
        render_result,
        diagnostics=_sanitize_profile_backed_adapter_diagnostics(
            render_result.diagnostics,
            connection=connection,
            config_tokens=config_tokens,
            numeric_field_tokens=numeric_field_tokens,
        ),
        adapter_type=_sanitize_profile_backed_adapter_type(
            render_result.adapter_type,
            connection=connection,
            config_tokens=config_tokens,
            numeric_field_tokens=numeric_field_tokens,
        ),
    )


def _sanitize_profile_backed_adapter_type(
    adapter_type: object | None,
    *,
    connection: ConnectionConfig,
    config_tokens: frozenset[str],
    numeric_field_tokens: frozenset[int],
) -> str | None:
    if not isinstance(adapter_type, str) or adapter_type == "":
        return None
    if not _text_mentions_config_token(
        adapter_type,
        config_tokens,
    ) and not _text_mentions_numeric_config_token(adapter_type, numeric_field_tokens):
        return adapter_type
    return connection.type


def _sanitize_profile_backed_adapter_diagnostic(
    diagnostic: Diagnostic,
    *,
    connection: ConnectionConfig,
    config_tokens: frozenset[str],
    numeric_field_tokens: frozenset[int],
) -> Diagnostic:
    if not _diagnostic_mentions_config_token(
        diagnostic,
        config_tokens,
        numeric_field_tokens,
    ):
        return diagnostic

    return Diagnostic(
        code=diagnostic.code,
        severity=diagnostic.severity,
        message=(
            f"Adapter `{connection.type}` reported a diagnostic for "
            f"connection `{connection.name}`; adapter diagnostic text was suppressed "
            "because profile diagnostics must not expose rendered connection values."
        ),
        resource_type="adapter",
        resource_name=connection.type,
        hint=(
            "Fix the adapter configuration or inspect the adapter locally without exposing secrets."
        ),
    )


def _discard_compiled_sql_artifacts(output_dir: Path) -> None:
    with suppress(OSError, ValueError):
        _clear_compiled_sql_artifact_directory(output_dir)


def _discard_compiled_yaml_artifacts(target_path: Path) -> None:
    for directory_name in (COMPILED_CONTRACTS_DIR_NAME, COMPILED_CHECKS_DIR_NAME):
        with suppress(OSError, ValueError):
            _clear_compiled_artifact_directory(target_path / directory_name)


def _connection_config_tokens(
    value: Mapping[str, Any],
    *,
    adapter_type: str,
) -> frozenset[str]:
    tokens: set[str] = set()
    _collect_connection_config_tokens(value, adapter_type=adapter_type, tokens=tokens)
    return frozenset(tokens)


def _connection_config_numeric_field_tokens(
    value: Mapping[str, Any],
    *,
    adapter_type: str,
) -> frozenset[int]:
    tokens: set[int] = set()
    _collect_connection_config_numeric_field_tokens(
        value,
        adapter_type=adapter_type,
        tokens=tokens,
    )
    return frozenset(tokens)


def _collect_connection_config_tokens(
    value: object,
    *,
    adapter_type: str,
    tokens: set[str],
    current_key: str | None = None,
) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            key_text = key if isinstance(key, str) else None
            if key_text is not None and key_text.casefold() != "type":
                tokens.add(key_text)
            _collect_connection_config_tokens(
                nested_value,
                adapter_type=adapter_type,
                tokens=tokens,
                current_key=key_text,
            )
        return

    if isinstance(value, str):
        if value != "" and value.casefold() != adapter_type.casefold():
            tokens.add(value)
        return

    if isinstance(value, list | tuple):
        for item in value:
            _collect_connection_config_tokens(
                item,
                adapter_type=adapter_type,
                tokens=tokens,
                current_key=current_key,
            )
        return

    if value is None or isinstance(value, bool):
        return

    token = str(value)
    if token != "" and (
        len(token) >= 3 or (current_key is not None and _is_secret_like_config_key(current_key))
    ):
        tokens.add(token)


def _collect_connection_config_numeric_field_tokens(
    value: object,
    *,
    adapter_type: str,
    tokens: set[int],
) -> None:
    if isinstance(value, Mapping):
        for nested_value in value.values():
            _collect_connection_config_numeric_field_tokens(
                nested_value,
                adapter_type=adapter_type,
                tokens=tokens,
            )
        return

    if isinstance(value, list | tuple):
        for item in value:
            _collect_connection_config_numeric_field_tokens(
                item,
                adapter_type=adapter_type,
                tokens=tokens,
            )
        return

    if isinstance(value, str) and value.casefold() == adapter_type.casefold():
        return

    numeric_value = _integer_like_value(value)
    if numeric_value is not None:
        tokens.add(numeric_value)


def _is_secret_like_config_key(key: str) -> bool:
    normalized_key = key.casefold()
    return any(
        secret_word in normalized_key
        for secret_word in ("password", "passwd", "pwd", "secret", "token", "credential", "key")
    )


def _diagnostic_mentions_config_token(
    diagnostic: Diagnostic,
    config_tokens: frozenset[str],
    numeric_field_tokens: frozenset[int],
) -> bool:
    if _diagnostic_numeric_fields_match_config_token(diagnostic, numeric_field_tokens):
        return True

    if not config_tokens:
        return False

    diagnostic_text = "\n".join(
        str(value)
        for value in (
            diagnostic.message,
            diagnostic.hint,
            diagnostic.path,
            diagnostic.resource_type,
            diagnostic.resource_name,
            diagnostic.line,
            diagnostic.column,
        )
        if value is not None
    )
    return _text_mentions_config_token(
        diagnostic_text,
        config_tokens,
    ) or _text_mentions_numeric_config_token(diagnostic_text, numeric_field_tokens)


def _diagnostic_numeric_fields_match_config_token(
    diagnostic: Diagnostic,
    numeric_field_tokens: frozenset[int],
) -> bool:
    if not numeric_field_tokens:
        return False

    return any(
        numeric_value in numeric_field_tokens
        for numeric_value in (
            _integer_like_value(diagnostic.line),
            _integer_like_value(diagnostic.column),
        )
        if numeric_value is not None
    )


def _text_mentions_config_token(text: str, config_tokens: frozenset[str]) -> bool:
    normalized_text = text.casefold()
    return any(token.casefold() in normalized_text for token in config_tokens)


def _text_mentions_numeric_config_token(
    text: str,
    numeric_field_tokens: frozenset[int],
) -> bool:
    return any(
        _text_mentions_numeric_token(text, str(numeric_token))
        for numeric_token in numeric_field_tokens
    )


def _text_mentions_numeric_token(text: str, token: str) -> bool:
    start = 0
    while True:
        index = text.find(token, start)
        if index == -1:
            return False
        end = index + len(token)
        if _numeric_token_has_text_boundaries(text, index, end):
            return True
        start = index + 1


def _numeric_token_has_text_boundaries(text: str, start: int, end: int) -> bool:
    previous_char = text[start - 1] if start > 0 else ""
    next_char = text[end] if end < len(text) else ""
    next_next_char = text[end + 1] if end + 1 < len(text) else ""

    if previous_char.isalnum() or previous_char in {"_", "+", "-"}:
        return False
    if next_char.isalnum() or next_char == "_":
        return False
    return not (next_char == "." and next_next_char.isdecimal())


def _integer_like_value(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        digits = stripped[1:] if stripped[:1] in {"+", "-"} else stripped
        if digits.isdecimal():
            return int(stripped)
    return None


def _render_compiled_sql_in_memory(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    *,
    adapters_by_connection: dict[str, BaseAdapter],
    adapter_diagnostics_by_connection: Mapping[str, tuple[Diagnostic, ...]] | None = None,
) -> _RenderSqlCompilationResult:
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
            _set_contract_render_block(
                results_by_check_id,
                compiled_contract=compiled_contract,
                diagnostics=adapter_diagnostics,
            )
            continue

        source_adapter = adapters_by_connection.get(source_connection)
        target_adapter = adapters_by_connection.get(target_connection)
        if source_adapter is None or target_adapter is None:
            continue
        source_config_tokens = _connection_config_tokens(
            source_adapter.connection.config,
            adapter_type=source_adapter.connection.type,
        )
        source_numeric_field_tokens = _connection_config_numeric_field_tokens(
            source_adapter.connection.config,
            adapter_type=source_adapter.connection.type,
        )
        target_config_tokens = _connection_config_tokens(
            target_adapter.connection.config,
            adapter_type=target_adapter.connection.type,
        )
        target_numeric_field_tokens = _connection_config_numeric_field_tokens(
            target_adapter.connection.config,
            adapter_type=target_adapter.connection.type,
        )
        source_adapter_type_resolution = resolve_adapter_type(source_adapter)
        target_adapter_type_resolution = resolve_adapter_type(target_adapter)
        source_metadata_diagnostics = _sanitize_profile_backed_adapter_diagnostics(
            source_adapter_type_resolution.diagnostics,
            connection=source_adapter.connection,
            config_tokens=source_config_tokens,
            numeric_field_tokens=source_numeric_field_tokens,
        )
        target_metadata_diagnostics = _sanitize_profile_backed_adapter_diagnostics(
            target_adapter_type_resolution.diagnostics,
            connection=target_adapter.connection,
            config_tokens=target_config_tokens,
            numeric_field_tokens=target_numeric_field_tokens,
        )
        metadata_diagnostics = source_metadata_diagnostics + target_metadata_diagnostics
        if metadata_diagnostics:
            diagnostics.extend(metadata_diagnostics)
            _set_contract_render_block(
                results_by_check_id,
                compiled_contract=compiled_contract,
                diagnostics=metadata_diagnostics,
            )
            continue
        assert source_adapter_type_resolution.adapter_type is not None
        assert target_adapter_type_resolution.adapter_type is not None
        source_adapter_type = _sanitize_profile_backed_adapter_type(
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
            _set_contract_render_block(
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
            _set_contract_render_block(
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
            diagnostic = _sanitize_profile_backed_adapter_diagnostic(
                diagnostic,
                connection=source_adapter.connection,
                config_tokens=source_config_tokens,
                numeric_field_tokens=source_numeric_field_tokens,
            )
            diagnostics.append(diagnostic)
            _set_contract_render_block(
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
            render_result = _sanitize_profile_backed_render_result(
                render_result,
                connection=source_adapter.connection,
                config_tokens=source_config_tokens,
                numeric_field_tokens=source_numeric_field_tokens,
            )
            results_by_check_id[check.id] = render_result
            diagnostics.extend(render_result.diagnostics)

    return _RenderSqlCompilationResult(
        results_by_check_id=results_by_check_id,
        diagnostics=_dedupe_diagnostics(tuple(diagnostics)),
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

    return _dedupe_diagnostics(tuple(diagnostics))


def _set_contract_render_block(
    results_by_check_id: dict[str, RenderedCheckSql],
    *,
    compiled_contract: ContractCompilationArtifacts,
    diagnostics: tuple[Diagnostic, ...],
    adapter_type: str | None = None,
) -> None:
    for check in compiled_contract.checks_artifact.checks:
        results_by_check_id[check.id] = RenderedCheckSql(
            check_id=check.id,
            diagnostics=diagnostics,
            adapter_type=adapter_type,
        )


def _same_connection_context(source_adapter: BaseAdapter, target_adapter: BaseAdapter) -> bool:
    return (
        source_adapter.connection.type == target_adapter.connection.type
        and source_adapter.connection.config == target_adapter.connection.config
    )


def _renderer_for_adapter_type(adapter_type: str) -> DuckDbSqlRenderer | None:
    if adapter_type == "duckdb":
        return DuckDbSqlRenderer()
    return None


def _pluralize(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
