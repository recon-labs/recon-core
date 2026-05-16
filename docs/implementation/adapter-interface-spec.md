# Adapter Interface Specification

## Purpose

This document defines implementation expectations for the adapter interface.

Adapters isolate database and system-specific behavior from Recon Core.

## Base adapter responsibilities

Adapters should implement:

- connection lifecycle,
- query execution,
- relation existence checks,
- metadata fetching,
- SQL quoting,
- SQL generation helpers,
- type normalization,
- capability declaration.

## Interface sketch

```python
class BaseAdapter:
    name: str

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def execute(self, query: str) -> QueryResult: ...
    def relation_exists(self, relation: Relation) -> bool: ...
    def get_columns(self, relation_or_query: RelationOrQuery) -> list[ColumnMetadata]: ...
    def quote_identifier(self, identifier: str) -> str: ...
    def compile_limit(self, query: str, limit: int) -> str: ...
    def capabilities(self) -> AdapterCapabilities: ...
```

## Query result

Suggested model:

```python
@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    row_count: int | None
```

Large result handling can be added later.

## Column metadata

Suggested model:

```python
@dataclass(frozen=True)
class ColumnMetadata:
    name: str
    logical_type: str
    physical_type: str
    nullable: bool | None
    precision: int | None
    scale: int | None
    timezone: str | None
```

## Capabilities

Suggested capabilities:

```python
@dataclass(frozen=True)
class AdapterCapabilities:
    relations: bool
    queries: bool
    metadata_columns: bool
    metadata_precision_scale: bool
    temp_tables: bool
    cte_support: bool
    timestamp_diff: bool
    safe_hash_expression: bool
    json_path: bool
    semi_structured_projection: bool
```

## Adapter registry

Adapters should register by connection type.

```python
registry.register("postgres", PostgresAdapter)
registry.register("snowflake", SnowflakeAdapter)
```

Core should resolve connection type through the registry.

## Capability validation

Checks declare required capabilities.

The compiler validates known capability mismatches.

Runtime validates anything that depends on live metadata.

## SQL generation

Core check logic may define abstract operations.

Adapters should provide dialect-specific SQL for:

- quoting,
- limits,
- casts,
- timestamp differences,
- null-safe equality,
- hashing when supported.

## Hashing

Adapters must not claim portable hash compatibility without tests.

Cross-database sampling should prefer persisted sample keys or numeric modulo when appropriate.

## Production adapters

Long-term production adapters:

```text
recon-postgres
recon-mysql
recon-snowflake
recon-sqlserver
recon-bigquery
recon-mongodb
recon-databricks
recon-redshift
recon-oracle
```

## Design principle

Core defines what reconciliation needs. Adapters define how each system can do it safely.
