"""In-memory adapter SQL rendering orchestration."""

from dataclasses import dataclass

from recon_core.adapters.base import BaseAdapter, SqlRenderer
from recon_core.adapters.capabilities import AdapterCapabilities, validate_required_capabilities
from recon_core.adapters.models import Relation, RenderedSql
from recon_core.compiler.models import CompiledCheck, CompiledContractArtifact
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

ADAPTER_QUERY_ENDPOINT_UNSUPPORTED = "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"
ADAPTER_INVALID_RELATION = "RC_ADAPTER_INVALID_RELATION"
ADAPTER_OPERATION_RENDER_FAILED = "RC_ADAPTER_OPERATION_RENDER_FAILED"


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
    endpoint_diagnostics = _endpoint_diagnostics(contract)
    if endpoint_diagnostics:
        return RenderedCheckSql(
            check_id=check.id,
            diagnostics=endpoint_diagnostics,
            adapter_type=adapter.adapter_type,
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
            adapter_type=adapter.adapter_type,
        )

    assert source_relation is not None
    assert target_relation is not None
    required_capabilities = ("relations",) + tuple(
        capability.value for capability in check.plan.required_capabilities
    )
    capability_diagnostics = validate_required_capabilities(
        adapter_type=adapter.adapter_type,
        capabilities=adapter.capabilities() if capabilities is None else capabilities,
        required_capabilities=required_capabilities,
    )
    if capability_diagnostics:
        return RenderedCheckSql(
            check_id=check.id,
            diagnostics=capability_diagnostics,
            adapter_type=adapter.adapter_type,
        )

    try:
        rendered_sql = renderer.render_plan(
            tuple(operation.to_dict() for operation in check.plan.operations),
            source_relation=source_relation,
            target_relation=target_relation,
        )
    except Exception as exc:
        return RenderedCheckSql(
            check_id=check.id,
            adapter_type=adapter.adapter_type,
            diagnostics=(
                Diagnostic(
                    code=ADAPTER_OPERATION_RENDER_FAILED,
                    severity=DiagnosticSeverity.ERROR,
                    message=(
                        f"Adapter `{adapter.adapter_type}` failed to render check `{check.id}`."
                    ),
                    resource_type="compiled_check",
                    resource_name=check.id,
                    hint=f"Renderer error: {exc}",
                ),
            ),
        )

    return RenderedCheckSql(check_id=check.id, sql=rendered_sql, adapter_type=adapter.adapter_type)


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
