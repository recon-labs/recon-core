import importlib
import os
from decimal import Decimal
from typing import Any

import pytest

from recon_core.adapters import Relation
from recon_core.adapters.duckdb import DuckDbSqlRenderer
from recon_core.compiler.models import (
    Identity,
    IdentityKind,
    KeyDiffDirection,
    OperationSide,
    TypedOperation,
)


@pytest.fixture
def renderer() -> DuckDbSqlRenderer:
    return DuckDbSqlRenderer()


@pytest.fixture
def source_relation() -> Relation:
    return Relation(schema="qa", identifier="customer_source")


@pytest.fixture
def target_relation() -> Relation:
    return Relation(schema="qa", identifier="customer_target")


_DUCKDB_NUMERIC_SUM_TYPES = (
    "'TINYINT', 'SMALLINT', 'INTEGER', 'BIGINT', 'HUGEINT', 'UTINYINT', "
    "'USMALLINT', 'UINTEGER', 'UBIGINT', 'FLOAT', 'DOUBLE', 'BIGNUM'"
)
_SOURCE_RELATION_SQL = '"qa"."customer_source"'
_TARGET_RELATION_SQL = '"qa"."customer_target"'


def _duckdb_module() -> Any:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            return importlib.import_module("duckdb")
        except ImportError:
            pytest.fail(
                "DuckDB SQL renderer semantic tests are required in this environment. "
                "Install with `.[dev,duckdb]`.",
                pytrace=False,
            )

    return pytest.importorskip("duckdb")


def _aggregate_input_predicate(relation: str, column: str = "revenue") -> str:
    input_type = f'typeof((select "{column}" from {relation} limit 1))'
    return f"({input_type} in ({_DUCKDB_NUMERIC_SUM_TYPES}) or {input_type} like 'DECIMAL(%)')"


def _single_aggregate_type_check(
    relation: str,
    *,
    error_message: str,
    column: str = "revenue",
) -> str:
    return (
        "select\n"
        "  case\n"
        "    when\n"
        f"      {_aggregate_input_predicate(relation, column)}\n"
        "    then true\n"
        f"    else error('{error_message}')\n"
        "  end as type_check"
    )


def _aggregate_pair_input_type_check(
    *,
    error_message: str,
    column: str = "revenue",
) -> str:
    source_type = f'typeof((select "{column}" from "qa"."customer_source" limit 1))'
    target_type = f'typeof((select "{column}" from "qa"."customer_target" limit 1))'
    return (
        "select\n"
        "  case\n"
        "    when\n"
        f"      {source_type} = {target_type}\n"
        f"        and {_aggregate_input_predicate(_SOURCE_RELATION_SQL, column)}\n"
        f"        and {_aggregate_input_predicate(_TARGET_RELATION_SQL, column)}\n"
        "    then true\n"
        f"    else error('{error_message}')\n"
        "  end as type_check"
    )


def _aggregate_result_type_check(*, error_message: str, column: str = "revenue") -> str:
    return (
        "select\n"
        "  case\n"
        "    when\n"
        f'      typeof((select sum("{column}") from "qa"."customer_source" limit 1)) = '
        f'typeof((select sum("{column}") from "qa"."customer_target" limit 1))\n'
        "    then true\n"
        f"    else error('{error_message}')\n"
        "  end as type_check"
    )


def _group_key_type_check(*, error_message: str, column: str = "month") -> str:
    return (
        "select\n"
        "  case\n"
        "    when\n"
        f'      typeof((select "{column}" from "qa"."customer_source" limit 1)) = '
        f'typeof((select "{column}" from "qa"."customer_target" limit 1))\n'
        "    then true\n"
        f"    else error('{error_message}')\n"
        "  end as type_check"
    )


_SOURCE_AGGREGATE_TYPE_CHECK = _single_aggregate_type_check(
    _SOURCE_RELATION_SQL,
    error_message="Recon DuckDB aggregate value type mismatch.",
)
_SOURCE_GROUPED_AGGREGATE_TYPE_CHECK = _single_aggregate_type_check(
    _SOURCE_RELATION_SQL,
    error_message="Recon DuckDB grouped aggregate value type mismatch.",
)
_AGGREGATE_PAIR_INPUT_TYPE_CHECK = _aggregate_pair_input_type_check(
    error_message="Recon DuckDB aggregate value type mismatch.",
)
_AGGREGATE_RESULT_TYPE_CHECK = _aggregate_result_type_check(
    error_message="Recon DuckDB aggregate value type mismatch.",
)
_GROUPED_KEY_TYPE_CHECK = _group_key_type_check(
    error_message="Recon DuckDB grouped aggregate key type mismatch.",
)
_GROUPED_AGGREGATE_PAIR_INPUT_TYPE_CHECK = _aggregate_pair_input_type_check(
    error_message="Recon DuckDB grouped aggregate value type mismatch.",
)
_GROUPED_AGGREGATE_RESULT_TYPE_CHECK = _aggregate_result_type_check(
    error_message="Recon DuckDB grouped aggregate value type mismatch.",
)


