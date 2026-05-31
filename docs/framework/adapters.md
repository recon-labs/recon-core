# Adapters

## Purpose

This document defines Recon adapters.

Adapters allow Recon Core to work with different databases, warehouses, document stores, and query engines.

## Definition

An adapter handles connection, SQL dialect, identifier quoting, metadata queries, limit syntax, timestamp syntax, numeric casting, hashing syntax, temporary objects, schema introspection, and capability declaration.

Connectors are user-facing connection config entries. Adapters are the code
packages that implement those connector types.

Example profile target:

```yaml
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
          warehouse:
            type: duckdb
```

In this example, `dev` is the selected target environment. `legacy` and
`warehouse` are named connections that contracts may reference from
`source.connection` and `target.connection`. `duckdb` resolves to an adapter
implementation. Long-term, production implementations should live in packages
such as `recon-postgres` and `recon-snowflake`.

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
The first local development adapter is DuckDB. It lives inside `recon-core`
while the adapter API and shared adapter test kit stabilize.

Long term, adapters should split into packages such as `recon-postgres`, `recon-mysql`, `recon-snowflake`, `recon-sqlserver`, `recon-bigquery`, `recon-mongodb`, `recon-databricks`, `recon-redshift`, and `recon-oracle`.

A future `recon-duckdb` package should not split from `recon-core` until the
adapter API and shared adapter test kit are stable enough for external adapter
packages.

## Interface concepts

The first adapter boundary separates base adapter behavior from SQL rendering:

```python
class BaseAdapter:
    adapter_type: str
    adapter_version: str
    supported_adapter_api_version: str

    def connect(self): ...
    def close(self): ...
    def execute(self, sql: str): ...
    def relation_exists(self, relation: str) -> bool: ...
    def get_columns(self, relation: str) -> list[Column]: ...
    def capabilities(self) -> AdapterCapabilities: ...


class SqlRenderer:
    def render_operation(self, operation): ...
    def render_relation(self, relation: str) -> str: ...
    def quote_identifier(self, name: str) -> str: ...
```

Core owns the typed operation payload. The renderer owns dialect SQL for that
payload.

## Capabilities

Adapters should declare capabilities such as relation support, query support, temp tables, metadata columns, hash expression, timestamp diff, precision/scale metadata, and JSON path support.

Capabilities allow Recon to fail early when a check cannot run.

Capabilities should be granular and conservative. Capability support uses these
states:

```text
unknown
unsupported
not_implemented
versioned
full
```

`unknown`, `unsupported`, and `not_implemented` do not satisfy required
capabilities. `versioned` support must be validated against adapter or engine
version before rendering or execution.

Examples include:

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

Policy-dependent value checks may later require additional granular
capabilities such as limited regex replacement. Add those capabilities only
with matching typed-plan payloads, adapter docs, and tests.

Adapters should also declare the adapter API version they support.

## Capability validation

If an adapter cannot run a requested check, Recon should fail during
compile/validation when possible.

If metadata is unavailable, the compiled plan should mark validation as deferred.

Compile without an adapter can still produce typed plans with
`rendering.status: not_rendered`. Adapter-aware rendering must validate adapter
API compatibility and required capabilities before writing compiled SQL.

## Compiled SQL rendering

Adapters render typed check-plan operations into SQL. Recon Core orchestrates
the render and writes generated SQL under:

```text
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

Compiled checks should reference rendered SQL files without embedding secrets or
fully rendered connection payloads. Rendered SQL must remain traceable to the
contract, check ID, typed operation or rendering step, source/target side when
applicable, and adapter type.

Milestone 6 adapter-aware rendering should migrate rendering statuses to:

```text
not_rendered
rendered
blocked
failed
```

`not_rendered` means adapter-aware rendering was not requested or no renderer
was available. `rendered` means all required SQL was produced. `blocked` means
rendering was skipped because validation failed. `failed` means rendering was
attempted and failed due to an adapter or renderer error.

Current pre-Milestone-6 compiler models may still expose earlier draft statuses
until the implementation migration updates code, tests, artifact examples, and
compatibility docs together.

## Profiles and secrets

Connection profiles live in `connections/profiles.yml` and should not be
committed. Profile resolution selects one profile and one target environment,
then resolves contract connection names against that target's `connections`
map. Contract-specific adapter rendering or execution renders only the named
connection payloads referenced by the selected contracts and supports
`env_var('NAME')` plus `env_var('NAME', 'default')` initially.

Missing environment variables in referenced connection payloads are errors.
Missing environment variables in unselected targets or unreferenced connections
do not fail contract-specific invocations.

Generated artifacts and diagnostics may include profile name, target name,
adapter type, and non-secret relation identifiers. They must not include
secrets or fully rendered credential payloads.

## Query endpoint boundary

Milestone 6 is relation-only for executable adapter-aware rendering and
execution. `source.query` and `target.query` may remain parseable, but they
must produce a clear unsupported diagnostic if adapter-aware rendering or
execution tries to use them.

Executable query endpoints require a later decision covering SELECT-only rules,
single-statement handling, wrapping, artifact visibility, and adapter
capabilities.

## Execution placement boundary

Milestone 6 renders SQL but does not execute checks. Before the check engine
executes typed plans, Recon must define where comparison work may run: source
system, target system, adapter-managed intermediate system, or bounded
Python-side comparison.

Unsupported SQL behavior must not silently fall back to Python. Any Python or
intermediate-system fallback requires explicit limits, privacy rules,
diagnostics, result semantics, and evidence visibility.

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
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`
