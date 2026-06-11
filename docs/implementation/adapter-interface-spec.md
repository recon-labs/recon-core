# Adapter Interface Specification

## Purpose

This document defines implementation expectations for the adapter interface.

Adapters isolate database and system-specific behavior from Recon Core.

This specification follows:

- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`
- `docs/decisions/adr-0021-execution-placement-and-comparison-engine-strategy.md`
- `docs/decisions/adr-0022-evidence-privacy-failure-detail-and-result-sinks.md`

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

Adapters do not own reconciliation semantics, execution placement, evidence
meaning, privacy classification, failure-detail bounds, or sink/result
classification. They declare capabilities and perform approved mechanics after
Core validates that a check is allowed to use those mechanics.

## Interface sketch

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
```

`get_columns` is required for ADR 0019 all-column expansion and physical
column/type validation.

The API separates connection/metadata/execution from SQL rendering. This avoids
forcing non-SQL adapters to implement SQL helper methods.

SQL renderer:

```python
class SqlRenderer:
    adapter_type: str

    def render_operation(
        self,
        operation: Mapping[str, Any],
        *,
        source_relation: Relation,
        target_relation: Relation,
    ) -> RenderedSql: ...
    def render_plan(
        self,
        operations: tuple[Mapping[str, Any], ...],
        *,
        source_relation: Relation,
        target_relation: Relation,
    ) -> tuple[RenderedSql, ...]: ...
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
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
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

Future adapter capability families include:

- execution in a resolved adapter context,
- adapter-managed staging or materialization,
- result and evidence sink writes,
- portable hash or adapter-local hash behavior,
- probabilistic key-summary build, merge, serialization, probe, reverse-probe,
  metrics, and cleanup,
- diagnostics and redaction behavior.

The exact capability names for these families are intentionally unstabilized in
this document. They become public adapter contract only when the implementing
milestone updates the adapter API, typed-plan compatibility docs, public
contract inventory, and shared adapter conformance tests together. Malformed,
incompatible, `unknown`, `unsupported`, or `not_implemented` capability states
must remain blockers.

## Adapter registry

Adapters should register by connection type.

```python
registry.register("postgres", PostgresAdapter)
registry.register("snowflake", SnowflakeAdapter)
registry.register("duckdb", DuckDbAdapterFactory())
```

Core should resolve connection type through the registry. Adapter factories
must return either an adapter or a diagnostic; a factory that returns neither
or returns a malformed resolution result fails resolution with
`RC_ADAPTER_RESOLUTION_FAILED`. A factory that raises an exception should also
fail resolution with a generic sanitized `RC_ADAPTER_RESOLUTION_FAILED`
diagnostic rather than surfacing raw adapter error text.
Resolution diagnostics must be structured `Diagnostic` entries. Malformed
diagnostic containers, entries, or field values inside an otherwise valid
resolution wrapper are malformed resolution results and must fail with
`RC_ADAPTER_RESOLUTION_FAILED` before downstream compile, redaction, rendering,
artifact-writing, or execution code consumes them. Resolution diagnostics must
be serialization-safe at the adapter boundary: `code` and `message` must be
non-empty strings, `severity` must be a `DiagnosticSeverity`, optional text
context fields must be strings when present, and `line` and `column` must be
integers when present.
Factory diagnostics are public output. They must not include credentials,
tokens, DSNs, passwords, fully rendered connection payloads, or other
secret-classified values from rendered profile config.

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
older unsupported adapter API version, or does not declare a valid adapter API
version, Recon should fail before execution with a clear diagnostic.

Adapter metadata is public adapter behavior. If `adapter_type` is missing,
empty, non-string, or raises while being read, Recon should fail rendering or
execution setup with `RC_ADAPTER_METADATA_INVALID`, suppress raw adapter error
text, and include only safe context such as the adapter class name and exception
class.

Adapter capability declaration is itself public adapter behavior. If
`capabilities()` raises, Recon should fail rendering or execution setup with
`RC_ADAPTER_CAPABILITY_DECLARATION_FAILED`, suppress the raw exception text, and
include only safe context such as the adapter type, check ID, and exception
class. Malformed capability support states should become structured
required-capability diagnostics instead of uncaught exceptions.

## SQL generation

Core check logic should define typed abstract operations.

Adapters should provide dialect-specific SQL for the operations emitted by the
compiler. The current adapter-aware rendering scope does not expand the typed
operation catalog.
For every check marked `rendered`, the renderer must return at least one SQL
step. Empty renderer output is `RC_ADAPTER_RENDERED_SQL_EMPTY` and must be
recorded as a rendering failure, not as `rendered` with empty `sql_paths`.
Malformed non-empty renderer output is also a rendering failure. Core expects
`render_plan()` to return a tuple of `RenderedSql` steps with non-empty string
`sql` and `operation_type` fields, plus unique safe single-segment `step_name`
values. Invalid output is reported as `RC_ADAPTER_OPERATION_RENDER_FAILED`
before compiled SQL artifact writing.

The exported compiled SQL writer applies the same rendered-step shape invariant
at the artifact boundary. Direct or batched writer requests with no rendered
steps, blank SQL, blank operation metadata, malformed required capability
declarations, unsafe step names, or duplicate step names for a check fail before
Core creates compiled SQL directories or files. Batched publication validates
every request and preflights every output path before the first artifact is
published, so an earlier valid check followed by a later empty or invalid
rendered SQL request must leave no partial compiled SQL output.

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
Adapters must render the typed operation semantics without relying on implicit
dialect coercion. DuckDB rendered predicates for key matching and grouped
aggregate group matching use `typeof(...)` guards with `IS NOT DISTINCT FROM`;
DuckDB key-diff rendering also compares distinct non-null key sets so null-key
and duplicate-key checks remain separate prerequisites. DuckDB key-diff and
grouped aggregate comparison SQL also renders explicit source/target key type
checks that raise clear Recon errors on physical type mismatch. DuckDB
aggregate and grouped aggregate comparison SQL emits preflight type-check
statements before native aggregate queries to check source/target metric input
column types and aggregate result types before subtracting aggregate values.
Valid numeric inputs use native DuckDB `sum(column)` rather than lossy casts.
Boolean aggregate inputs are rejected for current DuckDB `sum` metric rendering
because `sum(boolean)` is a true-value count, not a safe numeric aggregate
comparison. `UHUGEINT` aggregate inputs are rejected until DuckDB exact
aggregate behavior for that type is proven, because current DuckDB returns
approximate `DOUBLE` values for `sum(UHUGEINT)`. Grouped aggregate comparison
results expose source and target group keys separately as `source_<key>` and
`target_<key>` columns instead of coalescing group keys across sides.

Future adapter execution and shared adapter test-kit work must define empty
aggregate result semantics before aggregate comparison conformance is claimed.
For example, engines such as DuckDB return `NULL` for `sum` on empty groups
rather than zero. Recon must lock how two empty aggregate results compare, how
empty aggregate `NULL` differs from numeric zero, and how that behavior appears
in run results and evidence.

Rendered SQL belongs under:

```text
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

