# Typed Check Plan Compatibility

## Purpose

Typed check plans are the execution contract between Recon Core check planning
and adapter rendering or execution.

Core compiles reconciliation semantics into typed operations. Adapters render or
execute those typed operations for a specific system.

## Current status

Typed check plans are designed and the current compiler writes draft typed
plans into compiled checks artifacts.

Current state:

- ADR 0013 establishes the typed check-plan architecture.
- ADR 0015 establishes the compiled artifact shape that will contain typed
  plans.
- The typed plan model foundation exists in code.
- Built-in `recon_core.basic_equivalence` expansion helpers produce draft typed
  plans at library level.
- Explicit metric compilation helpers produce draft aggregate typed plans at
  library level.
- `recon compile` writes compiled checks artifacts containing draft typed
  plans.
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

Implemented typed operation models must reject payload fields that are not valid
for their operation type. For example, comparison operations such as
`compare_counts` must not serialize side-specific fields, and side-specific
operations such as `row_count` must not serialize aggregate or column fields.

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

The current model validates payload schemas for the operations emitted by the
compiler. Planned operation names must not be emitted until their payload schema,
capability expectations, docs, and tests exist.

Column selectors must be resolved before typed plans are emitted. Per ADR 0019,
raw wildcard selectors such as `columns: "*"` must not appear in typed
operation payloads; value operations should use concrete column names only.

Tolerance, null, and normalization policies must also be resolved before typed
plans are emitted. Per ADR 0009, typed operation payloads must use structured
policy fields and must not carry raw YAML strings such as `5 seconds` or
`trim_lower`.

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
