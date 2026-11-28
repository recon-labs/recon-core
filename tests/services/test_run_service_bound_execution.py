"""Project-run native binding and check-local lifecycle proof."""

import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

import recon_core.services.run as run_service_module
from recon_core.adapters import AdapterRegistry, AdapterResolutionResult, ConnectionConfig
from recon_core.adapters._local_resource_observation import _LocalObservation
from recon_core.adapters.duckdb import DuckDbAdapter
from recon_core.adapters.duckdb import _bound_execution as binding
from recon_core.artifacts import CompiledContractLoader
from recon_core.check_engine import CheckEngine, CheckStatus, RunResult
from recon_core.cli.main import main
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services import RunService
from recon_core.services.results import ExitCategory
from tests.services._run_service_fixtures import (
    _compiled_check_payload,
    _duckdb_module,
    _key_safety_payload_for,
    _write_duckdb_key_safety_tables,
    _write_duckdb_row_count_tables,
    row_count_plan,
    write_compiled_checks,
    write_compiled_contract,
    write_duckdb_row_count_run_inputs,
)


@pytest.mark.regression_capture("project-binding-check-local-cleanup")
def test_native_row_count_uses_owned_read_only_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    before = database.read_bytes()

    def forbidden(self: DuckDbAdapter) -> None:
        pytest.fail("Legacy writable connect must not run.")

    monkeypatch.setattr(DuckDbAdapter, "connect", forbidden)
    result = RunService(start_path=tmp_path).execute()
    assert result.exit_category is ExitCategory.SUCCESS
    assert database.read_bytes() == before
    writer = duckdb.connect(str(database))
    writer.close()


