"""Controlled owned session and child-side binding proof.

Only synthetic fixtures are used here. Scratch ownership, parent policy and
actual worker request transport must be proved before project activation.
"""

import importlib
import io
import os
import subprocess
import sys
import textwrap
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from recon_core.adapters._project_binding import _BoundSessionError
from recon_core.adapters.duckdb._aggregate_runtime import _DuckDbAggregateRuntimeRenderer
from recon_core.adapters.duckdb._native_resource_controls import _NativeControlRequest
from recon_core.adapters.duckdb._worker_bound_session import _WorkerBoundSession
from recon_core.adapters.duckdb._worker_result_codec import _read_result, _write_result
from recon_core.adapters.duckdb.renderer_operations import render_compare_counts
from recon_core.adapters.duckdb.runtime_scan_guard import _current_file_identity


@pytest.fixture
def duckdb() -> Any:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            return importlib.import_module("duckdb")
        except ImportError:
            pytest.fail("Required worker binding tests need .[dev,duckdb].", pytrace=False)
    return pytest.importorskip("duckdb")


@pytest.fixture
def controlled_session(tmp_path: Path, duckdb: Any) -> _WorkerBoundSession:
    path = tmp_path / "fixture.duckdb"
    connection = duckdb.connect(str(path))
    try:
        connection.execute("CREATE TABLE src AS SELECT 9007199254740993::BIGINT AS v")
        connection.execute("CREATE TABLE dst AS SELECT 9007199254740992::BIGINT AS v")
        connection.execute("CREATE VIEW not_base AS SELECT * FROM src")
    finally:
        connection.close()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    identity = _current_file_identity(path.resolve())
    assert identity is not None
    return _WorkerBoundSession(
        identity,
        controls=_NativeControlRequest(128 << 20, 1, 32 << 20, scratch.resolve()),
        session_id=uuid4(),
        policy_generation=1,
    )


@pytest.mark.regression_capture("duckdb-worker-bound-session-scope")
def test_worker_count_result_uses_exact_bound_relations(
    controlled_session: _WorkerBoundSession,
) -> None:
    session = controlled_session
    try:
        session.open()
        proof = session.bind(
            check_id="private-check", operation="row_count_diff", source="src", target="dst"
        )
        assert proof is not None
        assert proof.scope.check_id == "private-check"
        query = render_compare_counts(proof.scope.source, proof.scope.target)
        result = session.read_count(proof, query.sql)
        assert result.columns == ("source_row_count", "target_row_count", "row_count_diff")
        assert result.rows == ((1, 1, 0),)
    finally:
        assert session.close() == ()
        assert session.released


@pytest.mark.regression_capture("duckdb-worker-bound-session-scope")
@pytest.mark.parametrize(
    "change", ["session", "generation", "generation-bool", "nonce", "scope", "family"]
)
def test_wrong_worker_binding_is_rejected_before_query(
    controlled_session: _WorkerBoundSession, change: str
) -> None:
    session = controlled_session
    try:
        session.open()
        proof = session.bind(
            check_id="private-check", operation="row_count_diff", source="src", target="dst"
        )
        assert proof is not None
        if change == "session":
            forged = replace(proof, session_id=uuid4())
        elif change == "generation":
            forged = replace(proof, policy_generation=2)
        elif change == "generation-bool":
            forged = replace(proof, policy_generation=True)
        elif change == "nonce":
            forged = replace(proof, nonce=uuid4())
        elif change == "scope":
            forged = replace(proof, scope=replace(proof.scope, check_id="different"))
        else:
            forged = replace(proof, scope=replace(proof.scope, operation="sum_diff"))
        query = render_compare_counts(proof.scope.source, proof.scope.target).sql
        with pytest.raises(_BoundSessionError):
            session.read_count(forged, query)
        with pytest.raises(_BoundSessionError):
            session.read_count(proof, query)
    finally:
        assert session.close() == ()


@pytest.mark.regression_capture("duckdb-worker-bound-session-scope")
def test_unbound_or_refused_worker_cannot_execute(
    controlled_session: _WorkerBoundSession,
) -> None:
    session = controlled_session
    try:
        session.open()
        assert session.bind(
            check_id="private-check", operation="row_count_diff", source="not_base", target="dst"
        ) is None
        with pytest.raises(_BoundSessionError):
            session.bind(
                check_id="private-check", operation="row_count_diff", source="src", target="dst"
            )
    finally:
        assert session.close() == ()


