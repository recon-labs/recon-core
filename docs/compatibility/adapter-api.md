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
and an empty resolution result must fail with `RC_ADAPTER_RESOLUTION_FAILED`
instead of letting adapter-aware rendering or execution report success. Factory
exceptions and capability declaration exceptions must fail with sanitized
structured diagnostics that preserve the code and useful exception type without
preserving raw exception text. These tests must also assert that adapter
diagnostics carry safe non-empty messages and that core redaction replaces
unsafe message text with a generic actionable message rather than dropping the
message field.

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
Returning neither is an adapter resolution failure and must surface
`RC_ADAPTER_RESOLUTION_FAILED`. Factory exceptions must also resolve to a
generic sanitized `RC_ADAPTER_RESOLUTION_FAILED` diagnostic instead of leaking
raw adapter exception text.

Adapter capability declarations are public compatibility input to Core. If an
adapter raises while declaring capabilities, Core must surface a sanitized
`RC_ADAPTER_CAPABILITY_DECLARATION_FAILED` diagnostic instead of leaking raw
adapter exception text or continuing with ambiguous capability support.

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
- suppress adapter-resolution diagnostic text when it references rendered
  connection config keys or values, while preserving the original diagnostic
  code and severity.

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
- diagnostics that reference rendered connection config keys or values,
- diagnostics that reference rendered connection config keys or values with
  changed casing or other simple transformations.

Adapter diagnostics are public output. External adapters must not place
credentials, tokens, DSNs, passwords, rendered connection payloads, or other
secret-classified values in diagnostic message, hint, path, `resource_type`,
`resource_name`, or future structured diagnostic fields. Core may defensively
suppress unsafe adapter-resolution diagnostic text and unsafe resource
metadata, but
adapter packages and the shared test kit must treat secret-safe diagnostics as
an adapter author requirement. A secret-safe diagnostic must still include an
actionable message; adapter compatibility cannot rely on diagnostic codes or
hints alone. The shared test kit should include case-variant and
transformation-variant redaction cases, such as `PASSWORD`, `database`,
case-changed rendered values, DSN substrings, tokens, and passwords appearing
independently in diagnostic message, hint, path, `resource_type`, and
`resource_name`. It must also include adapter factory and capability
declaration exceptions whose raw exception messages contain rendered profile
keys or values.

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
