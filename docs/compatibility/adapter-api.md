# Adapter API Compatibility

## Purpose

This document records how Recon Core will manage compatibility for adapter
interfaces as the adapter ecosystem grows.

Adapters let Recon run the same core reconciliation semantics against different
systems. Core owns comparison meaning. Adapters own system-specific connection,
metadata, rendering, execution, and capability behavior.

## Current status

The adapter API is not stable yet.

Current state:

- no production adapter packages have been split from `recon-core`,
- no external adapter API version has been released,
- no shared adapter test kit exists yet,
- ADR 0020 locks the first adapter/profile/rendering boundary for Milestone 6,
- `ADAPTER_API_VERSION = "1"` exists in code as a pre-alpha adapter boundary,
- the in-core DuckDB local development adapter renders current typed check
  plans to SQL,
- adapter execution and metadata fetching are not implemented yet.

Adapter repositories such as `recon-postgres` and `recon-snowflake` should split
only after typed check plans, adapter API versioning, and shared adapter tests
are stable enough to support independent releases.

DuckDB is the first local development adapter and may live inside `recon-core`
while the adapter API stabilizes. A future `recon-duckdb` package should wait
for the adapter package split and shared adapter test-kit milestone.

Current DuckDB SQL rendering treats source/target key and grouped-aggregate
group physical type equality as part of safe comparison behavior. Mismatched
key/group types must fail with a clear Recon error rather than relying on
DuckDB comparison combination casting, returning misleading key-diff rows, or
surfacing raw dialect binder errors. Grouped aggregate comparison output uses
separate `source_<key>` and `target_<key>` group key columns instead of a
coalesced group key. DuckDB aggregate comparisons also treat aggregate result
type equality and metric input column type equality as part of safe comparison
behavior before subtracting source and target aggregate values. Current DuckDB
aggregate comparison SQL uses preflight type-check statements before native
aggregate queries so valid numeric inputs are not forced through lossy casts.
Boolean aggregate inputs are rejected for current DuckDB `sum` metric rendering
because DuckDB treats `sum(boolean)` as a true-value count, not a safe numeric
aggregate comparison. `UHUGEINT` aggregate inputs are rejected until DuckDB
exact aggregate behavior for that type is proven, because current DuckDB returns
approximate `DOUBLE` values for `sum(UHUGEINT)`.

Before creating, publishing, or splitting a shared adapter test-kit repository,
the test-kit design must define a SQL comparison conformance matrix. That matrix
must make adapter comparison semantics executable across repositories and cover
null-safe equality, distinct non-null key diff, nullable grouped aggregate keys,
no implicit type coercion, representative cross-type value cases, and clear
unsupported-capability behavior when an adapter cannot safely perform a
comparison. The matrix must also include the concrete type-safety cases exposed
by the in-core DuckDB renderer: key-diff type mismatches fail instead of
returning missing/extra rows, grouped aggregate key type mismatches fail with a
Recon-level error instead of a raw dialect binder error, empty source/target
relations with mismatched key types still fail, and grouped aggregate rendering
does not rely on cross-type group-key coalescing. It must also cover aggregate
value and input column type mismatches, including boolean aggregate inputs and
same-type unsupported or non-numeric aggregate metric inputs, so cross-type or
non-numeric metric comparisons cannot pass through dialect implicit casts,
aggregate-specific boolean semantics, raw dialect binder errors, or lossy casts
that round valid exact numeric aggregate values. For engines with unsigned
large-integer types, the matrix must prove exact aggregate behavior or require
the adapter to reject those inputs. The matrix must also lock empty aggregate
result semantics before execution tests or adapter packages rely on aggregate
comparison output: engines such as DuckDB return `NULL` for `sum` on empty
groups rather than zero, so the test kit must define whether two empty aggregate
results compare equal, how empty aggregate `NULL` differs from numeric zero,
and how that distinction is surfaced in run results and evidence.