def test_native_exact_numeric_result_survives_worker_codec(
    controlled_session: _WorkerBoundSession,
) -> None:
    session = controlled_session
    try:
        session.open()
        proof = session.bind(
            check_id="private-check", operation="sum_diff", source="src", target="dst"
        )
        assert proof is not None
        operations = (
            {"type": "aggregate", "side": "source", "aggregate": "sum", "column": "v"},
            {"type": "aggregate", "side": "target", "aggregate": "sum", "column": "v"},
            {"type": "compare_aggregates"},
        )
        plan = _DuckDbAggregateRuntimeRenderer().render_plan(
            operations, source_relation=proof.scope.source, target_relation=proof.scope.target
        )
        for guard in plan.type_guards:
            checked = session.read_aggregate(proof, guard.sql, expected_columns=("type_check",))
            assert checked.row == (1,)
        domain = session.read_aggregate(
            proof, plan.domain_guard.sql, expected_columns=("numeric_domain",)
        )
        assert domain.row == (1,)
        columns = plan.columns
        result = session.read_aggregate(proof, plan.exact_query.sql, expected_columns=columns)
        stream = io.BytesIO()
        _write_result(stream, result, expected_columns=columns)
        stream.seek(0)
        decoded = _read_result(stream, expected_columns=columns)
        assert decoded == result
        assert decoded.row == (9007199254740993, 9007199254740992, 1)
    finally:
        assert session.close() == ()


def test_bound_session_runs_in_separate_native_process(
    tmp_path: Path, duckdb: Any, controlled_session: _WorkerBoundSession
) -> None:
    # Validation-only harness: no project path is enabled by this test.
    database = tmp_path / "fixture.duckdb"
    scratch = tmp_path / "scratch"
    observer = duckdb.connect(
        str(database), read_only=True, config={"memory_limit": "96MiB", "threads": "1"}
    )
    code = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        from uuid import uuid4
        from recon_core.adapters.duckdb._native_resource_controls import _NativeControlRequest
        from recon_core.adapters.duckdb._worker_bound_session import _WorkerBoundSession
        from recon_core.adapters.duckdb._worker_result_codec import _write_result
        from recon_core.adapters.duckdb._aggregate_runtime import _DuckDbAggregateRuntimeRenderer
        from recon_core.adapters.duckdb.runtime_scan_guard import _current_file_identity

        identity = _current_file_identity(Path(sys.argv[1]).resolve())
        assert identity is not None
        session = _WorkerBoundSession(
            identity,
            controls=_NativeControlRequest(128 << 20, 1, 32 << 20, Path(sys.argv[2]).resolve()),
            session_id=uuid4(), policy_generation=1,
        )
        try:
            session.open()
            proof = session.bind(
                check_id="synthetic", operation="sum_diff", source="src", target="dst"
            )
            assert proof is not None
            operations = (
                {"type": "aggregate", "side": "source", "aggregate": "sum", "column": "v"},
                {"type": "aggregate", "side": "target", "aggregate": "sum", "column": "v"},
                {"type": "compare_aggregates"},
            )
            plan = _DuckDbAggregateRuntimeRenderer().render_plan(
                operations, source_relation=proof.scope.source, target_relation=proof.scope.target
            )
            for guard in plan.type_guards:
                assert session.read_aggregate(
                    proof, guard.sql, expected_columns=("type_check",)
                ).row == (1,)
            assert session.read_aggregate(
                proof, plan.domain_guard.sql, expected_columns=("numeric_domain",)
            ).row == (1,)
            result = session.read_aggregate(
                proof, plan.exact_query.sql, expected_columns=plan.columns
            )
        finally:
            assert session.close() == () and session.released
        _write_result(sys.stdout.buffer, result, expected_columns=plan.columns)
        """
    )
    try:
        before = observer.execute("SELECT current_setting('memory_limit')").fetchone()
        child = subprocess.run(
            [sys.executable, "-c", code, str(database), str(scratch)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        assert child.returncode == 0, "Synthetic controlled child execution failed."
        stream = io.BytesIO(child.stdout)
        result = _read_result(
            stream,
            expected_columns=("source_aggregate_value", "target_aggregate_value", "aggregate_diff"),
        )
        assert stream.read() == b""
        assert result.row == (9007199254740993, 9007199254740992, 1)
        assert observer.execute("SELECT current_setting('memory_limit')").fetchone() == before
        assert observer.execute("SELECT count(*) FROM src").fetchone() == (1,)
    finally:
        observer.close()