def test_render_row_count_operation(
    renderer: DuckDbSqlRenderer,
    source_relation: Relation,
    target_relation: Relation,
) -> None:
    rendered = renderer.render_operation(
        TypedOperation.row_count(side=OperationSide.SOURCE).to_dict(),
        source_relation=source_relation,
        target_relation=target_relation,
    )

    assert rendered.operation_type == "row_count"
    assert rendered.required_capabilities == ("row_count",)
    assert rendered.sql == 'select count(*) as row_count\nfrom "qa"."customer_source"'


@pytest.mark.parametrize(
    ("operation", "expected_sql"),
    [
        (
            TypedOperation.key_diff(
                direction=KeyDiffDirection.SOURCE_MINUS_TARGET,
                identity=Identity(IdentityKind.GRAIN, ("customer_id", "month")),
            ),
            (
                "with\n"
                "key_type_check as (\n"
                "  select\n"
                "    case\n"
                "      when\n"
                '        typeof((select "customer_id" from "qa"."customer_source" limit 1)) = '
                'typeof((select "customer_id" from "qa"."customer_target" limit 1))\n'
                '        and typeof((select "month" from "qa"."customer_source" limit 1)) = '
                'typeof((select "month" from "qa"."customer_target" limit 1))\n'
                "      then true\n"
                "      else error('Recon DuckDB key_diff key type mismatch.')\n"
                "    end as type_check\n"
                "),\n"
                "left_keys as (\n"
                "  select distinct\n"
                '    "customer_id",\n'
                '    "month"\n'
                '  from "qa"."customer_source"\n'
                '  where "customer_id" is not null and "month" is not null\n'
                "),\n"
                "right_keys as (\n"
                "  select distinct\n"
                '    "customer_id",\n'
                '    "month"\n'
                '  from "qa"."customer_target"\n'
                '  where "customer_id" is not null and "month" is not null\n'
                ")\n"
                "select\n"
                '  left_keys."customer_id",\n'
                '  left_keys."month"\n'
                "from key_type_check\n"
                "left join left_keys\n"
                "  on key_type_check.type_check\n"
                "left join right_keys\n"
                '  on (typeof(left_keys."customer_id") = '
                'typeof(right_keys."customer_id") and '
                'left_keys."customer_id" is not distinct from '
                'right_keys."customer_id") and (typeof(left_keys."month") = '
                'typeof(right_keys."month") and left_keys."month" is not distinct from '
                'right_keys."month")\n'
                'where key_type_check.type_check and left_keys."customer_id" is not null '
                'and right_keys."customer_id" is null'
            ),
        ),
        (
            TypedOperation.null_key(
                side=OperationSide.SOURCE,
                identity=Identity(IdentityKind.GRAIN, ("customer_id", "month")),
            ),
            """select
  "customer_id",
  "month"
from "qa"."customer_source"
where "customer_id" is null or "month" is null""",
        ),
        (
            TypedOperation.duplicate_key(
                side=OperationSide.SOURCE,
                identity=Identity(IdentityKind.GRAIN, ("customer_id", "month")),
            ),
            """select
  "customer_id",
  "month",
  count(*) as row_count
from "qa"."customer_source"
where "customer_id" is not null and "month" is not null
group by "customer_id", "month"
having count(*) > 1""",
        ),
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ),
            (
                f"{_SOURCE_AGGREGATE_TYPE_CHECK};\n\n"
                'select sum("revenue") as aggregate_value\n'
                'from "qa"."customer_source"'
            ),
        ),
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ),
            (
                f"{_SOURCE_GROUPED_AGGREGATE_TYPE_CHECK};\n\n"
                'select\n  "month",\n  sum("revenue") as aggregate_value\n'
                'from "qa"."customer_source"\ngroup by "month"'
            ),
        ),
    ],
)
def test_render_side_operations(
    renderer: DuckDbSqlRenderer,
    source_relation: Relation,
    target_relation: Relation,
    operation: TypedOperation,
    expected_sql: str,
) -> None:
    rendered = renderer.render_operation(
        operation.to_dict(),
        source_relation=source_relation,
        target_relation=target_relation,
    )

    assert rendered.sql == expected_sql


