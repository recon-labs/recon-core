"""Private bounded aggregate transport, independent of reconciliation policy."""

import importlib
import math
import os
import sys
from dataclasses import fields
from decimal import Decimal, localcontext
from types import SimpleNamespace
from typing import Any

import pytest

from recon_core.adapters import BaseAdapter, ConnectionConfig, QueryResult, SqlRenderer
from recon_core.adapters.duckdb import (
    ADAPTER_CONNECTION_FAILED,
    ADAPTER_QUERY_FAILED,
    AdapterLifecycleError,
    DuckDbAdapter,
)
from recon_core.adapters.duckdb import adapter as adapter_module

_QUERY = "SELECT private_synthetic_value"
_COLUMNS = ("value",)


class _Cursor:
    def __init__(self, description: object, rows: list[tuple[object, ...]]) -> None:
        self.description = description
        self.rows = rows
        self.fetch_sizes: list[int] = []

    def fetchmany(self, size: int) -> list[tuple[object, ...]]:
        self.fetch_sizes.append(size)
        return self.rows

    def fetchall(self) -> list[tuple[object, ...]]:
        raise AssertionError("Private transport must not fetch all rows")


class _Connection:
    def __init__(self, cursor: _Cursor, metadata: _Cursor | None = None) -> None:
        self.cursor = cursor
        self.metadata = metadata
        self.queries: list[str] = []
        self.closed = False

    def execute(self, query: str) -> _Cursor:
        self.queries.append(query)
        if query == _QUERY:
            return self.cursor
        if query == f"DESCRIBE {_QUERY}" and self.metadata is not None:
            return self.metadata
        raise RuntimeError("private_synthetic_value leaked")

    def close(self) -> None:
        self.closed = True


def _adapter(monkeypatch: pytest.MonkeyPatch, connection: _Connection) -> DuckDbAdapter:
    monkeypatch.setattr(
        adapter_module,
        "import_module",
        lambda name: SimpleNamespace(connect=lambda database: connection),
    )
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))
    adapter.connect()
    return adapter


def _execute(
    adapter: DuckDbAdapter, query: str = _QUERY, columns: tuple[str, ...] = _COLUMNS
) -> Any:
    execute = getattr(adapter, "_execute_aggregate_query", None)
    assert callable(execute), "Private typed aggregate execution boundary is not implemented"
    return execute(query, expected_columns=columns)


@pytest.mark.parametrize(
    ("logical_type", "value", "domain", "expected"),
    [
        ("TINYINT", 127, "exact_integer", 127),
        ("HUGEINT", 2**126 + 1, "exact_integer", 2**126 + 1),
        ("UBIGINT", 2**64 - 1, "exact_integer", 2**64 - 1),
        (
            "DECIMAL(38,18)",
            Decimal("99999999999999999999.000000000000000001"),
            "exact_decimal",
            Decimal("99999999999999999999.000000000000000001"),
        ),
        ("DOUBLE", 0.10000000000000003, "native_float", 0.10000000000000003),
        ("DOUBLE", -0.0, "native_float", -0.0),
        ("HUGEINT", None, "exact_integer", None),
        ("DECIMAL(38,18)", None, "exact_decimal", None),
        ("DOUBLE", None, "native_float", None),
        ("BIGNUM", "1000000000000000000000000000001", "exact_integer", 10**30 + 1),
        ("BIGNUM", 10**70 + 1, "exact_integer", 10**70 + 1),
    ],
)
def test_private_transport_preserves_native_numeric_values(
    monkeypatch: pytest.MonkeyPatch,
    logical_type: str,
    value: object,
    domain: str,
    expected: object,
) -> None:
    cursor = _Cursor((("value", logical_type),), [(value,)])
    connection = _Connection(cursor)
    adapter = _adapter(monkeypatch, connection)
    result = _execute(adapter)
    assert result.columns == _COLUMNS
    assert result.domains == (domain,)
    assert result.row == (expected,)
    assert type(result.row[0]) is type(expected)
    if isinstance(expected, float):
        assert math.copysign(1, result.row[0]) == math.copysign(1, expected)
    assert cursor.fetch_sizes == [2]
    assert connection.queries == [_QUERY]
    adapter.close()
    assert connection.closed