Adapter-aware rendering uses `not_rendered`, `rendered`, `blocked`, and
`failed`. Earlier draft statuses `deferred` and `unsupported` are no longer
emitted for SQL rendering metadata.
When an adapter is known, compiled checks also record `rendering.adapter_type`.

Compiled-check `rendering.sql_paths` stores paths relative to the configured
`target-path`, for example:

```text
compiled_sql/customer_revenue/check.ecommerce_recon.customer_revenue.row_count_diff/00-row_count-source.sql
```

## Profiles and secrets

Profiles are loaded from `connections/profiles.yml` when adapter-aware
rendering or execution needs connection configuration.

Resolution rules:

- select one profile and one target,
- treat the selected target as an environment containing named connections,
- resolve contract `source.connection` and `target.connection` values against
  the selected target's `connections` map,
- render only the named connection payloads referenced by selected contracts
  for contract-specific adapter rendering or execution,
- support `env_var('NAME')` and `env_var('NAME', 'default')` initially for
  non-routing connection config fields,
- require connection `type` values to be literal adapter types,
- reject resolved adapters whose `adapter_type` metadata differs from the
  literal profile connection `type` before renderer selection or execution,
- fail on missing environment variables in referenced connection payloads,
- fail on unsupported template syntax, including `{{ ... }}`, `{% ... %}`, and
  `{# ... #}`, in referenced connection payloads or env-var defaults,
- ignore missing environment variables in unselected targets and unreferenced
  connections for contract-specific invocations,
- never emit secrets or fully rendered credentials in generated artifacts or
  diagnostics.

