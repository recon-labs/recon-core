"""Private DuckDB aggregate SQL: typed preflight and bounded final results."""

from collections.abc import Mapping
from typing import Any

from recon_core.adapters._aggregate_runtime import (
    _SCALAR_COLUMNS,
    _SUMMARY_COLUMNS,
    _AggregateRuntimePlan,
)
from recon_core.adapters.models import Relation, RenderedSql

from .renderer_operations import (
    assert_matching_aggregate,
    required_string,
    required_string_tuple,
)
from .renderer_sql import (
    aggregate_expression_sql,
    aggregate_input_type_supported_predicate,
    column_type_expression,
    quote_identifier,
    render_aggregate_input_type_check_statement,
    render_relation,
    render_type_check_statement,
    select_lines,
    sql_string_literal,
    strict_null_safe_equality,
)

_VALUE_ERROR = "Recon DuckDB aggregate value type mismatch."


class _DuckDbAggregateRuntimeRenderer:
    """Render only the current explicit SUM comparison family."""

    adapter_type = "duckdb"

    def render_plan(
        self,
        operations: tuple[Mapping[str, Any], ...],
        *,
        source_relation: Relation,
        target_relation: Relation,
    ) -> _AggregateRuntimePlan:
        if len(operations) != 3:
            raise ValueError("Aggregate runtime requires three operations.")
        source, target, comparison = operations
        kind = source.get("type")
        if kind not in ("aggregate", "grouped_aggregate"):
            raise ValueError("Unsupported aggregate runtime operation.")
        grouped = kind == "grouped_aggregate"
        compare_kind = "compare_grouped_aggregates" if grouped else "compare_aggregates"
        if (
            target.get("type") != kind
            or source.get("side") != "source"
            or target.get("side") != "target"
            or comparison.get("type") != compare_kind
            or source.get("aggregate") != "sum"
        ):
            raise ValueError("Unsupported aggregate runtime plan.")
        assert_matching_aggregate(source, target)
        column = required_string(source, "column")
        keys = required_string_tuple(source, "group_by") if grouped else ()
        if grouped and not keys:
            raise ValueError("Grouped aggregate runtime requires group keys.")
        if column == "*" or any(not key or key == "*" for key in keys):
            raise ValueError("Unsupported aggregate runtime column.")
        if not grouped and source.get("group_by", []) not in ([], ()):
            raise ValueError("Scalar aggregate runtime cannot include group keys.")
        capabilities = ("grouped_aggregate" if grouped else "aggregate", "cte_support")
        guards: list[RenderedSql] = []
        if grouped:
            guards.append(
                RenderedSql(
                    sql=render_type_check_statement(
                        left_relation=source_relation,
                        right_relation=target_relation,
                        keys=keys,
                        error_message="Recon DuckDB grouped aggregate key type mismatch.",
                        runtime_guard=True,
                    ),
                    operation_type=compare_kind,
                    step_name="group-key-types",
                    required_capabilities=capabilities,
                )
            )
        guards.append(
            RenderedSql(
                sql=render_aggregate_input_type_check_statement(
                    left_relation=source_relation,
                    right_relation=target_relation,
                    column=column,
                    error_message=_VALUE_ERROR,
                    runtime_guard=True,
                ),
                operation_type=compare_kind,
                step_name="aggregate-input-types",
                required_capabilities=capabilities,
            )
        )
        domain_guard = RenderedSql(
            sql=_render_domain_guard(source_relation, target_relation, column),
            operation_type=compare_kind,
            step_name="aggregate-native-domain",
            required_capabilities=capabilities,
        )
        ctes = _aggregate_ctes(source_relation, target_relation, column, keys)
        if grouped:
            exact_sql = _grouped_summary(ctes, keys, floating=False)
            floating_sql = _grouped_summary(ctes, keys, floating=True)
        else:
            exact_sql = floating_sql = _scalar_result(ctes)

        return _AggregateRuntimePlan(
            type_guards=tuple(guards),
            domain_guard=domain_guard,
            exact_query=RenderedSql(
                sql=exact_sql,
                operation_type=compare_kind,
                step_name="aggregate-exact-result",
                required_capabilities=capabilities,
            ),
            floating_query=RenderedSql(
                sql=floating_sql,
                operation_type=compare_kind,
                step_name="aggregate-floating-result",
                required_capabilities=capabilities,
            ),
            columns=_SUMMARY_COLUMNS if grouped else _SCALAR_COLUMNS,
            required_capabilities=capabilities,
        )