@pytest.mark.regression_capture("project-binding-check-local-cleanup")
def test_row_count_refuses_view_scope(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    connection = duckdb.connect(str(database))
    try:
        connection.execute("create schema qa")
        connection.execute("create table qa.source_customers as select 1 as id")
        connection.execute("create view qa.target_customers as select * from qa.source_customers")
    finally:
        connection.close()
    write_duckdb_row_count_run_inputs(tmp_path, database)
    result = RunService(start_path=tmp_path).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


@pytest.mark.regression_capture("project-binding-check-local-cleanup")
def test_row_count_missing_file_does_not_create_database(tmp_path: Path) -> None:
    database = tmp_path / "absent.duckdb"
    write_duckdb_row_count_run_inputs(tmp_path, database)
    result = RunService(start_path=tmp_path).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert not database.exists()
    assert "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED" in {
        diagnostic.code for diagnostic in result.diagnostics
    }


class _CapturingEngine(CheckEngine):
    result: RunResult | None = None

    def run(self, *args: Any, **kwargs: Any) -> RunResult:
        self.result = super().run(*args, **kwargs)
        return self.result


@pytest.mark.parametrize(
    ("uncertain_close", "reported", "raises"),
    [(False, True, False), (True, True, False), (True, False, False), (True, False, True)],
)
@pytest.mark.regression_capture("project-binding-check-local-cleanup")
@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
def test_cleanup_failure_is_check_local_or_stops_native_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    uncertain_close: bool,
    reported: bool,
    raises: bool,
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    independent = tmp_path / "independent.duckdb"
    _write_duckdb_row_count_tables(duckdb, independent, source_rows=((3,),), target_rows=((4,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    checks = [
        _compiled_check_payload(
            check_id=f"check.ecommerce_recon.customer_revenue.count_{suffix}",
            name=f"count_{suffix}",
            operations=row_count_plan(),
        )
        for suffix in ("first", "dependent", "unrelated")
    ]
    checks[1]["prerequisites"] = [checks[0]["id"]]
    checks.append(
        _compiled_check_payload(
            check_id="check.ecommerce_recon.customer_revenue.malformed",
            name="malformed",
            operations=[{"type": "row_count", "side": "source"}],
        )
    )
    write_compiled_checks(tmp_path, checks=checks)
    profile_path = tmp_path / "connections" / "profiles.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    connections = profile["profiles"]["local"]["outputs"]["dev"]["connections"]
    connections["alias"] = dict(connections["warehouse"])
    connections["independent"] = dict(connections["warehouse"], database=str(independent))
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    alias = _compiled_check_payload(
        check_id="check.ecommerce_recon.other_revenue.row_count_diff",
        operations=row_count_plan(),
    )
    alias["plan"] = {
        "id": "plan.ecommerce_recon.other_revenue.row_count_diff",
        "operations": row_count_plan(),
        "required_capabilities": ["row_count"],
    }
    write_compiled_checks(tmp_path, contract_name="other_revenue", checks=[alias])
    write_compiled_contract(
        tmp_path,
        contract_name="other_revenue",
        source_connection="alias",
        target_connection="alias",
    )
    separate = _compiled_check_payload(
        check_id="check.ecommerce_recon.zeta_revenue.row_count_diff",
        operations=row_count_plan(),
    )
    separate["plan"] = {
        "id": "plan.ecommerce_recon.zeta_revenue.row_count_diff",
        "operations": row_count_plan(),
        "required_capabilities": ["row_count"],
    }
    write_compiled_checks(tmp_path, contract_name="zeta_revenue", checks=[separate])
    write_compiled_contract(
        tmp_path,
        contract_name="zeta_revenue",
        source_connection="independent",
        target_connection="independent",
    )
    original_open = binding._OwnedDuckDbSession.open
    original_close = binding._OwnedDuckDbSession.close
    opened: list[binding._OwnedDuckDbSession] = []

    def record_open(session: binding._OwnedDuckDbSession) -> None:
        opened.append(session)
        original_open(session)

    def injected_close(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        diagnostics = original_close(session)
        if session is opened[0]:
            # Real release keeps the synthetic fixture safe; inject the
            # uncertainty reported to the runner, not a real leaked handle.
            if raises:
                raise RuntimeError("private-close-exception")
            session._released = not uncertain_close
            if not reported:
                return diagnostics
            return diagnostics + (
                Diagnostic(
                    code="RC_ADAPTER_CLOSE_FAILED",
                    severity=DiagnosticSeverity.ERROR,
                    message="Synthetic cleanup failure.",
                ),
            )
        return diagnostics

    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", record_open)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "close", injected_close)
    engine = _CapturingEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    contracts = {contract.contract_name: contract for contract in engine.result.contract_results}
    first, dependent, unrelated, malformed = contracts["customer_revenue"].check_results
    aliased = contracts["other_revenue"].check_results[0]
    separate_result = contracts["zeta_revenue"].check_results[0]
    assert separate_result.status is CheckStatus.PASS and separate_result.executed
    assert malformed.status is CheckStatus.NOT_EXECUTABLE and not malformed.executed
    assert first.status is CheckStatus.ERROR
    assert "RC_ADAPTER_CLOSE_FAILED" in {d.code for d in first.diagnostics}
    assert not first.executed
    assert first.source_value is None and first.target_value is None
    assert "private-close-exception" not in repr(result.diagnostics)
    assert dependent.status is CheckStatus.BLOCKED
    assert dependent.blocked_by == (first.check_id,)
    if uncertain_close:
        assert unrelated.status is CheckStatus.ERROR
        assert "RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE" in {
            diagnostic.code for diagnostic in unrelated.diagnostics
        }
        assert aliased.status is CheckStatus.ERROR and not aliased.executed
        assert "RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE" in {d.code for d in aliased.diagnostics}
        assert len(opened) == 2
    else:
        assert unrelated.status is CheckStatus.PASS
        assert aliased.status is CheckStatus.PASS and aliased.executed
        assert len(opened) == 4
    assert opened[-1]._identity.path == independent.resolve()
    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", original_open)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "close", original_close)
    repeated = RunService(start_path=tmp_path)._execute_invocation()
    assert repeated.run_result is not None
    assert repeated.scope_facts.complete is True
    repeated_checks = {
        check.name: check for check in repeated.run_result.contract_results[0].check_results
    }
    assert repeated_checks["malformed"].status is CheckStatus.NOT_EXECUTABLE
    assert all(
        repeated_checks[name].status is CheckStatus.PASS
        for name in ("count_first", "count_dependent", "count_unrelated")
    )
    assert all(
        contract.check_results[0].status is CheckStatus.PASS
        for contract in repeated.run_result.contract_results[1:]
    )


@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_actual_session_and_aliases_writer_conflict(tmp_path: Path, read_only: bool) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    existing = duckdb.connect(str(database), read_only=read_only)
    engine = _CapturingEngine()
    try:
        result = RunService(start_path=tmp_path, engine=engine).execute()
        assert engine.result is not None
        check = engine.result.contract_results[0].check_results[0]
        if read_only:
            assert result.exit_category is ExitCategory.SUCCESS
            assert check.status is CheckStatus.PASS
        else:
            assert result.exit_category is ExitCategory.RUNTIME_ERROR
            assert check.status is CheckStatus.ERROR
            assert "RC_ADAPTER_CONNECTION_FAILED" in {d.code for d in check.diagnostics}
            assert not check.executed and check.source_value is None
        assert existing.execute("select count(*) from qa.source_customers").fetchall() == [(1,)]
    finally:
        existing.close()
    assert RunService(start_path=tmp_path).execute().exit_category is ExitCategory.SUCCESS


@pytest.mark.regression_capture("project-binding-check-local-cleanup")
def test_outside_project_row_count_refuses_without_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    database = tmp_path / "outside.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(project, database)

    def forbidden(session: binding._OwnedDuckDbSession) -> None:
        pytest.fail("Outside-project file must not be opened.")

    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", forbidden)
    engine = _CapturingEngine()
    result = RunService(start_path=project, engine=engine).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    check = engine.result.contract_results[0].check_results[0]
    assert check.status is CheckStatus.NOT_EXECUTABLE
    assert "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED" in {d.code for d in check.diagnostics}


@pytest.mark.parametrize("blocker", ["shape", "query", "rendering", "prerequisite"])
@pytest.mark.regression_capture("project-binding-check-local-cleanup")
def test_preflight_never_opens_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, blocker: str
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    check = _compiled_check_payload(
        operations=(
            row_count_plan() if blocker != "shape" else [{"type": "row_count", "side": "source"}]
        ),
        rendering={"status": "blocked", "sql_paths": []} if blocker == "rendering" else None,
        diagnostics=(
            [
                {
                    "code": "RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS",
                    "severity": "error",
                    "message": "Synthetic rendering blocker.",
                }
            ]
            if blocker == "rendering"
            else None
        ),
    )
    if blocker == "query":
        write_compiled_contract(tmp_path, source_relation=None, source_query="select 1")
    elif blocker == "prerequisite":
        check["prerequisites"] = ["check.ecommerce_recon.customer_revenue.absent"]
    write_compiled_checks(tmp_path, checks=[check])

    def forbidden(session: binding._OwnedDuckDbSession) -> None:
        pytest.fail("A preflight-blocked check must not open a native session.")

    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", forbidden)
    engine = _CapturingEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    outcome = engine.result.contract_results[0].check_results[0]
    assert not outcome.executed
    expected = {
        "shape": CheckStatus.NOT_EXECUTABLE,
        "query": CheckStatus.NOT_EXECUTABLE,
        "rendering": CheckStatus.ERROR,
        "prerequisite": CheckStatus.BLOCKED,
    }
    assert outcome.status is expected[blocker]


@pytest.mark.parametrize("failure", ["open", "query"])
def test_mixed_native_failure_preserves_unrelated_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    database = tmp_path / "warehouse.duckdb"
    other = tmp_path / "other.duckdb"
    duckdb = _duckdb_module()
    for path in (database, other):
        _write_duckdb_row_count_tables(duckdb, path, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    profile_path = tmp_path / "connections" / "profiles.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["profiles"]["local"]["outputs"]["dev"]["connections"]["other"] = {
        "type": "duckdb",
        "database": str(other),
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    first = _compiled_check_payload(operations=row_count_plan())
    dependent = _compiled_check_payload(
        check_id="check.ecommerce_recon.customer_revenue.dependent",
        name="dependent",
        operations=row_count_plan(),
    )
    dependent["prerequisites"] = [first["id"]]
    write_compiled_checks(tmp_path, checks=[first, dependent])
    unrelated = _compiled_check_payload(
        check_id="check.ecommerce_recon.other_revenue.row_count_diff",
        operations=row_count_plan(),
    )
    plan: Any = unrelated["plan"]
    plan["id"] = "plan.ecommerce_recon.other_revenue.row_count_diff"
    write_compiled_checks(tmp_path, contract_name="other_revenue", checks=[unrelated])
    write_compiled_contract(
        tmp_path,
        contract_name="other_revenue",
        source_connection="other",
        target_connection="other",
    )
    opened: list[Path] = []
    original_open = binding._OwnedDuckDbSession.open
    original_read = binding._OwnedDuckDbSession._read_bound_query

    def record_open(session: binding._OwnedDuckDbSession) -> None:
        opened.append(session._identity.path)
        if session._identity.path == database and failure == "open":
            raise binding._BoundSessionError(
                "RC_ADAPTER_CONNECTION_FAILED", "Synthetic read-only open failure."
            )
        original_open(session)

    def read(
        session: binding._OwnedDuckDbSession,
        lease: binding._BindingLease,
        scope: binding._BindingScope,
        query: str,
    ) -> Any:
        if session._identity.path == database and failure == "query":
            raise RuntimeError("private-native-query-error")
        return original_read(session, lease, scope, query)

    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", record_open)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "_read_bound_query", read)
    engine = _CapturingEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    outcomes = {
        check.check_id: check
        for contract in engine.result.contract_results
        for check in contract.check_results
    }
    first_result = outcomes[str(first["id"])]
    dependent_result = outcomes[str(dependent["id"])]
    unrelated_result = outcomes[str(unrelated["id"])]
    assert first_result.status is CheckStatus.ERROR and not first_result.executed
    assert first_result.source_value is None
    assert dependent_result.status is CheckStatus.BLOCKED
    assert dependent_result.blocked_by == (first_result.check_id,)
    assert unrelated_result.status is CheckStatus.PASS and unrelated_result.executed
    assert opened.count(database) == opened.count(other) == 1
    assert "private-native-query-error" not in repr(result)


@pytest.mark.parametrize(
    "failure", ["open", "query", "uncertain_close", "close_exception", "query_and_close_exception"]
)
@pytest.mark.regression_capture("project-binding-check-local-cleanup")
def test_native_failure_isolation_across_database_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    duckdb = _duckdb_module()
    first_file = tmp_path / "private-first.duckdb"
    other_file = tmp_path / "private-other.duckdb"
    for database in (first_file, other_file):
        _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, first_file)
    profile_path = tmp_path / "connections" / "profiles.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    connections = profile["profiles"]["local"]["outputs"]["dev"]["connections"]
    connections["private-other"] = {"type": "duckdb", "database": str(other_file)}
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    first = _compiled_check_payload(operations=row_count_plan())
    dependent = _compiled_check_payload(
        check_id="check.ecommerce_recon.customer_revenue.dependent",
        name="dependent",
        operations=row_count_plan(),
    )
    dependent["prerequisites"] = [first["id"]]
    write_compiled_checks(tmp_path, checks=[first, dependent])
    other = _compiled_check_payload(
        check_id="check.ecommerce_recon.other_revenue.row_count_diff",
        operations=row_count_plan(),
    )
    other["plan"] = {
        "id": "plan.ecommerce_recon.other_revenue.row_count_diff",
        "operations": row_count_plan(),
        "required_capabilities": ["row_count"],
    }
    write_compiled_checks(tmp_path, contract_name="other_revenue", checks=[other])
    write_compiled_contract(
        tmp_path,
        contract_name="other_revenue",
        source_connection="private-other",
        target_connection="private-other",
    )
    before = {path: path.read_bytes() for path in (first_file, other_file)}
    opened: list[binding._OwnedDuckDbSession] = []
    closed: list[binding._OwnedDuckDbSession] = []
    reads: list[binding._OwnedDuckDbSession] = []
    real_open = binding._OwnedDuckDbSession.open
    real_read = binding._OwnedDuckDbSession._read_bound_query
    real_close = binding._OwnedDuckDbSession.close

    def open_session(session: binding._OwnedDuckDbSession) -> None:
        opened.append(session)
        if len(opened) == 1 and failure == "open":
            raise binding._BoundSessionError(
                "RC_ADAPTER_CONNECTION_FAILED",
                "Read-only execution session could not be opened.",
            )
        real_open(session)

    def read(
        session: binding._OwnedDuckDbSession,
        lease: binding._BindingLease,
        scope: binding._BindingScope,
        query: str,
    ) -> Any:
        reads.append(session)
        if session is opened[0] and failure in {"query", "query_and_close_exception"}:
            raise RuntimeError("private-native-query-error")
        return real_read(session, lease, scope, query)

    def close_session(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        closed.append(session)
        diagnostics = real_close(session)
        if session is opened[0] and failure in {"close_exception", "query_and_close_exception"}:
            raise RuntimeError("private-close-exception")
        if session is opened[0] and failure == "uncertain_close":
            # Inject uncertainty after actual release so the test cannot leak a handle.
            session._released = False
            return diagnostics + (
                Diagnostic(
                    code="RC_ADAPTER_CLOSE_FAILED",
                    severity=DiagnosticSeverity.ERROR,
                    message="Read-only execution session cleanup failed.",
                ),
            )
        return diagnostics

    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", open_session)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "_read_bound_query", read)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "close", close_session)
    engine = _CapturingEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    contracts = {contract.contract_name: contract for contract in engine.result.contract_results}
    failed, blocked = contracts["customer_revenue"].check_results
    unrelated = contracts["other_revenue"].check_results[0]
    assert failed.status is CheckStatus.ERROR and not failed.executed
    assert failed.source_value is None and failed.target_value is None
    expected = {
        "open": "RC_ADAPTER_CONNECTION_FAILED",
        "query": "RC_ADAPTER_QUERY_FAILED",
        "uncertain_close": "RC_ADAPTER_CLOSE_FAILED",
        "close_exception": "RC_ADAPTER_CLOSE_FAILED",
        "query_and_close_exception": "RC_ADAPTER_CLOSE_FAILED",
    }
    assert expected[failure] in {d.code for d in failed.diagnostics}
    if failure == "query_and_close_exception":
        assert "RC_ADAPTER_QUERY_FAILED" in {d.code for d in failed.diagnostics}
    assert blocked.status is CheckStatus.BLOCKED
    assert blocked.blocked_by == (failed.check_id,)
    assert blocked.reason_code is not None and blocked.reason_code.value == "prerequisite_error"
    assert not blocked.executed
    assert opened == closed
    # An uncertain close must latch only the affected file/context, not
    # independent databases. The same-context alias test retains refusal.
    assert unrelated.status is CheckStatus.PASS and unrelated.executed
    assert unrelated.source_value == unrelated.target_value == 1
    assert len(opened) == 2
    assert reads == (opened[1:] if failure == "open" else opened)
    public = repr(engine.result.to_dict()) + repr(result.diagnostics)
    for token in (
        "private-first",
        "private-other",
        "private-native-query-error",
        "private-close-exception",
    ):
        assert token not in public
    assert all(path.read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("primary", ["data_fail", "scope_refusal", "query_error"])
@pytest.mark.parametrize("cleanup", ["rollback", "close", "both", "raise", "release_raise"])
@pytest.mark.regression_capture("project-binding-check-local-cleanup")
def test_primary_outcome_retained_on_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primary: str, cleanup: str
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,), (2,)), target_rows=((1,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    if primary == "scope_refusal":
        write_compiled_contract(tmp_path, target_relation="qa.absent")
    if primary == "query_error":

        def fail_read(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("private-primary-query-error")

        monkeypatch.setattr(binding._OwnedDuckDbSession, "_read_bound_query", fail_read)
    real_close = binding._OwnedDuckDbSession.close
    release_faults: list[binding._OwnedDuckDbSession] = []
    original_released = binding._OwnedDuckDbSession.released.fget
    assert original_released is not None

    def released(session: binding._OwnedDuckDbSession) -> bool:
        if session in release_faults:
            raise RuntimeError("private-release-proof-exception")
        return bool(original_released(session))

    def close_session(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        diagnostics = real_close(session)
        if cleanup == "raise":
            raise RuntimeError("private-close-exception")
        messages = []
        if cleanup == "release_raise":
            release_faults.append(session)
        if cleanup in {"rollback", "both", "release_raise"}:
            messages.append("Read-only transaction cleanup failed.")
        if cleanup in {"close", "both"}:
            messages.append("Read-only execution session cleanup failed.")
            session._released = False
        return diagnostics + tuple(
            Diagnostic(code="RC_ADAPTER_CLOSE_FAILED", severity=DiagnosticSeverity.ERROR, message=m)
            for m in messages
        )

    monkeypatch.setattr(binding._OwnedDuckDbSession, "close", close_session)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "released", property(released))
    engine = _CapturingEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert engine.result is not None
    check = engine.result.contract_results[0].check_results[0]
    assert check.status is CheckStatus.ERROR and not check.executed
    assert check.reason_code is None and check.blocked_by == ()
    assert check.source_value is check.target_value is check.diff_value is None
    assert check.failure_count is None and check.artifact_refs == check.sink_refs == ()
    assert sum(d.code == "RC_ADAPTER_CLOSE_FAILED" for d in check.diagnostics) == (
        2 if cleanup in {"both", "release_raise"} else 1
    )
    if primary == "scope_refusal":
        assert "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED" in {d.code for d in check.diagnostics}
    elif primary == "query_error":
        assert "RC_ADAPTER_QUERY_FAILED" in {d.code for d in check.diagnostics}
        assert "private-primary-query-error" not in repr(result.diagnostics)
    else:
        assert any("failing outcome before cleanup failed" in d.message for d in check.diagnostics)
        assert "RC_RUNTIME_CHECK_FAILURE_BEFORE_CLEANUP" in {d.code for d in check.diagnostics}
        assert "RC_ADAPTER_QUERY_FAILED" not in {d.code for d in check.diagnostics}
    assert "private-close-exception" not in repr(result.diagnostics)
    assert "private-release-proof-exception" not in repr(result.diagnostics)


@pytest.mark.parametrize("family", ["row", "key"])
@pytest.mark.parametrize("mismatch", ["database", "name", "mutated"])
@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_legacy_family_wrong_factory_binding_never_opens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, family: str, mismatch: str
) -> None:
    database = tmp_path / "warehouse.duckdb"
    wrong = tmp_path / "private-wrong.duckdb"
    _write_duckdb_key_safety_tables(
        _duckdb_module(), database, source_rows=((1, "x"),), target_rows=((1, "x"),)
    )
    write_duckdb_row_count_run_inputs(tmp_path, database)
    if family == "key":
        write_compiled_checks(tmp_path, checks=[_key_safety_payload_for("missing_keys")])

    def factory(connection: ConnectionConfig) -> AdapterResolutionResult:
        if mismatch == "mutated":
            connection.config["database"] = str(wrong)
        else:
            connection = ConnectionConfig(
                name="private-wrong-name" if mismatch == "name" else connection.name,
                type=connection.type,
                config={
                    **connection.config,
                    "database": str(wrong if mismatch == "database" else database),
                },
            )
        return AdapterResolutionResult(adapter=DuckDbAdapter(connection=connection))

    def forbidden(session: binding._OwnedDuckDbSession) -> None:
        pytest.fail("A mismatched factory binding must not open a native session.")

    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", forbidden)
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    result = RunService(start_path=tmp_path, adapter_registry=registry).execute()
    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert "RC_ADAPTER_METADATA_INVALID" in {d.code for d in result.diagnostics}
    assert "private-wrong" not in repr(result.diagnostics)
    assert not wrong.exists()


@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_project_run_never_borrows_or_closes_supplied_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    borrowed = duckdb.connect(str(database), read_only=True)
    adapters: list[DuckDbAdapter] = []

    def factory(connection: ConnectionConfig) -> AdapterResolutionResult:
        adapter = DuckDbAdapter(connection=connection)
        adapter._connection = borrowed
        adapters.append(adapter)
        return AdapterResolutionResult(adapter=adapter)

    def forbidden(self: DuckDbAdapter, *args: Any, **kwargs: Any) -> Any:
        pytest.fail("Project-run execution must not use the borrowed adapter handle.")

    monkeypatch.setattr(DuckDbAdapter, "connect", forbidden)
    monkeypatch.setattr(DuckDbAdapter, "execute", forbidden)
    monkeypatch.setattr(DuckDbAdapter, "close", forbidden)
    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    try:
        result = RunService(start_path=tmp_path, adapter_registry=registry).execute()
        assert result.exit_category is ExitCategory.SUCCESS
        assert len(adapters) == 1 and adapters[0]._connection is borrowed
        assert borrowed.execute("SELECT id FROM qa.source_customers").fetchall() == [(1,)]
    finally:
        borrowed.close()


@pytest.mark.parametrize("missing_scratch", [False, True])
@pytest.mark.regression_capture("duckdb-native-resource-control-readback")
def test_project_run_applies_selected_native_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_scratch: bool
) -> None:
    from recon_core.adapters.duckdb._native_resource_controls import _parse_native_size

    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    scratch = tmp_path / "scratch"
    if not missing_scratch:
        scratch.mkdir()
    profile_path = tmp_path / "connections" / "profiles.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["profiles"]["local"]["outputs"]["dev"]["execution"] = {
        "connections": {
            "warehouse": {
                "managed-memory": {"mib": 64},
                "threads": 1,
                "spill": {"mib": 32},
                "scratch-directory": "scratch",
            }
        }
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    seen: list[Path] = []
    original = binding._OwnedDuckDbSession._read_bound_query

    def read(
        session: binding._OwnedDuckDbSession,
        lease: binding._BindingLease,
        scope: binding._BindingScope,
        query: str,
    ) -> Any:
        native = session._connection
        memory = _parse_native_size(
            native.execute("SELECT current_setting('memory_limit')").fetchone()[0]
        )
        spill = _parse_native_size(
            native.execute("SELECT current_setting('max_temp_directory_size')").fetchone()[0]
        )
        assert memory is not None and memory.contains(64 * 1024 * 1024)
        assert spill is not None and spill.contains(32 * 1024 * 1024)
        assert native.execute("SELECT current_setting('threads')").fetchone() == (1,)
        owned = Path(native.execute("SELECT current_setting('temp_directory')").fetchone()[0])
        assert owned.parent == scratch.resolve() and owned.is_dir()
        assert session._guard is not None
        seen.append(owned)
        return original(session, lease, scope, query)

    monkeypatch.setattr(binding._OwnedDuckDbSession, "_read_bound_query", read)
    engine = _CapturingEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    assert engine.result is not None
    outcome = engine.result.contract_results[0].check_results[0]
    if missing_scratch:
        assert outcome.status is CheckStatus.NOT_EXECUTABLE and not outcome.executed
        assert "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE" in {d.code for d in outcome.diagnostics}
        assert not scratch.exists() and not seen
    else:
        assert result.exit_category is ExitCategory.SUCCESS
        assert outcome.status is CheckStatus.PASS and outcome.executed
        assert len(seen) == 1 and not seen[0].exists()
        assert list(scratch.iterdir()) == []


@pytest.mark.regression_capture("local-adaptive-resource-targets")
@pytest.mark.parametrize("conflict", ["none", "memory", "scratch"])
def test_project_run_alias_policy_uses_resolved_scratch_and_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conflict: str
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    scratch = tmp_path / "private-scratch"
    scratch.mkdir()
    other = tmp_path / "private-other"
    other.mkdir()
    project_path = tmp_path / "recon_project.yml"
    project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    project["execution"] = {"adapters": {"duckdb": {"managed-memory": {"mib": 128}, "threads": 2}}}
    project_path.write_text(yaml.safe_dump(project, sort_keys=False), encoding="utf-8")
    profile_path = tmp_path / "connections" / "profiles.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    target = profile["profiles"]["local"]["outputs"]["dev"]
    target["connections"]["alias"] = dict(target["connections"]["warehouse"])
    target["execution"] = {
        "adapters": {"duckdb": {"managed-memory": {"mib": 64}, "threads": 1}},
        "connections": {
            "warehouse": {"scratch-directory": "private-scratch"},
            "alias": {
                "scratch-directory": str(other if conflict == "scratch" else scratch),
                "managed-memory": {"mib": 128 if conflict == "memory" else 64},
            },
        },
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    write_compiled_contract(tmp_path, source_connection="warehouse", target_connection="alias")
    opened: list[binding._OwnedDuckDbSession] = []
    original = binding._OwnedDuckDbSession.open

    def open_session(session: binding._OwnedDuckDbSession) -> None:
        opened.append(session)
        original(session)

    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", open_session)
    engine = _CapturingEngine()
    invocation = RunService(start_path=tmp_path, engine=engine)._execute_invocation()
    result = invocation.service_result
    facts = invocation.resource_facts[0]
    assert facts.source_policy is not None and facts.target_policy is not None
    source = {fact.setting: fact for fact in facts.source_policy}
    target_facts = {fact.setting: fact for fact in facts.target_policy}
    assert source["managed-memory"].scope.value == "target"
    assert target_facts["managed-memory"].scope.value == "connection"
    assert str(scratch) not in repr(facts) and str(other) not in repr(facts)
    assert engine.result is not None
    outcome = engine.result.contract_results[0].check_results[0]
    if conflict == "none":
        assert facts.admission.value == "verified"
        assert result.exit_category is ExitCategory.SUCCESS
        assert outcome.status is CheckStatus.PASS and outcome.executed
        assert len(opened) == 1
        request = opened[0]._native_controls
        assert request is not None and request.threads == 1
        assert request.memory_bytes == 64 * 1024 * 1024
        assert request.scratch_directory.parent == scratch.resolve()
    else:
        assert facts.admission.value == "refused" and facts.native is None
        assert outcome.status is CheckStatus.NOT_EXECUTABLE and not outcome.executed
        assert outcome.source_value is None and outcome.target_value is None
        assert "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE" in {d.code for d in outcome.diagnostics}
        assert not opened
        assert str(scratch) not in repr(result) and str(other) not in repr(result)
    assert not list(scratch.iterdir()) and not list(other.iterdir())


@pytest.mark.regression_capture("local-adaptive-resource-targets")
@pytest.mark.parametrize(
    "mode",
    ["auto", "reduced", "percent", "percent-spill", "zero-memory", "zero-spill", "zero-threads"],
)
@pytest.mark.parametrize("different", [False, True])
def test_project_resource_advisories_are_safe_and_do_not_change_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, different: bool
) -> None:
    database = tmp_path / "private-warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(
        duckdb,
        database,
        source_rows=((1,),),
        target_rows=((2,), (3,)) if different else ((2,),),
    )
    write_duckdb_row_count_run_inputs(tmp_path, database)
    profile_path = tmp_path / "connections" / "profiles.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    tuning: dict[str, object] = {}
    if mode == "reduced":
        tuning = {"managed-memory": {"mib": 128}, "threads": 2, "spill": {"mib": 64}}
    elif mode == "percent":
        tuning = {"managed-memory": {"percent": 75}}
    elif mode == "percent-spill":
        tuning = {"spill": {"percent": 75}}
    profile["profiles"]["local"]["outputs"]["dev"]["execution"] = {
        "connections": {"warehouse": tuning}
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")

    def observe(scratch: Path) -> _LocalObservation:
        return _LocalObservation(
            host_available_bytes=(
                0 if mode == "zero-memory" else 64 * 1024 * 1024 if mode == "reduced" else None
            ),
            platform_cpu_count=0 if mode == "zero-threads" else 1 if mode == "reduced" else None,
            affinity_count=None,
            linux_constraints=None,
            scratch_free_bytes=(
                0 if mode == "zero-spill" else 32 * 1024 * 1024 if mode == "reduced" else None
            ),
            scratch_memory_backed=False,
            platform="synthetic",
        )

    monkeypatch.setattr(binding, "_observe_local_resources", observe)
    engine = _CapturingEngine()
    invocation = RunService(start_path=tmp_path, engine=engine)._execute_invocation()
    result = invocation.service_result
    facts = invocation.resource_facts[0]
    assert facts.preliminary_allowed is True
    assert invocation.plan is not None
    assert facts.check_id == invocation.plan.contracts[0].checks[0].check_id
    assert engine.result is not None
    outcome = engine.result.contract_results[0].check_results[0]
    refusal = mode.startswith(("percent", "zero"))
    if refusal:
        assert facts.admission.value == "refused"
        assert facts.native is not None
        assert not facts.native.readback_verified
        assert outcome.status is CheckStatus.NOT_EXECUTABLE and not outcome.executed
        assert outcome.source_value is None and outcome.target_value is None
        assert result.exit_category is ExitCategory.RUNTIME_ERROR
        expected = "percentage" if mode.startswith("percent") else "No usable"
        assert any(expected in d.message for d in result.diagnostics)
    else:
        assert facts.admission.value == "verified"
        assert facts.native is not None and facts.native.readback_verified
        assert facts.native.memory.reported_lower is not None
        assert facts.native.threads.reported_lower is not None
        assert not facts.native.physical_enforcement_proven
        if mode == "reduced":
            assert facts.native.memory.requested == 128 << 20
            assert facts.native.memory.adjusted == 64 << 20
            assert facts.native.threads.requested == 2
            assert facts.native.threads.adjusted == 1
            assert facts.native.spill.requested == 64 << 20
            assert facts.native.spill.adjusted == 32 << 20
        else:
            assert facts.native.memory.requested is None
            assert facts.native.memory_capacity_known is False
        assert outcome.status is (CheckStatus.FAIL if different else CheckStatus.PASS)
        assert result.exit_category is (
            ExitCategory.CHECK_FAILURE if different else ExitCategory.SUCCESS
        )
        warnings = [d for d in result.diagnostics if d.severity is DiagnosticSeverity.WARNING]
        assert len(warnings) == 3
        assert all(d.hint for d in warnings)
        assert all(
            any(dimension in d.message for d in warnings)
            for dimension in ("managed-memory", "threads", "spill")
        )
    assert set(result.to_dict()) == {"exit_category", "exit_code", "message", "diagnostics"}
    assert "resource_facts" not in repr(invocation)
    assert "scope_facts" not in repr(result.to_dict())
    assert "resource_facts" not in repr(result.to_dict())
    assert str(tmp_path) not in repr(facts)
    assert "synthetic" not in repr(facts)
    assert "private-warehouse" not in repr(facts)
    monkeypatch.chdir(tmp_path)
    cli = CliRunner().invoke(main, ["run"])
    assert cli.exit_code == (3 if refusal else 1 if different else 0)
    if not refusal:
        assert "Warning:" in cli.output
        assert all(d.code in cli.output for d in warnings)
    else:
        assert expected in cli.output
    assert invocation.run_id not in cli.output
    assert "resource_facts" not in cli.output and "scope_facts" not in cli.output
    assert str(database) not in repr(result) and str(database) not in cli.output
    assert str(tmp_path) not in repr(result) and str(tmp_path) not in cli.output


@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_future_platform_observation_label_does_not_refuse_verified_native_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    before = database.read_bytes()

    def observe(scratch: Path) -> _LocalObservation:
        return _LocalObservation(
            host_available_bytes=512 << 20,
            platform_cpu_count=1,
            affinity_count=1,
            linux_constraints=None,
            scratch_free_bytes=64 << 20,
            scratch_memory_backed=False,
            platform="future-platform-label",
        )

    monkeypatch.setattr(binding, "_observe_local_resources", observe)
    engine = _CapturingEngine()
    result = RunService(start_path=tmp_path, engine=engine).execute()
    assert result.exit_category is ExitCategory.SUCCESS
    assert engine.result is not None
    outcome = engine.result.contract_results[0].check_results[0]
    assert outcome.status is CheckStatus.PASS and outcome.executed
    assert outcome.source_value == outcome.target_value == 1
    assert not any("future-platform-label" in repr(d) for d in result.diagnostics)
    assert not any(d.severity is DiagnosticSeverity.WARNING for d in result.diagnostics)
    monkeypatch.chdir(tmp_path)
    cli = CliRunner().invoke(main, ["run"])
    assert cli.exit_code == 0
    assert "future-platform-label" not in cli.output
    assert "Warning:" not in cli.output
    assert database.read_bytes() == before


@pytest.mark.regression_capture("run-invocation-identity-timing")
def test_native_run_finish_is_recorded_after_confirmed_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    events: list[str] = []
    labels = iter(("2026-11-27T10:00:00.123Z", "2026-11-27T10:00:02.456Z"))
    real_close = binding._OwnedDuckDbSession.close

    def timestamp() -> str:
        events.append("timestamp")
        return next(labels)

    def close(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        diagnostics = real_close(session)
        assert session.released
        events.append("closed")
        return diagnostics

    monkeypatch.setattr(run_service_module, "_utc_timestamp", timestamp)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "close", close)
    result = RunService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert events == ["timestamp", "closed", "timestamp"]


@pytest.mark.regression_capture("run-invocation-identity-timing")
@pytest.mark.parametrize("reported_cleanup_failure", [False, True])
def test_invocation_elapsed_includes_native_cleanup_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reported_cleanup_failure: bool
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    tick = 1_000_000_000
    real_close = binding._OwnedDuckDbSession.close

    def close(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        nonlocal tick
        diagnostics = real_close(session)
        assert session.released
        tick += 250_000_000
        if reported_cleanup_failure:
            diagnostics += (
                Diagnostic(
                    code="RC_ADAPTER_CLOSE_FAILED",
                    severity=DiagnosticSeverity.ERROR,
                    message="Read-only execution session cleanup failed.",
                ),
            )
        return diagnostics

    monkeypatch.setattr(run_service_module, "monotonic_ns", lambda: tick)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "close", close)
    outcome = RunService(start_path=tmp_path)._execute_invocation()

    assert outcome.elapsed_ns == 250_000_000
    assert outcome.run_result is not None
    assert outcome.run_result.finished_at == outcome.finished_at
    check = outcome.run_result.contract_results[0].check_results[0]
    if reported_cleanup_failure:
        assert outcome.status.value == "failed"
        assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
        assert check.status is CheckStatus.ERROR and not check.executed
        assert check.source_value is check.target_value is check.diff_value is None
        assert "RC_ADAPTER_CLOSE_FAILED" in {d.code for d in check.diagnostics}
    else:
        assert outcome.status.value == "completed"
        assert outcome.service_result.exit_category is ExitCategory.SUCCESS
        assert check.status is CheckStatus.PASS and check.executed


@pytest.mark.regression_capture("run-loaded-compiled-scope")
def test_native_run_uses_loaded_artifacts_after_files_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    target = tmp_path / "target"
    checks = target / "compiled_checks" / "customer_revenue.yml"
    contract = target / "compiled_contracts" / "customer_revenue.yml"
    original_load = CompiledContractLoader._load_for_runtime
    loads = 0

    def load_then_change(*args: Any, **kwargs: Any) -> Any:
        nonlocal loads
        loads += 1
        result = original_load(*args, **kwargs)
        assert result[0].succeeded
        checks.write_text("invalid: [", encoding="utf-8")
        contract.write_text("invalid: [", encoding="utf-8")
        return result

    monkeypatch.setattr(CompiledContractLoader, "_load_for_runtime", load_then_change)
    outcome = RunService(start_path=tmp_path)._execute_invocation()

    assert loads == 1
    assert outcome.plan is not None
    assert outcome.run_result is not None
    assert outcome.service_result.exit_category is ExitCategory.SUCCESS
    check = outcome.run_result.contract_results[0].check_results[0]
    assert check.status is CheckStatus.PASS
    assert check.check_id == outcome.plan.contracts[0].checks[0].check_id
    assert checks.read_text(encoding="utf-8") == "invalid: ["
    assert contract.read_text(encoding="utf-8") == "invalid: ["
    assert not (target / "run_results.json").exists()


@pytest.mark.regression_capture("run-preparation-and-diagnostic-identity")
@pytest.mark.parametrize("distinct_alias", [False, True])
def test_legacy_setup_preserves_distinct_connection_failures(
    tmp_path: Path, distinct_alias: bool
) -> None:
    database = tmp_path / "private-database.duckdb"
    _write_duckdb_row_count_tables(
        _duckdb_module(), database, source_rows=((1,),), target_rows=((2,),)
    )
    write_duckdb_row_count_run_inputs(tmp_path, database)
    profile_path = tmp_path / "connections" / "profiles.yml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    connections = profile["profiles"]["local"]["outputs"]["dev"]["connections"]
    if distinct_alias:
        connections["private-alias"] = dict(connections["warehouse"])
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    connection_name = "private-alias" if distinct_alias else "warehouse"
    other = _compiled_check_payload(
        check_id="check.ecommerce_recon.other_revenue.row_count_diff",
        operations=row_count_plan(),
    )
    other["plan"] = {
        "id": "plan.ecommerce_recon.other_revenue.row_count_diff",
        "operations": row_count_plan(),
        "required_capabilities": ["row_count"],
    }
    write_compiled_checks(tmp_path, contract_name="other_revenue", checks=[other])
    write_compiled_contract(
        tmp_path,
        contract_name="other_revenue",
        source_connection=connection_name,
        target_connection=connection_name,
    )
    calls: list[str] = []

    def factory(connection: ConnectionConfig) -> AdapterResolutionResult:
        calls.append(connection.name)
        diagnostic = Diagnostic(
            code="RC_ADAPTER_RESOLUTION_FAILED",
            severity=DiagnosticSeverity.ERROR,
            message="Adapter resolution failed.",
            resource_type="adapter",
        )
        return AdapterResolutionResult(diagnostics=(diagnostic, diagnostic))

    registry = AdapterRegistry()
    registry.register("duckdb", factory)
    outcome = RunService(start_path=tmp_path, adapter_registry=registry)._execute_invocation()
    expected = {"warehouse", "private-alias"} if distinct_alias else {"warehouse"}
    assert len(calls) == len(expected) and set(calls) == expected
    assert outcome.stage.value == "runtime_setup"
    assert outcome.plan is not None and outcome.run_result is None
    assert outcome.service_result.exit_category is ExitCategory.CONFIGURATION_ERROR
    failures = [
        d for d in outcome.service_result.diagnostics if d.code == "RC_ADAPTER_RESOLUTION_FAILED"
    ]
    assert len(failures) == len(expected)
    assert len({d.hint for d in failures}) == len(expected)
    assert "private-alias" not in repr(outcome.service_result)
    assert "private-database" not in repr(outcome.service_result)


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
@pytest.mark.parametrize("cancel_after_cleanup", [False, True])
def test_native_invocation_control_preserves_completed_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel_after_cleanup: bool
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(check_id="first", name="first", operations=row_count_plan()),
            _compiled_check_payload(check_id="second", name="second", operations=row_count_plan()),
        ],
    )
    before = database.read_bytes()
    event = Event()
    closed: list[bool] = []
    real_close = binding._OwnedDuckDbSession.close

    def close(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        diagnostics = real_close(session)
        closed.append(session.released)
        if cancel_after_cleanup:
            event.set()
        return diagnostics

    monkeypatch.setattr(binding._OwnedDuckDbSession, "close", close)
    outcome = RunService(start_path=tmp_path)._execute_invocation(
        timeout_seconds=10**100, cancel_event=event
    )
    assert outcome.run_result is not None
    checks = outcome.run_result.contract_results[0].check_results
    assert len(checks) == 2
    assert checks[0].status is CheckStatus.PASS and checks[0].executed
    assert outcome.scope_facts.complete is True
    if cancel_after_cleanup:
        assert closed == [True]
        assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
        assert checks[1].status is CheckStatus.NOT_EXECUTABLE
        assert checks[1].reason_code is not None
        assert checks[1].reason_code.value == "run_cancelled"
        assert not checks[1].executed
        assert event.is_set()
    else:
        assert closed == [True, True]
        assert outcome.service_result.exit_category is ExitCategory.SUCCESS
        assert checks[1].status is CheckStatus.PASS and checks[1].executed
        assert not event.is_set()
    assert database.read_bytes() == before
    writer = duckdb.connect(str(database))
    writer.close()


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
@pytest.mark.parametrize(
    "phase", ["setup", "before_fetch", "after_fetch", "deadline_after_fetch", "cleanup_error"]
)
def test_native_stop_at_check_boundaries_preserves_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(check_id="first", name="first", operations=row_count_plan()),
            _compiled_check_payload(check_id="second", name="second", operations=row_count_plan()),
        ],
    )
    event = Event()
    now = 0
    opened: list[binding._OwnedDuckDbSession] = []
    closed: list[bool] = []
    fetched: list[int] = []
    real_open = binding._OwnedDuckDbSession.open
    real_close = binding._OwnedDuckDbSession.close
    real_fetch = binding._ControlledReadCursor.fetchmany
    cleanup_error = Diagnostic(
        code="RC_ADAPTER_CLOSE_FAILED",
        severity=DiagnosticSeverity.ERROR,
        message="Read-only execution session cleanup failed.",
    )

    def open_session(session: binding._OwnedDuckDbSession) -> None:
        real_open(session)
        opened.append(session)
        if phase == "setup":
            event.set()

    def fetch(cursor: binding._ControlledReadCursor, size: int) -> Any:
        nonlocal now
        if cursor._interrupt is None:
            return real_fetch(cursor, size)
        if phase == "before_fetch":
            event.set()
        result = real_fetch(cursor, size)
        fetched.append(size)
        if phase == "after_fetch":
            event.set()
        elif phase == "deadline_after_fetch":
            now = 1_000_000_000
        return result

    def close(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        if phase == "cleanup_error":
            event.set()
        diagnostics = real_close(session)
        closed.append(session.released)
        return diagnostics + (cleanup_error,) if phase == "cleanup_error" else diagnostics

    before = database.read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(run_service_module, "monotonic_ns", lambda: now)
        patch.setattr(binding._OwnedDuckDbSession, "open", open_session)
        patch.setattr(binding._OwnedDuckDbSession, "close", close)
        patch.setattr(binding._ControlledReadCursor, "fetchmany", fetch)
        outcome = RunService(start_path=tmp_path)._execute_invocation(
            timeout_seconds=1, cancel_event=event
        )
    assert len(opened) == 1 and closed == [True]
    assert outcome.run_result is not None
    first, second = outcome.run_result.contract_results[0].check_results
    assert first.status is CheckStatus.ERROR and not first.executed
    assert first.source_value is first.target_value is first.diff_value is None
    assert second.status is CheckStatus.NOT_EXECUTABLE and not second.executed
    assert second.reason_code is not None
    reason = "run_deadline_exceeded" if phase == "deadline_after_fetch" else "run_cancelled"
    assert second.reason_code.value == reason
    assert outcome.stop_cause is not None and outcome.stop_cause.value == reason
    assert outcome.scope_facts.complete is True
    assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
    assert "RC_RUNTIME_" + reason.upper() in {d.code for d in outcome.service_result.diagnostics}
    if phase in {"setup", "before_fetch"}:
        assert fetched == []
    else:
        assert fetched == [2]
    if phase == "cleanup_error":
        assert cleanup_error.code in {d.code for d in first.diagnostics}
    assert database.read_bytes() == before
    assert RunService(start_path=tmp_path).execute().exit_category is ExitCategory.SUCCESS


@pytest.mark.regression_capture("owned-scratch-discovery")
def test_abrupt_native_run_retains_residue_and_next_run_uses_fresh_scratch(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    project_path = tmp_path / "recon_project.yml"
    project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    project["execution"] = {"adapters": {"duckdb": {"scratch-directory": "scratch"}}}
    project_path.write_text(yaml.safe_dump(project, sort_keys=False), encoding="utf-8")
    before = database.read_bytes()
    code = textwrap.dedent(
        """
        import os
        import sys
        from pathlib import Path

        from recon_core.adapters.duckdb import _bound_execution as binding
        from recon_core.services import RunService

        original = binding._OwnedDuckDbSession.open

        def open_and_exit(session):
            original(session)
            assert session._transaction and not session.released
            assert session._scratch is not None
            (session._scratch.path / "abandoned.tmp").write_bytes(b"abandoned")
            os._exit(73)

        binding._OwnedDuckDbSession.open = open_and_exit
        RunService(start_path=Path(sys.argv[1])).execute()
        raise AssertionError("Abrupt exit was not reached.")
        """
    )
    child = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path.resolve())],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert child.returncode == 73, child.stderr
    abandoned = list(scratch.iterdir())
    assert len(abandoned) == 1
    residue = abandoned[0] / "abandoned.tmp"
    assert residue.read_bytes() == b"abandoned"
    outcome = RunService(start_path=tmp_path)._execute_invocation()
    assert outcome.service_result.exit_category is ExitCategory.SUCCESS
    assert outcome.scope_facts.complete is True
    assert list(scratch.iterdir()) == abandoned
    assert residue.read_bytes() == b"abandoned"
    assert database.read_bytes() == before
    assert not (tmp_path / "target" / "run_results.json").exists()


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
@pytest.mark.parametrize("mode", ["normal", "stop", "native_error"])
def test_invocation_counts_native_attempts_without_inventing_consumption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(check_id="first", name="first", operations=row_count_plan()),
            _compiled_check_payload(check_id="second", name="second", operations=row_count_plan()),
        ],
    )
    event = Event()
    opened: list[binding._OwnedDuckDbSession] = []
    active = 0
    peak = 0
    original_open = binding._OwnedDuckDbSession.open
    original_close = binding._OwnedDuckDbSession.close

    class BrokenActor:
        def __init__(self, native: Any) -> None:
            self.native = native

        def __getattr__(self, name: str) -> Any:
            return getattr(self.native, name)

        def execute(self, statement: str, *args: Any) -> Any:
            if statement == "ROLLBACK":
                return self.native.execute(statement, *args)
            if "count(" in statement.lower():
                raise RuntimeError("private-native-error")
            return self.native.execute(statement, *args)

    def open_session(session: binding._OwnedDuckDbSession) -> None:
        nonlocal active, peak
        original_open(session)
        opened.append(session)
        active += 1
        peak = max(peak, active)
        if mode == "native_error" and len(opened) == 1:
            session._connection = BrokenActor(session._connection)

    def close_session(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        nonlocal active
        diagnostics = original_close(session)
        assert session.released
        active -= 1
        if mode == "stop" and len(opened) == 1:
            event.set()
        return diagnostics

    with monkeypatch.context() as patch:
        patch.setattr(binding._OwnedDuckDbSession, "open", open_session)
        patch.setattr(binding._OwnedDuckDbSession, "close", close_session)
        service = RunService(start_path=tmp_path)
        outcome = (
            service._execute_invocation(cancel_event=event)
            if mode == "stop"
            else service._execute_invocation()
        )
    assert outcome.scope_facts.complete is True
    assert outcome.scope_facts.planned_check_count == 2
    assert outcome.scope_facts.finalized_check_count == 2
    assert outcome.scope_facts.executed_check_count == (2 if mode == "normal" else 1)
    assert active == 0 and peak == 1
    facts = outcome.execution_facts
    assert facts.attempted_check_count == len(opened) == (1 if mode == "stop" else 2)
    assert facts.native_execute_attempts == (1 if mode == "stop" else 2)
    assert facts.native_fetch_attempts == (2 if mode == "normal" else 1)
    assert facts.peak_active_native_checks == peak
    assert facts.actual_scanned_rows is None
    assert facts.actual_cpu_ns is None
    assert facts.actual_disk_bytes is None
    assert facts.actual_transport_bytes is None
    assert facts.actual_cost is None
    assert "private-native-error" not in repr(outcome.service_result)
    assert set(outcome.service_result.to_dict()) == {
        "exit_category",
        "exit_code",
        "message",
        "diagnostics",
    }
    repeated = RunService(start_path=tmp_path)._execute_invocation()
    assert repeated.run_id != outcome.run_id
    assert repeated.execution_facts.attempted_check_count == 2
    assert repeated.execution_facts.native_execute_attempts == 2
    assert repeated.execution_facts.native_fetch_attempts == 2


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
@pytest.mark.regression_capture("local-adaptive-resource-targets")
@pytest.mark.parametrize("deadline", [False, True])
def test_native_work_reobserves_capacity_and_shares_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, deadline: bool
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
    write_duckdb_row_count_run_inputs(tmp_path, database)
    write_compiled_checks(
        tmp_path,
        checks=[
            _compiled_check_payload(check_id="first", name="first", operations=row_count_plan()),
            _compiled_check_payload(check_id="second", name="second", operations=row_count_plan()),
        ],
    )
    project_path = tmp_path / "recon_project.yml"
    project = yaml.safe_load(project_path.read_text(encoding="utf-8"))
    project["execution"] = {"adapters": {"duckdb": {"managed-memory": {"mib": 128}, "threads": 1}}}
    project_path.write_text(yaml.safe_dump(project, sort_keys=False), encoding="utf-8")
    observed: list[int] = []
    tick = 0
    original_close = binding._OwnedDuckDbSession.close

    def observe(scratch: Path) -> _LocalObservation:
        available = (64 if not observed else 128) << 20
        observed.append(available)
        return _LocalObservation(
            host_available_bytes=available,
            platform_cpu_count=1,
            affinity_count=None,
            linux_constraints=None,
            scratch_free_bytes=None,
            scratch_memory_backed=False,
            platform="synthetic",
        )

    def close(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        nonlocal tick
        diagnostics = original_close(session)
        assert session.released
        tick += 1_000_000_000
        return diagnostics

    monkeypatch.setattr(binding, "_observe_local_resources", observe)
    monkeypatch.setattr(binding._OwnedDuckDbSession, "close", close)
    monkeypatch.setattr(run_service_module, "monotonic_ns", lambda: tick)
    outcome = RunService(start_path=tmp_path)._execute_invocation(
        timeout_seconds=1 if deadline else None
    )
    assert outcome.scope_facts.complete is True
    assert outcome.run_result is not None
    first, second = outcome.run_result.contract_results[0].check_results
    assert first.status is CheckStatus.PASS
    assert outcome.execution_facts.peak_active_native_checks == 1
    assert outcome.execution_facts.attempted_check_count == len(observed)
    native = [fact.native for fact in outcome.resource_facts if fact.native is not None]
    assert [fact.memory.adjusted for fact in native] == observed
    if deadline:
        assert observed == [64 << 20]
        assert outcome.elapsed_ns == 1_000_000_000
        assert second.status is CheckStatus.NOT_EXECUTABLE
        assert second.reason_code is not None
        assert second.reason_code.value == "run_deadline_exceeded"
        assert outcome.service_result.exit_category is ExitCategory.RUNTIME_ERROR
    else:
        assert observed == [64 << 20, 128 << 20]
        assert outcome.elapsed_ns == 2_000_000_000
        assert second.status is CheckStatus.PASS
        assert outcome.service_result.exit_category is ExitCategory.SUCCESS


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
def test_independent_invocations_overlap_without_shared_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    duckdb = _duckdb_module()
    projects = [tmp_path / name for name in ("one", "two")]
    for project in projects:
        project.mkdir()
        database = project / "warehouse.duckdb"
        _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
        write_duckdb_row_count_run_inputs(project, database)
        project_path = project / "recon_project.yml"
        config = yaml.safe_load(project_path.read_text(encoding="utf-8"))
        config["execution"] = {
            "adapters": {"duckdb": {"managed-memory": {"mib": 64}, "threads": 1}}
        }
        project_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    barrier = Barrier(2, timeout=15)
    original_open = binding._OwnedDuckDbSession.open

    def open_session(session: binding._OwnedDuckDbSession) -> None:
        original_open(session)
        barrier.wait()

    monkeypatch.setattr(binding._OwnedDuckDbSession, "open", open_session)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                RunService(start_path=project)._execute_invocation, cancel_event=Event()
            )
            for project in projects
        ]
        outcomes = [future.result(timeout=30) for future in futures]
    assert outcomes[0].run_id != outcomes[1].run_id
    for outcome in outcomes:
        assert outcome.service_result.exit_category is ExitCategory.SUCCESS
        assert outcome.scope_facts.complete is True
        assert outcome.execution_facts.attempted_check_count == 1
        assert outcome.execution_facts.native_execute_attempts == 1
        assert outcome.execution_facts.native_fetch_attempts == 1
        assert outcome.execution_facts.peak_active_native_checks == 1
