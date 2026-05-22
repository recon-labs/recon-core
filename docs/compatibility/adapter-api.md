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
- the interface in framework and architecture docs is illustrative,
- typed check plans are designed but not implemented yet.

Adapter repositories such as `recon-postgres` and `recon-snowflake` should split
only after typed check plans, adapter API versioning, and shared adapter tests
are stable enough to support independent releases.

## Compatibility contract

Once implemented, every adapter should declare at least:

```text
adapter_type
adapter_version
supported_adapter_api_version
capabilities
```

Core should validate adapter API compatibility before execution. An adapter that
does not support the required adapter API version should fail with a clear
diagnostic instead of running with ambiguous behavior.

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
