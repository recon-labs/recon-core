# CDC Policy Engine

## Purpose

The CDC policy engine resolves CDC-specific configuration for CDC check packs and checks.

CDC behavior must be explicit because CDC systems differ significantly.

## Inputs

Inputs:

- compiled contract,
- CDC policy,
- sampling policy,
- state backend,
- source metadata,
- target metadata,
- adapter capabilities.

## Outputs

Outputs:

- resolved CDC mode,
- resolved delete mode,
- resolved CDC keys,
- required columns,
- incremental window definition,
- operation mapping,
- validation diagnostics,
- state update requests.

## CDC modes

Supported design targets:

```text
snapshot
upsert
append_only_events
timestamp_window
batch_id
operation_column
```

Later modes:

```text
tombstone
scd2_history
```

## Upsert CDC

Example:

```yaml
cdc:
  mode: upsert
  timestamp_column: updated_at
  keys:
    same_as: grain
```

Checks may include:

- freshness lag,
- latest window count,
- incremental key coverage,
- sampled row value comparison.

## Operation-column CDC

Example:

```yaml
cdc:
  mode: append_only_events
  operation_column: operation
  keys:
    - source_order_id
  insert_value: I
  update_value: U
  delete_value: D
```

Checks may include operation count diff and delete propagation.

## Batch/load-id CDC

Example:

```yaml
cdc:
  mode: batch_id
  batch_column: load_id
```

Checks may compare batch-level counts and key coverage.

## Delete modes

No delete validation:

```yaml
cdc:
  delete_mode: none
```

Hard delete:

```yaml
cdc:
  delete_mode: hard_delete
```

Soft delete:

```yaml
cdc:
  delete_mode: soft_delete
  source_deleted_column: is_deleted
  target_deleted_column: is_deleted
```

Operation column:

```yaml
cdc:
  delete_mode: operation_column
  operation_column: op
  delete_value: D
```

These examples cover a single declared delete representation for the comparable
contract. Asymmetric source-target delete representation is not designed yet.
Examples include source hard delete to target soft delete, source soft delete
to target hard delete, and operation-column source to soft-delete target. Do
not implement CDC delete propagation checks for asymmetric representations
until a future decision defines the contract syntax, validation rules, compiled
artifact fields, and evidence output.

## Required config validation

CDC checks should fail validation when required config is missing.

Examples:

- timestamp-window mode without timestamp column,
- CDC propagation checks without CDC keys,
- CDC checks that need ordering without ordering configuration,
- operation-column mode without operation column,
- soft delete mode without deleted columns,
- incremental validation without bootstrap behavior.

Current compiler validation is intentionally narrower than CDC execution. It
validates `cdc.keys` only when the field is declared, accepting either a list of
non-empty string keys or `same_as: grain` when `grain.keys` exists. CDC mode,
delete behavior, ordering, windows, state, and execution validation remain
future work.

## State

CDC policy may use state for:

- watermarks,
- previous failed keys,
- sample keys,
- last successful batch/load id,
- CDC offsets later.

Watermarks should advance only after successful validation.

## Late-arriving data

Incremental CDC should support lookback overlap.

Example:

```yaml
lookback: 2 hours
```

## Evidence

CDC evidence should show:

- CDC mode,
- delete mode,
- CDC keys,
- operation mapping,
- watermark/window,
- lookback,
- freshness lag,
- state update behavior.
- any CDC behavior intentionally not validated, such as `delete_mode: none`.

## Design principle

CDC support should be explicit, configurable, and honest about supported modes.
