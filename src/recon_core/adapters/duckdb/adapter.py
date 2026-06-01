"""DuckDB local development adapter foundation."""

from collections.abc import Callable, Mapping
from dataclasses import replace
from importlib.util import find_spec
from typing import Any

from recon_core._version import get_version
from recon_core.adapters.base import BaseAdapter, SqlRenderer
from recon_core.adapters.capabilities import AdapterCapabilities, CapabilitySupport
from recon_core.adapters.models import (
    ADAPTER_API_VERSION,
    AdapterResolutionResult,
    ColumnMetadata,
    QueryResult,
    Relation,
    RenderedSql,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig

ADAPTER_DEPENDENCY_MISSING = "RC_ADAPTER_DEPENDENCY_MISSING"


class DuckDbAdapter(BaseAdapter):
    """DuckDB local development adapter shell."""

    adapter_type = "duckdb"
    adapter_version = get_version()
    supported_adapter_api_version = ADAPTER_API_VERSION

    def connect(self) -> None:
        raise NotImplementedError("DuckDB connection lifecycle is implemented in a later phase.")

    def close(self) -> None:
        raise NotImplementedError("DuckDB connection lifecycle is implemented in a later phase.")

    def execute(self, query: str) -> QueryResult:
        raise NotImplementedError("DuckDB query execution is implemented in a later phase.")

    def relation_exists(self, relation: Relation) -> bool:
        raise NotImplementedError("DuckDB metadata access is implemented in a later phase.")

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        raise NotImplementedError("DuckDB metadata access is implemented in a later phase.")

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            {
                "relations": CapabilitySupport.FULL,
                "queries": CapabilitySupport.UNSUPPORTED,
                "metadata_columns": CapabilitySupport.NOT_IMPLEMENTED,
                "metadata_precision_scale": CapabilitySupport.NOT_IMPLEMENTED,
                "cte_support": CapabilitySupport.FULL,
                "row_count": CapabilitySupport.FULL,
                "aggregate": CapabilitySupport.FULL,
                "grouped_aggregate": CapabilitySupport.FULL,
                "key_diff": CapabilitySupport.FULL,
                "null_key": CapabilitySupport.FULL,
                "duplicate_key": CapabilitySupport.FULL,
            }
        )


class DuckDbAdapterFactory:
    """Factory that checks whether the optional DuckDB dependency is installed."""

    def __init__(self, *, dependency_available: Callable[[], bool] | None = None) -> None:
        self._dependency_available = dependency_available or _duckdb_dependency_available

    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        if not self._dependency_available():
            return AdapterResolutionResult(
                diagnostics=(
                    Diagnostic(
                        code=ADAPTER_DEPENDENCY_MISSING,
                        severity=DiagnosticSeverity.ERROR,
                        message="DuckDB adapter dependency is not installed.",
                        resource_type="adapter",
                        resource_name="duckdb",
                        hint="Install Recon Core with `recon-core[duckdb]`.",
                    ),
                )
            )

        return AdapterResolutionResult(adapter=DuckDbAdapter(connection=connection))


