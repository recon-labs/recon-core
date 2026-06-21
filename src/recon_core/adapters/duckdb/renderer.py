"""DuckDB SQL renderer."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from recon_core.adapters.base import SqlRenderer
from recon_core.adapters.models import Relation, RenderedSql

from .renderer_operations import (
    operation_step_name,
    render_aggregate,
    render_compare_aggregates,
    render_compare_counts,
    render_compare_grouped_aggregates,
    render_duplicate_key,
    render_grouped_aggregate,
    render_key_diff,
    render_null_key,
    render_row_count,
    required_string,
)
from .renderer_sql import quote_identifier, render_relation


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
        operation_type = required_string(operation, "type")
        if operation_type == "row_count":
            return render_row_count(operation, source_relation, target_relation)
        if operation_type == "compare_counts":
            return render_compare_counts(source_relation, target_relation)
        if operation_type == "key_diff":
            return render_key_diff(operation, source_relation, target_relation)
        if operation_type == "null_key":
            return render_null_key(operation, source_relation, target_relation)
        if operation_type == "duplicate_key":
            return render_duplicate_key(operation, source_relation, target_relation)
        if operation_type == "aggregate":
            return render_aggregate(operation, source_relation, target_relation)
        if operation_type == "grouped_aggregate":
            return render_grouped_aggregate(operation, source_relation, target_relation)
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
            operation_type = required_string(operation, "type")
            if operation_type == "compare_aggregates":
                rendered_sql = render_compare_aggregates(
                    operations[:index],
                    source_relation,
                    target_relation,
                )
            elif operation_type == "compare_grouped_aggregates":
                rendered_sql = render_compare_grouped_aggregates(
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
                    step_name=operation_step_name(index=index, operation=operation),
                )
            )
        return tuple(rendered)

    def quote_identifier(self, identifier: str) -> str:
        return quote_identifier(identifier)

    def render_relation(self, relation: Relation) -> str:
        return render_relation(relation)
