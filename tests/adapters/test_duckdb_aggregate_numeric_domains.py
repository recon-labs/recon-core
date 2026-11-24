"""Synthetic numeric-domain proof for bounded aggregate execution.

These tests exercise DuckDB SQL and driver transport, not Recon runtime.
No project data, authored contract, or filesystem database is used.
"""

import importlib
import math
import os
import re
import struct
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any

import pytest

_HUGE_MAX = 2**127 - 1
_HUGE_MIN = -(2**127)
_DECIMAL_MAX = 10**38 - 1
_EXACT_CASES = [
    ("TINYINT", 127, 126),
    ("SMALLINT", 32767, 32766),
    ("INTEGER", 2**31 - 1, 2**31 - 2),
    ("BIGINT", 2**53 + 1, 2**53),
    ("HUGEINT", 2**126 + 1, 2**126),
    ("UTINYINT", 255, 254),
    ("USMALLINT", 65535, 65534),
    ("UINTEGER", 2**32 - 1, 2**32 - 2),
    ("UBIGINT", 2**64 - 1, 2**64 - 2),
    ("BIGNUM", 10**70 + 1, 10**70),
    ("DECIMAL(38,0)", _DECIMAL_MAX, _DECIMAL_MAX - 1),
    (
        "DECIMAL(38,18)",
        Decimal("99999999999999999999.000000000000000001"),
        Decimal("99999999999999999999.000000000000000000"),
    ),
]
_INTEGER_TYPES = {
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "UHUGEINT",
    "BIGNUM",
    "VARINT",
}
_SUMMARY_COLUMNS = (
    "total_group_count",
    "source_only_group_count",
    "target_only_group_count",
    "both_null_group_count",
    "null_mismatch_group_count",
    "valid_numeric_pair_count",
    "invalid_numeric_count",
    "min_signed_diff",
    "max_signed_diff",
)


@pytest.fixture
def con() -> Any:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            duckdb = importlib.import_module("duckdb")
        except ImportError:
            pytest.fail("Required DuckDB numeric tests need .[dev,duckdb].", pytrace=False)
    else:
        duckdb = pytest.importorskip("duckdb")
    connection = duckdb.connect(":memory:")
    try:
        connection.execute("SET threads=1")
        yield connection
    finally:
        connection.close()


def _cast(value: Any, kind: str) -> str:
    if value is None:
        return f"CAST(NULL AS {kind})"
    return f"CAST('{value}' AS {kind})"


def _kind(sql_type: str) -> str:
    return sql_type.upper().split("(")[0]


def _exact(value: Any, sql_type: str) -> Fraction:
    kind = _kind(sql_type)
    if type(value) is int and kind in _INTEGER_TYPES:
        return Fraction(value)
    if isinstance(value, Decimal) and value.is_finite() and kind == "DECIMAL":
        return Fraction(value)
    # Driver strings are accepted only with explicit native integer type evidence.
    if (
        isinstance(value, str)
        and kind in {"BIGNUM", "VARINT"}
        and re.fullmatch(r"-?(0|[1-9][0-9]*)", value)
    ):
        return Fraction(Decimal(value))
    raise AssertionError(f"Unproven exact transport: {sql_type}, {type(value).__name__}")


def _values(kind: str, values: list[Any]) -> str:
    return ",".join(f"({_cast(value, kind)})" for value in values)


def _scalar_sql(kind: str, source: list[Any], target: list[Any]) -> str:
    return (
        f"WITH s AS (SELECT sum(v) a FROM (VALUES {_values(kind, source)}) q(v)), "
        f"t AS (SELECT sum(v) b FROM (VALUES {_values(kind, target)}) q(v)) "
        "SELECT a, b, a-b d FROM s CROSS JOIN t"
    )


def _query(con: Any, sql: str) -> tuple[tuple[str, ...], tuple[str, ...], list[Any]]:
    cursor = con.execute(sql)
    names = tuple(str(col[0]) for col in cursor.description)
    types = tuple(str(col[1]) for col in cursor.description)
    rows = cursor.fetchall()
    # Older Python drivers report broad DB-API categories instead of logical types.
    if _engine_version()[0] == 1 and any(t.upper() in {"NUMBER", "STRING"} for t in types):
        description = con.execute(f"DESCRIBE {sql}").fetchall()
        assert tuple(str(col[0]) for col in description) == names
        types = tuple(str(col[1]) for col in description)
    return names, types, rows


