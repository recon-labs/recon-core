"""Adapter boundary models."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from recon_core.diagnostics import Diagnostic

if TYPE_CHECKING:
    from recon_core.adapters.base import BaseAdapter

ADAPTER_API_VERSION = "1"


@dataclass(frozen=True, slots=True)
class Relation:
    """Qualified relation identifier."""

    identifier: str
    schema: str | None = None
    catalog: str | None = None


@dataclass(frozen=True, slots=True)
class ColumnMetadata:
    """Column metadata returned by adapters."""

    name: str
    logical_type: str
    physical_type: str
    nullable: bool | None = None
    precision: int | None = None
    scale: int | None = None
    timezone: str | None = None


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Small query result envelope."""

    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    row_count: int | None = None


@dataclass(frozen=True, slots=True)
class RenderedSql:
    """SQL rendered from one typed operation."""

    sql: str
    operation_type: str
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AdapterResolutionResult:
    """Result for resolving a connection to an adapter instance."""

    adapter: "BaseAdapter | None" = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.adapter is not None and not self.diagnostics
