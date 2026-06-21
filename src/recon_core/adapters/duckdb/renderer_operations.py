"""DuckDB typed-operation SQL builders."""

from collections.abc import Mapping
from typing import Any

from recon_core.adapters.models import Relation, RenderedSql

from .renderer_sql import (
    aggregate_expression_sql,
    quote_identifier,
    render_aggregate_input_type_check_statement,
    render_aggregate_result_type_check_statement,
    render_relation,
    render_single_aggregate_input_type_check_statement,
    render_type_check_cte,
    render_type_check_statement,
    select_lines,
    strict_null_safe_equality,
)


def render_row_count(
    operation: Mapping[str, Any],
    source_relation: Relation,
    target_relation: Relation,
) -> RenderedSql:
    relation = side_relation(operation, source_relation, target_relation)
    return RenderedSql(
        sql=f"select count(*) as row_count\nfrom {render_relation(relation)}",
        operation_type="row_count",
        required_capabilities=("row_count",),
    )


def render_compare_counts(
    source_relation: Relation,
    target_relation: Relation,
) -> RenderedSql:
    sql = (
        "with\n"
        "source_count as (\n"
        "  select count(*) as row_count\n"
        f"  from {render_relation(source_relation)}\n"
        "),\n"
        "target_count as (\n"
        "  select count(*) as row_count\n"
        f"  from {render_relation(target_relation)}\n"
        ")\n"
        "select\n"
        "  source_count.row_count as source_row_count,\n"
        "  target_count.row_count as target_row_count,\n"
        "  source_count.row_count - target_count.row_count as row_count_diff\n"
        "from source_count\n"
        "cross join target_count"
    )
    return RenderedSql(
        sql=sql,
        operation_type="compare_counts",
        required_capabilities=("row_count", "cte_support"),
    )


def render_key_diff(
    operation: Mapping[str, Any],
    source_relation: Relation,
    target_relation: Relation,
) -> RenderedSql:
    identity_keys = identity_keys_from_operation(operation)
    direction = required_string(operation, "direction")
    if direction == "source_minus_target":
        left_relation = source_relation
        right_relation = target_relation
    elif direction == "target_minus_source":
        left_relation = target_relation
        right_relation = source_relation
    else:
        raise ValueError(f"Unsupported key_diff direction: {direction}")

    quoted_keys = tuple(quote_identifier(key) for key in identity_keys)
    cte_keys = select_lines(quoted_keys, indent=4)
    selected_keys = select_lines(f"left_keys.{quoted_key}" for quoted_key in quoted_keys)
    non_null_predicate = " and ".join(f"{quoted_key} is not null" for quoted_key in quoted_keys)
    join_predicate = " and ".join(
        strict_null_safe_equality(
            f"left_keys.{quoted_key}",
            f"right_keys.{quoted_key}",
        )
        for quoted_key in quoted_keys
    )
    type_check_cte = render_type_check_cte(
        cte_name="key_type_check",
        left_relation=left_relation,
        right_relation=right_relation,
        keys=identity_keys,
        error_message="Recon DuckDB key_diff key type mismatch.",
    )
    sql = (
        "with\n"
        f"{type_check_cte},\n"
        "left_keys as (\n"
        "  select distinct\n"
        f"{cte_keys}\n"
        f"  from {render_relation(left_relation)}\n"
        f"  where {non_null_predicate}\n"
        "),\n"
        "right_keys as (\n"
        "  select distinct\n"
        f"{cte_keys}\n"
        f"  from {render_relation(right_relation)}\n"
        f"  where {non_null_predicate}\n"
        ")\n"
        "select\n"
        f"{selected_keys}\n"
        "from key_type_check\n"
        "left join left_keys\n"
        "  on key_type_check.type_check\n"
        "left join right_keys\n"
        f"  on {join_predicate}\n"
        f"where key_type_check.type_check and "
        f"left_keys.{quote_identifier(identity_keys[0])} is not null and "
        f"right_keys.{quote_identifier(identity_keys[0])} is null"
    )
    return RenderedSql(
        sql=sql,
        operation_type="key_diff",
        required_capabilities=("key_diff", "cte_support"),
    )