def _engine_version() -> tuple[int, ...]:
    duckdb = importlib.import_module("duckdb")
    return tuple(int(part) for part in duckdb.__version__.split(".")[:2])


def _scalar(con: Any, kind: str, source: list[Any], target: list[Any]) -> tuple[Any, Any]:
    names, types, rows = _query(con, _scalar_sql(kind, source, target))
    assert names == ("a", "b", "d")
    assert len(rows) == 1 and len(rows[0]) == 3
    assert types[0] == types[1]
    return types, rows[0]


@pytest.mark.parametrize(("kind", "a", "b"), _EXACT_CASES)
@pytest.mark.parametrize("direction", (1, -1))
def test_exact_native_difference(con: Any, kind: str, a: Any, b: Any, direction: int) -> None:
    if direction == -1:
        a, b = b, a
    types, row = _scalar(con, kind, [a], [b])
    observed = tuple(_exact(v, t) for v, t in zip(row, types, strict=True))
    assert observed == (Fraction(a), Fraction(b), Fraction(a) - Fraction(b)), (types, row)


@pytest.mark.parametrize(("kind", "a", "b"), _EXACT_CASES)
def test_exact_multirow_sum(con: Any, kind: str, a: Any, b: Any) -> None:
    step = -1 if kind.startswith("DECIMAL") else 1
    types, row = _scalar(con, kind, [b, step], [b])
    observed = tuple(_exact(v, t) for v, t in zip(row, types, strict=True))
    assert observed == (Fraction(b) + step, Fraction(b), Fraction(step)), (types, row)


def _float_value(kind: str, value: Any) -> float:
    value = float(value)
    if kind == "FLOAT":
        return struct.unpack("f", struct.pack("f", value))[0]
    return value


def _check_float_row(types: Any, row: Any, a: float, b: float) -> None:
    assert tuple(_kind(t) for t in types) == ("DOUBLE", "DOUBLE", "DOUBLE"), types
    assert all(type(v) is float and math.isfinite(v) for v in row), row
    assert tuple(row) == (a, b, a - b), (types, row)


@pytest.mark.parametrize("kind", ("FLOAT", "DOUBLE"))
@pytest.mark.parametrize("direction", (1, -1))
def test_finite_native_difference(con: Any, kind: str, direction: int) -> None:
    a = _float_value(kind, 0.1) + _float_value(kind, 0.2)
    b = _float_value(kind, 0.2)
    source = ["0.1", "0.2"]
    target = ["0.2"]
    if direction == -1:
        a, b = b, a
        source, target = target, source
    types, row = _scalar(con, kind, source, target)
    _check_float_row(types, row, a, b)


@pytest.mark.parametrize("kind", ("FLOAT", "DOUBLE"))
def test_signed_zero(con: Any, kind: str) -> None:
    types, row = _scalar(con, kind, ["-0.0"], ["0.0"])
    _check_float_row(types, row, 0.0, 0.0)


def test_strict_native_float_threshold(con: Any) -> None:
    types, row = _scalar(con, "DOUBLE", ["0.1", "0.2"], ["0.2"])
    _check_float_row(types, row, 0.1 + 0.2, 0.2)
    magnitude = Fraction(Decimal(str(abs(row[2]))))
    assert magnitude > Fraction(Decimal("0.1"))
    assert magnitude == Fraction(Decimal("0.10000000000000003"))
    assert magnitude < Fraction(Decimal("0.101"))


@pytest.mark.parametrize(("a", "b"), [("5e-324", "0"), ("1e308", "9e307")])
def test_double_finite_extremes(con: Any, a: str, b: str) -> None:
    types, row = _scalar(con, "DOUBLE", [a], [b])
    _check_float_row(types, row, float(a), float(b))


@pytest.mark.parametrize("kind", ("BIGINT", "DECIMAL(38,18)", "BIGNUM", "DOUBLE"))
def test_null_and_zero(con: Any, kind: str) -> None:
    for a, b in ((None, None), (None, 0), (0, None)):
        types, row = _scalar(con, kind, [a], [b])
        for value, sql_type, expected in zip(row, types, (a, b, None), strict=True):
            if expected is None:
                assert value is None
            elif _kind(sql_type) == "DOUBLE":
                assert type(value) is float and value == expected
            else:
                assert _exact(value, sql_type) == expected


