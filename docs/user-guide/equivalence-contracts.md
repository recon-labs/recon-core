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

`grain.keys` are comparison identity. They do not have to be database primary keys; they should identify one comparable source row and one comparable target row.

The current contract model supports one default grain per contract. Advanced
multi-grain contracts are a future design.

For MVP behavior, expose canonical key column names through compare views or queries. Recon does not guess source-target key mappings.

## Columns

Columns define eligible comparison fields. They do not run checks by
themselves.

```yaml
columns:
  exact:
    - status

  numeric:
    - name: revenue
      tolerance: 0.01
```

They are used by compatible checks or check packs.

If a contract has a `columns` block, explicit checks and metrics should stay
inside that declared surface. All-column comparison must be requested
explicitly and must resolve to concrete column names before execution.

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

The current compiler accepts check-pack entries as strings or mappings with
only `name`. Future `config` and `on_empty` support is designed by ADR 0018 but
is not implemented yet.

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
  keys:
    same_as: grain
  delete_mode: soft_delete
  source_deleted_column: is_deleted
  target_deleted_column: is_deleted
```

This example assumes source and target both expose soft-delete indicators.
Asymmetric delete representation is not defined yet and should not be assumed.

CDC keys are change identity, not necessarily comparison identity. If CDC checks validate update, delete, or change propagation and the CDC key differs from the grain, declare it explicitly:

```yaml
cdc:
  mode: upsert
  timestamp_column: updated_at
  keys:
    - source_order_id
```

The current contract model supports one default CDC identity per contract.
Advanced contracts with multiple CDC identities are a future design.

If delete propagation is intentionally not validated, declare that explicitly:

```yaml
cdc:
  delete_mode: none
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

Compiled artifacts should also show check requirements, declared grain keys, declared CDC keys, generated safety checks, prerequisites, and blocked-check behavior.

Generated artifacts belong under `target/` and should not be committed.
