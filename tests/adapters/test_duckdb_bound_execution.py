"""Native and unit proof of the private local DuckDB binding boundary."""

import importlib
import os
from pathlib import Path
from typing import Any

import pytest

from recon_core.adapters.duckdb import runtime_scan_guard as guard
from recon_core.profiles import ConnectionConfig


@pytest.fixture
def duckdb() -> Any:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            return importlib.import_module("duckdb")
        except ImportError:
            pytest.fail("Required binding tests need .[dev,duckdb].", pytrace=False)
    return pytest.importorskip("duckdb")


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [("MiXeD", "mixed"), ("Ä", "Ä"), ("ä", "ä"), ("Straße", "straße")],
)
def test_binding_identifier_key_is_ascii_only(identifier: str, expected: str) -> None:
    assert guard._duckdb_identifier_key(identifier) == expected


@pytest.mark.parametrize("identifier", ["Ä", "ä"])
def test_qualified_relation_binding_preserves_distinct_unicode_tables(
    tmp_path: Path, duckdb: Any, identifier: str
) -> None:
    database = tmp_path / "local.data"
    connection = duckdb.connect(str(database))
    try:
        connection.execute('CREATE TABLE "Ä" AS SELECT 1 AS id')
        connection.execute('CREATE TABLE "ä" AS SELECT 2 AS id')
        assert connection.execute('SELECT id FROM "Ä"').fetchall() == [(1,)]
        assert connection.execute('SELECT id FROM "ä"').fetchall() == [(2,)]
    finally:
        connection.close()

    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": "local.data"})
    status = guard.bounded_local_duckdb_scan_status(
        config,
        source_relation=identifier,
        target_relation=identifier,
        project_root=tmp_path,
    )
    assert status.local_dev
    assert status.bounded, "Distinct identifiers must not be collapsed by Unicode folding."