@pytest.mark.parametrize(
    ("kind", "source", "target", "expected"),
    [
        ("HUGEINT", [_HUGE_MAX, 1], [0], (_HUGE_MAX + 1, 0, _HUGE_MAX + 1)),
        ("HUGEINT", [_HUGE_MAX], [_HUGE_MIN], (_HUGE_MAX, _HUGE_MIN, 2**128 - 1)),
        ("DECIMAL(38,0)", [_DECIMAL_MAX, 1], [0], (_DECIMAL_MAX + 1, 0, _DECIMAL_MAX + 1)),
        (
            "DECIMAL(38,0)",
            [_DECIMAL_MAX],
            [-_DECIMAL_MAX],
            (_DECIMAL_MAX, -_DECIMAL_MAX, 2 * _DECIMAL_MAX),
        ),
    ],
)
def test_exact_overflow_is_not_silent(
    con: Any, kind: str, source: list[Any], target: list[Any], expected: tuple[int, ...]
) -> None:
    try:
        types, row = _scalar(con, kind, source, target)
    except Exception as exc:
        # An explicit native arithmetic error is acceptable, but not a binder error.
        if type(exc).__name__ not in {"OutOfRangeException", "ConversionException"}:
            raise
        assert re.search(r"overflow|out.of.range|too large", str(exc), re.IGNORECASE)
    else:
        assert tuple(_exact(v, t) for v, t in zip(row, types, strict=True)) == expected


@pytest.mark.parametrize("kind", ("FLOAT", "DOUBLE"))
@pytest.mark.parametrize("special", ("NaN", "Infinity", "-Infinity"))
def test_nonfinite_native_result(con: Any, kind: str, special: str) -> None:
    types, row = _scalar(con, kind, [special], ["0"])
    assert all(_kind(t) == "DOUBLE" for t in types)
    assert not math.isfinite(row[0]) and not math.isfinite(row[2])
    _, _, flags = _query(
        con,
        "SELECT isfinite(a), isfinite(b), isfinite(d) "
        f"FROM ({_scalar_sql(kind, [special], ['0'])})",
    )
    assert flags == [tuple(math.isfinite(v) for v in row)]


@pytest.mark.parametrize(
    ("source", "target"),
    [(["1e308", "1e308"], ["0"]), (["1e308"], ["-1e308"])],
)
def test_double_overflow(con: Any, source: list[str], target: list[str]) -> None:
    _, row = _scalar(con, "DOUBLE", source, target)
    assert not math.isfinite(row[2])


def _group_relation(kind: str, entries: list[tuple[Any, Any, Any]]) -> str:
    if not entries:
        return f"SELECT NULL::INTEGER k, NULL::INTEGER k2, {_cast(None, kind)} v WHERE FALSE"
    values = ",".join(
        f"({_cast(k, 'INTEGER')},{_cast(k2, 'INTEGER')},{_cast(v, kind)})" for k, k2, v in entries
    )
    return f"SELECT * FROM (VALUES {values}) q(k,k2,v)"


def _grouped(
    con: Any,
    kind: str,
    source: str,
    target: str,
    counts: tuple[int, ...],
) -> tuple[Any, Any]:
    finite = (
        "(sp IS TRUE AND a IS NOT NULL AND NOT isfinite(a)) "
        "OR (tp IS TRUE AND b IS NOT NULL AND NOT isfinite(b)) "
        "OR (d IS NOT NULL AND NOT isfinite(d))"
        if kind in {"FLOAT", "DOUBLE"}
        else "FALSE"
    )
    sql = f"""
        WITH s AS (SELECT k,k2,sum(v) a,true sp FROM ({source}) q GROUP BY k,k2),
        t AS (SELECT k,k2,sum(v) b,true tp FROM ({target}) q GROUP BY k,k2),
        j AS (
            SELECT sp,tp,a,b,
                CASE WHEN sp IS TRUE AND tp IS TRUE AND a IS NOT NULL AND b IS NOT NULL
                     THEN a-b END d
            FROM s FULL OUTER JOIN t
            ON s.k IS NOT DISTINCT FROM t.k AND s.k2 IS NOT DISTINCT FROM t.k2
        ),
        c AS (
            SELECT d, CASE
                WHEN {finite} THEN 'invalid'
                WHEN tp IS NULL THEN 'source_only'
                WHEN sp IS NULL THEN 'target_only'
                WHEN a IS NULL AND b IS NULL THEN 'both_null'
                WHEN a IS NULL OR b IS NULL THEN 'null_mismatch'
                ELSE 'valid' END category FROM j
        )
        SELECT count(*) total_group_count,
            count(*) FILTER (WHERE category='source_only') source_only_group_count,
            count(*) FILTER (WHERE category='target_only') target_only_group_count,
            count(*) FILTER (WHERE category='both_null') both_null_group_count,
            count(*) FILTER (WHERE category='null_mismatch') null_mismatch_group_count,
            count(*) FILTER (WHERE category='valid') valid_numeric_pair_count,
            count(*) FILTER (WHERE category='invalid') invalid_numeric_count,
            min(d) FILTER (WHERE category='valid') min_signed_diff,
            max(d) FILTER (WHERE category='valid') max_signed_diff
        FROM c
    """
    names, types, rows = _query(con, sql)
    assert names == _SUMMARY_COLUMNS
    assert len(rows) == 1 and len(rows[0]) == 9
    row = rows[0]
    assert all(type(v) is int and v >= 0 for v in row[:7])
    assert row[:7] == counts and sum(row[1:7]) == row[0], (types, row)
    return types[7:], row[7:]