Before shared adapter test-kit or external adapter package compatibility is
claimed, adapter API conformance tests must cover profile rendering and
diagnostic redaction. Those tests should include selected target loading,
referenced-connection filtering, missing env vars, env-var defaults,
unsupported template syntax in values and defaults including `{{ ... }}`,
`{% ... %}`, and `{# ... #}`, adapter factory diagnostics, and future optional
dependency, API compatibility, capability, metadata, rendering, and execution
diagnostics.
Redaction conformance must cover unsafe rendered profile keys or
values independently in diagnostic `code`, `message`, `hint`, `path`,
`resource_type`, `resource_name`, `line`, `column`, and future structured
diagnostic fields. Diagnostic `code` cases must include unsafe config keys and
rendered values in delimiter-separated and separatorless forms, such as
`RC_PASSWORD_LEAK`, `RCPASSWORDLEAK`, `RCsuper-secretLEAK`, and `RC12LEAK`, so
conformance does not only prove value-shaped examples or delimiter-separated
matching. Redaction conformance must also cover parsed DSN component and
derived-fragment cases, including
username, password, host, path, query values, percent-decoded values, and
substrings of rendered connection strings, because adapters and database
clients often surface only one component of a rendered DSN in diagnostics.
It must also cover raw adapter exceptions from factories, adapter metadata
declarations, and capability declarations, plus empty and malformed renderer
output diagnostics. Current Core `render_check_sql()` orchestration validates
adapter API compatibility, renderer `adapter_type` binding, and renderer-step
`required_capabilities` before compiled SQL is published. Any shared helper,
adapter repository, or test-kit harness that accepts both a resolved adapter and
an explicit renderer must validate adapter API compatibility and the renderer's
`adapter_type` against the resolved adapter type before calling
`render_plan()`, including clear failure cases for incompatible adapter APIs and
missing, malformed, exception-raising, or mismatched renderer metadata.
Renderer output `required_capabilities` are also part of the adapter boundary:
future shared renderer orchestration, external adapter repositories, and test
kits must preserve Core's current enforcement and cover unsupported,
not-implemented, unknown, versioned, malformed, or extra step-level capability
declarations before SQL artifacts, run results, evidence, or adapter test
snapshots are published. If a shared adapter
test-kit harness drives core
`render-sql` flows, it must also cover compile-validation blocked metadata:
otherwise renderable checks are marked `blocked` with
`RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS`, no compiled SQL is
written, and adapter factories/renderers are not invoked when compile
validation has already failed.

If the shared adapter test kit, an external adapter repository, or future
adapter execution claims compatibility for runtime output, it must also prove
that raw adapter, database, and runtime exception text is summarized before it
reaches diagnostics, terminal output, logs, run results, evidence, reports,
failure details, or test snapshots. Raw exception text can contain executed
query text, relation names, row values, credentials, rendered connection
details, or engine-specific private payloads and is not safe public output by
default.

For current DuckDB SQL rendering, source and target connection names may
differ only when their selected profile entries resolve to the same adapter type
and connection config. Distinct connection contexts are blocked until explicit
cross-connection rendering or execution placement is designed.

## Query endpoints

Current adapter-aware rendering is relation-backed only. Query endpoints may
parse, but adapter-aware rendering should fail with a clear unsupported
diagnostic until query execution is designed. Adapter execution remains future
work.

## Execution placement

The adapter interface does not by itself decide where comparisons execute.
Execution placement is assigned by executable surface: row-count placement,
grain-key safety placement, and aggregate metric placement are separate
decisions. Each execution phase must define whether its comparisons run in
source systems, target systems, adapter-managed intermediate systems, or bounded
Python-side comparison. Unsupported SQL rendering or execution must not silently
fall back to Python.

The first check-engine boundary may introduce internal dispatch and blocker
metadata, but it must not add adapter execution, public placement syntax,
materialization, generated run-result artifacts, evidence, state, result sinks,
or probabilistic key-diff behavior.

Future placement-aware execution must define movement and materialization
rules before an adapter is allowed to move source or target rows into another
context. Source pushdown, target pushdown, intermediate adapter execution, and
bounded in-core comparison are separate strategies with separate capability,
privacy, result, and evidence requirements.

Production result/evidence sink writes require a sink contract before adapters
can claim support. That contract must cover schema versioning, idempotency,
retention, privacy/redaction, destination capability fit, write diagnostics,
and bounded local result objects that reference large sink output rather than
embedding it.

Probabilistic key-diff strategies, including Bloom-filter-like summaries and
other set sketches, require a separate strategy contract before adapters can
claim support. That contract must cover exact vs probabilistic semantics,
false-positive configuration, partition or window scope, deterministic
composite-key serialization, bidirectional probing when equivalence requires
both missing and extra coverage, intermediate summary storage and cleanup,
privacy classification, and exact confirmation before publishing concrete
failure rows.

## Future adapter conformance gates

External adapter packages should not claim production compatibility until the
shared adapter test kit covers the relevant public boundary. The test kit must
expand with each implemented family:

- execution placement capability validation when execution is implemented,
- staging and materialization conformance when staging is implemented,
- result and evidence sink write conformance when sinks are implemented,
- probabilistic key-summary lifecycle conformance when probabilistic key-diff
  is implemented.

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
shared adapter test-kit stability. Additional production adapter packages should
also wait for the adapter conformance gate.

## Design principle

Core defines what reconciliation needs. Adapters define how each system can do it safely.

Do not hide comparison semantics inside adapter-specific SQL or macro logic.
