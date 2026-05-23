# Contract Compiler and Validation

## Purpose

The contract compiler turns authored contracts into explicit compiled contracts and compiled checks.

The validator rejects unsafe, ambiguous, incompatible, or underspecified behavior before execution whenever possible.

See
`docs/decisions/adr-0015-compiled-artifact-schema-and-versioning.md`
for the compiled artifact schema, versioning, stable ID, and compiler coding
pattern decision.

## Compiler inputs

Primary inputs:

- parsed project,
- manifest,
- parsed contracts,
- check packs,
- sample policies,
- tolerance policies,
- schema policies,
- endpoint resources,
- project defaults,
- package resources,
- adapter registry and capabilities when available.

## Compiler outputs

Primary outputs:

```text
target/compiled_contracts/*.yml
target/compiled_checks/*.yml
target/compiled_sql/**/*.sql
```

`target/compiled_sql/` is written when adapter SQL rendering is available. When
SQL rendering is not available, compiled checks still include typed plans and
`rendering.status: not_rendered`.

Internal outputs:

```text
CompiledProject
CompiledContract
CompiledCheck
CheckPlan
```

## Compiler phases

Recommended compile phases:

```text
1. load parsed resources
2. resolve project and file defaults
3. resolve endpoint refs
4. normalize contracts
5. resolve columns and metrics
6. expand check packs
7. compile metrics into checks
8. resolve sampling for each check
9. resolve tolerances and null rules
10. resolve schema policies
11. resolve CDC policies
12. validate check requirements
13. validate adapter capabilities
14. produce typed check plans
15. render adapter SQL where possible
16. write compiled artifacts
```

The compiler should not make database-specific SQL strings the primary internal
representation. It should create typed compiled checks and typed check plans.
Adapters render those plans into dialect-specific SQL when SQL output is needed.

## Columns, metrics, and checks

Compiler rules:

```text
columns = eligible comparison fields and rules
metrics = named aggregate comparisons that compile into checks
checks = explicit execution intent
check packs = reusable execution intent that expands into checks
```

Columns do not create checks.

Metrics do create checks.

Check packs create checks through expansion.

## No silent all-column comparison

If one or more columns are defined, only those columns are eligible for value and aggregate inference.

If no columns are defined, value checks requiring columns should fail unless the check explicitly defines columns.

All-column comparison must be explicit:

```yaml
columns:
  include: "*"
```

or:

```yaml
checks:
  - type: row_diff
    columns: "*"
```

When `*` is used, the compiler should resolve and write the actual column list into compiled artifacts when metadata is available.

## Check-pack expansion

Check packs must expand into explicit compiled checks.

Example authored contract:

```yaml
checks:
  use:
    - recon_core.basic_equivalence
```

Compiled output should show checks such as:

```yaml
compiled_checks:
  - name: row_count_diff
    type: row_count_diff
  - name: missing_keys
    type: missing_keys
```

`recon_core.basic_equivalence` expands exactly to:

```text
row_count_diff
missing_keys
extra_keys
null_source_keys
null_target_keys
duplicate_source_keys
duplicate_target_keys
```

The pack requires `grain.keys`. It must not silently weaken to only
`row_count_diff` when grain is missing.

The expanded checks should lower to typed operations as follows:

| Check | Typed operation | Required capability |
| --- | --- | --- |
| `row_count_diff` | `row_count` on both sides, then `compare_counts` | `row_count` |
| `missing_keys` | `key_diff` with `source_minus_target` | `key_diff` |
| `extra_keys` | `key_diff` with `target_minus_source` | `key_diff` |
| `null_source_keys` | `null_key` with `side: source` | `null_key` |
| `null_target_keys` | `null_key` with `side: target` | `null_key` |
| `duplicate_source_keys` | `duplicate_key` with `side: source` | `duplicate_key` |
| `duplicate_target_keys` | `duplicate_key` with `side: target` | `duplicate_key` |

`null_key` checks actual data values in declared identity keys. It is not a
schema nullability check.

## Empty expansion

If a check pack requires inputs and expands to no checks, default behavior is error.

Example:

```yaml
checks:
  use:
    - recon_core.some_future_pack
```

Diagnostic:

```text
recon_core.some_future_pack expanded to no checks.
```

Optional future config may support `on_empty: warn` or `on_empty: skip`, but the default remains error.

## Metric compilation

Each explicit metric compiles into one aggregate comparison check. Metrics do
not require `grain.keys`; `metrics.group_by` is aggregate segmentation, not row
identity.

Example:

```yaml
metrics:
  - name: total_revenue
    type: sum
    column: revenue
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01
```

Compiled ungrouped metric check:

```yaml
- name: total_revenue
  type: sum_diff
  origin:
    kind: metric
    name: total_revenue
  identity:
    kind: none
    keys: []
  metric:
    type: sum
    column: revenue
    group_by: []
  plan:
    operations:
      - type: aggregate
        side: source
        aggregate: sum
        column: revenue
      - type: aggregate
        side: target
        aggregate: sum
        column: revenue
      - type: compare_aggregates
    required_capabilities:
      - aggregate
```

Compiled grouped metric check:

```yaml
- name: revenue_by_month
  type: grouped_aggregate_diff
  origin:
    kind: metric
    name: revenue_by_month
  identity:
    kind: none
    keys: []
  metric:
    type: sum
    column: revenue
    group_by:
      - month
  tolerance: 0.01
  plan:
    operations:
      - type: grouped_aggregate
        side: source
        aggregate: sum
        column: revenue
        group_by:
          - month
      - type: grouped_aggregate
        side: target
        aggregate: sum
        column: revenue
        group_by:
          - month
      - type: compare_grouped_aggregates
    required_capabilities:
      - grouped_aggregate
```

The first compiler implementation supports explicit `sum` metrics. Metric
names must be unique within a contract; duplicate names fail validation with
`RC_VALIDATE_DUPLICATE_METRIC_NAME`.

Metric column types must be compatible with metric type.

Explicit metrics are the first aggregate compilation path. The compiler must
not infer aggregate checks from eligible numeric columns unless a future
decision explicitly enables that behavior and defines the artifact visibility.

## Sampling resolution

Sampling precedence:

```text
check-level
check-pack-level
contract-level
project-level
framework default
```

Every compiled check should have resolved sampling.

Examples:

```yaml
sampling: full
```

```yaml
sampling:
  policy: latest_changed_records
```

Sampling does not remove non-null or uniqueness requirements for row-level checks.

## Tolerance and null resolution

Tolerance precedence:

```text
check-level
column-level
contract-level policy
project-level policy
framework default
```

Null and normalization rules follow the same precedence.

Compiled checks should show resolved tolerance and null behavior.

Default null behavior:

```text
NULL != ''
```

## Schema policy resolution

Schema policies should resolve:

- ignored source columns,
- ignored target columns,
- ignored patterns,
- type compatibility mode,
- precision/scale compatibility mode,
- nullable compatibility mode.

Schema ignore behavior must be visible in compiled artifacts.

## CDC policy resolution

CDC checks must have enough configuration to understand CDC mode.

Examples:

```yaml
cdc:
  mode: upsert
  timestamp_column: updated_at
```

```yaml
cdc:
  keys:
    same_as: grain
```

```yaml
cdc:
  keys:
    - source_order_id
```

```yaml
cdc:
  delete_mode: soft_delete
  source_deleted_column: is_deleted
  target_deleted_column: is_deleted
```

Missing required CDC config should fail validation.

CDC checks that validate key coverage, update propagation, delete propagation,
or changed-row value comparison must resolve CDC identity. `cdc.keys` are
separate from `grain.keys`. The compiler must not silently copy `grain.keys`
into CDC checks unless the contract explicitly says `same_as: grain`.

The current compiler should resolve one default comparison identity and one
default CDC identity per contract. Multiple named grains, multiple named CDC
identities, and per-check or per-pack identity role binding require a future
decision before implementation.

## Grain and uniqueness validation

Row-level checks require `grain.keys`.

Row-level value checks require non-null and unique source and target keys after filters, sampling, or windows are applied.