def _mixed_groups(a: Any, b: Any) -> tuple[list[Any], list[Any]]:
    return (
        [(None, 1, a), (2, None, b), (3, 3, None), (4, 4, None), (5, 5, b)],
        [(None, 1, b), (2, None, a), (3, 3, None), (4, 4, b), (6, 6, None)],
    )


@pytest.mark.parametrize(("kind", "a", "b"), _EXACT_CASES)
def test_exact_grouped_extrema(con: Any, kind: str, a: Any, b: Any) -> None:
    source, target = _mixed_groups(a, b)
    types, row = _grouped(
        con,
        kind,
        _group_relation(kind, source),
        _group_relation(kind, target),
        (6, 1, 1, 1, 1, 2, 0),
    )
    magnitude = abs(Fraction(a) - Fraction(b))
    observed = tuple(_exact(v, t) for v, t in zip(row, types, strict=True))
    assert observed == (-magnitude, magnitude), (types, row)


@pytest.mark.parametrize("kind", ("FLOAT", "DOUBLE"))
@pytest.mark.parametrize("invalid", (False, True))
def test_float_grouped_extrema(con: Any, kind: str, invalid: bool) -> None:
    source, target = _mixed_groups("0.3", "0.2")
    counts = (6, 1, 1, 1, 1, 2, 0)
    if invalid:
        source.extend([(7, 7, "NaN"), (8, 8, "Infinity")])
        target.append((8, 8, None))
        counts = (8, 1, 1, 1, 1, 2, 2)
    types, row = _grouped(
        con, kind, _group_relation(kind, source), _group_relation(kind, target), counts
    )
    magnitude = abs(_float_value(kind, 0.3) - _float_value(kind, 0.2))
    assert types == ("DOUBLE", "DOUBLE")
    assert all(type(v) is float and math.isfinite(v) for v in row)
    assert row == (-magnitude, magnitude)


def test_empty_grouped_summary(con: Any) -> None:
    relation = _group_relation("BIGINT", [])
    _, row = _grouped(con, "BIGINT", relation, relation, (0, 0, 0, 0, 0, 0, 0))
    assert row == (None, None)


def test_grouped_summary_is_bounded(con: Any) -> None:
    source = "SELECT i k, i%3 k2, 2::BIGINT v FROM range(10000) r(i)"
    target = "SELECT i k, i%3 k2, 1::BIGINT v FROM range(10000) r(i)"
    types, row = _grouped(con, "BIGINT", source, target, (10000, 0, 0, 0, 0, 10000, 0))
    assert tuple(_exact(v, t) for v, t in zip(row, types, strict=True)) == (1, 1)


def test_signed_hugeint_minimum_grouped_extrema(con: Any) -> None:
    kind = "HUGEINT"
    types, row = _grouped(
        con,
        kind,
        _group_relation(kind, [(1, 1, _HUGE_MIN)]),
        _group_relation(kind, [(1, 1, 0)]),
        (1, 0, 0, 0, 0, 1, 0),
    )
    extrema = tuple(_exact(v, t) for v, t in zip(row, types, strict=True))
    assert extrema == (_HUGE_MIN, _HUGE_MIN)
    assert max(abs(v) for v in extrema) == 2**127


