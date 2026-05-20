# Adapter Interface

## Purpose

Adapters isolate system-specific behavior from Recon Core.

Recon Core defines what needs to happen. Adapters define how it happens for a specific system.

## Adapter responsibilities

Adapters should handle:

- connection,
- query execution,
- SQL dialect,
- identifier quoting,
- relation metadata,
- column metadata,
- type mapping,
- timestamp behavior,
- hash behavior,
- temporary objects,
- capability declarations.

## Core responsibilities

Recon Core owns:

- contract model,
- compiler,
- validation rules,
- check planning,
- result model,
- evidence model,
- base adapter interface.

Core should not import production database drivers for every supported system.

Core also owns typed check plans. A check planner should express comparison
intent as typed operations, and SQL adapters should render those operations into
dialect SQL.

```text
CompiledCheck
  -> typed CheckPlan
  -> adapter SQL renderer or adapter execution request
```

This keeps comparison semantics consistent in core while isolating dialect
behavior in adapters.

## Long-term adapter packages

Expected adapter packages:

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

## Base interface

Illustrative interface:

```python
class Adapter:
    name: str

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def execute(self, query: str) -> QueryResult: ...
    def relation_exists(self, relation: Relation) -> bool: ...
    def get_columns(self, relation: Relation) -> list[ColumnMetadata]: ...
    def quote_identifier(self, identifier: str) -> str: ...
    def compile_limit(self, query: str, limit: int) -> str: ...
    def capabilities(self) -> AdapterCapabilities: ...
```

This is not final API.

The final API should separate base adapter behavior from SQL dialect rendering.

Illustrative split:

```python
class BaseAdapter:
    adapter_type: str
    supported_adapter_api_version: str

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def execute(self, query: str) -> QueryResult: ...
    def get_columns(self, relation: Relation) -> list[ColumnMetadata]: ...
    def capabilities(self) -> AdapterCapabilities: ...

class SqlRenderer:
    def quote_identifier(self, identifier: str) -> str: ...
    def render_limit(self, query: str, limit: int) -> str: ...
    def render_cast(self, expression: str, target_type: LogicalType) -> str: ...
    def render_null_safe_equal(self, left: str, right: str) -> str: ...
    def render_timestamp_diff(self, left: str, right: str, unit: str) -> str: ...
```

The exact method names should be finalized with
`docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`.

## Capabilities

Adapters should declare capabilities.

Examples:

```text
relations
queries
metadata_columns
metadata_precision_scale
temp_tables
cte_support
timestamp_diff
safe_hash_expression
json_path
semi_structured_projection
```

## Metadata

Column metadata should include:

```text
name
logical_type
physical_type
nullable
precision
scale
timezone
```

Some adapters may not know all fields. Missing metadata should be explicit.

## Hashing

Hash behavior is not portable by default.

Adapters should not claim safe hash compatibility unless it is intentionally implemented and tested.

## Semi-structured systems

MongoDB and semi-structured sources may require projection-based comparison rather than raw document comparison.

Adapters should expose canonical projections where possible.

## Adapter registry

Core should use an adapter registry to resolve adapter type to adapter implementation.

```text
postgres -> recon-postgres
snowflake -> recon-snowflake
```

Initial local/dev adapters may live in core until the interface stabilizes.

## Adapter test kit

A future adapter test kit should validate:

- connection behavior,
- metadata behavior,
- typed operation rendering,
- capability declarations,
- check compatibility.

It should also validate typed operation rendering. If core adds or changes a
typed operation, shared adapter tests should fail until every affected adapter
implements the operation or marks the capability unsupported.

## Design principle

Adapters make Recon portable without making Recon Core dependent on every database system.