The compiler can validate the presence of keys. The runner may need to validate actual uniqueness using duplicate-key checks.

Compiled plans should place null-key and duplicate-key checks before row-level value checks.

If row-level value checks require these safety checks and the user did not
author them explicitly, the compiler should generate them with origin
`framework_required_safety_check`.

`missing_keys` and `extra_keys` may compile as distinct non-null key coverage
checks even when null-key or duplicate-key safety checks also exist. Null and
duplicate failures still block row-level value checks.

`recon_core.basic_equivalence` requires `grain.keys`. It should fail validation
when grain is missing rather than silently compiling only `row_count_diff`.

## Adapter capability validation

Each check declares required adapter capabilities.

Compile should fail if required capabilities are known to be missing.

If capabilities are unknown until runtime, compiled artifacts should mark validation as deferred.

Capability validation should include typed operation requirements. For example,
a check plan that requires null-safe equality, timestamp diff, temporary tables,
or portable hashing must declare those requirements before adapter SQL is
rendered.

Adapter API version compatibility should be checked before execution. If an
adapter does not support the required adapter API version, Recon should return a
clear diagnostic rather than attempting a partial run.

## Typed check plans

Compiled checks should be lowered into typed check plans before execution.

Example operation families:

```text
row_count
aggregate
grouped_aggregate
key_diff
duplicate_key
null_safe_equal
cast
limit
hash
timestamp_diff
schema_metadata
```

The typed plan is owned by `recon-core`. SQL dialect rendering is owned by
adapters.

Generated SQL should be traceable back to the typed operations that produced it.
This keeps compiled artifacts debuggable and prevents adapter code from
silently changing comparison semantics.

## Diagnostics

Validation should produce structured diagnostics with stable codes.

Examples:

```text
RC_COMPILE_UNKNOWN_CHECK_PACK
RC_COMPILE_EMPTY_CHECK_PACK
RC_VALIDATE_ROW_CHECK_REQUIRES_KEYS
RC_VALIDATE_CHECK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_CHECK_REQUIRES_CDC_KEYS
RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_CDC_DELETE_MODE_REQUIRED
RC_VALIDATE_CDC_ORDERING_REQUIRED
RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE
RC_VALIDATE_MISSING_SAMPLE_POLICY
RC_VALIDATE_UNSUPPORTED_ADAPTER_CAPABILITY
```

## Compiled artifact requirements

Compiled artifacts should show:

- original resource name,
- source file path,
- source and target,
- identity kind and declared keys,
- resolved defaults,
- generated checks,
- check origins,
- check requirements,
- prerequisites and blocking policy,
- sampling,
- tolerances,
- null rules,
- schema rules,
- CDC rules,
- evidence behavior,
- diagnostics.

Compiled artifacts should use the top-level artifact header:

```text
artifact_type
artifact_version
recon_version
generated_at
invocation_id
```

Stable IDs should use these forms:

```text
contract.<project>.<contract>
check.<project>.<contract>.<check>
plan.<project>.<contract>.<check>
```

## Implementation pattern

The compiler should follow the existing parser and manifest style:

- frozen slotted dataclasses for compiler and artifact models,
- `StrEnum` for statuses, kinds, operation types, and artifact types,
- `TypedDict` for serialized public shapes,
- explicit `to_dict()` serialization,
- thin CLI modules,
- services that orchestrate rather than build ad hoc artifacts,
- dedicated artifact writer classes.

Recommended module shape:

```text
src/recon_core/compiler/models.py
src/recon_core/compiler/ids.py
src/recon_core/compiler/check_packs.py
src/recon_core/compiler/metrics.py
src/recon_core/compiler/plans.py
src/recon_core/compiler/compile.py
src/recon_core/artifacts/compiled_contract_writer.py
src/recon_core/artifacts/compiled_check_writer.py
```

Tests should cover model serialization, stable ID helpers, check-pack
expansion, explicit metric compilation, typed plan generation, artifact
writers, compile service behavior, and CLI behavior. Golden tests should be
reserved for final artifact snapshots.

## Design principle

The compiler is the safety layer between clean authored YAML and executable reconciliation checks.
