# Adapters

## Purpose

This document defines Recon adapters.

Adapters allow Recon Core to work with different databases, warehouses, document stores, and query engines.

## Definition

An adapter handles connection, SQL dialect, identifier quoting, optional metadata
queries, limit syntax, timestamp syntax, numeric casting, hashing syntax,
temporary objects, schema introspection, and capability declaration.

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

Adapters own connection implementation, SQL compilation details, optional
metadata access, dialect-specific functions, capability reporting, and
adapter-specific tests.

Core owns comparison meaning. Adapters own system-specific execution.

Recommended boundary:

```text
CompiledCheck -> typed CheckPlan -> adapter renders or executes dialect-specific operations
```

Core check planners should produce typed abstract operations such as row count,
aggregate, key diff, duplicate key, null-safe equality, casts, limits, hashes,
timestamp diff, and schema metadata requests. SQL adapters render those
operations into dialect SQL.

Future execution placement, materialization, result sinks, and probabilistic
key-summary strategies follow the same ownership boundary:

- Core owns reconciliation semantics, placement selection, comparison safety,
  result classification, privacy policy, artifact references, and evidence
  meaning.
- Adapters declare granular capabilities and perform system-specific mechanics
  such as rendering, execution, metadata reads, staging, writes, and summary
  operations.
- Adapter capability declarations do not create new comparison semantics.
  `unknown`, `unsupported`, `not_implemented`, malformed, or incompatible
  capability states must never satisfy required behavior.
- The first check-engine boundary may reserve internal planning metadata for
  those future boundaries, but it must not add public YAML placement syntax,
  check execution, generated run results, evidence, sinks, state, or
  probabilistic key-diff behavior.

Recon should not use macro dispatch as the primary comparison engine. Typed
plans are preferred because Recon must produce inspectable compiled checks,
generated SQL, diagnostics, and evidence.

## Initial strategy

Early `recon-core` may include minimal internal adapters to prove the engine.
The first local development adapter is DuckDB. It lives inside `recon-core`
while the adapter API and shared adapter test kit stabilize.

Long term, adapters should split into packages such as `recon-postgres`, `recon-mysql`, `recon-snowflake`, `recon-sqlserver`, `recon-bigquery`, `recon-mongodb`, `recon-databricks`, `recon-redshift`, and `recon-oracle`.

A future `recon-duckdb` package should not split from `recon-core` until the
adapter API and shared adapter test kit are stable enough for external adapter
packages.

The in-core DuckDB adapter is the early proof adapter. External adapter package
splits and additional production adapters should wait until adapter conformance
and shared test-kit gates exist. Production table/result sinks additionally
depend on the result-sink design gates and write/sink conformance. Bloom
filters, sketches, and other probabilistic key-summary strategies additionally
depend on the probabilistic key-diff gate and adapter test-kit conformance for
summary build, serialization, transport or storage, probing, reverse-direction
probing when needed, metrics, and cleanup.

Install the current in-core DuckDB local development adapter with:

```bash
pip install "recon-core[duckdb]"
```

In local repository development, use `pip install -e ".[dev,duckdb]"`.

## Interface concepts

The adapter boundary separates minimum adapter behavior, optional relation
metadata access, and SQL rendering:

```python
class BaseAdapter:
    adapter_type: str
    adapter_version: str
    supported_adapter_api_version: str

    def connect(self): ...
    def close(self): ...
    def execute(self, sql: str): ...
    def capabilities(self) -> AdapterCapabilities: ...


class RelationMetadataAdapter(BaseAdapter):
    def relation_exists(self, relation: str) -> bool: ...
    def get_columns(self, relation: str) -> list[Column]: ...


class SqlRenderer:
    def render_operation(self, operation, *, source_relation, target_relation): ...
    def render_plan(self, operations, *, source_relation, target_relation): ...
    def render_relation(self, relation: str) -> str: ...
    def quote_identifier(self, name: str) -> str: ...
```

