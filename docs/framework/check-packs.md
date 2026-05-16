# Check Packs

## Purpose

This document defines check packs: reusable groups of reconciliation checks.

## Definition

A check pack is a named bundle of checks and defaults.

Example:

```yaml
checks:
  use:
    - recon_core.basic_equivalence
    - recon_core.aggregate_equivalence
```

## Why check packs exist

Without check packs, every contract repeats the same checks. That creates inconsistent standards across projects.

Check packs let organizations say:

> Every CDC contract uses the standard CDC equivalence pack.

## Built-in check packs

### `recon_core.basic_equivalence`

Purpose: verify basic row/key coverage.

Includes:

- `row_count_diff`,
- `missing_keys`,
- `extra_keys`,
- `duplicate_source_keys`,
- `duplicate_target_keys`.

### `recon_core.value_equivalence`

Purpose: verify matching values at declared grain.

Includes:

- `exact_value_match`,
- `numeric_tolerance_match`,
- `timestamp_tolerance_match`,
- `normalized_string_match`,
- `null_equivalence`,
- optional `row_hash_match`.

### `recon_core.aggregate_equivalence`

Purpose: verify summarized values.

Includes:

- `sum_diff`,
- `min_diff`,
- `max_diff`,
- `avg_diff`,
- `count_distinct_diff`,
- `grouped_aggregate_diff`.

### `recon_core.cdc_equivalence`

Purpose: verify ongoing source-to-target synchronization.

Includes:

- `latest_window_count`,
- `incremental_window_key_coverage`,
- `freshness_lag`,
- `max_timestamp_lag`,
- `insert_propagation`,
- `update_propagation`,
- `delete_propagation`,
- `previous_failure_retest`.

### `recon_core.schema_equivalence`

Purpose: verify structural compatibility.

Likely v0.2+.

### `recon_core.medallion_equivalence`

Purpose: verify expected behavior across Bronze/Silver/Gold.

Likely v0.2+ or package-based.

## Custom check packs

Projects can define local check packs:

```yaml
name: company_finance_controls

checks:
  - type: sum_diff
    column: revenue
    group_by:
      - month
    tolerance: 0.01
    severity: error
```

## Package-provided check packs

Future packages may provide reusable packs:

- `recon-checks-cdc`,
- `recon-checks-finance`,
- `recon-checks-medallion`,
- `recon-checks-migration`.

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

Check packs should:

- contain reusable logic,
- avoid project-specific table names,
- avoid private business mappings,
- support overrides,
- document expected inputs,
- declare required capabilities.

## Design principle

Check packs turn Recon from a script runner into a framework with reusable reconciliation standards.