def test_render_target_minus_source_key_diff_uses_target_left_key_set(
    renderer: DuckDbSqlRenderer,
    source_relation: Relation,
    target_relation: Relation,
) -> None:
    rendered = renderer.render_operation(
        TypedOperation.key_diff(
            direction=KeyDiffDirection.TARGET_MINUS_SOURCE,
            identity=Identity(IdentityKind.GRAIN, ("customer_id", "month")),
        ).to_dict(),
        source_relation=source_relation,
        target_relation=target_relation,
    )

    assert '  from "qa"."customer_target"\n' in rendered.sql
    assert '  from "qa"."customer_source"\n' in rendered.sql
    assert rendered.sql.index('  from "qa"."customer_target"\n') < rendered.sql.index(
        '  from "qa"."customer_source"\n'
    )


def test_duplicate_key_excludes_null_containing_duplicate_candidates(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (customer_id integer, month varchar)")
    con.execute(
        """
        insert into source_table values
          (null, '2026-01'),
          (null, '2026-01'),
          (2, null),
          (2, null),
          (3, '2026-03'),
          (4, '2026-04'),
          (4, '2026-04')
        """
    )

    rendered = renderer.render_operation(
        TypedOperation.duplicate_key(
            side=OperationSide.SOURCE,
            identity=Identity(IdentityKind.GRAIN, ("customer_id", "month")),
        ).to_dict(),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    assert sorted(con.execute(rendered.sql).fetchall()) == [(4, "2026-04", 2)]


def test_render_count_comparison_plan(
    renderer: DuckDbSqlRenderer,
    source_relation: Relation,
    target_relation: Relation,
) -> None:
    rendered = renderer.render_plan(
        (
            TypedOperation.row_count(side=OperationSide.SOURCE).to_dict(),
            TypedOperation.row_count(side=OperationSide.TARGET).to_dict(),
            TypedOperation.compare_counts().to_dict(),
        ),
        source_relation=source_relation,
        target_relation=target_relation,
    )

    assert [sql.step_name for sql in rendered] == [
        "00-row_count-source",
        "01-row_count-target",
        "02-compare_counts",
    ]
    assert rendered[-1].operation_type == "compare_counts"
    assert (
        rendered[-1].sql
        == """with
source_count as (
  select count(*) as row_count
  from "qa"."customer_source"
),
target_count as (
  select count(*) as row_count
  from "qa"."customer_target"
)
select
  source_count.row_count as source_row_count,
  target_count.row_count as target_row_count,
  source_count.row_count - target_count.row_count as row_count_diff
from source_count
cross join target_count"""
    )


def test_render_aggregate_comparison_plan(
    renderer: DuckDbSqlRenderer,
    source_relation: Relation,
    target_relation: Relation,
) -> None:
    rendered = renderer.render_plan(
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.compare_aggregates().to_dict(),
        ),
        source_relation=source_relation,
        target_relation=target_relation,
    )

    assert rendered[-1].operation_type == "compare_aggregates"
    assert rendered[-1].sql == (
        f"{_AGGREGATE_PAIR_INPUT_TYPE_CHECK};\n\n"
        f"{_AGGREGATE_RESULT_TYPE_CHECK};\n\n"
        "with\n"
        "source_aggregate as (\n"
        '  select sum("revenue") as aggregate_value\n'
        '  from "qa"."customer_source"\n'
        "),\n"
        "target_aggregate as (\n"
        '  select sum("revenue") as aggregate_value\n'
        '  from "qa"."customer_target"\n'
        ")\n"
        "select\n"
        "  source_aggregate.aggregate_value as source_aggregate_value,\n"
        "  target_aggregate.aggregate_value as target_aggregate_value,\n"
        "  source_aggregate.aggregate_value - target_aggregate.aggregate_value as aggregate_diff\n"
        "from source_aggregate\n"
        "cross join target_aggregate"
    )


def test_render_aggregate_type_check_uses_closed_decimal_pattern(
    renderer: DuckDbSqlRenderer,
    source_relation: Relation,
    target_relation: Relation,
) -> None:
    rendered = renderer.render_plan(
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.compare_aggregates().to_dict(),
        ),
        source_relation=source_relation,
        target_relation=target_relation,
    )

    assert "like 'DECIMAL(%)')" in rendered[-1].sql


