# Check Packs

## Purpose

This document defines check packs: reusable groups of reconciliation checks.

## Definition

A check pack is a named bundle of checks and defaults.

```yaml
checks:
  use:
    - recon_core.basic_equivalence
    - recon_core.aggregate_equivalence
```

## Why check packs exist

Check packs let organizations standardize reconciliation behavior across contracts.

## Check-pack expansion

Check packs are execution intent, not hidden magic.

During compilation, a check pack must expand into explicit atomic checks. Compiled artifacts should show which check pack was used, which checks were generated, which columns or metrics each check uses, which sampling policy each check uses, which tolerance and null rules apply, and which CDC/schema options apply.

## Empty expansion rule

If a check pack needs input columns, metrics, or config and none are available, default behavior should be error.

```yaml
columns:
  exact:
    - status

checks:
  use:
    - recon_core.aggregate_equivalence
```

Default result:

```text
ERROR: aggregate_equivalence requires numeric columns or explicit metrics.
```

A future escape hatch may support `on_empty: warn`, but default should remain strict.

## Built-in check packs

### `recon_core.basic_equivalence`

Verifies basic row/key coverage.

Includes:

- `row_count_diff`,
- `missing_keys`,
- `extra_keys`,
- `duplicate_source_keys`,
- `duplicate_target_keys`.

`row_count_diff` can run without keys. Key coverage checks require `grain.keys`. Duplicate key checks validate whether row-level checks are safe.

### `recon_core.value_equivalence`

Verifies matching values at declared grain.

Includes:

- `exact_value_match`,
- `numeric_tolerance_match`,
- `timestamp_tolerance_match`,
- `normalized_string_match`,
- `null_equivalence`,
- optional `row_hash_match`.

Requirements:

- `grain.keys`,
- unique keys in source and target,
- eligible columns or explicit check-level columns.

This pack must not compare all columns unless explicitly configured.

### `recon_core.aggregate_equivalence`

Verifies summarized values.

Includes:

- `sum_diff`,
- `min_diff`,
- `max_diff`,
- `avg_diff`,
- `count_distinct_diff`,
- `grouped_aggregate_diff`.

Inputs are numeric columns, explicit metrics, or check-specific aggregate definitions.

This pack should use explicit metrics first. It may infer aggregates from eligible numeric columns only if documented and visible in compiled artifacts.

### `recon_core.cdc_equivalence`

Verifies ongoing source-to-target synchronization.

Potential checks:

- `latest_window_count`,
- `incremental_window_key_coverage`,
- `freshness_lag`,
- `max_timestamp_lag`,
- `operation_count_diff`,
- `insert_propagation`,
- `update_propagation`,
- `delete_propagation`,
- `previous_failure_retest`.

CDC mode must be explicit when behavior is ambiguous.

Supported modes should include snapshot comparison, upsert CDC, append-only event CDC, batch CDC by load/batch id, timestamp-window CDC, operation-column CDC, soft-delete CDC, hard-delete CDC, and SCD2-style history later.

### `recon_core.schema_equivalence`

Verifies structural compatibility.

Potential checks:

- `column_presence`,
- `type_compatibility`,
- `nullable_compatibility`,
- `precision_scale_compatibility`.

Schema checks should be strict by default but support explicit ignored source/target columns and ignore patterns.

### `recon_core.medallion_equivalence`

Verifies expected behavior across Bronze/Silver/Gold.

Potential checks include row preservation, expected row reduction, aggregate preservation, grain change validation, and layer freshness.

## CDC delete modes

CDC check packs must support explicit delete behavior.

```yaml
cdc:
  delete_mode: hard_delete
```

```yaml
cdc:
  delete_mode: soft_delete
  source_deleted_column: is_deleted
  target_deleted_column: is_deleted
```

```yaml
cdc:
  delete_mode: operation_column
  operation_column: op
  delete_value: D
```

Tombstone events and SCD2 history can be added later.

## Overrides

Contracts should be able to override pack defaults.

```yaml
checks:
  use:
    - name: recon_core.basic_equivalence
      config:
        row_count:
          tolerance: 10
          severity: warn
```

## Design rules

Check packs should contain reusable logic, avoid project-specific table names and private business mappings, support overrides, document expected inputs, declare required capabilities, compile into visible atomic checks, and avoid silent no-op behavior.

## Design principle

Check packs turn Recon from a script runner into a framework with reusable reconciliation standards, but they must remain transparent and auditable.
