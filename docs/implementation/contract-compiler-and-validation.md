# Contract Compiler and Validation

## Purpose

The contract compiler turns authored contracts into explicit compiled contracts and compiled checks.

The validator rejects unsafe, ambiguous, incompatible, or underspecified behavior before execution whenever possible.

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

Internal outputs:

```text
CompiledProject
CompiledContract
CompiledCheck
ExecutionPlan draft
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
14. write compiled artifacts
```

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

## Empty expansion

If a check pack requires inputs and expands to no checks, default behavior is error.

Example:

```yaml
columns:
  exact:
    - status

checks:
  use:
    - recon_core.aggregate_equivalence
```

Diagnostic:

```text
aggregate_equivalence requires numeric columns or explicit metrics.
```

Optional future config may support `on_empty: warn` or `on_empty: skip`, but the default remains error.

## Metric compilation

Each metric compiles into one or more aggregate checks.

Example:

```yaml
metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01
```

Compiled check:

```yaml
- name: revenue_by_month
  type: grouped_aggregate_diff
  metric: sum
  column: revenue
  group_by:
    - month
  tolerance: 0.01
```

Metric names must be unique within a contract.

Metric column types must be compatible with metric type.

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

Sampling does not remove uniqueness requirements for row-level checks.

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
  delete_mode: soft_delete
  source_deleted_column: is_deleted
  target_deleted_column: is_deleted
```

Missing required CDC config should fail validation.

## Grain and uniqueness validation

Row-level checks require `grain.keys`.

Row-level value checks require unique source and target keys after filters, sampling, or windows are applied.

The compiler can validate the presence of keys. The runner may need to validate actual uniqueness using duplicate-key checks.

Compiled plans should place duplicate-key checks before row-level value checks.

## Adapter capability validation

Each check declares required adapter capabilities.

Compile should fail if required capabilities are known to be missing.

If capabilities are unknown until runtime, compiled artifacts should mark validation as deferred.

## Diagnostics

Validation should produce structured diagnostics with stable codes.

Examples:

```text
RC_COMPILE_UNKNOWN_CHECK_PACK
RC_COMPILE_EMPTY_CHECK_PACK
RC_VALIDATE_ROW_CHECK_REQUIRES_KEYS
RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE
RC_VALIDATE_MISSING_SAMPLE_POLICY
RC_VALIDATE_UNSUPPORTED_ADAPTER_CAPABILITY
```

## Compiled artifact requirements

Compiled artifacts should show:

- original resource name,
- source file path,
- source and target,
- resolved defaults,
- generated checks,
- check origins,
- sampling,
- tolerances,
- null rules,
- schema rules,
- CDC rules,
- evidence behavior,
- diagnostics.

## Design principle

The compiler is the safety layer between clean authored YAML and executable reconciliation checks.
