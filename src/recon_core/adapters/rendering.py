"""In-memory adapter SQL rendering orchestration."""

from dataclasses import dataclass

from recon_core.adapters.base import BaseAdapter, SqlRenderer
from recon_core.adapters.capabilities import AdapterCapabilities, validate_required_capabilities
from recon_core.adapters.models import Relation, RenderedSql
from recon_core.adapters.registry import resolve_adapter_type
from recon_core.compiler.models import CompiledCheck, CompiledContractArtifact
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

ADAPTER_QUERY_ENDPOINT_UNSUPPORTED = "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"
ADAPTER_INVALID_RELATION = "RC_ADAPTER_INVALID_RELATION"
ADAPTER_CAPABILITY_DECLARATION_FAILED = "RC_ADAPTER_CAPABILITY_DECLARATION_FAILED"
ADAPTER_OPERATION_RENDER_FAILED = "RC_ADAPTER_OPERATION_RENDER_FAILED"
ADAPTER_RENDERED_SQL_EMPTY = "RC_ADAPTER_RENDERED_SQL_EMPTY"


@dataclass(frozen=True, slots=True)
class RenderedCheckSql:
    """In-memory rendered SQL for one compiled check."""

    check_id: str
    sql: tuple[RenderedSql, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    adapter_type: str | None = None

    @property
    def succeeded(self) -> bool:
        return not self.diagnostics


def render_check_sql(
    *,
    contract: CompiledContractArtifact,
    check: CompiledCheck,
    adapter: BaseAdapter,
    renderer: SqlRenderer,
    capabilities: AdapterCapabilities | None = None,
) -> RenderedCheckSql:
    """Render one compiled check to in-memory SQL without writing artifacts."""
    adapter_type_resolution = resolve_adapter_type(adapter)
    if adapter_type_resolution.diagnostics:
        return RenderedCheckSql(
            check_id=check.id,
            diagnostics=adapter_type_resolution.diagnostics,
        )
    adapter_type = adapter_type_resolution.adapter_type
    assert adapter_type is not None

    endpoint_diagnostics = _endpoint_diagnostics(contract)
    if endpoint_diagnostics:
        return RenderedCheckSql(
            check_id=check.id,
            diagnostics=endpoint_diagnostics,
            adapter_type=adapter_type,
        )

    source_relation, source_diagnostics = _relation_from_name(
        contract.source.relation,
        side="source",
        contract_name=contract.contract.name,
    )
    target_relation, target_diagnostics = _relation_from_name(
        contract.target.relation,
        side="target",
        contract_name=contract.contract.name,
    )
    relation_diagnostics = source_diagnostics + target_diagnostics
    if relation_diagnostics:
        return RenderedCheckSql(
            check_id=check.id,
            diagnostics=relation_diagnostics,
            adapter_type=adapter_type,
        )

    assert source_relation is not None
    assert target_relation is not None
    required_capabilities = ("relations",) + tuple(
        capability.value for capability in check.plan.required_capabilities
    )
    if capabilities is None:
        try:
            resolved_capabilities = adapter.capabilities()
        except Exception as exc:
            return RenderedCheckSql(
                check_id=check.id,
                diagnostics=(
                    Diagnostic(
                        code=ADAPTER_CAPABILITY_DECLARATION_FAILED,
                        severity=DiagnosticSeverity.ERROR,
                        message=(
                            f"Adapter `{adapter_type}` failed to declare capabilities "
                            f"for check `{check.id}`."
                        ),
                        resource_type="compiled_check",
                        resource_name=check.id,
                        hint=_capability_exception_hint(exc),
                    ),
                ),
                adapter_type=adapter_type,
            )
    else:
        resolved_capabilities = capabilities

    try:
        capability_diagnostics = validate_required_capabilities(
            adapter_type=adapter_type,
            capabilities=resolved_capabilities,
            required_capabilities=required_capabilities,
        )
    except Exception as exc:
        return RenderedCheckSql(
            check_id=check.id,
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_CAPABILITY_DECLARATION_FAILED,
                    severity=DiagnosticSeverity.ERROR,
                    message=(
                        f"Adapter `{adapter_type}` declared invalid capabilities "
                        f"for check `{check.id}`."
                    ),
                    resource_type="compiled_check",
                    resource_name=check.id,
                    hint=_capability_exception_hint(exc),
                ),
            ),
            adapter_type=adapter_type,
        )
    if capability_diagnostics:
        return RenderedCheckSql(
            check_id=check.id,
            diagnostics=capability_diagnostics,
            adapter_type=adapter_type,
        )

    try:
        rendered_sql: object = renderer.render_plan(
            tuple(operation.to_dict() for operation in check.plan.operations),
            source_relation=source_relation,
            target_relation=target_relation,
        )
    except Exception as exc:
        return RenderedCheckSql(
            check_id=check.id,
            adapter_type=adapter_type,
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_OPERATION_RENDER_FAILED,
                    severity=DiagnosticSeverity.ERROR,
                    message=(f"Adapter `{adapter_type}` failed to render check `{check.id}`."),
                    resource_type="compiled_check",
                    resource_name=check.id,
                    hint=_renderer_exception_hint(exc),
                ),
            ),
        )

    invalid_output_diagnostic = _invalid_rendered_sql_output_diagnostic(
        rendered_sql,
        adapter_type=adapter_type,
        check_id=check.id,
    )
    if invalid_output_diagnostic is not None:
        return RenderedCheckSql(
            check_id=check.id,
            adapter_type=adapter_type,
            diagnostics=(invalid_output_diagnostic,),
        )

    assert isinstance(rendered_sql, tuple)
    if not rendered_sql:
        return RenderedCheckSql(
            check_id=check.id,
            adapter_type=adapter_type,
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_RENDERED_SQL_EMPTY,
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Adapter `{adapter_type}` rendered no SQL for check `{check.id}`.",
                    resource_type="compiled_check",
                    resource_name=check.id,
                    hint=(
                        "Fix the renderer to return one or more SQL steps for each rendered "
                        "check or return a rendering diagnostic."
                    ),
                ),
            ),
        )

    return RenderedCheckSql(check_id=check.id, sql=rendered_sql, adapter_type=adapter_type)