def test_bignum_sum_transport_independent_of_subtraction(con: Any) -> None:
    sql = f"SELECT sum(v) FROM (VALUES {_values('BIGNUM', [10**70, 1])}) q(v)"
    _, types, rows = _query(con, sql)
    assert len(rows) == 1 and len(rows[0]) == 1
    assert _exact(rows[0][0], types[0]) == 10**70 + 1, (types, rows)


def test_arbitrary_precision_availability(con: Any) -> None:
    # The legacy lane explicitly deselects BIGNUM arithmetic cases, not ordinary domains.
    # Establish whether a native arbitrary-size integer SUM exists rather than assume it.
    if _engine_version() >= (1, 4):
        types, row = _scalar(con, "BIGNUM", [10**70, 1], [10**70])
        observed = tuple(_exact(v, t) for v, t in zip(row, types, strict=True))
        assert observed == (10**70 + 1, 10**70, 1)
        print("Arbitrary-size SUM/difference logical types:", types)
        return

    try:
        input_metadata = con.execute("DESCRIBE SELECT CAST('1' AS VARINT) AS v").fetchall()
    except Exception as exc:
        assert type(exc).__name__ in {"CatalogException", "BinderException", "ParserException"}
        assert re.search(r"varint|type", str(exc), re.IGNORECASE)
        print("Legacy arbitrary-size input type unavailable:", type(exc).__name__)
        return
    input_type = str(input_metadata[0][1])
    assert _kind(input_type) in {"VARINT", "BIGNUM"}
    sql = _scalar_sql("VARINT", [10**70, 1], [10**70])
    try:
        metadata = con.execute(f"DESCRIBE {sql}").fetchall()
    except Exception as exc:
        assert type(exc).__name__ == "BinderException"
        assert re.search(r"sum|function|overload", str(exc), re.IGNORECASE)
        print("Legacy exact SUM/difference cannot bind:", input_type, type(exc).__name__)
        return

    types = tuple(str(col[1]) for col in metadata)
    print("Legacy arbitrary-size SUM/difference logical types:", input_type, types)
    # A lossy or fixed-width aggregate is not exact arbitrary-size SUM support.
    # Unexpected exact native availability must be reviewed, not silently deselected.
    assert not all(_kind(t) in {"VARINT", "BIGNUM"} for t in types)


@pytest.mark.parametrize("direction", (1, -1))
def test_bignum_transport_beyond_python_digit_limit(con: Any, direction: int) -> None:
    digits = "1" + "0" * 5000 + "1"
    value = digits if direction == 1 else "-" + digits
    with localcontext() as context:
        context.prec = 6
        types, row = _scalar(con, "BIGNUM", [value], [0])
        expected = Fraction(Decimal(value))
        assert _exact(row[0], types[0]) == expected
        assert _exact(row[1], types[1]) == 0
        assert _exact(row[2], types[2]) == expected
        counts = (1, 0, 0, 0, 0, 1, 0)
        types, row = _grouped(
            con,
            "BIGNUM",
            _group_relation("BIGNUM", [(1, 1, value)]),
            _group_relation("BIGNUM", [(1, 1, 0)]),
            counts,
        )
        assert _exact(row[0], types[0]) == expected
        assert _exact(row[1], types[1]) == expected


@pytest.mark.parametrize("threads", (1, 4))
def test_bignum_parallel_sum_and_cancellation(con: Any, threads: int) -> None:
    con.execute(f"SET threads={threads}")
    magnitude = 10**70
    con.execute(
        "CREATE TEMP TABLE arbitrary_values AS "
        f"SELECT i%2 AS k, CAST(CASE WHEN i%2=0 THEN '{magnitude}' "
        f"ELSE '-{magnitude}' END AS BIGNUM) AS v FROM range(524288) r(i)"
    )
    _, types, rows = _query(con, "SELECT sum(v) FROM arbitrary_values")
    assert _exact(rows[0][0], types[0]) == 0
    _, types, rows = _query(con, "SELECT k,sum(v) FROM arbitrary_values GROUP BY k ORDER BY k")
    expected = 262144 * 10**70
    assert [(_exact(row[0], types[0]), _exact(row[1], types[1])) for row in rows] == [
        (0, expected),
        (1, -expected),
    ]