The same test-kit design must define adapter API conformance tests separate
from the SQL comparison matrix. At minimum, those tests must cover adapter
factory resolution: a registered factory must return an adapter or diagnostics,
and an empty or malformed resolution result must fail with
`RC_ADAPTER_RESOLUTION_FAILED` instead of letting adapter-aware rendering or
execution report success. Malformed diagnostic payloads inside a resolution
result are malformed resolution results and must fail with
`RC_ADAPTER_RESOLUTION_FAILED` before any compile-service diagnostic redaction,
rendering, artifact-writing, or execution code consumes them. This includes
field-level malformed diagnostics, not only malformed containers or non-
`Diagnostic` entries: adapter-provided resolution diagnostics must have a
non-empty string `code`, a `DiagnosticSeverity` `severity`, a non-empty string
`message`, optional string `resource_type`, `resource_name`, `path`, and `hint`
fields, and optional integer `line` and `column` fields. Representative
test-kit cases must include a string severity such as `"error"`, empty or
non-string `code` or `message`, non-string resource metadata, and non-integer
`line` or `column` values. If a factory returns both an adapter and diagnostics,
the diagnostics are setup failures and the adapter must not be used for
rendering or execution. Missing or invalid adapter API version
declarations must fail with `RC_ADAPTER_API_VERSION_UNSUPPORTED`, and missing,
non-string, empty, or exception-raising `adapter_type` metadata must fail with
`RC_ADAPTER_METADATA_INVALID` before rendering or execution. Malformed
capability support states must become structured required-capability diagnostics
instead of uncaught exceptions. Factory exceptions, adapter metadata exceptions,
and capability declaration exceptions must fail with sanitized structured
diagnostics that preserve the code and useful exception type without preserving
raw exception text. These tests must also assert that adapter diagnostics carry
safe non-empty messages and that core redaction replaces unsafe message text
with a generic actionable message rather than dropping the message field.

Adapter setup failures during adapter-aware compile must also produce blocked
compiled-check metadata without writing compiled SQL. If both source and target
adapter resolution fail for the same connection, service and CLI diagnostics
must de-duplicate the repeated setup diagnostic while compiled artifacts still
explain why each affected check is blocked. Setup diagnostics for distinct
referenced connections must remain visible in service, CLI, and blocked
compiled-check artifact output even when they share the same diagnostic code,
adapter type, or hint.

Compile validation failures that prevent adapter rendering from starting are a
core artifact conformance case. When `recon compile --render-sql` is requested
and validation diagnostics already make the compile fail, otherwise renderable
checks must be marked `blocked` with
`RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS`; they must not remain
`not_rendered`, because that would imply SQL rendering was not requested. Any
future adapter test-kit harness that drives core `render-sql` flows must include
this as an integration case and assert that adapter factories and renderers are
not invoked after compile validation has already failed.

Renderer conformance tests must prove that a renderer returns at least one SQL
step for each rendered check. Empty renderer output must fail with
`RC_ADAPTER_RENDERED_SQL_EMPTY`; it must not produce `rendering.status:
rendered` with empty `rendering.sql_paths`. Malformed non-empty renderer
output, including non-`RenderedSql` steps, empty/non-string rendered SQL
metadata fields, unsafe path-like step names, or duplicate step names, must
fail with `RC_ADAPTER_OPERATION_RENDER_FAILED` before compiled SQL artifacts
are written.

