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
            """select
  s."customer_id",
  s."month"
from "qa"."customer_source" as s
left join "qa"."customer_target" as t
  on s."customer_id" = t."customer_id" and s."month" = t."month"
where t."customer_id" is null""",
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
group by "customer_id", "month"
having count(*) > 1""",
        ),
        (
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
            ),
            'select sum("revenue") as aggregate_value\nfrom "qa"."customer_source"',
        ),
        (
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate="sum",
                column="revenue",
                group_by=("month",),
            ),
            (
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
    assert (
        rendered[-1].sql
        == """with
source_aggregate as (
  select sum("revenue") as aggregate_value
  from "qa"."customer_source"
),
target_aggregate as (
  select sum("revenue") as aggregate_value
  from "qa"."customer_target"
)
select
  source_aggregate.aggregate_value as source_aggregate_value,
  target_aggregate.aggregate_value as target_aggregate_value,
  source_aggregate.aggregate_value - target_aggregate.aggregate_value as aggregate_diff
from source_aggregate
cross join target_aggregate"""
    )


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
        ")\n"
        "select\n"
        '  coalesce(source_aggregate."month", target_aggregate."month") as "month",\n'
        "  source_aggregate.aggregate_value as source_aggregate_value,\n"
        "  target_aggregate.aggregate_value as target_aggregate_value,\n"
        "  source_aggregate.aggregate_value - target_aggregate.aggregate_value as aggregate_diff\n"
        "from source_aggregate\n"
        "full outer join target_aggregate\n"
        '  on source_aggregate."month" = target_aggregate."month"'
    )