@pytest.mark.parametrize("sign", ("", "-"))
def test_private_transport_large_typed_integer_ignores_decimal_context(
    monkeypatch: pytest.MonkeyPatch, sign: str
) -> None:
    digits = sign + "1" + "0" * 5000 + "1"
    cursor = _Cursor((("value", "BIGNUM"),), [(digits,)])
    adapter = _adapter(monkeypatch, _Connection(cursor))
    limit = sys.get_int_max_str_digits()
    with localcontext() as context:
        context.prec = 3
        result = _execute(adapter)
        assert result.row[0] == int(Decimal(digits))
    assert type(result.row[0]) is int
    assert sys.get_int_max_str_digits() == limit
    adapter.close()


@pytest.mark.parametrize(
    ("description", "rows"),
    [
        (None, [(1,)]),
        ((("value",),), [(1,)]),
        ((("other", "BIGINT"),), [(1,)]),
        ((("value", "BIGINT"), ("value", "BIGINT")), [(1, 1)]),
        ((("value", "BIGINT"),), []),
        ((("value", "BIGINT"),), [(1,), (2,)]),
        ((("value", "BIGINT"),), [(1, 2)]),
        ((("value", "BIGINT"),), [(True,)]),
        ((("value", "BIGINT"),), [("1",)]),
        ((("value", "BIGINT"),), [(1.0,)]),
        ((("value", "VARCHAR"),), [("1",)]),
        ((("value", "BOOLEAN"),), [(True,)]),
        ((("value", "DECIMAL(38,18)"),), [(1.0,)]),
        ((("value", "DECIMAL(38,18)"),), [(Decimal("NaN"),)]),
        ((("value", "DOUBLE"),), [(1,)]),
        ((("value", "BIGNUM"),), [("01",)]),
        ((("value", "BIGNUM"),), [("1e3",)]),
        ((("value", "BIGNUM"),), [("private_synthetic_value",)]),
        ((("value", "DECIMAL(0,0)"),), [(Decimal(0),)]),
        ((("value", "NUMBER"),), [(1,)]),
    ],
)
def test_private_transport_rejects_invalid_envelope_without_leaking_values(
    monkeypatch: pytest.MonkeyPatch, description: object, rows: list[tuple[object, ...]]
) -> None:
    adapter = _adapter(monkeypatch, _Connection(_Cursor(description, rows)))
    with pytest.raises(AdapterLifecycleError) as caught:
        _execute(adapter)
    assert caught.value.diagnostic.code == ADAPTER_QUERY_FAILED
    assert "private_synthetic_value" not in repr(caught.value.diagnostic)
    assert "private_synthetic_value" not in str(caught.value)
    adapter.close()


@pytest.mark.parametrize(
    ("category", "logical_type", "value", "domain"),
    [
        ("NUMBER", "HUGEINT", 2**126 + 1, "exact_integer"),
        ("NUMBER", "DOUBLE", 0.1, "native_float"),
        ("STRING", "BIGNUM", "1000000000000000000000000000001", "exact_integer"),
    ],
)
def test_private_transport_resolves_legacy_logical_metadata(
    monkeypatch: pytest.MonkeyPatch,
    category: str,
    logical_type: str,
    value: object,
    domain: str,
) -> None:
    cursor = _Cursor((("value", category),), [(value,)])
    metadata = _Cursor(None, [("value", logical_type, "YES", None, None, None)])
    connection = _Connection(cursor, metadata)
    adapter = _adapter(monkeypatch, connection)
    result = _execute(adapter)
    assert result.domains == (domain,)
    assert result.row == (int(value) if isinstance(value, str) else value,)
    assert cursor.fetch_sizes == [2]
    assert metadata.fetch_sizes == [2]
    assert connection.queries == [_QUERY, f"DESCRIBE {_QUERY}"]
    adapter.close()