These requirements are a release gate for the adapter ecosystem. Do not create,
publish, or split `recon-adapter-testkit`, `recon-duckdb`, or any production
adapter repository with a compatibility claim until the shared conformance
suite includes those sanitized factory-exception, capability-declaration, and
diagnostic-redaction cases, plus malformed adapter metadata and empty renderer
output cases, malformed non-empty renderer output cases, blocked compiled-check
metadata for adapter setup failures, preserved diagnostics when factories
return both an adapter and diagnostics, de-duplicated repeated same-connection
setup diagnostics, distinct source/target connection setup diagnostics,
numeric `line` and `column` diagnostic redaction cases, short numeric rendered
scalar redaction cases in text fields, resource metadata, and
`rendering.adapter_type`, including alternate public representations of the same
scalar such as `12`, `12.0`, `+12`, and integer-equivalent scientific notation,
and core render-sql compile-validation
blocked-metadata integration cases where the test kit drives core compile
flows. If the test kit or external adapter package claims execution
compatibility, it must also include source/target data privacy conformance for
runtime diagnostics, raw adapter/database/runtime exception text, rendered or
executed query text, run results, evidence, failure details, reports, logs, and
test snapshots before compatibility is claimed. Raw low-level exception text is
not a safe adapter diagnostic message unless it has been classified and
sanitized under the source/target data privacy policy.

## Compatibility contract

Every adapter declares at least:

```text
adapter_type
adapter_version
supported_adapter_api_version
capabilities
```

Core validates adapter API compatibility before adapter-aware SQL rendering and
must validate it again before future execution. An adapter that does not
support the required adapter API version fails with a clear diagnostic instead
of running with ambiguous behavior.

Adapter factories must return either an adapter or one or more diagnostics.
Returning neither, or returning a malformed resolution object, is an adapter
resolution failure and must surface `RC_ADAPTER_RESOLUTION_FAILED`. Factory
resolution diagnostics must be a tuple of structured diagnostics; malformed
diagnostic containers, entries, or field values are malformed resolution
results and must surface `RC_ADAPTER_RESOLUTION_FAILED`. Structured resolution
diagnostics must be safe to serialize before profile-backed redaction,
rendering, artifact writing, or execution sees them: `code` and `message` must
be non-empty strings, `severity` must be a `DiagnosticSeverity`, optional
text context fields must be strings when present, and `line` and `column` must
be integers when present. Factory exceptions must also resolve to a generic sanitized
`RC_ADAPTER_RESOLUTION_FAILED` diagnostic instead of leaking raw adapter
exception text.

Adapter capability declarations are public compatibility input to Core. If an
adapter raises while declaring capabilities, Core must surface a sanitized
`RC_ADAPTER_CAPABILITY_DECLARATION_FAILED` diagnostic instead of leaking raw
adapter exception text or continuing with ambiguous capability support.
Malformed capability support states must produce structured diagnostics instead
of uncaught exceptions.

Adapter metadata declarations are public compatibility input to Core. If
`adapter_type` is missing, empty, non-string, or raises while being read, Core
must surface `RC_ADAPTER_METADATA_INVALID` without leaking raw adapter exception
text or rendered profile values.

The first adapter boundary separates:

```text
BaseAdapter
SqlRenderer
```

`BaseAdapter` owns connection lifecycle, metadata, execution, adapter metadata,
and capability declarations. `SqlRenderer` owns dialect rendering for Core
typed operations.

## Core-owned behavior

Recon Core owns:

- contract parsing and validation,
- check-pack expansion,
- metric compilation,
- typed check-plan models,
- check requirements and prerequisites,
- capability requirements,
- result and evidence models,
- base adapter interfaces.
- comparison execution-placement policy.

Adapters must not redefine reconciliation semantics.

## Adapter-owned behavior

Adapters own:

- connection lifecycle,
- query execution,
- relation and query metadata,
- identifier quoting,
- dialect SQL rendering,
- type mapping,
- timestamp behavior,
- hash behavior,
- temporary object behavior,
- capability declarations,
- adapter-specific tests.

Adapters must not silently choose a different comparison strategy from the one
Core planned. Unsupported rendering or execution placement must produce a clear
diagnostic until the relevant strategy is designed.

## Profiles and secrets

Connection profiles are part of the adapter-facing compatibility surface.

Initial rules:

- load profiles from `connections/profiles.yml`,
- select one profile and one target,
- treat the selected target as an environment containing named connections,
- resolve contract `source.connection` and `target.connection` values against
  the selected target's `connections` map,
