# Check Packs

## Purpose

This document defines check packs: reusable groups of reconciliation checks.

## Definition

A check pack is a named bundle of checks and defaults.

```yaml
checks:
  use:
    - recon_core.basic_equivalence
```

Current implementation supports check-pack use entries as either strings or
mappings with only `name`:

```yaml
checks:
  use:
    - name: recon_core.basic_equivalence
```

Invocation fields such as `config`, `on_empty`, or package-specific overrides
are designed by ADR 0018 but are not implemented yet. Current compilation
rejects unsupported invocation fields instead of ignoring them.

## Why check packs exist

Check packs let organizations standardize reconciliation behavior across contracts.

## Check-pack expansion

Check packs are execution intent, not hidden magic.

During compilation, a check pack must expand into explicit atomic checks. Compiled artifacts should show which check pack was used, which checks were generated, which columns or metrics each check uses, which sampling policy each check uses, which tolerance and null rules apply, and which CDC/schema options apply.

## Empty expansion rule

If a check pack needs input columns, metrics, or config and none are available, default behavior should be error.

```yaml
checks:
  use:
    - recon_core.some_future_pack
```

Default result:

```text
ERROR: recon_core.some_future_pack expanded to no checks.
```

ADR 0018 locks future `on_empty` values as `error`, `warn`, and `skip`. The
default remains `error`. `warn` and `skip` require compiled artifact visibility
before implementation.

## Built-in check packs

### `recon_core.basic_equivalence`

Verifies basic row/key coverage.

Includes:

- `row_count_diff`,
- `missing_keys`,
- `extra_keys`,
- `null_source_keys`,
- `null_target_keys`,
- `duplicate_source_keys`,
- `duplicate_target_keys`.

`row_count_diff` can run without keys. Key coverage checks require `grain.keys`. Null-key and duplicate-key checks validate whether row-level checks are safe.

The pack itself requires `grain.keys`. It must not silently weaken to only `row_count_diff` when grain is missing. If users want only row-count behavior, they should request `row_count_diff` explicitly.

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
- non-null keys in source and target,
- unique keys in source and target,
- eligible columns or explicit check-level columns.

This pack must not compare all columns unless explicitly configured.

If required null-key or duplicate-key safety checks are not authored explicitly, the compiler should generate visible safety checks before value checks.

### `recon_core.aggregate_equivalence`

Verifies summarized values.

Includes:

- `sum_diff`,
- `min_diff`,
- `max_diff`,
- `avg_diff`,
- `count_distinct_diff`,
- `grouped_aggregate_diff`.

Inputs are explicit metrics or check-specific aggregate definitions. Numeric
columns provide type and tolerance metadata when referenced explicitly.

This pack should use explicit metrics or explicit aggregate check definitions.
It must not infer aggregates from eligible numeric columns unless a future
decision explicitly enables that behavior and defines how the generated checks
appear in compiled artifacts.

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

CDC checks that validate update, delete, key coverage, or change propagation require `cdc.keys`. CDC keys are separate from `grain.keys`; they may be declared as `same_as: grain` only when that assumption is intentional.

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

No delete validation:

```yaml
cdc:
  delete_mode: none
```

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

These examples do not define asymmetric source-target delete representation.
Cases such as source hard delete to target soft delete, source soft delete to
target hard delete, or operation-column source to soft-delete target require a
future decision before CDC delete propagation checks are implemented.

Tombstone events and SCD2 history can be added later.

## Invocation config

Contracts should eventually be able to override pack defaults through the ADR
0018 invocation model. The locked public shape is:

```yaml
checks:
  use:
    - name: recon_core.basic_equivalence
      on_empty: error
      config:
        severity: error
        sampling: full
        tolerance: strict
        params: {}
        checks:
          row_count_diff:
            severity: warn
```

Current compilation still rejects `config` and `on_empty`. When support is
implemented:

- unknown invocation fields must fail,
- unknown config keys must fail,
- package check packs must declare config schemas before accepting config,
- config that cannot apply to generated checks must fail,
- `on_empty` must be visible in compiled artifacts,
- config must not disable required safety checks unless a later ADR explicitly
  allows that behavior.

Per-check overrides under `config.checks` apply only to generated check names
declared by the check pack. The locked shape does not include `enabled`,
`exclude`, `only`, `except`, `alias`, or `as`.

## Design rules

Check packs should contain reusable logic, avoid project-specific table names and private business mappings, support overrides, document expected inputs, declare required capabilities, compile into visible atomic checks, and avoid silent no-op behavior.

## Design principle

Check packs turn Recon from a script runner into a framework with reusable reconciliation standards, but they must remain transparent and auditable.
