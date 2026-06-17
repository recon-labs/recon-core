from pathlib import Path

from recon_core.adapters.runtime_safety import (
    RuntimeSafetyCheckRegistry,
    RuntimeSafetyCheckRequest,
    RuntimeScanSafetyStatus,
    default_runtime_safety_check_registry,
)
from recon_core.profiles import ConnectionConfig


class AlwaysBoundedSafetyCheck:
    def scan_safety_status(
        self,
        request: RuntimeSafetyCheckRequest,
    ) -> RuntimeScanSafetyStatus:
        return RuntimeScanSafetyStatus(local_dev=True, bounded=True)


def test_runtime_safety_registry_fails_closed_for_unregistered_adapter(
    tmp_path: Path,
) -> None:
    registry = RuntimeSafetyCheckRegistry()

    status = registry.scan_safety_status(
        RuntimeSafetyCheckRequest(
            source_connection=ConnectionConfig(name="source", type="warehouse"),
            target_connection=ConnectionConfig(name="target", type="warehouse"),
            source_relation="source_customers",
            target_relation="target_customers",
            project_root=tmp_path,
        )
    )

    assert status == RuntimeScanSafetyStatus()


def test_runtime_safety_registry_uses_registered_shared_adapter_context(
    tmp_path: Path,
) -> None:
    registry = RuntimeSafetyCheckRegistry()
    registry.register("warehouse", AlwaysBoundedSafetyCheck())

    status = registry.scan_safety_status(
        RuntimeSafetyCheckRequest(
            source_connection=ConnectionConfig(name="source", type="warehouse"),
            target_connection=ConnectionConfig(name="target", type="warehouse"),
            source_relation="source_customers",
            target_relation="target_customers",
            project_root=tmp_path,
        )
    )

    assert status == RuntimeScanSafetyStatus(local_dev=True, bounded=True)


def test_runtime_safety_registry_fails_closed_for_mixed_adapter_context(
    tmp_path: Path,
) -> None:
    registry = RuntimeSafetyCheckRegistry()
    registry.register("warehouse", AlwaysBoundedSafetyCheck())

    status = registry.scan_safety_status(
        RuntimeSafetyCheckRequest(
            source_connection=ConnectionConfig(name="source", type="warehouse"),
            target_connection=ConnectionConfig(name="target", type="other"),
            source_relation="source_customers",
            target_relation="target_customers",
            project_root=tmp_path,
        )
    )

    assert status == RuntimeScanSafetyStatus()


def test_default_runtime_safety_registry_routes_same_context_duckdb_scan(
    tmp_path: Path,
) -> None:
    registry = default_runtime_safety_check_registry()
    connection = ConnectionConfig(
        name="warehouse",
        type="duckdb",
        config={"database": "warehouse.duckdb"},
    )

    status = registry.scan_safety_status(
        RuntimeSafetyCheckRequest(
            source_connection=connection,
            target_connection=connection,
            source_relation="qa.source_customers",
            target_relation="qa.target_customers",
            project_root=tmp_path,
        )
    )

    assert status == RuntimeScanSafetyStatus(local_dev=True, bounded=False)
