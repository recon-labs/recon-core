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

    def relation_exists(self, relation: Relation) -> bool:
        """Return whether a relation exists.

        Relation metadata support is optional. Metadata-capable adapters should
        implement RelationMetadataAdapter; this default exists for pre-alpha
        compatibility with callers that still probe the old base method.
        """
        raise NotImplementedError("Relation metadata access is not implemented by this adapter.")

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        """Return relation column metadata.

        Relation metadata support is optional. Metadata-capable adapters should
        implement RelationMetadataAdapter; this default exists for pre-alpha
        compatibility with callers that still probe the old base method.
        """
        raise NotImplementedError("Relation column metadata is not implemented by this adapter.")

    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Return declared adapter capabilities."""


class RelationMetadataAdapter(BaseAdapter):
    """Adapter interface for relation metadata access."""

    @abstractmethod
    def relation_exists(self, relation: Relation) -> bool:
        """Return whether a relation exists."""

    @abstractmethod
    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        """Return relation column metadata."""


class SqlRenderer(ABC):
    """Base interface for dialect SQL renderers."""

    adapter_type: ClassVar[str]

    @abstractmethod
    def render_operation(
        self,
        operation: Mapping[str, Any],
        *,
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql:
        """Render one typed operation into SQL."""

    @abstractmethod
    def render_plan(
        self,
        operations: tuple[Mapping[str, Any], ...],
        *,
        source_relation: Relation,
        target_relation: Relation,
    ) -> tuple[RenderedSql, ...]:
        """Render a typed operation sequence into SQL."""

    @abstractmethod
    def quote_identifier(self, identifier: str) -> str:
        """Quote one identifier part."""

    @abstractmethod
    def render_relation(self, relation: Relation) -> str:
        """Render a relation identifier."""
