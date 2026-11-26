"""Controlled owned session and child-side binding proof.

Only synthetic fixtures are used here. Scratch ownership, parent policy and
actual worker request transport must be proved before project activation.
"""

import importlib
import io
import os
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from recon_core.adapters._project_binding import _BoundSessionError
from recon_core.adapters.duckdb._native_resource_controls import _NativeControlRequest
from recon_core.adapters.duckdb._worker_bound_session import _WorkerBoundSession
from recon_core.adapters.duckdb._worker_result_codec import _read_result, _write_result
from recon_core.adapters.duckdb.renderer_operations import render_compare_counts
from recon_core.adapters.duckdb.renderer_sql import render_relation
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
@pytest.mark.parametrize("change", ["session", "generation", "nonce", "scope", "family"])
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
        # Synthetic trusted SELECT exercising the real bound numeric reader.
        source = render_relation(proof.scope.source)
        target = render_relation(proof.scope.target)
        query = (
            f"WITH s AS (SELECT sum(v) a FROM {source}), "
            f"t AS (SELECT sum(v) b FROM {target}) "
            "SELECT a AS source_aggregate_value, b AS target_aggregate_value, a-b AS aggregate_diff "
            "FROM s CROSS JOIN t"
        )
        columns = ("source_aggregate_value", "target_aggregate_value", "aggregate_diff")
        result = session.read_aggregate(proof, query, expected_columns=columns)
        stream = io.BytesIO()
        _write_result(stream, result, expected_columns=columns)
        stream.seek(0)
        decoded = _read_result(stream, expected_columns=columns)
        assert decoded == result
        assert decoded.row == (9007199254740993, 9007199254740992, 1)
    finally:
        assert session.close() == ()