class DuckDbSqlRenderer(SqlRenderer):
    """DuckDB SQL renderer shell."""

    adapter_type = "duckdb"

    def render_operation(
        self,
        operation: Mapping[str, Any],
        *,
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        operation_type = _required_string(operation, "type")
        if operation_type == "row_count":
            return self._render_row_count(operation, source_relation, target_relation)
        if operation_type == "compare_counts":
            return self._render_compare_counts(source_relation, target_relation)
        if operation_type == "key_diff":
            return self._render_key_diff(operation, source_relation, target_relation)
        if operation_type == "null_key":
            return self._render_null_key(operation, source_relation, target_relation)
        if operation_type == "duplicate_key":
            return self._render_duplicate_key(operation, source_relation, target_relation)
        if operation_type == "aggregate":
            return self._render_aggregate(operation, source_relation, target_relation)
        if operation_type == "grouped_aggregate":
            return self._render_grouped_aggregate(operation, source_relation, target_relation)
        if operation_type in {"compare_aggregates", "compare_grouped_aggregates"}:
            raise ValueError(f"{operation_type} requires plan context")
        raise ValueError(f"Unsupported DuckDB operation: {operation_type}")

    def render_plan(
        self,
        operations: tuple[Mapping[str, Any], ...],
        *,
        source_relation: Relation,
        target_relation: Relation,
    ) -> tuple[RenderedSql, ...]:
        rendered: list[RenderedSql] = []
        for index, operation in enumerate(operations):
            operation_type = _required_string(operation, "type")
            if operation_type == "compare_aggregates":
                rendered_sql = self._render_compare_aggregates(
                    operations[:index],
                    source_relation,
                    target_relation,
                )
            elif operation_type == "compare_grouped_aggregates":
                rendered_sql = self._render_compare_grouped_aggregates(
                    operations[:index],
                    source_relation,
                    target_relation,
                )
            else:
                rendered_sql = self.render_operation(
                    operation,
                    source_relation=source_relation,
                    target_relation=target_relation,
                )
            rendered.append(
                replace(
                    rendered_sql,
                    step_name=_operation_step_name(index=index, operation=operation),
                )
            )
        return tuple(rendered)

    def quote_identifier(self, identifier: str) -> str:
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'

    def render_relation(self, relation: Relation) -> str:
        return ".".join(
            self.quote_identifier(part)
            for part in (relation.catalog, relation.schema, relation.identifier)
            if part is not None
        )

    def _render_row_count(
        self,
        operation: Mapping[str, Any],
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        relation = self._side_relation(operation, source_relation, target_relation)
        return RenderedSql(
            sql=f"select count(*) as row_count\nfrom {self.render_relation(relation)}",
            operation_type="row_count",
            required_capabilities=("row_count",),
        )

    def _render_compare_counts(
        self,
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        sql = (
            "with\n"
            "source_count as (\n"
            "  select count(*) as row_count\n"
            f"  from {self.render_relation(source_relation)}\n"
            "),\n"
            "target_count as (\n"
            "  select count(*) as row_count\n"
            f"  from {self.render_relation(target_relation)}\n"
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
            required_capabilities=("row_count",),
        )

    def _render_key_diff(
        self,
        operation: Mapping[str, Any],
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        identity_keys = _identity_keys(operation)
        direction = _required_string(operation, "direction")
        if direction == "source_minus_target":
            left_relation = source_relation
            right_relation = target_relation
        elif direction == "target_minus_source":
            left_relation = target_relation
            right_relation = source_relation
        else:
            raise ValueError(f"Unsupported key_diff direction: {direction}")

        quoted_keys = tuple(self.quote_identifier(key) for key in identity_keys)
        cte_keys = _select_lines(quoted_keys, indent=4)
        selected_keys = _select_lines(f"left_keys.{quoted_key}" for quoted_key in quoted_keys)
        non_null_predicate = " and ".join(f"{quoted_key} is not null" for quoted_key in quoted_keys)
        join_predicate = " and ".join(
            self._strict_null_safe_equality(
                f"left_keys.{quoted_key}",
                f"right_keys.{quoted_key}",
            )
            for quoted_key in quoted_keys
        )
        type_check_cte = self._render_type_check_cte(
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
            f"  from {self.render_relation(left_relation)}\n"
            f"  where {non_null_predicate}\n"
            "),\n"
            "right_keys as (\n"
            "  select distinct\n"
            f"{cte_keys}\n"
            f"  from {self.render_relation(right_relation)}\n"
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
            f"left_keys.{self.quote_identifier(identity_keys[0])} is not null and "
            f"right_keys.{self.quote_identifier(identity_keys[0])} is null"
        )
        return RenderedSql(
            sql=sql,
            operation_type="key_diff",
            required_capabilities=("key_diff",),
        )

    def _render_null_key(
        self,
        operation: Mapping[str, Any],
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        relation = self._side_relation(operation, source_relation, target_relation)
        identity_keys = _identity_keys(operation)
        sql = (
            "select\n"
            f"{_select_lines(self.quote_identifier(key) for key in identity_keys)}\n"
            f"from {self.render_relation(relation)}\n"
            "where " + " or ".join(f"{self.quote_identifier(key)} is null" for key in identity_keys)
        )
        return RenderedSql(
            sql=sql,
            operation_type="null_key",
            required_capabilities=("null_key",),
        )

    def _render_duplicate_key(
        self,
        operation: Mapping[str, Any],
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        relation = self._side_relation(operation, source_relation, target_relation)
        identity_keys = _identity_keys(operation)
        quoted_keys = tuple(self.quote_identifier(key) for key in identity_keys)
        sql = (
            "select\n"
            f"{_select_lines((*quoted_keys, 'count(*) as row_count'))}\n"
            f"from {self.render_relation(relation)}\n"
            f"group by {', '.join(quoted_keys)}\n"
            "having count(*) > 1"
        )
        return RenderedSql(
            sql=sql,
            operation_type="duplicate_key",
            required_capabilities=("duplicate_key",),
        )

    def _render_aggregate(
        self,
        operation: Mapping[str, Any],
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        relation = self._side_relation(operation, source_relation, target_relation)
        aggregate = _required_string(operation, "aggregate")
        column = _required_string(operation, "column")
        sql = (
            f"select {aggregate}({self.quote_identifier(column)}) as aggregate_value\n"
            f"from {self.render_relation(relation)}"
        )
        return RenderedSql(
            sql=sql,
            operation_type="aggregate",
            required_capabilities=("aggregate",),
        )

    def _render_grouped_aggregate(
        self,
        operation: Mapping[str, Any],
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        relation = self._side_relation(operation, source_relation, target_relation)
        aggregate = _required_string(operation, "aggregate")
        column = _required_string(operation, "column")
        group_by = _required_string_tuple(operation, "group_by")
        group_select = _select_lines(self.quote_identifier(column_name) for column_name in group_by)
        sql = (
            "select\n"
            f"{group_select},\n"
            f"  {aggregate}({self.quote_identifier(column)}) as aggregate_value\n"
            f"from {self.render_relation(relation)}\n"
            f"group by {', '.join(self.quote_identifier(column_name) for column_name in group_by)}"
        )
        return RenderedSql(
            sql=sql,
            operation_type="grouped_aggregate",
            required_capabilities=("grouped_aggregate",),
        )

    def _render_compare_aggregates(
        self,
        previous_operations: tuple[Mapping[str, Any], ...],
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        source_operation, target_operation = _side_operations(previous_operations, "aggregate")
        aggregate = _required_string(source_operation, "aggregate")
        column = _required_string(source_operation, "column")
        _assert_matching_aggregate(source_operation, target_operation)
        aggregate_type_check = self._render_aggregate_type_check_cte(
            cte_name="aggregate_type_check",
            left_relation=source_relation,
            right_relation=target_relation,
            aggregate=aggregate,
            column=column,
            error_message="Recon DuckDB aggregate value type mismatch.",
        )
        sql = (
            "with\n"
            f"{aggregate_type_check},\n"
            "source_aggregate as (\n"
            f"  select {aggregate}({self.quote_identifier(column)}) as aggregate_value\n"
            f"  from {self.render_relation(source_relation)}\n"
            "),\n"
            "target_aggregate as (\n"
            f"  select {aggregate}({self.quote_identifier(column)}) as aggregate_value\n"
            f"  from {self.render_relation(target_relation)}\n"
            ")\n"
            "select\n"
            "  source_aggregate.aggregate_value as source_aggregate_value,\n"
            "  target_aggregate.aggregate_value as target_aggregate_value,\n"
            "  source_aggregate.aggregate_value - target_aggregate.aggregate_value "
            "as aggregate_diff\n"
            "from aggregate_type_check\n"
            "cross join source_aggregate\n"
            "cross join target_aggregate\n"
            "where aggregate_type_check.type_check"
        )
        return RenderedSql(
            sql=sql,
            operation_type="compare_aggregates",
            required_capabilities=("aggregate",),
        )

    def _render_compare_grouped_aggregates(
        self,
        previous_operations: tuple[Mapping[str, Any], ...],
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        source_operation, target_operation = _side_operations(
            previous_operations, "grouped_aggregate"
        )
        aggregate = _required_string(source_operation, "aggregate")
        column = _required_string(source_operation, "column")
        group_by = _required_string_tuple(source_operation, "group_by")
        _assert_matching_aggregate(source_operation, target_operation)
        group_select = "\n".join(f"    {self.quote_identifier(key)}," for key in group_by)
        group_by_clause = ", ".join(self.quote_identifier(key) for key in group_by)
        join_predicate = " and ".join(
            self._strict_null_safe_equality(
                f"source_aggregate.{self.quote_identifier(key)}",
                f"target_aggregate.{self.quote_identifier(key)}",
            )
            for key in group_by
        )
        type_check_cte = self._render_type_check_cte(
            cte_name="group_type_check",
            left_relation=source_relation,
            right_relation=target_relation,
            keys=group_by,
            error_message="Recon DuckDB grouped aggregate key type mismatch.",
        )
        aggregate_type_check = self._render_aggregate_type_check_cte(
            cte_name="aggregate_type_check",
            left_relation=source_relation,
            right_relation=target_relation,
            aggregate=aggregate,
            column=column,
            error_message="Recon DuckDB grouped aggregate value type mismatch.",
        )
        joined_group_keys = ",\n".join(
            f"    source_aggregate.{self.quote_identifier(key)} as "
            f"{self.quote_identifier(f'source_{key}')},\n"
            f"    target_aggregate.{self.quote_identifier(key)} as "
            f"{self.quote_identifier(f'target_{key}')}"
            for key in group_by
        )
        selected_group_key_expressions = tuple(
            expression
            for key in group_by
            for expression in (
                f"joined_aggregate.{self.quote_identifier(f'source_{key}')}",
                f"joined_aggregate.{self.quote_identifier(f'target_{key}')}",
            )
        )
        selected_group_keys = _select_lines(selected_group_key_expressions)
        sql = (
            "with\n"
            "source_aggregate as (\n"
            "  select\n"
            f"{group_select}\n"
            f"    {aggregate}({self.quote_identifier(column)}) as aggregate_value\n"
            f"  from {self.render_relation(source_relation)}\n"
            f"  group by {group_by_clause}\n"
            "),\n"
            "target_aggregate as (\n"
            "  select\n"
            f"{group_select}\n"
            f"    {aggregate}({self.quote_identifier(column)}) as aggregate_value\n"
            f"  from {self.render_relation(target_relation)}\n"
            f"  group by {group_by_clause}\n"
            "),\n"
            f"{type_check_cte},\n"
            f"{aggregate_type_check},\n"
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
            "from group_type_check\n"
            "cross join aggregate_type_check\n"
            "left join joined_aggregate\n"
            "  on group_type_check.type_check and aggregate_type_check.type_check\n"
            "where group_type_check.type_check and aggregate_type_check.type_check "
            "and joined_aggregate.has_aggregate_row"
        )
        return RenderedSql(
            sql=sql,
            operation_type="compare_grouped_aggregates",
            required_capabilities=("grouped_aggregate",),
        )

    def _strict_null_safe_equality(
        self,
        left_expression: str,
        right_expression: str,
    ) -> str:
        return (
            f"(typeof({left_expression}) = typeof({right_expression}) and "
            f"{left_expression} is not distinct from {right_expression})"
        )

    def _render_type_check_cte(
        self,
        *,
        cte_name: str,
        left_relation: Relation,
        right_relation: Relation,
        keys: tuple[str, ...],
        error_message: str,
    ) -> str:
        left_relation_sql = self.render_relation(left_relation)
        right_relation_sql = self.render_relation(right_relation)
        predicates = "\n        and ".join(
            f"typeof((select {self.quote_identifier(key)} from {left_relation_sql} limit 1)) = "
            f"typeof((select {self.quote_identifier(key)} from {right_relation_sql} limit 1))"
            for key in keys
        )
        return (
            f"{cte_name} as (\n"
            "  select\n"
            "    case\n"
            "      when\n"
            f"        {predicates}\n"
            "      then true\n"
            f"      else error({_sql_string_literal(error_message)})\n"
            "    end as type_check\n"
            ")"
        )

    def _render_aggregate_type_check_cte(
        self,
        *,
        cte_name: str,
        left_relation: Relation,
        right_relation: Relation,
        aggregate: str,
        column: str,
        error_message: str,
    ) -> str:
        column_expression = self.quote_identifier(column)
        aggregate_expression = f"{aggregate}({column_expression})"
        left_relation_sql = self.render_relation(left_relation)
        right_relation_sql = self.render_relation(right_relation)
        source_input_type = f"typeof((select {column_expression} from {left_relation_sql} limit 1))"
        target_input_type = (
            f"typeof((select {column_expression} from {right_relation_sql} limit 1))"
        )
        predicate = (
            f"{source_input_type} = {target_input_type}\n"
            "        and "
            f"{source_input_type} <> 'BOOLEAN'\n"
            "        and "
            f"{target_input_type} <> 'BOOLEAN'\n"
            "        and "
            f"typeof((select {aggregate_expression} from {left_relation_sql} limit 1)) = "
            f"typeof((select {aggregate_expression} from {right_relation_sql} limit 1))"
        )
        return (
            f"{cte_name} as (\n"
            "  select\n"
            "    case\n"
            "      when\n"
            f"        {predicate}\n"
            "      then true\n"
            f"      else error({_sql_string_literal(error_message)})\n"
            "    end as type_check\n"
            ")"
        )

    def _side_relation(
        self,
        operation: Mapping[str, Any],
        source_relation: Relation,
        target_relation: Relation,
    ) -> Relation:
        side = _required_string(operation, "side")
        if side == "source":
            return source_relation
        if side == "target":
            return target_relation
        raise ValueError(f"Unsupported operation side: {side}")


def _duckdb_dependency_available() -> bool:
    return find_spec("duckdb") is not None


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _operation_step_name(*, index: int, operation: Mapping[str, Any]) -> str:
    operation_type = _required_string(operation, "type")
    step_parts = [f"{index:02d}", operation_type]
    side = operation.get("side")
    if isinstance(side, str) and side:
        step_parts.append(side)
    direction = operation.get("direction")
    if isinstance(direction, str) and direction:
        step_parts.append(direction)
    return "-".join(step_parts)


def _required_string(operation: Mapping[str, Any], field_name: str) -> str:
    value = operation.get(field_name)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"Operation field `{field_name}` must be a non-empty string")
    return value


def _required_string_tuple(operation: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    value = operation.get(field_name)
    if not isinstance(value, list | tuple) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Operation field `{field_name}` must be a string list")
    return tuple(value)


def _identity_keys(operation: Mapping[str, Any]) -> tuple[str, ...]:
    identity = operation.get("identity")
    if not isinstance(identity, Mapping):
        raise ValueError("Operation requires identity")
    keys = identity.get("keys")
    if not isinstance(keys, list | tuple) or not all(isinstance(item, str) for item in keys):
        raise ValueError("Operation identity requires string keys")
    return tuple(keys)


def _select_lines(expressions: tuple[str, ...] | Any, *, indent: int = 2) -> str:
    values = tuple(expressions)
    indentation = " " * indent
    return ",\n".join(f"{indentation}{value}" for value in values)


def _side_operations(
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


def _assert_matching_aggregate(
    source_operation: Mapping[str, Any],
    target_operation: Mapping[str, Any],
) -> None:
    for field_name in ("aggregate", "column", "group_by"):
        if source_operation.get(field_name) != target_operation.get(field_name):
            raise ValueError(f"Aggregate comparison requires matching `{field_name}`")
