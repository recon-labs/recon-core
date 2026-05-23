# Adapter Interface Specification

## Purpose

This document defines implementation expectations for the adapter interface.

Adapters isolate database and system-specific behavior from Recon Core.

This specification follows
`docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`.

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

SQL-capable adapters should also implement a dialect renderer for typed check
plan operations. Core defines the operations; adapters define dialect rendering.

## Interface sketch

```python
class BaseAdapter:
    name: str
    adapter_type: str
    adapter_version: str
    supported_adapter_api_version: str

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def execute(self, query: str) -> QueryResult: ...
    def relation_exists(self, relation: Relation) -> bool: ...
    def get_columns(self, relation_or_query: RelationOrQuery) -> list[ColumnMetadata]: ...
    def quote_identifier(self, identifier: str) -> str: ...
    def compile_limit(self, query: str, limit: int) -> str: ...
    def capabilities(self) -> AdapterCapabilities: ...
```

The final API should separate connection/metadata/execution from SQL rendering.
This avoids forcing non-SQL adapters to implement SQL helper methods.

Illustrative SQL renderer:

```python
class SqlRenderer:
    def quote_identifier(self, identifier: str) -> str: ...
    def render_relation(self, relation: Relation) -> str: ...
    def render_limit(self, query: str, limit: int) -> str: ...
    def render_cast(self, expression: str, target_type: LogicalType) -> str: ...
    def render_null_safe_equal(self, left: str, right: str) -> str: ...
    def render_hash(self, expressions: list[str]) -> str: ...
    def render_timestamp_diff(self, left: str, right: str, unit: str) -> str: ...
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
    row_count: bool
    aggregate: bool
    grouped_aggregate: bool
    key_diff: bool
    null_key: bool
    duplicate_key: bool
    null_safe_equality: bool
    numeric_cast: bool
    string_cast: bool
    timestamp_diff: bool
    safe_hash_expression: bool
    portable_hash_compatible: bool
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

Adapter API compatibility should also be validated. If an adapter declares an
older unsupported adapter API version, Recon should fail before execution with a
clear diagnostic.

## SQL generation

Core check logic should define typed abstract operations.

Adapters should provide dialect-specific SQL for:

- quoting,
- limits,
- casts,
- timestamp differences,
- null-safe equality,
- hashing when supported.

Examples of core-owned typed operations:

```text
row_count
aggregate
grouped_aggregate
key_diff
null_key
duplicate_key
null_safe_equal
cast
limit
hash
timestamp_diff
schema_metadata
compare_counts
compare_aggregates
compare_grouped_aggregates
```

Generated SQL should remain traceable to the typed operation that produced it.

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

Do not hide comparison semantics inside adapter-specific SQL or macro logic.
