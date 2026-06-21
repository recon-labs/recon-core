from pathlib import Path
from typing import Any

import pytest

import recon_core.adapters.duckdb.runtime_scan_guard as duckdb_scan_guard_module
from recon_core.adapters import (
    AdapterCapabilities,
    AdapterRegistry,
    CapabilitySupport,
)
from recon_core.adapters.duckdb import (
    ADAPTER_CLOSE_FAILED,
    ADAPTER_CONNECTION_FAILED,
    ADAPTER_DEPENDENCY_MISSING,
    ADAPTER_QUERY_FAILED,
    DuckDbAdapterFactory,
)
from recon_core.services import RunService
from recon_core.services.results import ExitCategory
from tests.services._run_service_fixtures import (
    BOUNDED_LOCAL_SCAN_REQUIRED,
    RecordingDuckDbFactory,
    RecordingWarehouseFactory,
    _assert_no_runtime_outputs,
    _compiled_check_payload,
    _key_safety_check_payload,
    _key_safety_payload_for,
    _service_result_text,
    row_count_plan,
    write_bounded_local_duckdb_fixture,
    write_compiled_checks,
    write_compiled_contract,
    write_profiles,
    write_project,
)


def test_run_service_reports_missing_compiled_contract_before_profile_or_adapter_work(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compiled-contract artifacts could not be loaded."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND"
    ]
    assert factory.adapters == []


def test_run_service_reports_referenced_profile_diagnostic_before_adapter_resolution(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: "{{ env_var('WAREHOUSE_DB') }}"
          unused:
            type: duckdb
            database: "{{ env_var('UNUSED_DB') }}"
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run profile configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_PROFILE_ENV_VAR_MISSING"
    ]
    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"
    assert "WAREHOUSE_DB" in diagnostic_text
    assert "UNUSED_DB" not in diagnostic_text
    assert factory.adapters == []


def test_run_service_ignores_unsupported_later_phase_contract_profile_env(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
          later_phase:
            type: duckdb
            database: "{{ env_var('LATER_PHASE_DB') }}"
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    write_compiled_checks(
        tmp_path,
        contract_name="later_phase_contract",
        checks=[
            _compiled_check_payload(
                check_id="check.ecommerce_recon.later_phase_contract.sum_diff",
                name="sum_diff",
                check_type="sum_diff",
                operations=[
                    {
                        "type": "aggregate",
                        "side": "source",
                        "aggregate": "sum",
                        "column": "revenue",
                    },
                    {
                        "type": "aggregate",
                        "side": "target",
                        "aggregate": "sum",
                        "column": "revenue",
                    },
                    {"type": "compare_aggregates"},
                ],
                required_capabilities=[],
            )
        ],
    )
    write_compiled_contract(
        tmp_path,
        contract_name="later_phase_contract",
        source_connection="later_phase",
        target_connection="later_phase",
    )
    factory = RecordingDuckDbFactory()
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_CHECK_NOT_EXECUTABLE"
    ]
    assert "LATER_PHASE_DB" not in _service_result_text(result)
    assert len(factory.adapters) == 1
    adapter = factory.adapters[0]
    assert adapter.connection.name == "warehouse"
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_keeps_aggregate_not_executable_with_full_capability(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(
                check_id="check.ecommerce_recon.customer_revenue.sum_diff",
                name="sum_diff",
                check_type="sum_diff",
                operations=[
                    {
                        "type": "aggregate",
                        "side": "source",
                        "aggregate": "sum",
                        "column": "revenue",
                    },
                    {
                        "type": "aggregate",
                        "side": "target",
                        "aggregate": "sum",
                        "column": "revenue",
                    },
                    {"type": "compare_aggregates"},
                ],
                required_capabilities=["aggregate", "cte_support"],
            )
        ],
    )
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities(
            {
                "aggregate": CapabilitySupport.FULL,
                "cte_support": CapabilitySupport.FULL,
                "row_count": CapabilitySupport.FULL,
                "key_diff": CapabilitySupport.FULL,
                "null_key": CapabilitySupport.FULL,
                "duplicate_key": CapabilitySupport.FULL,
            }
        ),
        connect_error=RuntimeError("opened aggregate adapter before runtime phase exists"),
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_MISSING_ENGINE_CAPABILITY"
    ]
    assert "aggregate" in result.diagnostics[0].message
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("key-safety-adapter-capability-preflight")
def test_run_service_requires_key_safety_capability_before_connect(tmp_path: Path) -> None:
    write_bounded_local_duckdb_fixture(tmp_path)
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities({"cte_support": CapabilitySupport.FULL})
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "key_diff" in result.diagnostics[0].message
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []


@pytest.mark.parametrize(
    ("check_type", "missing_capability", "capabilities"),
    [
        (
            "null_source_keys",
            "null_key",
            {
                "cte_support": CapabilitySupport.FULL,
                "key_diff": CapabilitySupport.FULL,
                "duplicate_key": CapabilitySupport.FULL,
            },
        ),
        (
            "duplicate_source_keys",
            "duplicate_key",
            {
                "cte_support": CapabilitySupport.FULL,
                "key_diff": CapabilitySupport.FULL,
                "null_key": CapabilitySupport.FULL,
            },
        ),
    ],
)
@pytest.mark.regression_capture("key-safety-adapter-capability-preflight")
def test_run_service_requires_each_key_safety_capability_before_connect(
    tmp_path: Path,
    check_type: str,
    missing_capability: str,
    capabilities: dict[str, CapabilitySupport],
) -> None:
    write_bounded_local_duckdb_fixture(tmp_path)
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_payload_for(check_type)])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(capabilities=AdapterCapabilities(capabilities))
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert missing_capability in result.diagnostics[0].message
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []


@pytest.mark.regression_capture("key-safety-adapter-capability-preflight")
def test_run_service_blocks_key_safety_malformed_capability_before_connect(
    tmp_path: Path,
) -> None:
    write_bounded_local_duckdb_fixture(tmp_path)
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path)
    malformed_capabilities: dict[str, Any] = {
        "cte_support": CapabilitySupport.FULL,
        "key_diff": "wat",
    }
    factory = RecordingDuckDbFactory(capabilities=AdapterCapabilities(malformed_capabilities))
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "key_diff" in result.diagnostics[0].message
    assert "invalid support state" in result.diagnostics[0].message
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []


def test_run_service_sanitizes_key_safety_capability_declaration_exception(
    tmp_path: Path,
) -> None:
    write_bounded_local_duckdb_fixture(tmp_path)
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
            password: super-secret
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        capabilities_error=RuntimeError("capabilities leaked password=super-secret")
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_DECLARATION_FAILED"
    ]
    assert "super-secret" not in _service_result_text(result)
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []


def test_run_service_blocks_key_safety_scan_budget_for_non_local_adapter(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: warehouse_test
            database: warehouse
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path)
    factory = RecordingWarehouseFactory(
        capabilities=AdapterCapabilities(
            {
                "key_diff": CapabilitySupport.FULL,
                "cte_support": CapabilitySupport.FULL,
            }
        )
    )
    registry = AdapterRegistry()
    registry.register("warehouse_test", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run completed with non-executable checks."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_SCAN_ESTIMATE_UNKNOWN"
    ]
    assert factory.adapters == []
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("key-safety-duckdb-metadata-open-failure-adapter-diagnostic")
def test_run_service_reports_missing_duckdb_dependency_when_metadata_probe_cannot_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "warehouse.duckdb").write_bytes(b"not opened by metadata probe")
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path)

    real_import_module = duckdb_scan_guard_module.import_module

    def import_module_without_duckdb(name: str) -> Any:
        if name == "duckdb":
            raise ImportError("No module named duckdb")
        return real_import_module(name)

    monkeypatch.setattr(duckdb_scan_guard_module, "import_module", import_module_without_duckdb)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: False))

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [ADAPTER_DEPENDENCY_MISSING]
    assert BOUNDED_LOCAL_SCAN_REQUIRED not in _service_result_text(result)
    _assert_no_runtime_outputs(tmp_path)


@pytest.mark.regression_capture("key-safety-duckdb-metadata-open-failure-adapter-diagnostic")
def test_run_service_reports_adapter_connection_when_metadata_probe_cannot_open_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "warehouse.duckdb").write_bytes(b"not opened by metadata probe")
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
            password: super-secret
""",
    )
    write_compiled_checks(tmp_path, checks=[_key_safety_check_payload()])
    write_compiled_contract(tmp_path)

    class FailingDuckDbModule:
        def connect(self, database: str, *, read_only: bool = False) -> object:
            raise RuntimeError(f"metadata open failed for {database} {read_only}")

    real_import_module = duckdb_scan_guard_module.import_module

    def import_module_with_metadata_open_failure(name: str) -> Any:
        if name == "duckdb":
            return FailingDuckDbModule()
        return real_import_module(name)

    monkeypatch.setattr(
        duckdb_scan_guard_module,
        "import_module",
        import_module_with_metadata_open_failure,
    )
    factory = RecordingDuckDbFactory(
        connect_error=RuntimeError("password=super-secret database=warehouse.duckdb")
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run adapter connection failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [ADAPTER_CONNECTION_FAILED]
    assert "super-secret" not in _service_result_text(result)
    assert BOUNDED_LOCAL_SCAN_REQUIRED not in _service_result_text(result)
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.queries == []
    _assert_no_runtime_outputs(tmp_path)


def test_run_service_reports_adapter_setup_failure_before_connect(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities({"row_count": CapabilitySupport.FULL})
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "cte_support" in result.diagnostics[0].message
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []


def test_run_service_requires_row_count_capability_even_if_compiled_artifact_omits_it(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
""",
    )
    write_compiled_checks(
        tmp_path,
        checks=[_compiled_check_payload(operations=row_count_plan(), required_capabilities=[])],
    )
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        capabilities=AdapterCapabilities({"cte_support": CapabilitySupport.FULL})
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "Run adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "row_count" in result.diagnostics[0].message
    adapter = factory.adapters[0]
    assert adapter.connect_count == 0
    assert adapter.queries == []


def test_run_service_reports_connect_failure_without_engine_execution(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
            password: super-secret
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        connect_error=RuntimeError("password=super-secret database=warehouse.duckdb")
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run adapter connection failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [ADAPTER_CONNECTION_FAILED]
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 0
    assert adapter.queries == []


def test_run_service_reports_close_failure_after_success(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
            password: super-secret
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(close_error=RuntimeError("close leaked password=super-secret"))
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during adapter lifecycle cleanup."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [ADAPTER_CLOSE_FAILED]
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1


def test_run_service_preserves_execution_failure_when_close_also_fails(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(
        tmp_path,
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          warehouse:
            type: duckdb
            database: warehouse.duckdb
            password: super-secret
""",
    )
    write_compiled_checks(tmp_path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(tmp_path)
    factory = RecordingDuckDbFactory(
        execute_error=RuntimeError("query leaked password=super-secret"),
        close_error=RuntimeError("close leaked password=super-secret"),
    )
    registry = AdapterRegistry()
    registry.register("duckdb", factory)

    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()

    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Run failed during check-engine evaluation."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        ADAPTER_QUERY_FAILED,
        ADAPTER_CLOSE_FAILED,
    ]
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    adapter = factory.adapters[0]
    assert adapter.connect_count == 1
    assert adapter.close_count == 1
    assert len(adapter.queries) == 1