Core owns the typed operation payload. The renderer owns dialect SQL for that
payload. Relation metadata is optional and nominal: future metadata callers
should require `RelationMetadataAdapter` plus the relevant metadata capability
before reading metadata. Inherited pre-alpha metadata method shims on
`BaseAdapter` are not a support signal.

## Capabilities

Adapters should declare capabilities such as relation support, query support,
temp tables, metadata columns, hash expression, timestamp diff, precision/scale
metadata, and JSON path support.

Capability families should remain granular enough to distinguish:

- metadata and relation introspection,
- typed operation rendering,
- execution in an adapter context,
- adapter-managed staging or materialization,
- result and evidence sink writes,
- portable or adapter-local hashing,
- probabilistic key-summary build, merge, serialization, probe, and cleanup,
- diagnostics and redaction behavior.

Exact capability names for future execution, staging, sinks, and probabilistic
summaries are not stable until their implementing phases update the adapter API,
typed-plan compatibility docs, and shared adapter conformance tests.

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

If metadata is unavailable, the compiled plan should mark validation as
deferred. `metadata_columns` support means column metadata can satisfy a
metadata request only when the adapter also implements the relation metadata
interface; capability support alone must not authorize metadata calls.

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

Successful rendered checks must produce at least one SQL step and at least one
compiled SQL path. Empty renderer output and exported compiled SQL writer
requests with no rendered steps fail before Core creates compiled SQL
directories or files. Malformed non-empty rendered SQL steps, such as blank SQL,
blank operation types, malformed required capability declarations, or unsafe
step names, are also publication failures. Batched publication validates the
full rendered SQL output set before publishing anything, so a later empty or
malformed rendered SQL request cannot leave partial SQL artifacts from an
earlier request.

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

Adapter-aware rendering should use these rendering statuses:

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
`CompiledSqlWriter` revalidates the same rendered-step shape before filesystem
publication and preflights exact output paths before creating files, so direct
writer calls and future test-kit harnesses cannot bypass the renderer guard or
publish misleading SQL artifacts through symlinks, directories, non-file output
targets, or partial batches.

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
connection payloads referenced by the selected contracts and supports both
`{{ env_var('NAME') }}` and bare `env_var('NAME')` forms, with optional
defaults, for non-routing connection config fields. Bare `env_var(...)` is only
valid as the whole rendered scalar aside from whitespace; unsupported bare
env-var expressions, embedded env-var calls, filters, Jinja statement/comment
fragments such as `{% ... %}` and `{# ... #}`, and unsupported template
fragments in referenced non-routing fields or env-var defaults fail profile
loading instead of passing through as literal config. Connection `type` values
must be literal adapter types and must not contain template fragments. Resolved
adapter `adapter_type` metadata must match the literal profile `type` before
Core selects a renderer or executes adapter-backed behavior.

Missing environment variables in referenced connection payloads are errors.
Missing environment variables in unselected targets or unreferenced connections
do not fail contract-specific invocations.

For current DuckDB SQL rendering, source and target connection names may differ
only when their selected profile entries resolve to the same adapter type and
connection config. Distinct connection contexts are blocked because the rendered
SQL targets one execution context and does not attach or bridge multiple
databases.

Generated artifacts and diagnostics may include profile name, target name,
adapter type, and non-secret relation identifiers. They must not include
secrets or fully rendered credential payloads.

