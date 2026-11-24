"""Private typed aggregate transport contract, independent of SQL dialect."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

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
