"""Private typed aggregate transport contract, independent of SQL dialect."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from recon_core.adapters.models import Relation, RenderedSql

_NumericValue = int | Decimal | float | None


class _NumericDomain(StrEnum):
    EXACT_INTEGER = "exact_integer"
    EXACT_DECIMAL = "exact_decimal"
    NATIVE_FLOAT = "native_float"


@dataclass(frozen=True, slots=True)
class _AggregateQueryResult:
    """One final row with verified numeric domains, not a public QueryResult."""

    columns: tuple[str, ...]
    domains: tuple[_NumericDomain, ...]
    row: tuple[_NumericValue, ...] = field(repr=False)


class _AggregateQueryExecutor(Protocol):
    """Private collaborator using an already-open adapter connection."""

    def _execute_aggregate_query(
        self, query: str, *, expected_columns: tuple[str, ...]
    ) -> _AggregateQueryResult: ...


@dataclass(frozen=True, slots=True)
class _AggregateRuntimePlan:
    """Ordered private guards and a bounded final query for the proven domain."""

    type_guards: tuple[RenderedSql, ...] = field(repr=False)
    domain_guard: RenderedSql = field(repr=False)
    exact_query: RenderedSql = field(repr=False)
    floating_query: RenderedSql = field(repr=False)
    columns: tuple[str, ...]
    required_capabilities: tuple[str, ...]

    def domain_from_guard(self, result: _AggregateQueryResult) -> _NumericDomain:
        if (
            result.columns != ("numeric_domain",)
            or result.domains != (_NumericDomain.EXACT_INTEGER,)
            or len(result.row) != 1
            or type(result.row[0]) is not int
        ):
            raise ValueError("Invalid aggregate numeric domain proof.")
        domains = {
            1: _NumericDomain.EXACT_INTEGER,
            2: _NumericDomain.EXACT_DECIMAL,
            3: _NumericDomain.NATIVE_FLOAT,
        }
        domain = domains.get(result.row[0])
        if domain is None:
            raise ValueError("Invalid aggregate numeric domain proof.")
        return domain

    def final_query(self, domain: _NumericDomain | str) -> RenderedSql:
        if domain == _NumericDomain.NATIVE_FLOAT:
            return self.floating_query
        if domain in (_NumericDomain.EXACT_INTEGER, _NumericDomain.EXACT_DECIMAL):
            return self.exact_query
        raise ValueError("Unproven aggregate numeric domain.")


class _AggregateRuntimeRenderer(Protocol):
    adapter_type: str

    def render_plan(
        self,
        operations: tuple[Mapping[str, Any], ...],
        *,
        source_relation: Relation,
        target_relation: Relation,
    ) -> _AggregateRuntimePlan: ...
