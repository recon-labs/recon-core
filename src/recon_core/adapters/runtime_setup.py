"""Runtime adapter setup validation for execution phases."""

from dataclasses import dataclass

from recon_core.adapters.base import BaseAdapter
from recon_core.adapters.capabilities import AdapterCapabilities, validate_required_capabilities
from recon_core.adapters.diagnostic_redaction import (
    sanitize_profile_backed_adapter_diagnostics,
)
from recon_core.adapters.duckdb import DuckDbAdapterFactory
from recon_core.adapters.registry import (
    AdapterRegistry,
    resolve_adapter_type,
    validate_adapter_api_compatibility,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig

ADAPTER_TYPE_MISMATCH = "RC_ADAPTER_TYPE_MISMATCH"
ADAPTER_CAPABILITY_DECLARATION_FAILED = "RC_ADAPTER_CAPABILITY_DECLARATION_FAILED"


@dataclass(frozen=True, slots=True)
class RuntimeAdapterSetupResult:
    """Validated adapter setup result before connection lifecycle starts."""

    adapter: BaseAdapter | None = None
    adapter_type: str | None = None
    capabilities: AdapterCapabilities | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return (
            self.adapter is not None
            and self.adapter_type is not None
            and self.capabilities is not None
            and not self.diagnostics
        )


def prepare_runtime_adapter(
    *,
    connection: ConnectionConfig,
    required_capabilities: tuple[str, ...],
    registry: AdapterRegistry | None = None,
) -> RuntimeAdapterSetupResult:
    """Resolve and validate an adapter without opening a connection."""
    resolved_registry = registry if registry is not None else _default_runtime_adapter_registry()
    resolution = resolved_registry.resolve(connection)
    if resolution.diagnostics or resolution.adapter is None:
        return RuntimeAdapterSetupResult(
            diagnostics=_sanitize_runtime_diagnostics(
                resolution.diagnostics,
                connection=connection,
            )
        )

    adapter = resolution.adapter
    adapter_type_resolution = resolve_adapter_type(adapter)
    if adapter_type_resolution.diagnostics:
        return RuntimeAdapterSetupResult(
            diagnostics=_sanitize_runtime_diagnostics(
                adapter_type_resolution.diagnostics,
                connection=connection,
            )
        )

    adapter_type = adapter_type_resolution.adapter_type
    assert adapter_type is not None
    if adapter_type != connection.type:
        return RuntimeAdapterSetupResult(
            adapter_type=adapter_type,
            diagnostics=(_adapter_type_mismatch_diagnostic(connection),),
        )

    api_diagnostics = validate_adapter_api_compatibility(adapter)
    if api_diagnostics:
        return RuntimeAdapterSetupResult(
            adapter_type=adapter_type,
            diagnostics=_sanitize_runtime_diagnostics(
                api_diagnostics,
                connection=connection,
            ),
        )

    capabilities, capability_diagnostics = _adapter_capabilities(
        adapter,
        adapter_type=adapter_type,
    )
    if capability_diagnostics:
        return RuntimeAdapterSetupResult(
            adapter_type=adapter_type,
            diagnostics=_sanitize_runtime_diagnostics(
                capability_diagnostics,
                connection=connection,
            ),
        )
    assert capabilities is not None

    required_capability_diagnostics = _required_capability_diagnostics(
        adapter_type=adapter_type,
        capabilities=capabilities,
        required_capabilities=required_capabilities,
    )
    if required_capability_diagnostics:
        return RuntimeAdapterSetupResult(
            adapter_type=adapter_type,
            diagnostics=_sanitize_runtime_diagnostics(
                required_capability_diagnostics,
                connection=connection,
            ),
        )

    return RuntimeAdapterSetupResult(
        adapter=adapter,
        adapter_type=adapter_type,
        capabilities=capabilities,
    )


def _default_runtime_adapter_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory())
    return registry


def _sanitize_runtime_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    *,
    connection: ConnectionConfig,
) -> tuple[Diagnostic, ...]:
    return sanitize_profile_backed_adapter_diagnostics(
        diagnostics,
        connection=connection,
    )


def _adapter_capabilities(
    adapter: BaseAdapter,
    *,
    adapter_type: str,
) -> tuple[AdapterCapabilities | None, tuple[Diagnostic, ...]]:
    try:
        capabilities = adapter.capabilities()
    except Exception as exc:
        return None, (
            Diagnostic(
                code=ADAPTER_CAPABILITY_DECLARATION_FAILED,
                severity=DiagnosticSeverity.ERROR,
                message=f"Adapter `{adapter_type}` failed to declare runtime capabilities.",
                resource_type="adapter_capability",
                resource_name=adapter_type,
                hint=_capability_exception_hint(exc),
            ),
        )
    if not isinstance(capabilities, AdapterCapabilities):
        return None, (
            Diagnostic(
                code=ADAPTER_CAPABILITY_DECLARATION_FAILED,
                severity=DiagnosticSeverity.ERROR,
                message=f"Adapter `{adapter_type}` returned invalid runtime capabilities.",
                resource_type="adapter_capability",
                resource_name=adapter_type,
                hint="Return an AdapterCapabilities instance from adapter.capabilities().",
            ),
        )
    return capabilities, ()


def _required_capability_diagnostics(
    *,
    adapter_type: str,
    capabilities: AdapterCapabilities,
    required_capabilities: tuple[str, ...],
) -> tuple[Diagnostic, ...]:
    try:
        return validate_required_capabilities(
            adapter_type=adapter_type,
            capabilities=capabilities,
            required_capabilities=_unique_capabilities(required_capabilities),
        )
    except Exception as exc:
        return (
            Diagnostic(
                code=ADAPTER_CAPABILITY_DECLARATION_FAILED,
                severity=DiagnosticSeverity.ERROR,
                message=f"Adapter `{adapter_type}` declared invalid runtime capabilities.",
                resource_type="adapter_capability",
                resource_name=adapter_type,
                hint=_capability_exception_hint(exc),
            ),
        )


def _unique_capabilities(capabilities: tuple[str, ...]) -> tuple[str, ...]:
    unique: list[str] = []
    seen: set[str] = set()
    for capability in capabilities:
        if capability in seen:
            continue
        seen.add(capability)
        unique.append(capability)
    return tuple(unique)


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


def _capability_exception_hint(exc: Exception) -> str:
    return (
        f"Adapter capability declaration raised {type(exc).__name__}. Raw adapter error "
        "text was suppressed because runtime adapter diagnostics must not expose "
        "rendered connection config."
    )
