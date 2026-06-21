import pytest

from recon_core.adapters import (
    ADAPTER_API_VERSION,
    AdapterCapabilities,
    BaseAdapter,
    CapabilitySupport,
    ColumnMetadata,
    ConnectionConfig,
    QueryResult,
    Relation,
    RelationMetadataAdapter,
)
from recon_core.adapters.duckdb import DuckDbAdapter


class MinimalAdapter(BaseAdapter):
    adapter_type = "minimal"
    adapter_version = "0.1.0"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def execute(self, query: str) -> QueryResult:
        return QueryResult(columns=(), rows=(), row_count=0)

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities({})


class MetadataAdapter(RelationMetadataAdapter):
    adapter_type = "metadata"
    adapter_version = "0.1.0"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def execute(self, query: str) -> QueryResult:
        return QueryResult(columns=(), rows=(), row_count=0)

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities({"metadata_columns": CapabilitySupport.FULL})

    def relation_exists(self, relation: Relation) -> bool:
        return relation.identifier == "customers"

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        return (
            ColumnMetadata(
                name="customer_id",
                logical_type="integer",
                physical_type="INTEGER",
                nullable=False,
            ),
        )


class MethodOnlyAdapter(MinimalAdapter):
    def relation_exists(self, relation: Relation) -> bool:
        return True

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        return ()


def test_base_adapter_does_not_force_relation_metadata_methods() -> None:
    adapter = MinimalAdapter(connection=ConnectionConfig(name="warehouse", type="minimal"))

    assert isinstance(adapter, BaseAdapter)
    assert not isinstance(adapter, RelationMetadataAdapter)
    assert adapter.capabilities().support_for("metadata_columns") is CapabilitySupport.UNKNOWN


def test_base_adapter_relation_metadata_shims_fail_clearly() -> None:
    adapter = MinimalAdapter(connection=ConnectionConfig(name="warehouse", type="minimal"))
    relation = Relation(identifier="customers")

    with pytest.raises(NotImplementedError, match="Relation metadata access"):
        adapter.relation_exists(relation)
    with pytest.raises(NotImplementedError, match="Relation column metadata"):
        adapter.get_columns(relation)


def test_relation_metadata_adapter_is_nominal_metadata_interface() -> None:
    adapter = MetadataAdapter(connection=ConnectionConfig(name="warehouse", type="metadata"))
    relation = Relation(identifier="customers")

    assert isinstance(adapter, BaseAdapter)
    assert isinstance(adapter, RelationMetadataAdapter)
    assert adapter.capabilities().support_for("metadata_columns") is CapabilitySupport.FULL
    assert adapter.relation_exists(relation)
    assert adapter.get_columns(relation)[0].name == "customer_id"


def test_method_presence_alone_does_not_make_adapter_metadata_capable() -> None:
    adapter = MethodOnlyAdapter(connection=ConnectionConfig(name="warehouse", type="minimal"))

    assert hasattr(adapter, "relation_exists")
    assert hasattr(adapter, "get_columns")
    assert not isinstance(adapter, RelationMetadataAdapter)


def test_duckdb_adapter_does_not_claim_relation_metadata_support() -> None:
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))

    assert isinstance(adapter, BaseAdapter)
    assert not isinstance(adapter, RelationMetadataAdapter)
    assert adapter.capabilities().support_for("metadata_columns") is (
        CapabilitySupport.NOT_IMPLEMENTED
    )
