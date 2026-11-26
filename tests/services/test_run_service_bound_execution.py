"""Project-run native binding and check-local lifecycle proof."""

from pathlib import Path
from typing import Any

import pytest

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
    write_duckdb_row_count_run_inputs,
)


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
