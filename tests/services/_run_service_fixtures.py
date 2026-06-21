import importlib
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from recon_core.adapters import (
    ADAPTER_API_VERSION,
    AdapterCapabilities,
    AdapterResolutionResult,
    BaseAdapter,
    CapabilitySupport,
    ConnectionConfig,
    QueryResult,
)
from recon_core.artifacts import LoadedCompiledChecksArtifact
from recon_core.check_engine import (
    CheckExecutionContext,
    CheckResult,
    CheckStatus,
    ContractResult,
    RunResult,
)

BOUNDED_LOCAL_SCAN_ALLOWED = "RC_RUNTIME_BOUNDED_LOCAL_SCAN_ALLOWED"
BOUNDED_LOCAL_SCAN_REQUIRED = "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED"


def write_bounded_local_duckdb_fixture(
    path: Path,
    database_name: str = "warehouse.duckdb",
) -> None:
    _write_duckdb_key_safety_tables(
        _duckdb_module(),
        path / database_name,
        source_rows=(),
        target_rows=(),
    )


def write_project(path: Path, *, profile: str | None = None) -> None:
    profile_line = f"profile: {profile}\n" if profile is not None else ""
    (path / "recon_project.yml").write_text(
        f"""
name: ecommerce_recon
version: 0.1.0
config-version: 1
{profile_line}\
contract-paths:
  - contracts
target-path: target
report-path: reports
state-path: state
""".lstrip(),
        encoding="utf-8",
    )


def write_profiles(path: Path, content: str) -> None:
    profiles_path = path / "connections" / "profiles.yml"
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles_path.write_text(content.lstrip(), encoding="utf-8")


def write_duckdb_row_count_run_inputs(path: Path, database: Path) -> None:
    write_project(path, profile="local")
    write_profiles(
        path,
        yaml.safe_dump(
            {
                "profiles": {
                    "local": {
                        "target": "dev",
                        "outputs": {
                            "dev": {
                                "connections": {
                                    "warehouse": {
                                        "type": "duckdb",
                                        "database": str(database),
                                    }
                                }
                            }
                        },
                    }
                }
            },
            sort_keys=False,
        ),
    )
    write_compiled_checks(path, checks=[_compiled_check_payload(operations=row_count_plan())])
    write_compiled_contract(path)


def write_duckdb_key_safety_run_inputs(
    path: Path,
    database: Path,
    *,
    checks: list[dict[str, object]],
) -> None:
    write_project(path, profile="local")
    write_profiles(
        path,
        yaml.safe_dump(
            {
                "profiles": {
                    "local": {
                        "target": "dev",
                        "outputs": {
                            "dev": {
                                "connections": {
                                    "warehouse": {
                                        "type": "duckdb",
                                        "database": str(database),
                                    }
                                }
                            }
                        },
                    }
                }
            },
            sort_keys=False,
        ),
    )
    write_compiled_checks(path, checks=checks)
    write_compiled_contract(path, grain_keys=_grain_keys_from_checks(checks))