- for contract-specific adapter rendering or execution, render only the named
  connection payloads referenced by the selected contracts,
- support `env_var('NAME')` and `env_var('NAME', 'default')`,
- fail on missing environment variables in referenced connection payloads,
- fail on unsupported `{{ ... }}` template syntax in referenced connection
  payloads,
- ignore missing environment variables in unselected targets and unreferenced
  connections for contract-specific invocations,
- never emit secrets or fully rendered credential payloads in generated
  artifacts, diagnostics, terminal output, or evidence,
- suppress profile-backed adapter diagnostic text, including adapter factory,
  adapter API compatibility, and render-phase adapter diagnostics, when it
  references rendered connection config keys or values, while preserving the
  original diagnostic code and severity.

For current DuckDB SQL rendering, source and target connection names may differ
only when the referenced profile entries resolve to the same adapter type and
connection config. Distinct adapter connection contexts are blocked until
cross-connection rendering or execution placement is explicitly designed.

Changes to profile selection, target precedence, environment rendering, or
secret redaction affect adapter compatibility.

## Profile and diagnostic conformance

Profile rendering and adapter diagnostic redaction are compatibility surfaces
for future adapter execution, connection debug or profile validation commands,
shared adapter test-kit work, and external adapter repositories.

This is a hard gate for those surfaces. Before any future adapter execution
milestone, profile/debug command, shared adapter test-kit repository, or
external adapter package claims compatibility, its tests must prove that
adapter factory exceptions, `capabilities()` exceptions, and adapter-supplied
diagnostics cannot leak rendered profile keys or values into CLI output,
compiled artifacts, run results, evidence, or test snapshots.

Before those surfaces are implemented or claimed compatible, shared conformance
tests must cover:

- selected profile and target loading,
- referenced-connection rendering without rendering unreferenced connections,
- missing environment variables in referenced connection payloads,
- environment-variable defaults,
- unsupported `{{ ... }}` template syntax,
- adapter factory diagnostics returned after profile rendering,
- optional dependency, API compatibility, capability, metadata, rendering, and
  execution diagnostics once those phases exist,
- adapter setup failures that write no compiled SQL and mark affected compiled
  checks blocked with structured diagnostics,
- repeated source/target adapter setup failures for the same connection that are
  de-duplicated in service and CLI diagnostics,
- distinct referenced-connection setup failures that remain visible in service
  and CLI diagnostics and blocked compiled-check artifacts,
- diagnostics that reference rendered connection config keys or values,
- diagnostics that reference rendered connection config keys or values with
  changed casing or other simple transformations,
- numeric diagnostic fields such as `line` and `column` when they match rendered
  scalar profile values, including integer-valued fields, numeric strings, and
  short numeric scalars such as port values,
- short numeric rendered scalar values, such as `port: 12`, when they appear in
  diagnostic text, unsafe resource metadata, or `rendering.adapter_type`, not
  only when they appear in numeric diagnostic fields. These cases must include
  alternate integer-equivalent representations such as `12.0`, `+12`, and
  `1.2e1`, because adapters and database clients may format the same rendered
  scalar differently. They must also include rendered numeric-string profile
  values, such as quoted YAML or env-var-derived `"12.0"`, when an adapter emits
  the equivalent value as `12`, `+12`, or `1.2e1`.

