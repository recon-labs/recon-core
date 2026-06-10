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
- ADR 0021 establishes the future execution-placement and adapter-capability
  strategy.
- ADR 0022 establishes the future evidence, failure-detail, and result-sink
  strategy.
- The typed plan model foundation exists in code.
- Built-in `recon_core.basic_equivalence` expansion helpers produce draft typed
  plans at library level.
- Explicit metric compilation helpers produce draft aggregate typed plans at
  library level.
- `recon compile` writes compiled checks artifacts containing draft typed
  plans.
- ADR 0020 locks Milestone 6 as SQL rendering for currently emitted operations
  only.
- `recon compile --render-sql` renders currently emitted typed operations to
  DuckDB SQL for relation-backed contracts.
- No stable typed check-plan schema has been released.
- No adapter executes typed plans yet.
- No public typed-plan placement, materialization, sink, or probabilistic
  key-summary schema has been released.

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

Future execution-aware plans may need metadata concepts for operation execution
location, comparison location, materialization or staging policy, required
adapter capabilities, placement blockers, sink or artifact references, and
exact/probabilistic result classification. Those concepts are not stable
serialized fields today. Their exact schema belongs to the implementation
milestone that first emits them and must be updated with adapter API docs,
artifact compatibility docs, and conformance tests in the same change.

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

Milestone 6 must not expand the emitted operation catalog. SQL renderers should
render only operations already produced by current check-pack and metric
compilation. Placeholder operations such as `null_safe_equal`, `cast`, `limit`,
`hash`, `timestamp_diff`, and `schema_metadata` remain non-emittable until
payload schemas, capability mappings, renderer tests, and compatibility docs
are updated together.

Column selectors must be resolved before typed plans are emitted. Per ADR 0019,
raw wildcard selectors such as `columns: "*"` must not appear in typed
operation payloads; value operations should use concrete column names only.

Tolerance, null, and normalization policies must also be resolved before typed
plans are emitted. Per ADR 0009, typed operation payloads must use structured
policy fields and must not carry raw YAML strings such as `5 seconds` or
`trim_lower`. Regex normalization must use typed step payloads with explicit
pattern and replacement fields, not adapter-specific SQL fragments.

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
| Changing where typed plan comparisons execute | Compatibility-impacting for adapters, results, evidence, and privacy. |
| Adding or changing placement, materialization, or sink metadata | Compatibility-impacting for adapters, artifacts, results, evidence, and privacy. |
| Adding probabilistic key-summary operations or result classification | Compatibility-impacting for adapters, artifacts, evidence, privacy, and test kits. |

Core must keep comparison semantics in typed operations and compiled checks.
Adapters must not hide new reconciliation behavior in dialect-specific rendering.

## Rendering and execution placement

Milestone 6 renders typed operations to SQL through adapters but does not
execute checks.

Execution is split after Milestone 6. Milestone 7.2 owns row-count typed-plan
execution, Milestone 7.3 owns grain-key safety typed-plan execution, and
Milestone 7.4 owns current aggregate metric typed-plan execution. Each execution
sub-milestone must resolve comparison placement for its assigned operations
before implementation and must not silently fall back to Python, adapter dialect
casts, inferred mappings, or unsupported comparison behavior.

Rendered SQL belongs under:

```text
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

Compiled-check `rendering.sql_paths` references those files relative to the
configured `target-path`, for example:

```text
compiled_sql/customer_revenue/check.ecommerce_recon.customer_revenue.row_count_diff/00-row_count-source.sql
```

When an adapter has been resolved, compiled-check rendering metadata also
records `rendering.adapter_type` so rendered, blocked, or failed SQL rendering
state remains traceable to the adapter dialect.

Before typed plans execute, Recon must define comparison placement for each
operation: source system, target system, adapter-managed intermediate system,
or bounded Python-side comparison. Unsupported SQL behavior must not silently
fall back to Python.

Placement is a Core decision, not an adapter decision. Adapters declare
capabilities for mechanics such as rendering, execution, metadata reads,
staging, sink writes, and future probabilistic summaries. Core validates that
the required placement and capabilities satisfy the check semantics before any
execution starts. `unknown`, `unsupported`, `not_implemented`, malformed, or
incompatible capability states are blockers.

Execution-aware typed plans must not encode a hidden fallback path. If source
pushdown, target pushdown, an intermediate adapter context, or bounded in-core
comparison is required but unavailable, the plan or execution result must carry
a clear blocker instead of moving data implicitly.

Future probabilistic key-diff operations, including Bloom-filter-like summaries
and other set sketches, must distinguish exact and probabilistic semantics.
Plans and results must not present possible presence, approximate coverage, or
unconfirmed candidate rows as exact source-target equivalence. Such operations
require gate-backed payload schemas, false-positive configuration, partition or
window scope, deterministic composite-key serialization, bidirectional probing
when both missing and extra coverage are needed, intermediate summary
references, cleanup semantics, privacy classification, and adapter conformance
tests before emission.

Future sink-backed result or evidence references must also be explicit. Typed
plans and execution results should reference bounded local artifacts or
configured sink destinations for large details rather than embedding unbounded
failure rows in Core result objects.

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
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`
