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

Before creating, publishing, or splitting a shared adapter test-kit repository,
the test-kit design must define a SQL comparison conformance matrix. That matrix
must make adapter comparison semantics executable across repositories and cover
null-safe equality, distinct non-null key diff, nullable grouped aggregate keys,
no implicit type coercion, representative cross-type value cases, and clear
unsupported-capability behavior when an adapter cannot safely perform a
comparison.

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
- ignore missing environment variables in unselected targets and unreferenced
  connections for contract-specific invocations,
- never emit secrets or fully rendered credential payloads in generated
  artifacts, diagnostics, terminal output, or evidence.

Changes to profile selection, target precedence, environment rendering, or
secret redaction affect adapter compatibility.

## Compiled SQL compatibility

Adapter-rendered SQL is generated under:

```text
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

Compiled checks may reference those SQL files. SQL references must preserve
traceability to contract, check ID, rendering step or typed operation, side when
applicable, and adapter type.

Rendered SQL content must preserve Core typed operation semantics. The current
DuckDB renderer treats key-diff inputs as distinct non-null key sets and guards
key/group comparison predicates with `typeof(...)` before null-safe equality so
DuckDB comparison combination casting cannot make unlike physical types match.

Compiled-check `rendering.sql_paths` stores paths relative to the configured
`target-path`, for example:

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
