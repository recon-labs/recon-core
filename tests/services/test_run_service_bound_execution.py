"""Project-run native binding and check-local lifecycle proof."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from recon_core.adapters.duckdb import DuckDbAdapter
from recon_core.adapters.duckdb import _bound_execution as binding
from recon_core.check_engine import CheckEngine, CheckStatus, RunResult
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services import RunService
from recon_core.services.results import ExitCategory
from tests.services._run_service_fixtures import (
    _compiled_check_payload,
    _duckdb_module,
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


@pytest.mark.parametrize("uncertain_close", [False, True])
@pytest.mark.regression_capture("project-binding-check-local-cleanup")
def test_cleanup_failure_is_check_local_or_stops_native_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, uncertain_close: bool
) -> None:
    database = tmp_path / "warehouse.duckdb"
    duckdb = _duckdb_module()
    _write_duckdb_row_count_tables(duckdb, database, source_rows=((1,),), target_rows=((2,),))
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
    write_compiled_checks(tmp_path, checks=checks)
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
            session._released = not uncertain_close
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
    first, dependent, unrelated = engine.result.contract_results[0].check_results
    assert first.status is CheckStatus.ERROR
    assert not first.executed
    assert first.source_value is None and first.target_value is None
    assert dependent.status is CheckStatus.BLOCKED
    assert dependent.blocked_by == (first.check_id,)
    if uncertain_close:
        assert unrelated.status is CheckStatus.ERROR
        assert "RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE" in {
            diagnostic.code for diagnostic in unrelated.diagnostics
        }
        assert len(opened) == 1
    else:
        assert unrelated.status is CheckStatus.PASS
        assert len(opened) == 2


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


@pytest.mark.parametrize("failure", ["open", "query", "uncertain_close"])
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
        if session is opened[0] and failure == "query":
            raise RuntimeError("private-native-query-error")
        return real_read(session, lease, scope, query)

    def close_session(session: binding._OwnedDuckDbSession) -> tuple[Diagnostic, ...]:
        closed.append(session)
        diagnostics = real_close(session)
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
    }
    assert expected[failure] in {d.code for d in failed.diagnostics}
    assert blocked.status is CheckStatus.BLOCKED
    assert blocked.blocked_by == (failed.check_id,)
    assert blocked.reason_code is not None and blocked.reason_code.value == "prerequisite_error"
    assert not blocked.executed
    assert opened == closed
    if failure == "uncertain_close":
        assert unrelated.status is CheckStatus.ERROR and not unrelated.executed
        assert "RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE" in {d.code for d in unrelated.diagnostics}
        assert len(opened) == 1
        assert reads == opened
    else:
        assert unrelated.status is CheckStatus.PASS and unrelated.executed
        assert unrelated.source_value == unrelated.target_value == 1
        assert len(opened) == 2
        assert reads == (opened[1:] if failure == "open" else opened)
    public = repr(engine.result.to_dict()) + repr(result.diagnostics)
    for token in ("private-first", "private-other", "private-native-query-error"):
        assert token not in public
    assert all(path.read_bytes() == content for path, content in before.items())
