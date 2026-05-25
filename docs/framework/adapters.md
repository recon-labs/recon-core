# Adapters

## Purpose

This document defines Recon adapters.

Adapters allow Recon Core to work with different databases, warehouses, document stores, and query engines.

## Definition

An adapter handles connection, SQL dialect, identifier quoting, metadata queries, limit syntax, timestamp syntax, numeric casting, hashing syntax, temporary objects, schema introspection, and capability declaration.

Connectors are user-facing connection config entries. Adapters are the code
packages that implement those connector types.

Example:

```yaml
connections:
  legacy:
    type: postgres
  warehouse:
    type: snowflake
```

In this example, `postgres` and `snowflake` resolve to adapter
implementations. Long-term those implementations should live in packages such
as `recon-postgres` and `recon-snowflake`.

## Core vs adapter responsibilities

`recon-core` owns CLI, project loading, contract parsing, check planning, result model, evidence generation, base adapter interface, extension mechanism, and framework-level validation rules.

Adapters own connection implementation, SQL compilation details, metadata access, dialect-specific functions, capability reporting, and adapter-specific tests.

Core owns comparison meaning. Adapters own system-specific execution.

Recommended boundary:

```text
CompiledCheck -> typed CheckPlan -> adapter renders or executes dialect-specific operations
```

Core check planners should produce typed abstract operations such as row count,
aggregate, key diff, duplicate key, null-safe equality, casts, limits, hashes,
timestamp diff, and schema metadata requests. SQL adapters render those
operations into dialect SQL.

This follows the adapter-boundary maturity of dbt, but Recon should not use
dbt-style macro dispatch as the primary comparison engine. Typed plans are
preferred because Recon must produce inspectable compiled checks, generated SQL,
diagnostics, and evidence.

## Initial strategy

Early `recon-core` may include minimal internal adapters to prove the engine.

Long term, adapters should split into packages such as `recon-postgres`, `recon-mysql`, `recon-snowflake`, `recon-sqlserver`, `recon-bigquery`, `recon-mongodb`, `recon-databricks`, `recon-redshift`, and `recon-oracle`.

## Interface concepts

Illustrative interface:

```python
class Adapter:
    def connect(self): ...
    def execute_query(self, sql: str): ...
    def quote_identifier(self, name: str) -> str: ...
    def relation_exists(self, relation: str) -> bool: ...
    def get_columns(self, relation: str) -> list[Column]: ...
    def compile_limit(self, sql: str, limit: int) -> str: ...
    def compile_hash(self, columns: list[str]) -> str: ...
    def capabilities(self) -> AdapterCapabilities: ...
```

This is not final API.

## Capabilities

Adapters should declare capabilities such as relation support, query support, temp tables, metadata columns, hash expression, timestamp diff, precision/scale metadata, and JSON path support.

Capabilities allow Recon to fail early when a check cannot run.

Capabilities should be granular and conservative. Examples include:

```text
relations
queries
metadata_columns
metadata_precision_scale
temp_tables
cte_support
null_safe_equality
timestamp_diff
numeric_cast
string_cast
safe_hash_expression
portable_hash_compatible
json_path
semi_structured_projection
```

Adapters should also declare the adapter API version they support.

## Capability validation

If an adapter cannot run a requested check, Recon should fail during compile/validation when possible.

If metadata is unavailable, the compiled plan should mark validation as deferred.

## Hashing warning

Hash functions differ across databases.

Recon should not assume `hash()` in one system equals `hash()` in another.

Safe approaches include persisted sample keys, sampling from source and applying keys to target, numeric modulo when valid, or adapter-declared portable hashing.

Adapter capability differences may also affect which side can efficiently
produce sample keys. Recon should not choose a source or target sampling anchor
silently. If adapter-optimized sampling is supported later, compiled artifacts
and evidence must show the resolved anchor side and key-set reference.

## Type and schema metadata

Adapters should expose normalized metadata where possible: column name, logical
type, physical type, nullable, precision, scale, and timezone behavior when
known.

This supports schema checks, ADR 0019 all-column expansion, and column/type
validation.

## Semi-structured adapters

MongoDB and similar systems are important later.

They require document projection, nested fields, arrays, ObjectId handling, schema drift, and CDC operation metadata.

Recon should compare canonical projections, not raw documents blindly.

## Adapter test kit

Future repo:

```text
recon-adapter-testkit
```

Purpose:

- adapter compliance tests,
- SQL compilation tests,
- metadata tests,
- capability validation,
- check compatibility tests.

The test kit should include shared tests for typed operation rendering and
capability declarations. Every production adapter should run the shared test kit
in CI after the adapter API stabilizes.

## Design principle

Recon Core should be adapter-aware but not adapter-bloated. Core defines the framework contract; adapters handle system-specific behavior.

See also:

- `docs/decisions/adr-0012-adapter-and-package-ecosystem.md`
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
