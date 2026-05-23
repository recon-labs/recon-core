# Typed Check Plan Compatibility

## Purpose

Typed check plans are the execution contract between Recon Core check planning
and adapter rendering or execution.

Core compiles reconciliation semantics into typed operations. Adapters render or
execute those typed operations for a specific system.

## Current status

Typed check plans are designed but not implemented yet.

Current state:

- ADR 0013 establishes the typed check-plan architecture.
- ADR 0015 establishes the compiled artifact shape that will contain typed
  plans.
- The typed plan model foundation exists in code.
- End-to-end contract compilation is not implemented yet.
- No stable typed check-plan schema has been released.
- No adapter currently consumes typed plans.

## Planned plan shape

Compiled checks should contain a `plan` section like:

```yaml
plan:
  id: plan.<project>.<contract>.<check>
  operations:
    - type: row_count
      side: source
    - type: row_count
      side: target
    - type: compare_counts
  required_capabilities:
    - row_count
```

Typed operation payloads should be modeled explicitly in Python. They must not
be arbitrary dictionaries passed through the compiler.

## Draft operation catalog

The current draft operation names come from ADR 0013 and ADR 0015:

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

This catalog is not stable until the compiler and adapter interface implement
it and tests protect the payload schemas.

`null_key` is the typed operation for side-specific key null checks. It is a
data check over declared comparison identity keys, not a schema nullability
check.

Example:

```yaml
- type: null_key
  side: source
  identity:
    kind: grain
    keys:
      - customer_id
```

`compare_aggregates` compares ungrouped source and target aggregate operation
results. `compare_grouped_aggregates` compares aggregate results segmented by
`group_by` fields.

## Compatibility rules

Once typed plans are implemented, these changes affect compatibility:

| Change | Compatibility impact |
| --- | --- |
| Adding a new operation that adapters can mark unsupported | Usually compatible if capability validation is explicit. |
| Adding a required operation for existing checks | Compatibility-impacting for adapters. |
| Renaming an operation | Breaking typed plan change. |
| Changing operation payload fields or meaning | Compatibility-impacting and often breaking. |
| Changing `required_capabilities` semantics | Compatibility-impacting for adapters and test kits. |
| Changing plan IDs or stable ID rules | Compatibility-impacting for artifacts and automation. |
| Changing rendering status semantics | Compatibility-impacting for artifacts and adapters. |

Core must keep comparison semantics in typed operations and compiled checks.
Adapters must not hide new reconciliation behavior in dialect-specific rendering.

## Required documentation updates

When typed plan behavior changes, update:

- this document,
- `docs/compatibility/capability-catalog.md`,
- `docs/compatibility/adapter-api.md` when adapters are affected,
- `docs/compatibility/artifact-versions.md` when artifact shape changes,
- `docs/implementation/compiled-artifacts.md`,
- relevant ADRs when the behavior is durable.

## Related docs

- `docs/framework/contract-compilation.md`
- `docs/architecture/artifact-model.md`
- `docs/architecture/adapter-interface.md`
- `docs/implementation/compiled-artifacts.md`
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
- `docs/decisions/adr-0015-compiled-artifact-schema-and-versioning.md`
