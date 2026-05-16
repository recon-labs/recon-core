# Equivalence Contracts

## Overview

An equivalence contract defines how Recon should compare a source output and a target output.

A contract answers:

> What does it mean for this target to match this source?

## Minimal contract

```yaml
version: 1

name: orders

source:
  connection: legacy
  relation: recon.v_orders_compare

target:
  connection: warehouse
  relation: recon.v_orders_compare

grain:
  keys:
    - order_id

checks:
  use:
    - recon_core.basic_equivalence
```

## Source and target

Source and target can reference relations:

```yaml
source:
  connection: legacy
  relation: recon.v_orders_compare
```

They may later support custom queries:

```yaml
source:
  connection: legacy
  query: |
    select ...
```

Use queries or compare views when source and target need canonicalization before comparison.

## Grain

`grain.keys` define row identity for row-level checks.

```yaml
grain:
  keys:
    - order_id
```

Composite grain:

```yaml
grain:
  keys:
    - customer_id
    - month
```

Row-level checks require keys and require those keys to be unique in both source and target.

## Columns

Columns define eligible comparison fields.

```yaml
columns:
  exact:
    - status

  numeric:
    - name: revenue
      tolerance: 0.01
```

Columns do not run checks by themselves.

They are used by compatible checks or check packs.

## Metrics

Metrics define aggregate comparisons that should run.

```yaml
metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01
```

Metrics compile into aggregate checks.

## Checks

Checks can be explicit:

```yaml
checks:
  - name: revenue_sum
    type: sum_diff
    column: revenue
    tolerance: 0.01
```

or use check packs:

```yaml
checks:
  use:
    - recon_core.basic_equivalence
```

## Sampling

Sampling can be defined once and overridden per check.

```yaml
sampling:
  default_policy: full
```

```yaml
checks:
  - name: sampled_row_diff
    type: row_diff
    sampling: stable_hash_5_percent
```

## Tolerances

Tolerance precedence should be:

1. check-level,
2. column-level,
3. contract-level,
4. project-level,
5. framework default.

## Schema policy

Schema policies define structural comparison behavior.

```yaml
schema:
  ignore_target_columns:
    - _loaded_at
    - _dms_operation
```

Schema ignores must be explicit.

## CDC policy

CDC contracts should define CDC behavior when using CDC check packs.

```yaml
cdc:
  mode: upsert
  timestamp_column: updated_at
  delete_mode: soft_delete
  source_deleted_column: is_deleted
  target_deleted_column: is_deleted
```

## Evidence

Evidence settings define generated outputs.

```yaml
evidence:
  level: detailed
  store_failures: true
  max_failure_rows: 1000
```

## Compiled contract

Recon should compile authored YAML into explicit generated artifacts showing the resolved checks, columns, metrics, sampling, tolerances, schema ignores, CDC mode, and evidence behavior.

Generated artifacts belong under `target/` and should not be committed.