def render_null_key(
    operation: Mapping[str, Any],
    source_relation: Relation,
    target_relation: Relation,
) -> RenderedSql:
    relation = side_relation(operation, source_relation, target_relation)
    identity_keys = identity_keys_from_operation(operation)
    sql = (
        "select\n"
        f"{select_lines(quote_identifier(key) for key in identity_keys)}\n"
        f"from {render_relation(relation)}\n"
        "where " + " or ".join(f"{quote_identifier(key)} is null" for key in identity_keys)
    )
    return RenderedSql(
        sql=sql,
        operation_type="null_key",
        required_capabilities=("null_key",),
    )


def render_duplicate_key(
    operation: Mapping[str, Any],
    source_relation: Relation,
    target_relation: Relation,
) -> RenderedSql:
    relation = side_relation(operation, source_relation, target_relation)
    identity_keys = identity_keys_from_operation(operation)
    quoted_keys = tuple(quote_identifier(key) for key in identity_keys)
    non_null_predicate = " and ".join(f"{quoted_key} is not null" for quoted_key in quoted_keys)
    sql = (
        "select\n"
        f"{select_lines((*quoted_keys, 'count(*) as row_count'))}\n"
        f"from {render_relation(relation)}\n"
        f"where {non_null_predicate}\n"
        f"group by {', '.join(quoted_keys)}\n"
        "having count(*) > 1"
    )
    return RenderedSql(
        sql=sql,
        operation_type="duplicate_key",
        required_capabilities=("duplicate_key",),
    )


def render_aggregate(
    operation: Mapping[str, Any],
    source_relation: Relation,
    target_relation: Relation,
) -> RenderedSql:
    relation = side_relation(operation, source_relation, target_relation)
    aggregate = required_string(operation, "aggregate")
    column = required_string(operation, "column")
    aggregate_expression = aggregate_expression_sql(aggregate, quote_identifier(column))
    aggregate_type_check = render_single_aggregate_input_type_check_statement(
        relation=relation,
        column=column,
        error_message="Recon DuckDB aggregate value type mismatch.",
    )
    sql = (
        f"{aggregate_type_check};\n\n"
        f"select {aggregate_expression} as aggregate_value\n"
        f"from {render_relation(relation)}"
    )
    return RenderedSql(
        sql=sql,
        operation_type="aggregate",
        required_capabilities=("aggregate",),
    )


def render_grouped_aggregate(
    operation: Mapping[str, Any],
    source_relation: Relation,
    target_relation: Relation,
) -> RenderedSql:
    relation = side_relation(operation, source_relation, target_relation)
    aggregate = required_string(operation, "aggregate")
    column = required_string(operation, "column")
    group_by = required_string_tuple(operation, "group_by")
    aggregate_expression = aggregate_expression_sql(aggregate, quote_identifier(column))
    group_select = select_lines(quote_identifier(column_name) for column_name in group_by)
    aggregate_type_check = render_single_aggregate_input_type_check_statement(
        relation=relation,
        column=column,
        error_message="Recon DuckDB grouped aggregate value type mismatch.",
    )
    sql = (
        f"{aggregate_type_check};\n\n"
        "select\n"
        f"{group_select},\n"
        f"  {aggregate_expression} as aggregate_value\n"
        f"from {render_relation(relation)}\n"
        f"group by {', '.join(quote_identifier(column_name) for column_name in group_by)}"
    )
    return RenderedSql(
        sql=sql,
        operation_type="grouped_aggregate",
        required_capabilities=("grouped_aggregate",),
    )


