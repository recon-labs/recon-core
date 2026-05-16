# ADR 0011: CDC Policy and Delete Modes

## Context

CDC systems use different patterns.

Examples include:

- timestamp-window upserts,
- append-only event logs,
- batch/load-id replication,
- operation columns,
- hard deletes,
- soft deletes,
- tombstone events,
- SCD2-style history.

A single CDC assumption would make Recon unreliable.

## Decision

CDC behavior must be explicit when CDC-specific checks are used.

`recon_core.cdc_equivalence` should support configurable CDC modes and delete modes.

Supported design targets include:

- snapshot comparison,
- upsert CDC,
- append-only event CDC,
- batch/load-id CDC,
- timestamp-window CDC,
- operation-column CDC,
- hard-delete CDC,
- soft-delete CDC,
- tombstone CDC later,
- SCD2 history later.

## Delete modes

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

## Consequences

CDC check packs should fail validation when required CDC configuration is missing.

CDC assumptions must appear in compiled checks and evidence.

Recon should start with a small supported CDC subset and document unsupported modes clearly.
