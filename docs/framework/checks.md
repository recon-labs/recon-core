# Checks

## Purpose

This document defines Recon check types.

A check is an atomic reconciliation operation that compares source and target outputs.

## Design principles

Checks should be:

- explicit,
- reusable,
- composable,
- adapter-aware,
- evidence-producing,
- testable.

Checks should not hide business meaning. The contract defines the business grain and comparison rules.

## Coverage checks

Coverage checks answer:

> Do source and target have the same records at the declared grain?

### `row_count_diff`

Compares source row count to target row count.

### `missing_keys`

Finds keys that exist in source but not target.

This is critical for CDC and replication validation.

### `extra_keys`

Finds keys that exist in target but not source.

### `duplicate_source_keys`

Finds duplicate keys in source at the declared grain.

### `duplicate_target_keys`

Finds duplicate keys in target at the declared grain.

Duplicate target keys often indicate grain mismatch or join explosion.

## Value checks

Value checks compare column values for matching keys.

### `exact_value_match`

Compares exact values such as status, category, country, or flags.

### `numeric_tolerance_match`

Compares numeric values within tolerance.

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
```

### `timestamp_tolerance_match`

Compares timestamps within tolerance.

### `normalized_string_match`

Compares strings after normalization such as trim/lower/upper.

### `null_equivalence`

Defines how nulls, blanks, and empty strings compare.

### `row_hash_match`

Compares hashes of selected columns.

Warning: hash functions differ across systems. Recon must not assume hashes are portable unless explicitly designed.

## Aggregate checks

Aggregate checks compare summarized values.

- `sum_diff`,
- `min_diff`,
- `max_diff`,
- `avg_diff`,
- `count_distinct_diff`,
- `grouped_aggregate_diff`.

Grouped aggregate checks are important because global totals can hide local differences.

## Freshness and CDC checks

These checks answer:

> Is the target up to date with the source?

Examples:

- `max_timestamp_lag`,
- `incremental_window_key_coverage`,
- `operation_count_diff`,
- `insert_propagation`,
- `update_propagation`,
- `delete_propagation`,
- `previous_failure_retest`.

These are important for continuous validation.

## Schema checks

Schema checks compare source and target structure.

Examples:

- `column_presence`,
- `type_compatibility`,
- `nullable_compatibility`,
- `precision_scale_compatibility`.

These are useful but not the core v0.1 scope.

## Check outputs

A check should return a structured result:

- check name,
- check type,
- status,
- severity,
- source value,
- target value,
- diff value,
- tolerance,
- failure count,
- evidence references.

## Status values

Possible statuses:

- `pass`,
- `fail`,
- `warn`,
- `error`,
- `skipped`.

`error` means the check could not run. `fail` means the check ran and found mismatches.

## Severity

Severity controls run outcome.

- `error`: failing check exits non-zero,
- `warn`: report but may not fail,
- `info`: evidence only.

## Execution order

A good default order:

1. validate contract,
2. resolve sampling,
3. run cheap coverage checks,
4. run aggregate checks,
5. run value/row checks,
6. capture evidence,
7. persist state/results.

## Design principle

A check belongs in Recon Core when it helps prove source-target equivalence, CDC validity, old-new parity, medallion validation, or evidence generation.
