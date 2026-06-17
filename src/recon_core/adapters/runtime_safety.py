"""Runtime safety-check boundaries for adapter-backed execution."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from recon_core.profiles import ConnectionConfig


@dataclass(frozen=True, slots=True)
class RuntimeSafetyCheckRequest:
    """Neutral request shape for runtime safety checks."""

    source_connection: ConnectionConfig | None
    target_connection: ConnectionConfig | None
    source_relation: str | None
    target_relation: str | None
    project_root: Path


@dataclass(frozen=True, slots=True)
class RuntimeScanSafetyStatus:
    """Runtime scan safety classification used before scan-heavy execution."""

    local_dev: bool = False
    bounded: bool = False
    metadata_open_failed: bool = False


class RuntimeSafetyCheck(Protocol):
    """Adapter-provided runtime safety check implementation."""

    def scan_safety_status(
        self,
        request: RuntimeSafetyCheckRequest,
    ) -> RuntimeScanSafetyStatus:
        """Classify whether scan-heavy runtime execution is safe."""


class RuntimeSafetyCheckRegistry:
    """Registry of adapter runtime safety-check implementations."""

    def __init__(self) -> None:
        self._checks: dict[str, RuntimeSafetyCheck] = {}

    def register(self, adapter_type: str, check: RuntimeSafetyCheck) -> None:
        """Register runtime safety checks for an adapter type."""
        self._checks[adapter_type] = check

    def scan_safety_status(
        self,
        request: RuntimeSafetyCheckRequest,
    ) -> RuntimeScanSafetyStatus:
        """Return the scan safety status for the request's adapter context."""
        adapter_type = _shared_adapter_type(
            request.source_connection,
            request.target_connection,
        )
        if adapter_type is None:
            return RuntimeScanSafetyStatus()
        check = self._checks.get(adapter_type)
        if check is None:
            return RuntimeScanSafetyStatus()
        return check.scan_safety_status(request)


def default_runtime_safety_check_registry() -> RuntimeSafetyCheckRegistry:
    """Return the built-in runtime safety-check registry."""
    from recon_core.adapters.duckdb.runtime_scan_guard import (  # noqa: PLC0415
        DuckDbBoundedLocalScanSafetyCheck,
    )

    registry = RuntimeSafetyCheckRegistry()
    registry.register("duckdb", DuckDbBoundedLocalScanSafetyCheck())
    return registry


def _shared_adapter_type(
    source_connection: ConnectionConfig | None,
    target_connection: ConnectionConfig | None,
) -> str | None:
    if source_connection is None or target_connection is None:
        return None
    if source_connection.type != target_connection.type:
        return None
    return source_connection.type
