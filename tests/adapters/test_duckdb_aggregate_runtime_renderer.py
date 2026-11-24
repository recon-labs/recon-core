"""Private aggregate runtime rendering against actual supported DuckDB engines."""

import importlib
import os
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest

from recon_core.adapters import ConnectionConfig, Relation
from recon_core.adapters._aggregate_runtime import _AggregateQueryResult, _NumericDomain
from recon_core.adapters.duckdb import AdapterLifecycleError, DuckDbAdapter, DuckDbSqlRenderer

_SCALAR_COLUMNS = ("source_aggregate_value", "target_aggregate_value", "aggregate_diff")
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
_RELATIONS = {
    "source_relation": Relation(identifier="source table"),
    "target_relation": Relation(identifier="target table"),
}


@pytest.fixture
def adapter() -> Iterator[DuckDbAdapter]:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            importlib.import_module("duckdb")
        except ImportError:
            pytest.fail("Required DuckDB renderer tests need .[dev,duckdb].", pytrace=False)
    else:
        pytest.importorskip("duckdb")
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))
    adapter.connect()
    try:
        yield adapter
    finally:
        adapter.close()


def _operations(keys: tuple[str, ...]) -> tuple[dict[str, object], ...]:
    kind = "grouped_aggregate" if keys else "aggregate"
    operations: list[dict[str, object]] = [
        {"type": kind, "side": side, "aggregate": "sum", "column": "v"}
        for side in ("source", "target")
    ]
    if keys:
        for operation in operations:
            operation["group_by"] = list(keys)
    operations.append({"type": "compare_grouped_aggregates" if keys else "compare_aggregates"})
    return tuple(operations)


def _plan(keys: tuple[str, ...] = ()) -> Any:
    try:
        module = importlib.import_module("recon_core.adapters.duckdb._aggregate_runtime")
    except ModuleNotFoundError as exc:
        assert exc.name == "recon_core.adapters.duckdb._aggregate_runtime"
        pytest.fail("Private bounded aggregate renderer is not implemented", pytrace=False)
    return module._DuckDbAggregateRuntimeRenderer().render_plan(_operations(keys), **_RELATIONS)


def _tables(adapter: DuckDbAdapter, source: str, target: str) -> None:
    adapter.execute(f'CREATE TABLE "source table" AS {source}')
    adapter.execute(f'CREATE TABLE "target table" AS {target}')


def _guard(adapter: DuckDbAdapter, guard: Any) -> None:
    result = adapter._execute_aggregate_query(guard.sql, expected_columns=("type_check",))
    assert result.row == (1,)
    assert result.domains == ("exact_integer",)


def _domain(adapter: DuckDbAdapter, plan: Any) -> Any:
    for guard in plan.type_guards:
        _guard(adapter, guard)
    proof = adapter._execute_aggregate_query(
        plan.domain_guard.sql, expected_columns=("numeric_domain",)
    )
    return plan.domain_from_guard(proof)


def _result(adapter: DuckDbAdapter, plan: Any) -> Any:
    domain = _domain(adapter, plan)
    query = plan.final_query(domain)
    result = adapter._execute_aggregate_query(query.sql, expected_columns=plan.columns)
    assert result.columns == plan.columns
    return result