def render_compare_aggregates(
    previous_operations: tuple[Mapping[str, Any], ...],
    source_relation: Relation,
    target_relation: Relation,
) -> RenderedSql:
    source_operation, target_operation = side_operations(previous_operations, "aggregate")
    aggregate = required_string(source_operation, "aggregate")
    column = required_string(source_operation, "column")
    assert_matching_aggregate(source_operation, target_operation)
    aggregate_type_check = render_aggregate_input_type_check_statement(
        left_relation=source_relation,
        right_relation=target_relation,
        column=column,
        error_message="Recon DuckDB aggregate value type mismatch.",
    )
    aggregate_result_type_check = render_aggregate_result_type_check_statement(
        left_relation=source_relation,
        right_relation=target_relation,
        aggregate=aggregate,
        column=column,
        error_message="Recon DuckDB aggregate value type mismatch.",
    )
    sql = (
        f"{aggregate_type_check};\n\n"
        f"{aggregate_result_type_check};\n\n"
        "with\n"
        "source_aggregate as (\n"
        f"  select {aggregate_expression_sql(aggregate, quote_identifier(column))} "
        "as aggregate_value\n"
        f"  from {render_relation(source_relation)}\n"
        "),\n"
        "target_aggregate as (\n"
        f"  select {aggregate_expression_sql(aggregate, quote_identifier(column))} "
        "as aggregate_value\n"
        f"  from {render_relation(target_relation)}\n"
        ")\n"
        "select\n"
        "  source_aggregate.aggregate_value as source_aggregate_value,\n"
        "  target_aggregate.aggregate_value as target_aggregate_value,\n"
        "  source_aggregate.aggregate_value - target_aggregate.aggregate_value "
        "as aggregate_diff\n"
        "from source_aggregate\n"
        "cross join target_aggregate"
    )
    return RenderedSql(
        sql=sql,
        operation_type="compare_aggregates",
        required_capabilities=("aggregate", "cte_support"),
    )


def render_compare_grouped_aggregates(
    previous_operations: tuple[Mapping[str, Any], ...],
    source_relation: Relation,
    target_relation: Relation,
) -> RenderedSql:
    source_operation, target_operation = side_operations(previous_operations, "grouped_aggregate")
    aggregate = required_string(source_operation, "aggregate")
    column = required_string(source_operation, "column")
    group_by = required_string_tuple(source_operation, "group_by")
    assert_matching_aggregate(source_operation, target_operation)
    group_select = "\n".join(f"    {quote_identifier(key)}," for key in group_by)
    group_by_clause = ", ".join(quote_identifier(key) for key in group_by)
    join_predicate = " and ".join(
        strict_null_safe_equality(
            f"source_aggregate.{quote_identifier(key)}",
            f"target_aggregate.{quote_identifier(key)}",
        )
        for key in group_by
    )
    group_type_check = render_type_check_statement(
        left_relation=source_relation,
        right_relation=target_relation,
        keys=group_by,
        error_message="Recon DuckDB grouped aggregate key type mismatch.",
    )
    aggregate_type_check = render_aggregate_input_type_check_statement(
        left_relation=source_relation,
        right_relation=target_relation,
        column=column,
        error_message="Recon DuckDB grouped aggregate value type mismatch.",
    )
    aggregate_result_type_check = render_aggregate_result_type_check_statement(
        left_relation=source_relation,
        right_relation=target_relation,
        aggregate=aggregate,
        column=column,
        error_message="Recon DuckDB grouped aggregate value type mismatch.",
    )
    joined_group_keys = ",\n".join(
        f"    source_aggregate.{quote_identifier(key)} as "
        f"{quote_identifier(f'source_{key}')},\n"
        f"    target_aggregate.{quote_identifier(key)} as "
        f"{quote_identifier(f'target_{key}')}"
        for key in group_by
    )
    selected_group_key_expressions = tuple(
        expression
        for key in group_by
        for expression in (
            f"joined_aggregate.{quote_identifier(f'source_{key}')}",
            f"joined_aggregate.{quote_identifier(f'target_{key}')}",
        )
    )
    selected_group_keys = select_lines(selected_group_key_expressions)
    sql = (
        f"{group_type_check};\n\n"
        f"{aggregate_type_check};\n\n"
        f"{aggregate_result_type_check};\n\n"
        "with\n"
        "source_aggregate as (\n"
        "  select\n"
        f"{group_select}\n"
        f"    {aggregate_expression_sql(aggregate, quote_identifier(column))} "
        "as aggregate_value\n"
        f"  from {render_relation(source_relation)}\n"
        f"  group by {group_by_clause}\n"
        "),\n"
        "target_aggregate as (\n"
        "  select\n"
        f"{group_select}\n"
        f"    {aggregate_expression_sql(aggregate, quote_identifier(column))} "
        "as aggregate_value\n"
        f"  from {render_relation(target_relation)}\n"
        f"  group by {group_by_clause}\n"
        "),\n"
        "joined_aggregate as (\n"
        "  select\n"
        f"{joined_group_keys},\n"
        "    source_aggregate.aggregate_value as source_aggregate_value,\n"
        "    target_aggregate.aggregate_value as target_aggregate_value,\n"
        "    true as has_aggregate_row\n"
        "  from source_aggregate\n"
        "  full outer join target_aggregate\n"
        f"  on {join_predicate}"
        "\n)\n"
        "select\n"
        f"{selected_group_keys},\n"
        "  joined_aggregate.source_aggregate_value,\n"
        "  joined_aggregate.target_aggregate_value,\n"
        "  joined_aggregate.source_aggregate_value - "
        "joined_aggregate.target_aggregate_value as aggregate_diff\n"
        "from joined_aggregate\n"
        "where joined_aggregate.has_aggregate_row"
    )
    return RenderedSql(
        sql=sql,
        operation_type="compare_grouped_aggregates",
        required_capabilities=("grouped_aggregate", "cte_support"),
    )


