# Adapter Interface Specification

## Purpose

This document defines implementation expectations for the adapter interface.

Adapters isolate database and system-specific behavior from Recon Core.

This specification follows:

- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`

## Base adapter responsibilities

Adapters should implement:

- connection lifecycle,
- query execution,
- relation existence checks,
- metadata fetching,
- adapter metadata,
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
    def get_columns(self, relation: Relation) -> list[ColumnMetadata]: ...
    def capabilities(self) -> AdapterCapabilities: ...
```

`get_columns` is required for ADR 0019 all-column expansion and physical
column/type validation.

The API separates connection/metadata/execution from SQL rendering. This avoids
forcing non-SQL adapters to implement SQL helper methods.

SQL renderer:

```python
class SqlRenderer:
    adapter_type: str

    def render_operation(self, operation: TypedOperation) -> RenderedSql: ...
    def quote_identifier(self, identifier: str) -> str: ...
    def render_relation(self, relation: Relation) -> str: ...
```

The renderer may expose helper methods internally, but the public boundary is
typed operation payload to rendered SQL.

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

Capability support should be represented by a support state, not a boolean:

```python
class CapabilitySupport(str, Enum):
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    NOT_IMPLEMENTED = "not_implemented"
    VERSIONED = "versioned"
    FULL = "full"
```

Suggested capability map:

```python
@dataclass(frozen=True)
class AdapterCapabilities:
    support: dict[str, CapabilitySupport]
```

`unknown`, `unsupported`, and `not_implemented` do not satisfy required
capabilities. `versioned` support must be checked against adapter or engine
version before rendering or execution.

## Adapter registry

Adapters should register by connection type.

```python
registry.register("postgres", PostgresAdapter)
registry.register("snowflake", SnowflakeAdapter)
registry.register("duckdb", DuckDbAdapter)
```

Core should resolve connection type through the registry.

The DuckDB adapter starts in `recon-core` as the local development adapter.
External adapter packages should wait until the adapter API and shared adapter
test kit are stable.

## Capability validation

Checks declare required capabilities.

Compile without an adapter may emit typed plans with
`rendering.status: not_rendered`.

Adapter-aware rendering validates adapter API compatibility and required
capabilities before SQL files are written.

Runtime validates anything that depends on live metadata.

Adapter API compatibility should also be validated. If an adapter declares an
older unsupported adapter API version, Recon should fail before execution with a
clear diagnostic.

## SQL generation

Core check logic should define typed abstract operations.

Adapters should provide dialect-specific SQL for the operations emitted by the
compiler. Milestone 6 does not expand the typed operation catalog.

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

Rendered SQL belongs under:

```text
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

Rendering status values are `not_rendered`, `rendered`, `blocked`, and
`failed`.

## Profiles and secrets

Profiles are loaded from `connections/profiles.yml` when adapter-aware
rendering or execution needs connection configuration.

Resolution rules:

- select one profile and one target,
- render only the selected target,
- support `env_var('NAME')` and `env_var('NAME', 'default')` initially,
- fail on missing environment variables in the selected target,
- ignore missing environment variables in unselected targets,
- never emit secrets or fully rendered credentials in generated artifacts or
  diagnostics.

## Query endpoints

Milestone 6 is relation-only for executable adapter-aware behavior. Query
endpoints may parse, but adapter-aware rendering or execution should fail with
a clear unsupported diagnostic until query execution is designed.

## Execution placement

The adapter interface does not by itself decide where comparisons execute.
Milestone 7 check-engine work must define whether comparisons run in source
systems, target systems, adapter-managed intermediate systems, or bounded
Python-side comparison. Unsupported SQL rendering must not silently fall back to
Python.

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

`recon-duckdb` is a future external package candidate after adapter API and
shared adapter test-kit stability.

## Design principle

Core defines what reconciliation needs. Adapters define how each system can do it safely.

Do not hide comparison semantics inside adapter-specific SQL or macro logic.