def write_compiled_checks(
    path: Path,
    *,
    contract_name: str = "customer_revenue",
    checks: list[dict[str, object]] | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> None:
    artifact_path = path / "target" / "compiled_checks" / f"{contract_name}.yml"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        yaml.safe_dump(
            _compiled_checks_payload(
                contract_name=contract_name,
                checks=checks,
                diagnostics=diagnostics,
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_compiled_contract(
    path: Path,
    *,
    contract_name: str = "customer_revenue",
    source_connection: str = "warehouse",
    target_connection: str = "warehouse",
    source_relation: str | None = "qa.source_customers",
    target_relation: str | None = "qa.target_customers",
    source_query: str | None = None,
    target_query: str | None = None,
    grain_keys: tuple[str, ...] = ("customer_id",),
) -> None:
    artifact_path = path / "target" / "compiled_contracts" / f"{contract_name}.yml"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        yaml.safe_dump(
            _compiled_contract_payload(
                contract_name=contract_name,
                source_connection=source_connection,
                target_connection=target_connection,
                source_relation=source_relation,
                target_relation=target_relation,
                source_query=source_query,
                target_query=target_query,
                grain_keys=grain_keys,
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )


class _FailingEngine:
    def run(
        self,
        artifacts: tuple[LoadedCompiledChecksArtifact, ...],
        *,
        run_id: str,
        started_at: str,
        finished_at: str,
        project_name: str | None = None,
        execution_context: CheckExecutionContext | None = None,
    ) -> RunResult:
        check_result = CheckResult(
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            name="row_count_diff",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=CheckStatus.FAIL,
            executed=True,
            source_value=10,
            target_value=11,
        )
        contract_result = ContractResult.from_check_results(
            contract_name="customer_revenue",
            check_results=(check_result,),
        )
        return RunResult.from_contract_results(
            run_id=run_id,
            project_name=project_name or artifacts[0].project_name,
            started_at=started_at,
            finished_at=finished_at,
            contract_results=(contract_result,),
        )


class _CapturingPassEngine:
    def __init__(self) -> None:
        self.execution_context: CheckExecutionContext | None = None

    def run(
        self,
        artifacts: tuple[LoadedCompiledChecksArtifact, ...],
        *,
        run_id: str,
        started_at: str,
        finished_at: str,
        project_name: str | None = None,
        execution_context: CheckExecutionContext | None = None,
    ) -> RunResult:
        self.execution_context = execution_context
        check_result = CheckResult(
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            name="row_count_diff",
            check_type="row_count_diff",
            contract_name="customer_revenue",
            status=CheckStatus.PASS,
            executed=True,
            source_value=10,
            target_value=10,
        )
        contract_result = ContractResult.from_check_results(
            contract_name="customer_revenue",
            check_results=(check_result,),
        )
        return RunResult.from_contract_results(
            run_id=run_id,
            project_name=project_name or artifacts[0].project_name,
            started_at=started_at,
            finished_at=finished_at,
            contract_results=(contract_result,),
        )


class _RaisingEngine:
    def run(
        self,
        artifacts: tuple[LoadedCompiledChecksArtifact, ...],
        *,
        run_id: str,
        started_at: str,
        finished_at: str,
        project_name: str | None = None,
        execution_context: CheckExecutionContext | None = None,
    ) -> RunResult:
        raise RuntimeError("super-secret database error")


def _compiled_checks_payload(
    *,
    contract_name: str = "customer_revenue",
    checks: list[dict[str, object]] | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "artifact_type": "compiled_checks",
        "artifact_version": 1,
        "recon_version": "0.0.test",
        "generated_at": "2026-05-23T12:00:00Z",
        "invocation_id": "01JTESTINVOCATION0000000000",
        "project": {"name": "ecommerce_recon", "version": "0.1.0"},
        "contract": {
            "id": f"contract.ecommerce_recon.{contract_name}",
            "name": contract_name,
            "source_file": f"contracts/{contract_name}.yml",
        },
        "checks": checks if checks is not None else [_compiled_check_payload()],
        "diagnostics": diagnostics if diagnostics is not None else [],
    }


def _compiled_check_payload(
    *,
    check_id: str = "check.ecommerce_recon.customer_revenue.row_count_diff",
    name: str = "row_count_diff",
    check_type: str = "row_count_diff",
    operations: list[dict[str, object]] | None = None,
    required_capabilities: list[str] | None = None,
    rendering: dict[str, object] | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    resolved_required_capabilities = (
        required_capabilities if required_capabilities is not None else ["row_count"]
    )
    return {
        "id": check_id,
        "name": name,
        "type": check_type,
        "origin": {"kind": "check_pack", "name": "recon_core.basic_equivalence"},
        "identity": {"kind": "none", "keys": []},
        "requirements": {
            "requires_grain_keys": False,
            "requires_non_null_grain": False,
            "requires_unique_grain": False,
            "requires_cdc_keys": False,
            "required_columns": [],
            "required_metrics": [],
            "required_capabilities": resolved_required_capabilities,
        },
        "sampling": {"mode": "full"},
        "tolerance": None,
        "prerequisites": [],
        "blocking_policy": {"on_prerequisite_failure": "skipped"},
        "plan": {
            "id": f"plan.ecommerce_recon.customer_revenue.{name}",
            "operations": operations
            if operations is not None
            else [{"type": "row_count", "side": "source"}],
            "required_capabilities": resolved_required_capabilities,
        },
        "rendering": rendering
        if rendering is not None
        else {"status": "not_rendered", "sql_paths": []},
        "diagnostics": diagnostics if diagnostics is not None else [],
    }


def _compiled_contract_payload(
    *,
    contract_name: str,
    source_connection: str,
    target_connection: str,
    source_relation: str | None,
    target_relation: str | None,
    source_query: str | None = None,
    target_query: str | None = None,
    grain_keys: tuple[str, ...],
) -> dict[str, object]:
    source: dict[str, object] = {"connection": source_connection}
    if source_relation is not None:
        source["relation"] = source_relation
    if source_query is not None:
        source["query"] = source_query
    target: dict[str, object] = {"connection": target_connection}
    if target_relation is not None:
        target["relation"] = target_relation
    if target_query is not None:
        target["query"] = target_query
    return {
        "artifact_type": "compiled_contract",
        "artifact_version": 1,
        "recon_version": "0.0.test",
        "generated_at": "2026-05-23T12:00:00Z",
        "invocation_id": "01JTESTINVOCATION0000000000",
        "project": {"name": "ecommerce_recon", "version": "0.1.0"},
        "contract": {
            "id": f"contract.ecommerce_recon.{contract_name}",
            "name": contract_name,
            "source_file": f"contracts/{contract_name}.yml",
        },
        "identity": {"grain": {"keys": list(grain_keys)}, "cdc": {"keys": []}},
        "source": source,
        "target": target,
        "columns": [],
        "metrics": [],
        "checks": [],
        "diagnostics": [],
    }


def _grain_keys_from_checks(checks: list[dict[str, object]]) -> tuple[str, ...]:
    for check in checks:
        plan = check.get("plan")
        if not isinstance(plan, dict):
            continue
        operations = plan.get("operations")
        if not isinstance(operations, list):
            continue
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            identity = operation.get("identity")
            if not isinstance(identity, dict):
                continue
            keys = identity.get("keys")
            if isinstance(keys, list) and all(isinstance(key, str) for key in keys):
                return tuple(keys)
    return ("customer_id",)


def row_count_plan() -> list[dict[str, object]]:
    return [
        {"type": "row_count", "side": "source"},
        {"type": "row_count", "side": "target"},
        {"type": "compare_counts"},
    ]


def _key_safety_check_payload(
    *,
    check_id: str = "check.ecommerce_recon.customer_revenue.missing_keys",
    name: str = "missing_keys",
    check_type: str = "missing_keys",
    operations: list[dict[str, object]] | None = None,
    required_capabilities: list[str] | None = None,
    rendering: dict[str, object] | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    resolved_operations = (
        operations if operations is not None else [_key_diff_operation("source_minus_target")]
    )
    resolved_required_capabilities = (
        required_capabilities if required_capabilities is not None else ["key_diff"]
    )
    return _compiled_check_payload(
        check_id=check_id,
        name=name,
        check_type=check_type,
        operations=resolved_operations,
        required_capabilities=resolved_required_capabilities,
        rendering=rendering,
        diagnostics=diagnostics,
    )


def _key_safety_payload_for(
    check_type: str,
    *,
    keys: tuple[str, ...] = ("customer_id",),
) -> dict[str, object]:
    if check_type == "null_source_keys":
        operation = _null_key_operation("source", keys=keys)
        required_capabilities = ["null_key"]
    elif check_type == "null_target_keys":
        operation = _null_key_operation("target", keys=keys)
        required_capabilities = ["null_key"]
    elif check_type == "duplicate_source_keys":
        operation = _duplicate_key_operation("source", keys=keys)
        required_capabilities = ["duplicate_key"]
    elif check_type == "duplicate_target_keys":
        operation = _duplicate_key_operation("target", keys=keys)
        required_capabilities = ["duplicate_key"]
    elif check_type == "missing_keys":
        operation = _key_diff_operation("source_minus_target", keys=keys)
        required_capabilities = ["key_diff"]
    elif check_type == "extra_keys":
        operation = _key_diff_operation("target_minus_source", keys=keys)
        required_capabilities = ["key_diff"]
    else:
        raise AssertionError(f"Unsupported key-safety test check type: {check_type}")
    return _key_safety_check_payload(
        check_id=f"check.ecommerce_recon.customer_revenue.{check_type}",
        name=check_type,
        check_type=check_type,
        operations=[operation],
        required_capabilities=required_capabilities,
    )


def _all_key_safety_checks(
    *,
    keys: tuple[str, ...] = ("customer_id",),
) -> list[dict[str, object]]:
    return [
        _key_safety_payload_for(check_type, keys=keys)
        for check_type in (
            "null_source_keys",
            "null_target_keys",
            "duplicate_source_keys",
            "duplicate_target_keys",
            "missing_keys",
            "extra_keys",
        )
    ]


def _key_diff_operation(
    direction: str,
    *,
    keys: tuple[str, ...] = ("customer_id",),
) -> dict[str, object]:
    return {
        "type": "key_diff",
        "direction": direction,
        "identity": {"kind": "grain", "keys": list(keys)},
    }


def _null_key_operation(
    side: str,
    *,
    keys: tuple[str, ...] = ("customer_id",),
) -> dict[str, object]:
    return {
        "type": "null_key",
        "side": side,
        "identity": {"kind": "grain", "keys": list(keys)},
    }


def _duplicate_key_operation(
    side: str,
    *,
    keys: tuple[str, ...] = ("customer_id",),
) -> dict[str, object]:
    return {
        "type": "duplicate_key",
        "side": side,
        "identity": {"kind": "grain", "keys": list(keys)},
    }


def _duckdb_module() -> Any:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            return importlib.import_module("duckdb")
        except ImportError:
            pytest.fail(
                "DuckDB run-service execution tests are required in this environment. "
                "Install with `.[dev,duckdb]`.",
                pytrace=False,
            )

    return pytest.importorskip("duckdb")


def _write_duckdb_row_count_tables(
    duckdb: Any,
    database: Path,
    *,
    source_rows: tuple[tuple[int], ...],
    target_rows: tuple[tuple[int], ...],
    create_target: bool = True,
) -> None:
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create schema qa")
        connection.execute("create table qa.source_customers(id integer)")
        if source_rows:
            connection.executemany("insert into qa.source_customers values (?)", source_rows)
        if create_target:
            connection.execute("create table qa.target_customers(id integer)")
            if target_rows:
                connection.executemany("insert into qa.target_customers values (?)", target_rows)
    finally:
        connection.close()


def _write_duckdb_key_safety_tables(
    duckdb: Any,
    database: Path,
    *,
    source_rows: tuple[tuple[object, ...], ...],
    target_rows: tuple[tuple[object, ...], ...],
    source_column_definitions: tuple[str, ...] = ("customer_id integer", "region varchar"),
    target_column_definitions: tuple[str, ...] = ("customer_id integer", "region varchar"),
) -> None:
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create schema qa")
        connection.execute(
            f"create table qa.source_customers({', '.join(source_column_definitions)})"
        )
        connection.execute(
            f"create table qa.target_customers({', '.join(target_column_definitions)})"
        )
        _insert_duckdb_rows(connection, "qa.source_customers", source_rows)
        _insert_duckdb_rows(connection, "qa.target_customers", target_rows)
    finally:
        connection.close()


def _write_mixed_case_duckdb_key_safety_tables(
    duckdb: Any,
    database: Path,
    *,
    source_rows: tuple[tuple[object, ...], ...],
    target_rows: tuple[tuple[object, ...], ...],
) -> None:
    connection = duckdb.connect(str(database))
    try:
        connection.execute('create schema "Qa"')
        connection.execute(
            'create table "Qa"."Source_Customers"("Customer_ID" integer, "Region" varchar)'
        )
        connection.execute(
            'create table "Qa"."Target_Customers"("Customer_ID" integer, "Region" varchar)'
        )
        _insert_duckdb_rows(connection, '"Qa"."Source_Customers"', source_rows)
        _insert_duckdb_rows(connection, '"Qa"."Target_Customers"', target_rows)
    finally:
        connection.close()


def _insert_duckdb_rows(
    connection: Any,
    relation_name: str,
    rows: tuple[tuple[object, ...], ...],
) -> None:
    if not rows:
        return
    placeholders = ", ".join("?" for _ in rows[0])
    connection.executemany(f"insert into {relation_name} values ({placeholders})", rows)


def _assert_no_runtime_outputs(path: Path) -> None:
    assert not (path / "target" / "run_results.json").exists()
    assert not (path / "target" / "failures").exists()
    assert not (path / "target" / "compiled_sql").exists()
    assert not (path / "reports").exists()
    assert not (path / "state").exists()


def _service_result_text(result: object) -> str:
    fields: list[str] = []
    message = getattr(result, "message", None)
    if message is not None:
        fields.append(str(message))
    for diagnostic in getattr(result, "diagnostics", ()):
        fields.extend(
            str(value)
            for value in (
                diagnostic.code,
                diagnostic.message,
                diagnostic.hint,
                diagnostic.resource_type,
                diagnostic.resource_name,
                diagnostic.path,
                diagnostic.line,
                diagnostic.column,
            )
            if value is not None
        )
    return "\n".join(fields)


class RecordingDuckDbFactory:
    def __init__(
        self,
        *,
        result: QueryResult | None = None,
        results: tuple[QueryResult, ...] | None = None,
        capabilities: AdapterCapabilities | None = None,
        capabilities_error: Exception | None = None,
        connect_error: Exception | None = None,
        execute_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.result = result
        self.results = results
        self.capabilities = capabilities
        self.capabilities_error = capabilities_error
        self.connect_error = connect_error
        self.execute_error = execute_error
        self.close_error = close_error
        self.adapters: list[RecordingDuckDbAdapter] = []

    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        adapter = RecordingDuckDbAdapter(
            connection=connection,
            result=self.result,
            results=self.results,
            capabilities=self.capabilities,
            capabilities_error=self.capabilities_error,
            connect_error=self.connect_error,
            execute_error=self.execute_error,
            close_error=self.close_error,
        )
        self.adapters.append(adapter)
        return AdapterResolutionResult(adapter=adapter)


class RecordingWarehouseFactory:
    def __init__(self, *, capabilities: AdapterCapabilities | None = None) -> None:
        self.capabilities = capabilities
        self.adapters: list[RecordingWarehouseAdapter] = []

    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        adapter = RecordingWarehouseAdapter(
            connection=connection,
            result=None,
            results=None,
            capabilities=self.capabilities,
            capabilities_error=None,
            connect_error=None,
            execute_error=None,
            close_error=None,
        )
        self.adapters.append(adapter)
        return AdapterResolutionResult(adapter=adapter)


class RecordingDuckDbAdapter(BaseAdapter):
    adapter_type = "duckdb"
    adapter_version = "test"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def __init__(
        self,
        *,
        connection: ConnectionConfig,
        result: QueryResult | None,
        results: tuple[QueryResult, ...] | None,
        capabilities: AdapterCapabilities | None,
        capabilities_error: Exception | None,
        connect_error: Exception | None,
        execute_error: Exception | None,
        close_error: Exception | None,
    ) -> None:
        super().__init__(connection=connection)
        default_result = result or QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((1, 1, 0),),
            row_count=1,
        )
        self.results = list(results) if results is not None else [default_result]
        self._capabilities = capabilities or AdapterCapabilities(
            {
                "row_count": CapabilitySupport.FULL,
                "cte_support": CapabilitySupport.FULL,
                "key_diff": CapabilitySupport.FULL,
                "null_key": CapabilitySupport.FULL,
                "duplicate_key": CapabilitySupport.FULL,
            }
        )
        self.capabilities_error = capabilities_error
        self.connect_error = connect_error
        self.execute_error = execute_error
        self.close_error = close_error
        self.connect_count = 0
        self.close_count = 0
        self.connected = False
        self.queries: list[str] = []

    def connect(self) -> None:
        self.connect_count += 1
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True

    def close(self) -> None:
        self.close_count += 1
        if self.close_error is not None:
            raise self.close_error
        self.connected = False

    def execute(self, query: str) -> QueryResult:
        self.queries.append(query)
        if self.execute_error is not None:
            raise self.execute_error
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]

    def capabilities(self) -> AdapterCapabilities:
        if self.capabilities_error is not None:
            raise self.capabilities_error
        return self._capabilities


class RecordingWarehouseAdapter(RecordingDuckDbAdapter):
    adapter_type = "warehouse_test"