def _invalid_rendered_sql_output_diagnostic(
    rendered_sql: object,
    *,
    adapter_type: str,
    check_id: str,
) -> Diagnostic | None:
    reason = _invalid_rendered_sql_output_reason(rendered_sql)
    if reason is None:
        return None

    return Diagnostic(
        code=ADAPTER_OPERATION_RENDER_FAILED,
        severity=DiagnosticSeverity.ERROR,
        message=f"Adapter `{adapter_type}` returned invalid rendered SQL for check `{check_id}`.",
        resource_type="compiled_check",
        resource_name=check_id,
        hint=(
            f"{reason} Fix the renderer to return a non-empty tuple of RenderedSql "
            "steps with non-empty string `sql`, `operation_type`, and `step_name` fields."
        ),
    )


def _invalid_rendered_sql_output_reason(rendered_sql: object) -> str | None:
    if not isinstance(rendered_sql, tuple):
        return "Renderer output must be a tuple of RenderedSql steps."

    for index, rendered_step in enumerate(rendered_sql):
        if not isinstance(rendered_step, RenderedSql):
            return f"Renderer output step {index} is not a RenderedSql instance."
        if not isinstance(rendered_step.sql, str) or rendered_step.sql.strip() == "":
            return f"Renderer output step {index} must define non-empty string SQL."
        if (
            not isinstance(rendered_step.operation_type, str)
            or rendered_step.operation_type.strip() == ""
        ):
            return f"Renderer output step {index} must define a non-empty operation type."
        if not isinstance(rendered_step.step_name, str) or rendered_step.step_name.strip() == "":
            return f"Renderer output step {index} must define a non-empty step name."
        if not isinstance(rendered_step.required_capabilities, tuple) or not all(
            isinstance(capability, str) and capability.strip() != ""
            for capability in rendered_step.required_capabilities
        ):
            return (
                f"Renderer output step {index} must define required capabilities as "
                "a tuple of non-empty strings."
            )

    return None


def _endpoint_diagnostics(contract: CompiledContractArtifact) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if contract.source.query is not None:
        diagnostics.append(_query_endpoint_diagnostic(contract.contract.name, "source"))
    if contract.target.query is not None:
        diagnostics.append(_query_endpoint_diagnostic(contract.contract.name, "target"))
    return tuple(diagnostics)


def _query_endpoint_diagnostic(contract_name: str, side: str) -> Diagnostic:
    return Diagnostic(
        code=ADAPTER_QUERY_ENDPOINT_UNSUPPORTED,
        severity=DiagnosticSeverity.ERROR,
        message=(
            f"Adapter-aware SQL rendering does not support `{side}.query` endpoints "
            f"for contract `{contract_name}`."
        ),
        resource_type="contract_endpoint",
        resource_name=contract_name,
        hint="Use a relation endpoint for Milestone 6 adapter-aware SQL rendering.",
    )


def _renderer_exception_hint(exc: Exception) -> str:
    return (
        f"Renderer raised {type(exc).__name__}. Raw adapter error text was suppressed "
        "because rendering diagnostics are written to generated artifacts."
    )


def _capability_exception_hint(exc: Exception) -> str:
    return (
        f"Capability declaration raised {type(exc).__name__}. Raw adapter error text "
        "was suppressed because rendering diagnostics are written to generated artifacts."
    )


def _relation_from_name(
    relation_name: str | None,
    *,
    side: str,
    contract_name: str,
) -> tuple[Relation | None, tuple[Diagnostic, ...]]:
    if relation_name is None:
        return None, (
            Diagnostic(
                code=ADAPTER_INVALID_RELATION,
                severity=DiagnosticSeverity.ERROR,
                message=(f"Contract `{contract_name}` {side} endpoint does not define a relation."),
                resource_type="contract_endpoint",
                resource_name=contract_name,
                hint="Use relation endpoints for Milestone 6 adapter-aware SQL rendering.",
            ),
        )

    parts = tuple(part for part in relation_name.split(".") if part)
    if len(parts) not in {1, 2, 3} or len(parts) != len(relation_name.split(".")):
        return None, (
            Diagnostic(
                code=ADAPTER_INVALID_RELATION,
                severity=DiagnosticSeverity.ERROR,
                message=(
                    f"Contract `{contract_name}` {side} relation must have one to three "
                    "non-empty identifier parts."
                ),
                resource_type="contract_endpoint",
                resource_name=contract_name,
                hint="Use relation, schema.relation, or catalog.schema.relation.",
            ),
        )

    if len(parts) == 1:
        return Relation(identifier=parts[0]), ()
    if len(parts) == 2:
        return Relation(schema=parts[0], identifier=parts[1]), ()
    return Relation(catalog=parts[0], schema=parts[1], identifier=parts[2]), ()
