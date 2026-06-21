"""Compiled-check rendering metadata helpers for compile."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Protocol

from recon_core.adapters.models import RenderedSql
from recon_core.adapters.rendering import (
    ADAPTER_OPERATION_RENDER_FAILED,
    ADAPTER_RENDERED_SQL_EMPTY,
    RenderedCheckSql,
)
from recon_core.compiler import (
    CompiledCheck,
    ContractCompilationArtifacts,
    Rendering,
    RenderingStatus,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

ADAPTER_RENDERING_OUTPUT_SUPPRESSED = "RC_ADAPTER_RENDERING_OUTPUT_SUPPRESSED"
ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS = (
    "RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS"
)


class RenderedCheckSqlResult(Protocol):
    """Rendered check SQL shape consumed by compile artifact publication."""

    @property
    def sql(self) -> tuple[RenderedSql, ...]:
        """Rendered SQL steps for the check."""
        ...

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Rendering diagnostics for the check."""
        ...

    @property
    def adapter_type(self) -> str | None:
        """Adapter type used to render the check."""
        ...


def apply_rendered_sql_metadata(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    *,
    render_results_by_check_id: Mapping[str, RenderedCheckSqlResult],
    sql_paths_by_check_id: dict[str, tuple[str, ...]],
) -> tuple[ContractCompilationArtifacts, ...]:
    """Attach successful rendered SQL path metadata to compiled checks."""
    rendered_contracts: list[ContractCompilationArtifacts] = []

    for compiled_contract in compiled_contracts:
        rendered_checks = []
        for check in compiled_contract.checks_artifact.checks:
            render_result = render_results_by_check_id.get(check.id)
            if render_result is None:
                rendered_checks.append(check)
                continue
            rendered_checks.append(
                replace(
                    check,
                    rendering=Rendering(
                        status=RenderingStatus.RENDERED,
                        sql_paths=sql_paths_by_check_id[check.id],
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


def apply_render_failure_metadata(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
    *,
    render_results_by_check_id: Mapping[str, RenderedCheckSqlResult],
) -> tuple[ContractCompilationArtifacts, ...]:
    """Attach blocked or failed rendering metadata after render diagnostics."""
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


def apply_compile_diagnostic_render_block_metadata(
    compiled_contracts: tuple[ContractCompilationArtifacts, ...],
) -> tuple[ContractCompilationArtifacts, ...]:
    """Mark render-SQL output blocked when compile diagnostics already exist."""
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


def set_contract_render_block(
    results_by_check_id: dict[str, RenderedCheckSql],
    *,
    compiled_contract: ContractCompilationArtifacts,
    diagnostics: tuple[Diagnostic, ...],
    adapter_type: str | None = None,
) -> None:
    """Set blocked render results for all checks in one compiled contract."""
    for check in compiled_contract.checks_artifact.checks:
        results_by_check_id[check.id] = RenderedCheckSql(
            check_id=check.id,
            diagnostics=diagnostics,
            adapter_type=adapter_type,
        )


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