@pytest.mark.parametrize(
    ("kind", "a", "b", "expected", "domain"),
    [
        ("TINYINT", "127", "126", 1, "exact_integer"),
        ("SMALLINT", "32767", "32766", 1, "exact_integer"),
        ("INTEGER", str(2**31 - 1), str(2**31 - 2), 1, "exact_integer"),
        ("BIGINT", "9007199254740993", "9007199254740992", 1, "exact_integer"),
        ("HUGEINT", str(2**126 + 1), str(2**126), 1, "exact_integer"),
        ("UTINYINT", "255", "254", 1, "exact_integer"),
        ("USMALLINT", "65535", "65534", 1, "exact_integer"),
        ("UINTEGER", str(2**32 - 1), str(2**32 - 2), 1, "exact_integer"),
        ("UBIGINT", str(2**64 - 1), str(2**64 - 2), 1, "exact_integer"),
        ("DECIMAL(38,0)", str(10**38 - 1), str(10**38 - 2), Decimal(1), "exact_decimal"),
        (
            "DECIMAL(38,18)",
            "99999999999999999999.000000000000000001",
            "99999999999999999999.000000000000000000",
            Decimal("0.000000000000000001"),
            "exact_decimal",
        ),
        ("FLOAT", "0.3", "0.2", None, "native_float"),
        ("DOUBLE", "0.3", "0.2", None, "native_float"),
    ],
)
@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.regression_capture("duckdb-private-aggregate-native-domain-guards")
def test_runtime_renderer_native_domains(
    adapter: DuckDbAdapter,
    kind: str,
    a: str,
    b: str,
    expected: object,
    domain: str,
    grouped: bool,
) -> None:
    _tables(
        adapter,
        f"SELECT 1 AS k, CAST('{a}' AS {kind}) AS v",
        f"SELECT 1 AS k, CAST('{b}' AS {kind}) AS v",
    )
    plan = _plan(("k",) if grouped else ())
    assert _domain(adapter, plan) == domain
    result = _result(adapter, plan)
    if grouped:
        assert result.columns == _SUMMARY_COLUMNS
        assert result.row[:7] == (1, 0, 0, 0, 0, 1, 0)
        assert result.domains[:7] == ("exact_integer",) * 7
        assert result.domains[7:] == (domain, domain)
        assert result.row[7] == result.row[8]
        observed = result.row[7]
    else:
        assert result.columns == _SCALAR_COLUMNS
        assert result.domains == (domain,) * 3
        observed = result.row[2]
    if expected is not None:
        assert observed == expected
    else:
        reference = adapter.execute(
            f"SELECT CAST('{a}' AS {kind})::DOUBLE - CAST('{b}' AS {kind})::DOUBLE"
        )
        assert observed == reference.rows[0][0]


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.parametrize(
    ("source_type", "target_type"),
    [
        ("BOOLEAN", "BOOLEAN"),
        ("VARCHAR", "VARCHAR"),
        ("UHUGEINT", "UHUGEINT"),
        ("INTEGER", "BIGINT"),
        ("DECIMAL(10,2)", "DECIMAL(10,3)"),
    ],
)
@pytest.mark.regression_capture("duckdb-private-aggregate-native-domain-guards")
def test_runtime_renderer_input_guards_fail_before_sum_binding(
    adapter: DuckDbAdapter, grouped: bool, source_type: str, target_type: str
) -> None:
    _tables(
        adapter,
        f"SELECT 1 AS k, NULL::{source_type} AS v WHERE FALSE",
        f"SELECT 1 AS k, NULL::{target_type} AS v WHERE FALSE",
    )
    plan = _plan(("k",) if grouped else ())
    assert plan.type_guards
    for guard in plan.type_guards[:-1]:
        _guard(adapter, guard)
    assert "sum(" not in plan.type_guards[-1].sql.lower()
    with pytest.raises(AdapterLifecycleError):
        _guard(adapter, plan.type_guards[-1])


@pytest.mark.regression_capture("duckdb-private-aggregate-native-domain-guards")
def test_runtime_renderer_empty_group_key_mismatch(adapter: DuckDbAdapter) -> None:
    _tables(
        adapter,
        "SELECT NULL::INTEGER AS k, NULL::BIGINT AS v WHERE FALSE",
        "SELECT NULL::BIGINT AS k, NULL::BIGINT AS v WHERE FALSE",
    )
    with pytest.raises(AdapterLifecycleError):
        _guard(adapter, _plan(("k",)).type_guards[0])


@pytest.mark.regression_capture("duckdb-private-bounded-grouped-summary")
def test_runtime_renderer_composite_null_keys_and_alias_collisions(adapter: DuckDbAdapter) -> None:
    _tables(
        adapter,
        "SELECT * FROM (VALUES (NULL,1,4),(2,NULL,1),(3,3,NULL),"
        '(4,4,NULL),(5,5,1)) q("aggregate_value","source_present",v)',
        "SELECT * FROM (VALUES (NULL,1,1),(2,NULL,4),(3,3,NULL),"
        '(4,4,1),(6,6,NULL)) q("aggregate_value","source_present",v)',
    )
    result = _result(adapter, _plan(("aggregate_value", "source_present")))
    assert result.row == (6, 1, 1, 1, 1, 2, 0, -3, 3)


@pytest.mark.regression_capture("duckdb-private-bounded-grouped-summary")
def test_runtime_renderer_invalid_precedes_presence_and_null(adapter: DuckDbAdapter) -> None:
    _tables(
        adapter,
        "SELECT * FROM (VALUES (1,'NaN'::DOUBLE),(2,'Infinity'::DOUBLE),"
        "(3,1e308::DOUBLE),(4,4::DOUBLE)) q(k,v)",
        "SELECT * FROM (VALUES (2,NULL::DOUBLE),(3,-1e308::DOUBLE),(4,1::DOUBLE)) q(k,v)",
    )
    result = _result(adapter, _plan(("k",)))
    assert result.row == (4, 0, 0, 0, 0, 1, 3, 3.0, 3.0)