Adapter diagnostics are public output. External adapters must not place
credentials, tokens, DSNs, passwords, rendered connection payloads, or other
secret-classified values in diagnostic message, hint, path, `resource_type`,
`resource_name`, `line`, `column`, or future structured diagnostic fields. Core
may defensively suppress unsafe profile-backed adapter diagnostic text and unsafe
resource metadata, including factory, adapter API compatibility, and render-phase
diagnostics plus `rendering.adapter_type` metadata, but
adapter packages and the shared test kit must treat secret-safe diagnostics as
an adapter author requirement. A secret-safe diagnostic must still include an
actionable message; adapter compatibility cannot rely on diagnostic codes or
hints alone. The shared test kit should include case-variant and
transformation-variant redaction cases, such as `PASSWORD`, `database`,
case-changed rendered values, DSN substrings, tokens, and passwords appearing
independently in diagnostic message, hint, path, `resource_type`,
`resource_name`, `line`, `column`, and `rendering.adapter_type`. Short numeric
rendered scalar cases must include text fields, resource metadata,
`rendering.adapter_type`, and numeric fields such as `line` and `column`; they
must also include equivalent formatted variants such as `12.0`, `+12`, and
`1.2e1`, including the reverse case where the rendered profile value is a
numeric string such as `"12.0"` and the adapter emits an integer-equivalent
variant such as `12`. Long password-shaped numeric values alone are not
sufficient. It must
also include adapter factory and capability declaration exceptions and
exception-raising adapter metadata whose raw exception messages contain rendered
profile keys or values.

A future structured redaction API or secret-classification model would be a
durable adapter contract change. If Recon needs that model, update the adapter
ADR and compatibility docs before implementing adapter execution, debug
commands, or external adapter compatibility claims that depend on it.

## Compiled SQL compatibility

Adapter-rendered SQL is generated under:

```text
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

Compiled checks may reference those SQL files. SQL references must preserve
traceability to contract, check ID, rendering step or typed operation, side when
applicable, and adapter type. When an adapter is known, compiled checks record
that adapter in `rendering.adapter_type`.

Rendered SQL content must preserve Core typed operation semantics. The current
DuckDB renderer treats key-diff inputs as distinct non-null key sets and guards
key/group comparison predicates with `typeof(...)` before null-safe equality so
DuckDB comparison combination casting cannot make unlike physical types match.
It also guards aggregate metric input column types and aggregate result types
with preflight statements before native aggregate queries, preserves native
numeric `sum(column)` behavior for valid inputs, and rejects boolean aggregate
inputs and `UHUGEINT` aggregate inputs for current `sum` metric rendering.

Compiled-check `rendering.sql_paths` stores paths relative to the configured
`target-path`, and `rendering.adapter_type` stores the adapter type when known,
for example:

```text
compiled_sql/customer_revenue/check.ecommerce_recon.customer_revenue.row_count_diff/00-row_count-source.sql
```

Changing compiled SQL paths, rendering status meanings, or SQL reference shape
is compatibility-impacting.

## Compatibility change rules

The following changes affect adapter API compatibility:

| Change | Compatibility impact |
| --- | --- |
| Adding an optional adapter method with a default core fallback | Usually compatible. |
| Adding a required adapter method | Adapter API version change. |
| Renaming or removing an adapter method | Breaking adapter API change. |
| Changing a method payload, return model, or error semantics | Adapter API version change. |
| Adding a typed operation adapters may explicitly mark unsupported | Usually compatible if capability validation is clear. |
| Requiring all adapters to support a new typed operation | Adapter API version change. |
| Changing capability meaning | Compatibility-impacting and may be breaking. |
| Changing adapter registry behavior | Compatibility-impacting. |
| Changing profile selection, env-var rendering, or secret redaction rules | Compatibility-impacting. |
| Changing compiled SQL path or rendering status semantics | Compatibility-impacting for artifacts and adapters. |
| Moving an in-core adapter into an external package | Compatibility-impacting and requires migration guidance. |

Before 1.0, breaking changes may still happen, but they must be documented and
reflected in the compatibility matrix.

After adapter packages exist, a breaking adapter API change should include:

- an ADR or ADR update when the decision is durable,
- updates to `docs/compatibility/`,
- adapter test-kit updates,
- adapter package migration guidance,
- changelog entries in affected repositories.

## Related docs

- `docs/framework/adapters.md`
- `docs/architecture/adapter-interface.md`
- `docs/implementation/adapter-interface-spec.md`
- `docs/decisions/adr-0012-adapter-and-package-ecosystem.md`
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`
