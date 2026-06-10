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
- whether grain keys must be non-null and unique,
- whether it requires `cdc.keys`,
- whether it requires CDC ordering or windows,
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

Finds distinct non-null grain keys that exist in source but not target. Requires `grain.keys`.

### `extra_keys`

Finds distinct non-null grain keys that exist in target but not source. Requires `grain.keys`.

`missing_keys` and `extra_keys` may run as distinct non-null key coverage even when null or duplicate keys exist. Null-key and duplicate-key failures still block row-level value checks.

### `null_source_keys`

Finds rows with null source grain key values. Requires `grain.keys`.

### `null_target_keys`

Finds rows with null target grain key values. Requires `grain.keys`.

### `duplicate_source_keys`

Finds duplicate keys in source at the declared grain. Requires `grain.keys`.

### `duplicate_target_keys`

Finds duplicate keys in target at the declared grain. Requires `grain.keys`.

Duplicate keys often indicate grain mismatch, join explosion, or incorrect canonicalization.

## Row-level value checks

Row-level value checks compare source and target values after matching rows by
key. Column selection and compatibility are governed by ADR 0019.

Examples:

- `exact_value_match`,
- `numeric_tolerance_match`,
- `timestamp_tolerance_match`,
- `sampled_value_match`,
- `row_diff`,
- `row_hash_match`.

These checks require:

- `grain.keys`,
- non-null grain keys,
- unique keys in source,
- unique keys in target,
- declared eligible columns or explicit check-level columns,
- concrete column names before execution.

If keys are null or duplicated, row-level value checks should be blocked rather than guessed.

If users did not author null-key and duplicate-key checks explicitly, Recon should generate visible safety checks for row-level value checks.

## Sampling and row-level checks

Sampling does not remove non-null or uniqueness requirements.

For sampled row-level checks, non-null and uniqueness requirements must hold inside the sampled/windowed comparable output.

For CDC latest-window checks, non-null and uniqueness requirements must hold inside the incremental window.

## Value checks

### `exact_value_match`

Compares exact values such as status, category, country, or flags.
It should use `exact` columns unless the check explicitly supports another
category exactly.

### `numeric_tolerance_match`

Compares numeric values within tolerance. MVP tolerance is absolute numeric
tolerance only. It must run only on numeric-compatible columns.

### `timestamp_tolerance_match`

Compares timestamps within tolerance. Timestamp tolerance execution is future
gated. When implemented, timestamp checks should distinguish event time,
ingestion time, and target processing time, and must not silently convert
timezones.

### `normalized_string_match`

Compares strings after explicit normalization. Allowed simple normalization
steps are `trim`, `collapse_whitespace`, `lower`, and `upper`. MVP also
supports limited `regex_replace` normalization with literal replacements.
Locale-specific case folding, unrestricted regex features, arbitrary SQL, and
macro-based normalization are future gated.

### `null_equivalence`

Defines how nulls, blanks, and empty strings compare. Default is strict:
`NULL != ''`. Resolved comparisons use null-safe equality: `NULL` equals
`NULL`, but one null and one non-null value differ.

### `row_hash_match`

Compares hashes of selected columns.

Hash functions differ across systems. Recon must not assume hashes are portable unless adapters declare safe behavior or sample keys are persisted.

Cross-database row hashes require a future adapter/canonicalization decision
before they can be trusted.

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

CDC checks that validate key coverage, update propagation, or delete propagation require explicit `cdc.keys`. CDC freshness and count checks may not require `cdc.keys` if they only compare configured windows, timestamps, or counts.

## CDC delete checks

Delete checks must support multiple delete representations:

- hard delete,
- soft delete flag,
- operation column,
- tombstone event,
- SCD2 current/history model later.

A CDC check pack must not assume one delete model.

If delete propagation is intentionally not validated, `delete_mode: none` should be explicit and visible in compiled artifacts and evidence.

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

A check should return a structured result: check name, check type, status,
severity, source value, target value, diff value, tolerance, failure count,
diagnostics, and machine-readable reason code when applicable. Blocked checks
should include `blocked_by`. Artifact, evidence, failure-detail, state, and
sink references should appear only when an owning writer actually produced
those outputs.

## Status values

Possible statuses:

- `pass`,
- `fail`,
- `warn`,
- `error`,
- `skipped`,
- `blocked`,
- `not_executable`.

`pass`, `fail`, and `warn` require the check to have executed. `error` means
Recon hit a runtime, artifact, internal, or unsafe-condition problem that
prevents a trustworthy result. `skipped` means explicit user, configuration, or
future selector policy intentionally skipped the check. `blocked` means a
prerequisite failed, errored, or was unavailable. `not_executable` means the
compiled check is valid but cannot run with the current engine, typed
operation, capability, placement, materialization policy, or implemented
surface.

Prerequisite failures should not be represented as skipped checks. A dependent
check should return `blocked` with `blocked_by`, a machine-readable reason
code, and safe diagnostics.

## Severity

Severity controls run outcome.

- `error`: failing check exits non-zero,
- `warn`: report but may not fail,
- `info`: evidence only.

## Error versus warning defaults

Unsafe or ambiguous behavior should default to error.

Errors should include row-level checks without keys, row-level checks with duplicate keys, numeric checks on text columns, metric references to undefined columns, unknown check packs, empty check-pack expansion, missing sample policies, and random sampling without persisted keys.

CDC propagation checks without required `cdc.keys`, CDC checks without required delete mode, and CDC checks without required ordering should also be errors.

Warnings may include defined columns not used by any compiled check, deferred
adapter metadata validation, target freshness lag making row comparison
unreliable, or timestamp comparison without explicit timezone policy in
non-strict mode.

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
