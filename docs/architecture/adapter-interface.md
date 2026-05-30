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
recon-duckdb
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

DuckDB starts as the first local development adapter inside `recon-core`.
External adapter packages, including a future `recon-duckdb`, should split only
after the adapter API and shared adapter test kit are stable.

## Base interface

The Milestone 6 API boundary separates base adapter behavior from SQL dialect
rendering:

```python
class BaseAdapter:
    adapter_type: str
    adapter_version: str
    supported_adapter_api_version: str

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def execute(self, query: str) -> QueryResult: ...
    def relation_exists(self, relation: Relation) -> bool: ...
    def get_columns(self, relation: Relation) -> list[ColumnMetadata]: ...
    def capabilities(self) -> AdapterCapabilities: ...


class SqlRenderer:
    adapter_type: str

    def render_operation(self, operation: TypedOperation) -> RenderedSql: ...
    def render_relation(self, relation: Relation) -> str: ...
    def quote_identifier(self, identifier: str) -> str: ...
```

Core owns the typed operation payload and required capabilities. `SqlRenderer`
owns dialect SQL for those payloads. Production implementations may refine
method names, but they must preserve this ownership boundary.

## Capabilities

Adapters should declare capabilities using support states:

```text
unknown
unsupported
not_implemented
versioned
full
```

`unknown`, `unsupported`, and `not_implemented` do not satisfy required
capabilities. `versioned` support must be checked against adapter, engine, or
database version.

Examples:

```text
relations
queries
metadata_columns
metadata_precision_scale
temp_tables
cte_support
row_count
aggregate
grouped_aggregate
key_diff
null_key
duplicate_key
timestamp_diff
safe_hash_expression
json_path
semi_structured_projection
```

Additional policy-dependent capabilities, such as limited regex replacement,
should be added only with typed-plan payloads, adapter tests, and compatibility
docs.

Compile without an adapter may produce typed plans with
`rendering.status: not_rendered`. Adapter-aware rendering must validate adapter
API compatibility and required capabilities before writing SQL.

## Profiles and secrets

Profile files live in `connections/profiles.yml` and are not committed.
Profiles select one target. Recon renders only the selected target's connection
payload and initially supports `env_var('NAME')` plus
`env_var('NAME', 'default')`.

Generated artifacts may identify the profile name, target name, adapter type,
and non-secret relation identifiers. They must not contain secrets or fully
rendered credential payloads.

## Compiled SQL artifacts

Adapter-rendered SQL is generated under:

```text
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

Compiled checks reference rendered SQL artifacts. SQL output must remain
traceable to contract, check ID, rendering step or typed operation, side when
applicable, and adapter type.

Rendering status values are `not_rendered`, `rendered`, `blocked`, and
`failed`.

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

DuckDB is the first local development adapter. It should prove profile loading,
adapter registration, capability validation, SQL rendering, and the first
adapter test-kit shape without declaring a production adapter package.

## Query endpoint boundary

Milestone 6 is relation-only for executable adapter-aware behavior. Query
endpoints can remain parseable, but adapter-aware rendering or execution must
return a clear unsupported diagnostic for `source.query` or `target.query`.

Executable query endpoints require a later design for SELECT-only validation,
single-statement handling, wrapping, artifact visibility, and adapter
capabilities.

## Execution placement

The adapter interface enables rendering and execution, but comparison execution
placement is a check-engine decision. Before check execution, Recon must define
whether each comparison runs in the source system, target system,
adapter-managed intermediate system, or bounded Python-side comparison.

Unsupported SQL behavior must not silently fall back to Python.

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

See also:

- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`
