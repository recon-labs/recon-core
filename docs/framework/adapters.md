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

Install the current in-core DuckDB local development adapter with:

```bash
pip install "recon-core[duckdb]"
```

In local repository development, use `pip install -e ".[dev,duckdb]"`.

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
    def render_operation(self, operation, *, source_relation, target_relation): ...
    def render_plan(self, operations, *, source_relation, target_relation): ...
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
applicable, and adapter type. When an adapter is known, compiled checks record
that adapter in `rendering.adapter_type`.

Adapters must preserve Core comparison semantics when rendering SQL. The
current DuckDB renderer emits key-diff SQL over distinct non-null key sets and
uses `typeof(...)` guards with null-safe equality for key and grouped aggregate
join predicates so DuckDB comparison combination casting does not create
cross-type matches. It also emits explicit key/group type-check CTEs for
key-diff and grouped aggregate comparisons; physical type mismatches raise a
clear Recon error instead of producing misleading missing/extra rows or raw
DuckDB binder errors. Aggregate and grouped aggregate comparison SQL uses
preflight type-check statements before native aggregate queries to check source
and target metric input column types and aggregate result types before
subtracting values. Valid numeric inputs use native DuckDB `sum(column)` rather
than lossy casts, while unsafe inputs fail before the aggregate query is
evaluated. Boolean aggregate inputs are rejected for current `sum` metric
rendering because DuckDB treats `sum(boolean)` as a true-value count, which is
not a safe numeric aggregate comparison. `UHUGEINT` aggregate inputs are also
rejected until DuckDB exact aggregate behavior for that type is proven, because
current DuckDB returns approximate `DOUBLE` values for `sum(UHUGEINT)`. Grouped
aggregate comparison output keeps source and target group keys separate as
`source_<key>` and `target_<key>` columns instead of coalescing group keys
across sides.

Future adapter execution and the shared adapter test kit must explicitly define
empty aggregate result semantics before aggregate comparison conformance is
claimed. Engines can return `NULL` for `sum` on empty groups instead of zero;
Recon must define whether two empty aggregate results compare equal, how that
differs from comparing numeric zero, and how the distinction appears in run
results and evidence.

Milestone 6 adapter-aware rendering should migrate rendering statuses to:

```text
not_rendered
rendered
blocked
failed
```

`not_rendered` means adapter-aware rendering was not requested. `rendered`
means all required SQL was produced. `blocked` means rendering was skipped
because validation failed. `failed` means rendering was attempted and failed
due to an adapter or renderer error. A missing renderer during adapter-aware
rendering is a `blocked` capability diagnostic, not `not_rendered`.
If a renderer returns no SQL steps for a check, Recon treats that as
`RC_ADAPTER_RENDERED_SQL_EMPTY` and marks the check `failed`; `rendered` must
not be paired with empty `rendering.sql_paths`.
If a renderer returns malformed non-empty output, such as non-`RenderedSql`
steps, empty/non-string SQL metadata fields, unsafe path-like step names, or
duplicate step names, Recon treats that as `RC_ADAPTER_OPERATION_RENDER_FAILED`
and marks the check `failed` before compiled SQL artifacts are written.

If any check in an adapter-aware compile invocation produces a rendering
diagnostic, Recon writes no compiled SQL files for that invocation. Checks with
validation or capability blockers are marked `blocked`, renderer errors are
marked `failed`, and otherwise renderable checks are also marked `blocked`
because their SQL artifacts were intentionally not written. Otherwise renderable
checks blocked only by invocation-wide SQL output suppression include a
`RC_ADAPTER_RENDERING_OUTPUT_SUPPRESSED` diagnostic in the compiled checks
artifact.

Current compiler models emit these four statuses. Earlier draft statuses
`deferred` and `unsupported` are no longer used for SQL rendering metadata.
Known adapter-aware checks also include `rendering.adapter_type`.

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

For Milestone 6 DuckDB SQL rendering, source and target connection names may
differ only when their selected profile entries resolve to the same adapter type
and connection config. Distinct connection contexts are blocked because the
rendered SQL targets one execution context and does not attach or bridge
multiple databases.

Generated artifacts and diagnostics may include profile name, target name,
adapter type, and non-secret relation identifiers. They must not include
secrets or fully rendered credential payloads.

Adapter diagnostics are public output. Adapter authors should not include
credentials, tokens, DSNs, passwords, rendered connection payloads, or other
secret-classified values in diagnostic message, hint, path, or resource fields.
Adapter diagnostics should still include safe actionable messages; redaction
may replace unsafe text, but compatibility should not depend on diagnostic
codes or hints alone. Adapter diagnostics must remain safe even when they use
case-changed config keys, case-changed rendered values, DSN fragments, tokens,
passwords, or other simple transformations of rendered profile config.
Before external adapter packages or a shared adapter test kit are published,
the test kit must include profile-rendering and diagnostic-redaction
conformance cases, including safe non-empty diagnostic messages, for adapter
factories and future dependency, API, capability, metadata, rendering, and
execution diagnostics. This is a cross-repo gate: factory exceptions and
`capabilities()` exceptions must become sanitized structured diagnostics before
any external adapter repo or shared test-kit repo claims compatibility.
Adapter setup failures must also keep compiled SQL absent, mark affected
compiled checks blocked with structured diagnostics, and de-duplicate repeated
source/target setup diagnostics in service or CLI output before those claims are
made.

## Query endpoint boundary

Milestone 6 is relation-only for executable adapter-aware rendering and
execution. `source.query` and `target.query` may remain parseable, but they
must produce a clear unsupported diagnostic if adapter-aware rendering or
execution tries to use them.

Current adapter-aware compile implements this boundary for SQL rendering:
query endpoints produce `blocked` rendering metadata and no SQL files.

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
- check compatibility tests,
- profile-rendering tests,
- diagnostic-redaction tests.

The test kit should include shared tests for typed operation rendering and
capability declarations. Every production adapter should run the shared test kit
in CI after the adapter API stabilizes. The first version of that shared suite
must include profile-rendering and diagnostic-redaction conformance, including
sanitized adapter factory exceptions, sanitized capability declaration
exceptions, sanitized adapter metadata exceptions, empty and malformed
renderer output failures, field-by-field diagnostic redaction, and safe
non-empty diagnostic messages. It must also include adapter setup failure cases
that assert no compiled SQL output, blocked compiled-check metadata, and
de-duplicated repeated source/target service diagnostics.

## Design principle

Recon Core should be adapter-aware but not adapter-bloated. Core defines the framework contract; adapters handle system-specific behavior.

See also:

- `docs/decisions/adr-0012-adapter-and-package-ecosystem.md`
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`
