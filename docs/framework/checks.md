# Checks

## Purpose

This document defines Recon check types.

A check is an atomic reconciliation operation that compares source and target outputs.

## Design principles

Checks should be explicit, reusable, composable, adapter-aware, evidence-producing, testable, and strict about unsafe assumptions.

Checks should not hide business meaning. The contract defines the business grain and comparison rules.

## Check compatibility

Every check should declare what it requires:

- whether it requires `grain.keys`,
- whether keys must be unique,
- whether it requires numeric columns,
- whether it can run on sampled data,
- whether it can run without source/target metadata,
- which adapter capabilities it needs.

Recon should validate these requirements before execution when possible.

## Coverage checks

Coverage checks answer whether source and target have the same records at the declared grain.

### `row_count_diff`

Compares source row count to target row count. This can run without `grain.keys`.

### `missing_keys`

Finds keys that exist in source but not target. Requires `grain.keys`.

### `extra_keys`

Finds keys that exist in target but not source. Requires `grain.keys`.

### `duplicate_source_keys`

Finds duplicate keys in source at the declared grain. Requires `grain.keys`.

### `duplicate_target_keys`

Finds duplicate keys in target at the declared grain. Requires `grain.keys`.

Duplicate keys often indicate grain mismatch, join explosion, or incorrect canonicalization.

## Row-level value checks

Row-level value checks compare source and target values after matching rows by key.

Examples:

- `exact_value_match`,
- `numeric_tolerance_match`,
- `timestamp_tolerance_match`,
- `sampled_value_match`,
- `row_diff`,
- `row_hash_match`.

These checks require:

- `grain.keys`,
- unique keys in source,
- unique keys in target,
- declared eligible columns or explicit check-level columns.

If keys are duplicated, row-level value checks should be blocked rather than guessed.

## Sampling and row-level checks

Sampling does not remove uniqueness requirements.

For sampled row-level checks, uniqueness must hold inside the sampled/windowed comparable output.

For CDC latest-window checks, uniqueness must hold inside the incremental window.

## Value checks

### `exact_value_match`

Compares exact values such as status, category, country, or flags.

### `numeric_tolerance_match`

Compares numeric values within tolerance. It must run only on numeric-compatible columns.

### `timestamp_tolerance_match`

Compares timestamps within tolerance. Timestamp checks should distinguish event time, ingestion time, and target processing time.

### `normalized_string_match`

Compares strings after explicit normalization such as trim, lower, upper, or whitespace canonicalization.

### `null_equivalence`

Defines how nulls, blanks, and empty strings compare. Default should be strict: `NULL != ''`.

### `row_hash_match`

Compares hashes of selected columns.

Hash functions differ across systems. Recon must not assume hashes are portable unless adapters declare safe behavior or sample keys are persisted.

## Aggregate checks

Aggregate checks compare summarized values.

Examples:

- `sum_diff`,
- `min_diff`,
- `max_diff`,
- `avg_diff`,
- `count_distinct_diff`,
- `grouped_aggregate_diff`.

Aggregate checks can run without row-level `grain.keys` when they have explicit columns or metrics.

`metrics.group_by` is used for segmentation. It is not the same as row identity.

## Metrics and aggregate checks

Metrics compile into aggregate checks.

```yaml
metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
```

Metric names must be unique, and metric types must be compatible with referenced columns.

## Freshness and CDC checks

CDC and freshness checks answer whether the target is up to date with the source.

Examples:

- `max_timestamp_lag`,
- `incremental_window_key_coverage`,
- `operation_count_diff`,
- `insert_propagation`,
- `update_propagation`,
- `delete_propagation`,
- `previous_failure_retest`.

CDC checks should require explicit CDC mode when behavior is ambiguous.

## CDC delete checks

Delete checks must support multiple delete representations:

- hard delete,
- soft delete flag,
- operation column,
- tombstone event,
- SCD2 current/history model later.

A CDC check pack must not assume one delete model.

## Schema checks

Schema checks compare source and target structure.

Examples:

- `column_presence`,
- `type_compatibility`,
- `nullable_compatibility`,
- `precision_scale_compatibility`.

Schema checks may compare all columns by default, but they must support explicit ignore rules for technical columns.

## Precision and scale checks

Precision/scale compatibility is a schema check.

Numeric value tolerance is a value comparison rule.

These are related but different.

## Check outputs

A check should return a structured result: check name, check type, status, severity, source value, target value, diff value, tolerance, failure count, evidence references, and skip/error reason when applicable.

## Status values

Possible statuses:

- `pass`,
- `fail`,
- `warn`,
- `error`,
- `skipped`.

`error` means the check could not run. `fail` means the check ran and found mismatches. `skipped` should include a clear reason and should not hide unsafe behavior.

## Severity

Severity controls run outcome.

- `error`: failing check exits non-zero,
- `warn`: report but may not fail,
- `info`: evidence only.

## Error versus warning defaults

Unsafe or ambiguous behavior should default to error.

Errors should include row-level checks without keys, row-level checks with duplicate keys, numeric checks on text columns, metric references to undefined columns, unknown check packs, empty check-pack expansion, missing sample policies, and random sampling without persisted keys.

Warnings may include defined columns not used by any compiled check, target freshness lag making row comparison unreliable, or timestamp comparison without explicit timezone policy in non-strict mode.

## Execution order

A good default order:

1. validate contract structure,
2. resolve refs/defaults,
3. compile check packs and metrics,
4. resolve sampling and tolerances,
5. validate adapter capabilities,
6. run cheap coverage/freshness checks,
7. run aggregate checks,
8. run row-level value checks,
9. capture evidence,
10. persist results/state.

## Design principle

A check belongs in Recon Core when it helps prove source-target equivalence, CDC validity, old-new parity, medallion validation, schema compatibility, or evidence generation.