def test_render_grouped_aggregate_comparison_plan(
    renderer: DuckDbSqlRenderer,
    source_relation: Relation,
    target_relation: Relation,
) -> None:
    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=source_relation,
        target_relation=target_relation,
    )

    assert rendered[-1].operation_type == "compare_grouped_aggregates"
    assert rendered[-1].sql == (
        f"{_GROUPED_KEY_TYPE_CHECK};\n\n"
        f"{_GROUPED_AGGREGATE_PAIR_INPUT_TYPE_CHECK};\n\n"
        f"{_GROUPED_AGGREGATE_RESULT_TYPE_CHECK};\n\n"
        "with\n"
        "source_aggregate as (\n"
        "  select\n"
        '    "month",\n'
        '    sum("revenue") as aggregate_value\n'
        '  from "qa"."customer_source"\n'
        '  group by "month"\n'
        "),\n"
        "target_aggregate as (\n"
        "  select\n"
        '    "month",\n'
        '    sum("revenue") as aggregate_value\n'
        '  from "qa"."customer_target"\n'
        '  group by "month"\n'
        "),\n"
        "joined_aggregate as (\n"
        "  select\n"
        '    source_aggregate."month" as "source_month",\n'
        '    target_aggregate."month" as "target_month",\n'
        "    source_aggregate.aggregate_value as source_aggregate_value,\n"
        "    target_aggregate.aggregate_value as target_aggregate_value,\n"
        "    true as has_aggregate_row\n"
        "  from source_aggregate\n"
        "  full outer join target_aggregate\n"
        '  on (typeof(source_aggregate."month") = typeof(target_aggregate."month") and '
        'source_aggregate."month" is not distinct from target_aggregate."month")\n'
        ")\n"
        "select\n"
        '  joined_aggregate."source_month",\n'
        '  joined_aggregate."target_month",\n'
        "  joined_aggregate.source_aggregate_value,\n"
        "  joined_aggregate.target_aggregate_value,\n"
        "  joined_aggregate.source_aggregate_value - joined_aggregate.target_aggregate_value "
        "as aggregate_diff\n"
        "from joined_aggregate\n"
        "where joined_aggregate.has_aggregate_row"
    )