def _render_domain_guard(source: Relation, target: Relation, column: str) -> str:
    # Bind native arithmetic against empty relations, never aggregate actual data
    # during preflight. Input guards run independently before SUM is even bound.
    expression = aggregate_expression_sql("sum", quote_identifier(column))
    source_type = column_type_expression(source, column, metadata_only=True)
    target_type = column_type_expression(target, column, metadata_only=True)
    supported = aggregate_input_type_supported_predicate("input_kind")
    return (
        "with source_native as (\n"
        f"  select {expression} as a from {render_relation(source)} where false\n"
        "), target_native as (\n"
        f"  select {expression} as b from {render_relation(target)} where false\n"
        "), native_types as (\n"
        f"  select {source_type} as input_kind, {target_type} as target_kind,\n"
        "    typeof(a) as sum_kind, typeof(b) as target_sum_kind,\n"
        "    typeof(a-b) as diff_kind\n"
        "  from source_native cross join target_native\n"
        ")\n"
        "select case\n"
        f"  when input_kind = target_kind and {supported}\n"
        "    and sum_kind = target_sum_kind then case\n"
        "      when input_kind in ('FLOAT', 'DOUBLE')\n"
        "        and sum_kind = 'DOUBLE' and diff_kind = 'DOUBLE' then 3\n"
        "      when input_kind = 'BIGNUM'\n"
        "        and sum_kind = 'BIGNUM' and diff_kind = 'BIGNUM' then 1\n"
        "      when input_kind like 'DECIMAL(%)' and sum_kind like 'DECIMAL(%)'\n"
        "        and diff_kind like 'DECIMAL(%)'\n"
        "        and split_part(input_kind, ',', 2) = split_part(sum_kind, ',', 2)\n"
        "        and split_part(sum_kind, ',', 2) = split_part(diff_kind, ',', 2)\n"
        "        and sum_kind = diff_kind then 2\n"
        "      when input_kind not in ('FLOAT', 'DOUBLE', 'BIGNUM')\n"
        "        and input_kind not like 'DECIMAL(%)'\n"
        "        and sum_kind = 'HUGEINT' and diff_kind = 'HUGEINT' then 1\n"
        "      else error('Recon DuckDB aggregate native domain unavailable.') end\n"
        f"  else error({sql_string_literal(_VALUE_ERROR)}) end as numeric_domain\n"
        "from native_types"
    )


def _aggregate_ctes(source: Relation, target: Relation, column: str, keys: tuple[str, ...]) -> str:
    expression = aggregate_expression_sql("sum", quote_identifier(column))
    # Internal positional aliases are independent of authored group-key names.
    key_select = tuple(
        f"{quote_identifier(key)} as group_key_{index}" for index, key in enumerate(keys)
    )
    group_clause = ""
    if keys:
        group_clause = "\n  group by " + ", ".join(str(i + 1) for i in range(len(keys)))
    select = select_lines((*key_select, f"{expression} as aggregate_value", "true as present"))
    return (
        "with source_aggregate as (\n"
        f"  select\n{select}\n  from {render_relation(source)}{group_clause}\n"
        "), target_aggregate as (\n"
        f"  select\n{select}\n  from {render_relation(target)}{group_clause}\n"
        ")"
    )


def _scalar_result(ctes: str) -> str:
    return (
        f"{ctes}\n"
        "select\n"
        "  s.aggregate_value as source_aggregate_value,\n"
        "  t.aggregate_value as target_aggregate_value,\n"
        "  s.aggregate_value - t.aggregate_value as aggregate_diff\n"
        "from source_aggregate s cross join target_aggregate t"
    )


def _grouped_summary(ctes: str, keys: tuple[str, ...], *, floating: bool) -> str:
    join = " and ".join(
        strict_null_safe_equality(f"s.group_key_{i}", f"t.group_key_{i}") for i in range(len(keys))
    )
    invalid = (
        "(sp is true and a is not null and not isfinite(a)) or "
        "(tp is true and b is not null and not isfinite(b)) or "
        "(d is not null and not isfinite(d))"
        if floating
        else "false"
    )
    categories = (
        "source_only",
        "target_only",
        "both_null",
        "null_mismatch",
        "valid",
        "invalid",
    )
    counts = tuple(
        f"count(*) filter (where category = '{category}') as {name}"
        for category, name in zip(categories, _SUMMARY_COLUMNS[1:7], strict=True)
    )
    summary = select_lines(
        (
            "count(*) as total_group_count",
            *counts,
            "min(d) filter (where category = 'valid') as min_signed_diff",
            "max(d) filter (where category = 'valid') as max_signed_diff",
        )
    )
    return (
        f"{ctes}, joined_aggregate as (\n"
        "  select s.present as sp, t.present as tp,\n"
        "    s.aggregate_value as a, t.aggregate_value as b,\n"
        "    case when s.present is true and t.present is true\n"
        "      and s.aggregate_value is not null and t.aggregate_value is not null\n"
        "      then s.aggregate_value - t.aggregate_value end as d\n"
        "  from source_aggregate s full outer join target_aggregate t\n"
        f"  on {join}\n"
        "), classified as (\n"
        "  select d, case\n"
        f"    when {invalid} then 'invalid'\n"
        "    when tp is null then 'source_only'\n"
        "    when sp is null then 'target_only'\n"
        "    when a is null and b is null then 'both_null'\n"
        "    when a is null or b is null then 'null_mismatch'\n"
        "    else 'valid' end as category\n"
        "  from joined_aggregate\n"
        ")\n"
        f"select\n{summary}\nfrom classified"
    )