@pytest.mark.regression_capture("duckdb-private-bounded-grouped-summary")
def test_runtime_renderer_full_union_is_bounded(adapter: DuckDbAdapter) -> None:
    _tables(
        adapter,
        "SELECT i AS k, 2::BIGINT AS v FROM range(10000) q(i)",
        "SELECT i AS k, 1::BIGINT AS v FROM range(10000) q(i)",
    )
    result = _result(adapter, _plan(("k",)))
    assert result.row == (10000, 0, 0, 0, 0, 10000, 0, 1, 1)


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.regression_capture("duckdb-private-bounded-grouped-summary")
def test_runtime_renderer_empty_relations(adapter: DuckDbAdapter, grouped: bool) -> None:
    empty = "SELECT NULL::INTEGER AS k, NULL::BIGINT AS v WHERE FALSE"
    _tables(adapter, empty, empty)
    result = _result(adapter, _plan(("k",) if grouped else ()))
    assert result.row == ((0, 0, 0, 0, 0, 0, 0, None, None) if grouped else (None, None, None))


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.regression_capture("duckdb-private-aggregate-native-domain-guards")
def test_runtime_renderer_arbitrary_integer_version_availability(
    adapter: DuckDbAdapter, grouped: bool
) -> None:
    version = tuple(
        int(part) for part in importlib.import_module("duckdb").__version__.split(".")[:2]
    )
    plan = _plan(("k",) if grouped else ())
    if version < (1, 3):
        with pytest.raises(AdapterLifecycleError):
            adapter.execute("SELECT CAST('1' AS VARINT)")
        return
    if version < (1, 4):
        _tables(adapter, "SELECT 1 AS k, 1::VARINT AS v", "SELECT 1 AS k, 1::VARINT AS v")
        with pytest.raises(AdapterLifecycleError):
            _domain(adapter, plan)
        return
    digits = "1" + "0" * 5000 + "1"
    _tables(
        adapter,
        f"SELECT 1 AS k, CAST('{digits}' AS BIGNUM) AS v",
        "SELECT 1 AS k, 0::BIGNUM AS v",
    )
    result = _result(adapter, plan)
    expected = int(Decimal(digits))
    if grouped:
        assert result.row[:7] == (1, 0, 0, 0, 0, 1, 0)
        assert result.row[7] == result.row[8] == expected
    else:
        assert result.row == (expected, 0, expected)


@pytest.mark.regression_capture("duckdb-private-aggregate-renderer-separation")
def test_runtime_renderer_does_not_replace_public_detail_renderer() -> None:
    public = DuckDbSqlRenderer().render_plan(_operations(("k",)), **_RELATIONS)
    private = _plan(("k",))
    assert private.columns == _SUMMARY_COLUMNS
    assert "source_k" in public[-1].sql
    assert "target_k" in public[-1].sql
    assert "total_group_count" not in public[-1].sql
    assert private.required_capabilities == ("grouped_aggregate", "cte_support")
    assert private.final_query("exact_integer").required_capabilities == (
        "grouped_aggregate",
        "cte_support",
    )


@pytest.mark.parametrize(
    ("columns", "domains", "row"),
    [
        (("wrong",), (_NumericDomain.EXACT_INTEGER,), (1,)),
        (("numeric_domain",), (_NumericDomain.NATIVE_FLOAT,), (1,)),
        (("numeric_domain",), (_NumericDomain.EXACT_INTEGER,), ()),
        (("numeric_domain",), (_NumericDomain.EXACT_INTEGER,), (1, 2)),
        (("numeric_domain",), (_NumericDomain.EXACT_INTEGER,), (True,)),
        (("numeric_domain",), (_NumericDomain.EXACT_INTEGER,), (0,)),
        (("numeric_domain",), (_NumericDomain.EXACT_INTEGER,), (4,)),
        (("numeric_domain",), (_NumericDomain.EXACT_INTEGER,), (None,)),
    ],
)
@pytest.mark.regression_capture("duckdb-private-aggregate-native-domain-guards")
def test_runtime_renderer_rejects_malformed_domain_proof(
    columns: Any, domains: Any, row: Any
) -> None:
    plan = _plan()
    result = _AggregateQueryResult(columns=columns, domains=domains, row=row)
    with pytest.raises(ValueError, match="Invalid aggregate numeric domain proof"):
        plan.domain_from_guard(result)
    with pytest.raises(ValueError, match="Unproven aggregate numeric domain"):
        plan.final_query("unverified")


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.regression_capture("duckdb-private-aggregate-native-domain-guards")
def test_runtime_renderer_native_float_subtraction_regression(
    adapter: DuckDbAdapter, grouped: bool
) -> None:
    _tables(
        adapter,
        "SELECT 1 AS k, v FROM (VALUES (0.1::DOUBLE),(0.2::DOUBLE)) q(v)",
        "SELECT 1 AS k, 0.2::DOUBLE AS v",
    )
    result = _result(adapter, _plan(("k",) if grouped else ()))
    expected = (0.1 + 0.2) - 0.2
    assert expected == 0.10000000000000003
    if grouped:
        assert result.row == (1, 0, 0, 0, 0, 1, 0, expected, expected)
    else:
        assert result.row == (0.1 + 0.2, 0.2, expected)


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.regression_capture("duckdb-private-bounded-grouped-summary")
def test_runtime_renderer_null_is_distinct_from_zero(adapter: DuckDbAdapter, grouped: bool) -> None:
    _tables(adapter, "SELECT 1 AS k, NULL::BIGINT AS v", "SELECT 1 AS k, 0::BIGINT AS v")
    result = _result(adapter, _plan(("k",) if grouped else ()))
    assert result.row == ((1, 0, 0, 0, 1, 0, 0, None, None) if grouped else (None, 0, None))