def operation_step_name(*, index: int, operation: Mapping[str, Any]) -> str:
    operation_type = required_string(operation, "type")
    step_parts = [f"{index:02d}", operation_type]
    side = operation.get("side")
    if isinstance(side, str) and side:
        step_parts.append(side)
    direction = operation.get("direction")
    if isinstance(direction, str) and direction:
        step_parts.append(direction)
    return "-".join(step_parts)


def required_string(operation: Mapping[str, Any], field_name: str) -> str:
    value = operation.get(field_name)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"Operation field `{field_name}` must be a non-empty string")
    return value


def required_string_tuple(operation: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    value = operation.get(field_name)
    if not isinstance(value, list | tuple) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Operation field `{field_name}` must be a string list")
    return tuple(value)


def identity_keys_from_operation(operation: Mapping[str, Any]) -> tuple[str, ...]:
    identity = operation.get("identity")
    if not isinstance(identity, Mapping):
        raise ValueError("Operation requires identity")
    keys = identity.get("keys")
    if (
        not isinstance(keys, list | tuple)
        or not keys
        or not all(isinstance(item, str) and item for item in keys)
    ):
        raise ValueError("Operation identity requires non-empty string keys")
    return tuple(keys)


def side_operations(
    operations: tuple[Mapping[str, Any], ...],
    operation_type: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    source_operation: Mapping[str, Any] | None = None
    target_operation: Mapping[str, Any] | None = None
    for operation in operations:
        if operation.get("type") != operation_type:
            continue
        side = operation.get("side")
        if side == "source":
            source_operation = operation
        elif side == "target":
            target_operation = operation
    if source_operation is None or target_operation is None:
        raise ValueError(f"{operation_type} comparison requires source and target operations")
    return source_operation, target_operation


def assert_matching_aggregate(
    source_operation: Mapping[str, Any],
    target_operation: Mapping[str, Any],
) -> None:
    for field_name in ("aggregate", "column", "group_by"):
        if source_operation.get(field_name) != target_operation.get(field_name):
            raise ValueError(f"Aggregate comparison requires matching `{field_name}`")


def side_relation(
    operation: Mapping[str, Any],
    source_relation: Relation,
    target_relation: Relation,
) -> Relation:
    side = required_string(operation, "side")
    if side == "source":
        return source_relation
    if side == "target":
        return target_relation
    raise ValueError(f"Unsupported operation side: {side}")
