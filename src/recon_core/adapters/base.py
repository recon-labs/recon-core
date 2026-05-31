"""Base adapter interfaces."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar

from recon_core.adapters.capabilities import AdapterCapabilities
from recon_core.adapters.models import ColumnMetadata, QueryResult, Relation, RenderedSql
from recon_core.profiles import ConnectionConfig


class BaseAdapter(ABC):
    """Base interface for adapter instances."""

    adapter_type: ClassVar[str]
    adapter_version: ClassVar[str]
    supported_adapter_api_version: ClassVar[str]

    def __init__(self, *, connection: ConnectionConfig) -> None:
        self.connection = connection

    @abstractmethod
    def connect(self) -> None:
        """Open adapter resources."""

    @abstractmethod
    def close(self) -> None:
        """Close adapter resources."""

    @abstractmethod
    def execute(self, query: str) -> QueryResult:
        """Execute a query."""

    @abstractmethod
    def relation_exists(self, relation: Relation) -> bool:
        """Return whether a relation exists."""

    @abstractmethod
    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        """Return relation column metadata."""

    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Return declared adapter capabilities."""


class SqlRenderer(ABC):
    """Base interface for dialect SQL renderers."""

    adapter_type: ClassVar[str]

    @abstractmethod
    def render_operation(self, operation: Mapping[str, Any]) -> RenderedSql:
        """Render one typed operation into SQL."""

    @abstractmethod
    def quote_identifier(self, identifier: str) -> str:
        """Quote one identifier part."""

    @abstractmethod
    def render_relation(self, relation: Relation) -> str:
        """Render a relation identifier."""