@pytest.mark.regression_capture("duckdb-private-aggregate-native-domain-guards")
def test_runtime_renderer_signed_hugeint_minimum(adapter: DuckDbAdapter) -> None:
    minimum = -(2**127)
    _tables(
        adapter,
        f"SELECT 1 AS k, CAST('{minimum}' AS HUGEINT) AS v",
        "SELECT 1 AS k, 0::HUGEINT AS v",
    )
    result = _result(adapter, _plan(("k",)))
    assert result.row == (1, 0, 0, 0, 0, 1, 0, minimum, minimum)


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.parametrize("operation", ("sum", "difference"))
@pytest.mark.parametrize("kind", ("HUGEINT", "DECIMAL(38,0)"))
@pytest.mark.regression_capture("duckdb-private-aggregate-native-domain-guards")
def test_runtime_renderer_overflow_guards_do_not_read_aggregate_data(
    adapter: DuckDbAdapter, grouped: bool, operation: str, kind: str
) -> None:
    maximum = 2**127 - 1 if kind == "HUGEINT" else 10**38 - 1
    source = f"SELECT 1 AS k, CAST('{maximum}' AS {kind}) AS v"
    if operation == "sum":
        source += f" UNION ALL SELECT 1, 1::{kind}"
    _tables(
        adapter,
        source,
        f"SELECT 1 AS k, CAST('{-maximum if operation == 'difference' else 0}' AS {kind}) AS v",
    )
    plan = _plan(("k",) if grouped else ())
    domain = _domain(adapter, plan)
    assert domain == ("exact_integer" if kind == "HUGEINT" else "exact_decimal")
    query = plan.final_query(domain)
    # Native overflow must not become a rounded or wrapped comparison.
    try:
        result = adapter._execute_aggregate_query(query.sql, expected_columns=plan.columns)
    except AdapterLifecycleError as exc:
        assert exc.diagnostic.code == "RC_ADAPTER_QUERY_FAILED"
        assert str(maximum) not in repr(exc.diagnostic)
        assert "source table" not in repr(exc.diagnostic)
    else:
        expected = maximum + 1 if operation == "sum" else maximum * 2
        if grouped:
            assert result.row == (1, 0, 0, 0, 0, 1, 0, expected, expected)
        else:
            assert result.row[2] == expected


@pytest.mark.regression_capture("duckdb-private-bounded-grouped-summary")
def test_runtime_renderer_repeated_and_quoted_group_keys(adapter: DuckDbAdapter) -> None:
    _tables(
        adapter,
        'SELECT NULL::INTEGER AS "key ""with quote", 3::BIGINT AS v',
        'SELECT NULL::INTEGER AS "key ""with quote", 1::BIGINT AS v',
    )
    result = _result(adapter, _plan(('key "with quote', 'key "with quote')))
    assert result.row == (1, 0, 0, 0, 0, 1, 0, 2, 2)


@pytest.mark.regression_capture("duckdb-private-bounded-grouped-summary")
def test_runtime_renderer_all_null_groups(adapter: DuckDbAdapter) -> None:
    same = "SELECT 1 AS k, NULL::BIGINT AS v"
    _tables(adapter, same, same)
    result = _result(adapter, _plan(("k",)))
    assert result.row == (1, 0, 0, 1, 0, 0, 0, None, None)