Adapter diagnostics are public output. Adapter authors should not include
credentials, tokens, DSNs, passwords, rendered connection payloads, or other
secret-classified values in diagnostic code, message, hint, path, resource
fields, `line`, `column`, or future structured diagnostic fields.
Adapter diagnostics should still include safe actionable messages; redaction
may replace unsafe codes or text, but compatibility should not depend on
diagnostic codes or hints alone. Adapter diagnostics must remain safe even when they use
case-changed config keys, case-changed rendered values, DSN fragments, tokens,
passwords, numeric `line`/`column` values, or other simple transformations of
rendered profile config. Short numeric profile values must remain safe when an
adapter exposes an equivalent formatted representation, such as a profile
`port: 12` appearing publicly as `12.0`, `+12`, or `1.2e1`.
DSN redaction conformance must include parsed components and derived fragments,
not only the whole rendered DSN string: username, password, host, path, query
values, percent-decoded values, and substrings must not leak through public
diagnostics, artifacts, logs, run results, evidence, or adapter test snapshots.
Diagnostic codes must also remain safe when unsafe config keys or rendered
values are embedded in delimiter-separated or separatorless forms, such as
`RC_PASSWORD_LEAK`, `RCPASSWORDLEAK`, `RCsuper-secretLEAK`, or `RC12LEAK`.
Before external adapter packages or a shared adapter test kit are published,
the test kit must include profile-rendering and diagnostic-redaction
conformance cases, including safe non-empty diagnostic messages, for adapter
factories and future dependency, API, capability, metadata, rendering, and
execution diagnostics. Profile-rendering cases must cover both
`{{ env_var(...) }}` and bare `env_var(...)` forms, defaults, missing
environment variables, unsupported bare expressions, unsupported Jinja
statement/comment fragments such as `{% ... %}` and `{# ... #}`, and the
requirement that invalid env-var or template syntax fails before adapter
resolution rather than surviving as literal connection config. This is a
cross-repo gate: factory exceptions and
`capabilities()` exceptions must become sanitized structured diagnostics before
any external adapter repo or shared test-kit repo claims compatibility.
Malformed factory diagnostic payloads are adapter-boundary failures, not
adapter-authored diagnostics; they must become `RC_ADAPTER_RESOLUTION_FAILED`
before profile-backed redaction, rendering, execution, or artifact-writing code
consumes them. This includes invalid `Diagnostic` field values, not only
malformed containers or non-`Diagnostic` entries: resolution diagnostics must
carry a non-empty string `code`, `DiagnosticSeverity` severity, non-empty string
`message`, optional string context fields, and optional integer `line` and
`column` fields.
Adapter setup failures must also keep compiled SQL absent, mark affected
compiled checks blocked with structured diagnostics, treat factory results that
include both adapters and diagnostics as setup failures, de-duplicate repeated
same-connection setup diagnostics in service or CLI output, and preserve
distinct source/target connection setup diagnostics in service, CLI, and
blocked compiled-check artifact output before those claims are made. Setup
diagnostics must not hide unrelated render diagnostics from other affected
contracts in the same adapter-aware compile invocation.
If a shared adapter test-kit harness drives `recon compile --render-sql`, it
must also include the core compile-validation case where adapter rendering is
requested but not started: otherwise renderable checks are marked `blocked` with
`RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS`, no compiled SQL is
written, and adapter factories/renderers are not invoked.
Current Core `render_check_sql()` and `recon compile --render-sql` validate
adapter API compatibility, renderer `adapter_type` binding, and renderer output
`required_capabilities` before compiled SQL publication. Renderer output
`required_capabilities` are enforceable requirements, not comments; future
adapter repositories, shared renderer helpers, and shared test kits must
preserve this behavior and cover unsupported, not-implemented, unknown,
versioned, malformed, or extra step-level capability requirements before SQL,
run results, evidence, or adapter test snapshots are published.

## Query endpoint boundary

Current adapter-aware rendering, row-count execution, and bounded local/dev
grain-key safety execution are relation-backed only. `source.query` and
`target.query` may remain parseable, but they must produce a clear unsupported
diagnostic if adapter-aware rendering or current execution tries to use them.
Executable query endpoints remain future work. Current bounded local/dev
grain-key safety execution also excludes views and externally backed relations;
the compiled relation endpoints must resolve to local DuckDB base tables.