def test_key_diff_type_mismatch_raises_duckdb_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (customer_id integer)")
    con.execute("create table target_table (customer_id varchar)")
    con.execute("insert into source_table values (1)")
    con.execute("insert into target_table values ('1')")

    rendered = renderer.render_operation(
        TypedOperation.key_diff(
            direction=KeyDiffDirection.SOURCE_MINUS_TARGET,
            identity=Identity(IdentityKind.GRAIN, ("customer_id",)),
        ).to_dict(),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB key_diff key type mismatch"):
        con.execute(rendered.sql).fetchall()


def test_key_diff_type_mismatch_raises_duckdb_error_without_rows(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (customer_id integer)")
    con.execute("create table target_table (customer_id varchar)")

    rendered = renderer.render_operation(
        TypedOperation.key_diff(
            direction=KeyDiffDirection.SOURCE_MINUS_TARGET,
            identity=Identity(IdentityKind.GRAIN, ("customer_id",)),
        ).to_dict(),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB key_diff key type mismatch"):
        con.execute(rendered.sql).fetchall()


def test_aggregate_value_type_mismatch_raises_duckdb_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (revenue integer)")
    con.execute("create table target_table (revenue double)")
    con.execute("insert into source_table values (10)")
    con.execute("insert into target_table values (10.0)")

    rendered = renderer.render_plan(
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.compare_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_aggregate_input_type_mismatch_raises_duckdb_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (revenue boolean)")
    con.execute("create table target_table (revenue integer)")
    con.execute("insert into source_table values (true), (false)")
    con.execute("insert into target_table values (1), (0)")

    rendered = renderer.render_plan(
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.compare_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_aggregate_boolean_input_raises_duckdb_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (flag boolean)")
    con.execute("create table target_table (flag boolean)")
    con.execute("insert into source_table values (true), (true), (false)")
    con.execute("insert into target_table values (true), (false), (false)")

    rendered = renderer.render_plan(
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="flag",
            ).to_dict(),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="flag",
            ).to_dict(),
            TypedOperation.compare_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_aggregate_unsupported_same_input_type_raises_recon_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (revenue varchar)")
    con.execute("create table target_table (revenue varchar)")
    con.execute("insert into source_table values ('10')")
    con.execute("insert into target_table values ('10')")

    rendered = renderer.render_plan(
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.compare_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_aggregate_large_bigint_preserves_exact_difference(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (revenue bigint)")
    con.execute("create table target_table (revenue bigint)")
    con.execute("insert into source_table values (9007199254740992)")
    con.execute("insert into target_table values (9007199254740993)")

    rendered = renderer.render_plan(
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.compare_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    assert con.execute(rendered[-1].sql).fetchall() == [(9007199254740992, 9007199254740993, -1)]


def test_aggregate_decimal_input_preserves_exact_difference(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (revenue decimal(10, 2))")
    con.execute("create table target_table (revenue decimal(10, 2))")
    con.execute("insert into source_table values (10.25)")
    con.execute("insert into target_table values (9.00)")

    rendered = renderer.render_plan(
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.compare_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    assert con.execute(rendered[-1].sql).fetchall() == [
        (Decimal("10.25"), Decimal("9.00"), Decimal("1.25"))
    ]


def test_aggregate_uhugeint_input_raises_recon_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (revenue uhugeint)")
    con.execute("create table target_table (revenue uhugeint)")
    con.execute("insert into source_table values (9007199254740992)")
    con.execute("insert into target_table values (9007199254740993)")

    rendered = renderer.render_plan(
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
            ).to_dict(),
            TypedOperation.compare_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_grouped_aggregate_key_type_mismatch_raises_duckdb_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (month integer, revenue integer)")
    con.execute("create table target_table (month varchar, revenue integer)")
    con.execute("insert into source_table values (1, 10)")
    con.execute("insert into target_table values ('1', 10)")

    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB grouped aggregate key type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_grouped_aggregate_value_type_mismatch_raises_duckdb_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (month integer, revenue integer)")
    con.execute("create table target_table (month integer, revenue double)")
    con.execute("insert into source_table values (1, 10)")
    con.execute("insert into target_table values (1, 10.0)")

    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB grouped aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_grouped_aggregate_input_type_mismatch_raises_duckdb_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (month integer, revenue integer)")
    con.execute("create table target_table (month integer, revenue bigint)")
    con.execute("insert into source_table values (1, 10)")
    con.execute("insert into target_table values (1, 10)")

    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB grouped aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_grouped_aggregate_boolean_input_raises_duckdb_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (month integer, flag boolean)")
    con.execute("create table target_table (month integer, flag boolean)")
    con.execute("insert into source_table values (1, true), (1, true), (2, false)")
    con.execute("insert into target_table values (1, true), (1, false), (2, false)")

    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="flag",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="flag",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB grouped aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_grouped_aggregate_unsupported_same_input_type_raises_recon_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (month varchar, revenue varchar)")
    con.execute("create table target_table (month varchar, revenue varchar)")
    con.execute("insert into source_table values ('2026-01', '10')")
    con.execute("insert into target_table values ('2026-01', '10')")

    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB grouped aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_grouped_aggregate_large_bigint_preserves_exact_difference(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (month varchar, revenue bigint)")
    con.execute("create table target_table (month varchar, revenue bigint)")
    con.execute("insert into source_table values ('2026-01', 9007199254740992)")
    con.execute("insert into target_table values ('2026-01', 9007199254740993)")

    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    assert con.execute(rendered[-1].sql).fetchall() == [
        ("2026-01", "2026-01", 9007199254740992, 9007199254740993, -1)
    ]


def test_grouped_aggregate_decimal_input_preserves_exact_difference(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (month varchar, revenue decimal(10, 2))")
    con.execute("create table target_table (month varchar, revenue decimal(10, 2))")
    con.execute("insert into source_table values ('2026-01', 10.25)")
    con.execute("insert into target_table values ('2026-01', 9.00)")

    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    assert con.execute(rendered[-1].sql).fetchall() == [
        ("2026-01", "2026-01", Decimal("10.25"), Decimal("9.00"), Decimal("1.25"))
    ]


def test_grouped_aggregate_uhugeint_input_raises_recon_error(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (month varchar, revenue uhugeint)")
    con.execute("create table target_table (month varchar, revenue uhugeint)")
    con.execute("insert into source_table values ('2026-01', 9007199254740992)")
    con.execute("insert into target_table values ('2026-01', 9007199254740993)")

    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB grouped aggregate value type mismatch"):
        con.execute(rendered[-1].sql).fetchall()


def test_grouped_aggregate_key_type_mismatch_raises_duckdb_error_without_rows(
    renderer: DuckDbSqlRenderer,
) -> None:
    duckdb = _duckdb_module()
    con = duckdb.connect(database=":memory:")
    con.execute("create table source_table (month integer, revenue integer)")
    con.execute("create table target_table (month varchar, revenue integer)")

    rendered = renderer.render_plan(
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ).to_dict(),
            TypedOperation.compare_grouped_aggregates().to_dict(),
        ),
        source_relation=Relation(identifier="source_table"),
        target_relation=Relation(identifier="target_table"),
    )

    with pytest.raises(Exception, match="Recon DuckDB grouped aggregate key type mismatch"):
        con.execute(rendered[-1].sql).fetchall()
