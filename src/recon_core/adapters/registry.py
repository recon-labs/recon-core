"""Adapter registry and compatibility validation."""

from collections.abc import Callable
from typing import Protocol, cast

from recon_core.adapters.base import BaseAdapter
from recon_core.adapters.models import (
    ADAPTER_API_VERSION,
    AdapterResolutionResult,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig

ADAPTER_UNKNOWN_TYPE = "RC_ADAPTER_UNKNOWN_TYPE"
ADAPTER_API_VERSION_UNSUPPORTED = "RC_ADAPTER_API_VERSION_UNSUPPORTED"
ADAPTER_RESOLUTION_FAILED = "RC_ADAPTER_RESOLUTION_FAILED"


class AdapterFactory(Protocol):
    """Factory protocol for adapters that need custom creation checks."""

    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        """Create an adapter or return diagnostics."""


AdapterCreator = Callable[[ConnectionConfig], AdapterResolutionResult]


class AdapterRegistry:
    """Connection-type adapter registry."""

    def __init__(self) -> None:
        self._creators: dict[str, AdapterCreator] = {}

    def register(
        self,
        adapter_type: str,
        factory: type[BaseAdapter] | AdapterFactory | AdapterCreator,
    ) -> None:
        """Register an adapter class, factory, or creator callback."""
        self._creators[adapter_type] = _adapter_creator(factory)

    def resolve(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        """Resolve a rendered connection config to an adapter instance."""
        creator = self._creators.get(connection.type)
        if creator is None:
            return AdapterResolutionResult(
                diagnostics=(
                    Diagnostic(
                        code=ADAPTER_UNKNOWN_TYPE,
                        severity=DiagnosticSeverity.ERROR,
                        message=f"Unknown adapter type `{connection.type}`.",
                        resource_type="adapter",
                        resource_name=connection.type,
                        hint="Install or register an adapter for this connection type.",
                    ),
                )
            )

        try:
            result = creator(connection)
        except Exception as exc:
            return AdapterResolutionResult(
                diagnostics=(
                    Diagnostic(
                        code=ADAPTER_RESOLUTION_FAILED,
                        severity=DiagnosticSeverity.ERROR,
                        message=f"Adapter factory for type `{connection.type}` failed.",
                        resource_type="adapter",
                        resource_name=connection.type,
                        hint=_factory_exception_hint(exc),
                    ),
                )
            )
        if not isinstance(result, AdapterResolutionResult):
            return _invalid_resolution_result(connection)
        if result.adapter is None and not result.diagnostics:
            return _invalid_resolution_result(connection)
        if result.adapter is not None and not isinstance(result.adapter, BaseAdapter):
            return _invalid_resolution_result(connection)

        return result


def _factory_exception_hint(exc: Exception) -> str:
    return (
        f"Adapter factory raised {type(exc).__name__}. Raw adapter error text was "
        "suppressed because profile diagnostics must not expose rendered connection values."
    )


def validate_adapter_api_compatibility(adapter: BaseAdapter) -> tuple[Diagnostic, ...]:
    """Validate adapter API compatibility."""
    adapter_type = _safe_adapter_type(adapter)
    try:
        supported_adapter_api_version = adapter.supported_adapter_api_version
    except Exception:
        supported_adapter_api_version = None

    if supported_adapter_api_version == ADAPTER_API_VERSION:
        return ()

    if not isinstance(supported_adapter_api_version, str) or supported_adapter_api_version == "":
        return (
            Diagnostic(
                code=ADAPTER_API_VERSION_UNSUPPORTED,
                severity=DiagnosticSeverity.ERROR,
                message=(
                    f"Adapter `{adapter_type}` does not declare a valid supported "
                    f"adapter API version; Recon Core requires `{ADAPTER_API_VERSION}`."
                ),
                resource_type="adapter",
                resource_name=adapter_type,
                hint=(
                    "Declare the adapter API version supported by this adapter and "
                    "use an adapter version compatible with this Recon Core version."
                ),
            ),
        )

    return (
        Diagnostic(
            code=ADAPTER_API_VERSION_UNSUPPORTED,
            severity=DiagnosticSeverity.ERROR,
            message=(
                f"Adapter `{adapter_type}` supports adapter API "
                f"`{supported_adapter_api_version}`, but Recon Core requires "
                f"`{ADAPTER_API_VERSION}`."
            ),
            resource_type="adapter",
            resource_name=adapter_type,
            hint="Use an adapter version compatible with this Recon Core version.",
        ),
    )


def _invalid_resolution_result(connection: ConnectionConfig) -> AdapterResolutionResult:
    return AdapterResolutionResult(
        diagnostics=(
            Diagnostic(
                code=ADAPTER_RESOLUTION_FAILED,
                severity=DiagnosticSeverity.ERROR,
                message=(
                    f"Adapter factory for type `{connection.type}` returned an invalid "
                    "resolution result."
                ),
                resource_type="adapter",
                resource_name=connection.type,
                hint="Fix the adapter factory to return an adapter or a diagnostic.",
            ),
        )
    )


def _safe_adapter_type(adapter: BaseAdapter) -> str:
    try:
        adapter_type = adapter.adapter_type
    except Exception:
        return type(adapter).__name__
    if not isinstance(adapter_type, str) or adapter_type == "":
        return type(adapter).__name__
    return adapter_type


def _adapter_creator(
    factory: type[BaseAdapter] | AdapterFactory | AdapterCreator,
) -> AdapterCreator:
    if isinstance(factory, type) and issubclass(factory, BaseAdapter):
        adapter_cls = factory

        def create_from_class(connection: ConnectionConfig) -> AdapterResolutionResult:
            return AdapterResolutionResult(adapter=adapter_cls(connection=connection))

        return create_from_class

    if hasattr(factory, "create"):
        adapter_factory = cast(AdapterFactory, factory)
        return adapter_factory.create

    return cast(AdapterCreator, factory)
