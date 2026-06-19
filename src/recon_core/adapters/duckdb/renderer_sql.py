"""DuckDB SQL rendering fragments."""

from collections.abc import Iterable

from recon_core.adapters.models import Relation


def quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def render_relation(relation: Relation) -> str:
    return ".".join(
        quote_identifier(part)
        for part in (relation.catalog, relation.schema, relation.identifier)
        if part is not None
    )


def select_lines(expressions: Iterable[str], *, indent: int = 2) -> str:
    values = tuple(expressions)
    indentation = " " * indent
    return ",\n".join(f"{indentation}{value}" for value in values)


def strict_null_safe_equality(
    left_expression: str,
    right_expression: str,
) -> str:
    return (
        f"(typeof({left_expression}) = typeof({right_expression}) and "
        f"{left_expression} is not distinct from {right_expression})"
    )


def render_type_check_cte(
    *,
    cte_name: str,
    left_relation: Relation,
    right_relation: Relation,
    keys: tuple[str, ...],
    error_message: str,
) -> str:
    left_relation_sql = render_relation(left_relation)
    right_relation_sql = render_relation(right_relation)
    predicates = "\n        and ".join(
        f"typeof((select {quote_identifier(key)} from {left_relation_sql} limit 1)) = "
        f"typeof((select {quote_identifier(key)} from {right_relation_sql} limit 1))"
        for key in keys
    )
    return (
        f"{cte_name} as (\n"
        "  select\n"
        "    case\n"
        "      when\n"
        f"        {predicates}\n"
        "      then true\n"
        f"      else error({sql_string_literal(error_message)})\n"
        "    end as type_check\n"
        ")"
    )


def render_type_check_statement(
    *,
    left_relation: Relation,
    right_relation: Relation,
    keys: tuple[str, ...],
    error_message: str,
) -> str:
    left_relation_sql = render_relation(left_relation)
    right_relation_sql = render_relation(right_relation)
    predicates = "\n        and ".join(
        f"typeof((select {quote_identifier(key)} from {left_relation_sql} limit 1)) = "
        f"typeof((select {quote_identifier(key)} from {right_relation_sql} limit 1))"
        for key in keys
    )
    return render_type_check_select(
        predicate=predicates,
        error_message=error_message,
    )


def render_single_aggregate_input_type_check_statement(
    *,
    relation: Relation,
    column: str,
    error_message: str,
) -> str:
    column_expression = quote_identifier(column)
    relation_sql = render_relation(relation)
    input_type = f"typeof((select {column_expression} from {relation_sql} limit 1))"
    predicate = aggregate_input_type_supported_predicate(input_type)
    return render_type_check_select(
        predicate=predicate,
        error_message=error_message,
    )


def render_aggregate_input_type_check_statement(
    *,
    left_relation: Relation,
    right_relation: Relation,
    column: str,
    error_message: str,
) -> str:
    column_expression = quote_identifier(column)
    left_relation_sql = render_relation(left_relation)
    right_relation_sql = render_relation(right_relation)
    source_input_type = f"typeof((select {column_expression} from {left_relation_sql} limit 1))"
    target_input_type = (
        f"typeof((select {column_expression} from {right_relation_sql} limit 1))"
    )
    predicate = (
        f"{source_input_type} = {target_input_type}\n"
        "        and "
        f"{aggregate_input_type_supported_predicate(source_input_type)}\n"
        "        and "
        f"{aggregate_input_type_supported_predicate(target_input_type)}"
    )
    return render_type_check_select(
        predicate=predicate,
        error_message=error_message,
    )


def render_aggregate_result_type_check_statement(
    *,
    left_relation: Relation,
    right_relation: Relation,
    aggregate: str,
    column: str,
    error_message: str,
) -> str:
    column_expression = quote_identifier(column)
    aggregate_expression = aggregate_expression_sql(aggregate, column_expression)
    left_relation_sql = render_relation(left_relation)
    right_relation_sql = render_relation(right_relation)
    predicate = (
        f"typeof((select {aggregate_expression} from {left_relation_sql} limit 1)) = "
        f"typeof((select {aggregate_expression} from {right_relation_sql} limit 1))"
    )
    return render_type_check_select(
        predicate=predicate,
        error_message=error_message,
    )


def render_type_check_select(*, predicate: str, error_message: str) -> str:
    return (
        "select\n"
        "  case\n"
        "    when\n"
        f"      {predicate}\n"
        "    then true\n"
        f"    else error({sql_string_literal(error_message)})\n"
        "  end as type_check"
    )


def sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def aggregate_expression_sql(aggregate: str, column_expression: str) -> str:
    return f"{aggregate}({column_expression})"


_DUCKDB_NUMERIC_SUM_TYPES = (
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "FLOAT",
    "DOUBLE",
    "BIGNUM",
)


def aggregate_input_type_supported_predicate(type_expression: str) -> str:
    numeric_types = ", ".join(
        sql_string_literal(type_name) for type_name in _DUCKDB_NUMERIC_SUM_TYPES
    )
    return f"({type_expression} in ({numeric_types}) or {type_expression} like 'DECIMAL(%)')"