@pytest.mark.parametrize(
    "metadata_rows",
    [
        [],
        [("other", "BIGINT")],
        [("value", "BIGINT"), ("extra", "BIGINT")],
        [("value", "STRING")],
        [("value", "VARCHAR")],
        [("value",)],
    ],
)
def test_private_transport_rejects_unverified_legacy_metadata(
    monkeypatch: pytest.MonkeyPatch, metadata_rows: list[tuple[object, ...]]
) -> None:
    cursor = _Cursor((("value", "NUMBER"),), [(1,)])
    connection = _Connection(cursor, _Cursor(None, metadata_rows))
    adapter = _adapter(monkeypatch, connection)
    with pytest.raises(AdapterLifecycleError) as caught:
        _execute(adapter)
    assert caught.value.diagnostic.code == ADAPTER_QUERY_FAILED
    adapter.close()


def test_private_transport_requires_existing_open_connection() -> None:
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))
    with pytest.raises(AdapterLifecycleError) as caught:
        _execute(adapter)
    assert caught.value.diagnostic.code == ADAPTER_CONNECTION_FAILED


def test_private_transport_query_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection(_Cursor((("value", "BIGINT"),), [(1,)]))
    adapter = _adapter(monkeypatch, connection)
    with pytest.raises(AdapterLifecycleError) as caught:
        _execute(adapter, "SELECT private_synthetic_value error")
    assert caught.value.diagnostic.code == ADAPTER_QUERY_FAILED
    assert "private_synthetic_value" not in repr(caught.value.diagnostic)
    adapter.close()
    assert connection.closed


def test_public_adapter_contract_stays_unmodified() -> None:
    assert tuple(field.name for field in fields(QueryResult)) == ("columns", "rows", "row_count")
    assert not hasattr(BaseAdapter, "_execute_aggregate_query")
    assert not hasattr(SqlRenderer, "_execute_aggregate_query")


@pytest.fixture
def real_adapter() -> Any:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            importlib.import_module("duckdb")
        except ImportError:
            pytest.fail("Required DuckDB transport tests need .[dev,duckdb].", pytrace=False)
    else:
        pytest.importorskip("duckdb")
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))
    adapter.connect()
    try:
        yield adapter
    finally:
        adapter.close()


def test_private_transport_real_driver_domains_and_public_execute(real_adapter: Any) -> None:
    sql = (
        "SELECT CAST('9007199254740993' AS HUGEINT) AS i, "
        "CAST('99999999999999999999.000000000000000001' AS DECIMAL(38,18)) AS d, "
        "CAST('0.1' AS DOUBLE) AS f, CAST(NULL AS BIGINT) AS n"
    )
    result = _execute(real_adapter, sql, ("i", "d", "f", "n"))
    assert result.domains == ("exact_integer", "exact_decimal", "native_float", "exact_integer")
    assert result.row == (
        9007199254740993,
        Decimal("99999999999999999999.000000000000000001"),
        0.1,
        None,
    )
    public = real_adapter.execute("SELECT 1 AS value UNION ALL SELECT 2")
    assert public == QueryResult(columns=("value",), rows=((1,), (2,)), row_count=2)


def test_private_transport_real_driver_rejects_multiple_rows(real_adapter: Any) -> None:
    with pytest.raises(AdapterLifecycleError) as caught:
        _execute(real_adapter, "SELECT i AS value FROM range(10000) r(i)")
    assert caught.value.diagnostic.code == ADAPTER_QUERY_FAILED


def test_private_transport_real_driver_arbitrary_integer_availability(real_adapter: Any) -> None:
    version_parts = importlib.import_module("duckdb").__version__.split(".")[:2]
    version = tuple(int(part) for part in version_parts)
    if version < (1, 4):
        # Legacy engines are still required to transport ordinary exact integers.
        # Arbitrary-size native SUM availability is tested separately in the numeric probes.
        result = _execute(real_adapter, "SELECT CAST('9007199254740993' AS HUGEINT) AS value")
        assert result.domains == ("exact_integer",)
        assert result.row == (9007199254740993,)
        return
    digits = "1" + "0" * 5000 + "1"
    result = _execute(real_adapter, f"SELECT CAST('{digits}' AS BIGNUM) AS value")
    assert result.domains == ("exact_integer",)
    assert type(result.row[0]) is int
    assert result.row[0] == int(Decimal(digits))