Current adapter-aware compile implements this boundary for SQL rendering:
query endpoints produce `blocked` rendering metadata and no SQL files. Current
run execution also blocks query endpoints before adapter query execution.

Executable query endpoints require a later decision covering SELECT-only rules,
single-statement handling, wrapping, artifact visibility, and adapter
capabilities.

## Execution placement boundary

Current adapter-aware compile produces SQL, and current run execution is limited
to relation-backed same-context DuckDB `row_count_diff` checks plus grain-key
safety checks that pass the internal bounded local/dev scan guard. That guard
requires project-local DuckDB base tables, not views or externally backed
relations. Before the check engine executes any additional typed-plan surface,
Recon must define where comparison work may run: source system, target system,
adapter-managed intermediate system, or bounded Python-side comparison.

Unsupported SQL behavior must not silently fall back to Python. Any Python or
intermediate-system fallback requires explicit limits, privacy rules,
diagnostics, result semantics, and evidence visibility.

Execution placement is not an adapter choice. Adapters expose what they can do;
Core decides whether a check is allowed to use source pushdown, target pushdown,
an intermediate adapter context, or bounded in-core comparison. If the required
placement or capability is unavailable, Recon must return a clear blocker
instead of moving data implicitly or producing misleading evidence.

Future placement-aware execution must also decide where intermediate data may
be materialized, where large result or evidence rows may be written, and which
references can appear in run results or evidence. Large failure details should
be represented by bounded samples and sink references, not by embedding
unbounded rows in Core result objects.

Probabilistic key-diff strategies such as Bloom filters or set sketches are
future execution strategies, not general adapter shortcuts. They require
explicit false-positive semantics, partition or window scope, deterministic
composite-key serialization, bidirectional probing when equivalence requires
both missing and extra coverage, exact-confirmation rules before publishing
failure rows, privacy classification for serialized summaries, and adapter
capabilities for every lifecycle phase.

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
validation. Relation metadata access belongs to `RelationMetadataAdapter`, not
the minimum `BaseAdapter` lifecycle/execution boundary.

## Semi-structured adapters

Document and semi-structured systems are important later.

They require document projection, nested fields, arrays, document identifier
handling, schema drift, and CDC operation metadata.

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
must include profile-rendering, renderer-output/artifact-publication, and
diagnostic-redaction conformance, including sanitized adapter factory
exceptions, sanitized capability declaration exceptions, sanitized adapter
metadata exceptions, empty and malformed renderer output failures, empty or
malformed direct and later-batch compiled SQL writer requests that leave no
partial SQL artifacts, field-by-field diagnostic redaction, and safe non-empty
diagnostic messages. It must also include profile `type`/adapter
metadata mismatch rejection before renderer selection, plus malformed factory
diagnostic payload cases for invalid `Diagnostic` field values, including
string severities, empty or non-string `code` or `message`, non-string
optional context fields, and non-integer `line` or `column` values. Adapter
setup failure cases must assert no compiled SQL output, blocked compiled-check
metadata, and de-duplicated repeated same-connection service diagnostics while
preserving distinct source/target connection diagnostics in service and
blocked compiled-check artifact output. Field-by-field diagnostic redaction
includes diagnostic code, `line` and `column`, short numeric rendered scalars,
equivalent formatted variants such as `12.0`, `+12`, and `1.2e1`, unsafe
resource metadata, `rendering.adapter_type`, and separatorless diagnostic-code
embeddings for unsafe config keys and rendered values, such as
`RC_PASSWORD_LEAK`, `RCPASSWORDLEAK`, `RCsuper-secretLEAK`, and `RC12LEAK`.
Compile-flow harnesses must cover
`RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS` when compile validation
prevents a requested adapter rendering phase from starting.

## Design principle

Recon Core should be adapter-aware but not adapter-bloated. Core defines the framework contract; adapters handle system-specific behavior.

See also:

- `docs/decisions/adr-0012-adapter-and-package-ecosystem.md`
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`
