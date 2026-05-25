# Equivalence Contracts

## Purpose

This document defines Recon’s core product object: the **equivalence contract**.

An equivalence contract tells Recon:

> Compare this source output to this target output at this grain, using these checks, tolerances, sampling rules, schema rules, CDC rules, and evidence settings.

## Why contracts

A test usually checks one condition. A contract defines the whole comparison agreement between two outputs: what is being compared, how rows match, which values matter, what differences are acceptable, how much data to compare, what schema differences are allowed, how CDC behavior should be interpreted, and what evidence to capture.

## Contract layers

The contract has related but different layers:

1. **Source/target** define the comparable outputs.
2. **Grain** defines row identity.
3. **Columns** define eligible comparison fields and comparison rules.
4. **Metrics** define named aggregate comparisons to run.
5. **Checks/check packs** define execution intent.
6. **Sampling** defines which records each check sees.
7. **Tolerances/normalization** define acceptable value differences.
8. **Schema policy** defines structural comparison rules.
9. **Evidence** defines generated artifacts.

These should not be confused.

## Minimal example

```yaml
version: 1

name: customer_revenue
description: Customer monthly revenue equivalence between old and new pipeline.

source:
  connection: redshift_legacy
  relation: qa.v_customer_revenue_compare

target:
  connection: snowflake_new
  relation: qa.v_customer_revenue_compare

grain:
  keys:
    - customer_id
    - month

columns:
  numeric:
    - name: revenue
      tolerance: 0.01

metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01

checks:
  use:
    - recon_core.basic_equivalence

sampling:
  default_policy: stable_hash_5_percent

evidence:
  level: detailed
  store_failures: true
```

In this example, `basic_equivalence` runs row count, missing keys, extra keys,
null-key checks, and duplicate-key checks. The explicit `revenue_by_month`
metric compiles into an aggregate check. `revenue` is available as a numeric
comparable column with `0.01` tolerance. `stable_hash_5_percent` is the default
sampling policy unless a check overrides it.

## Columns do not run checks

This declares comparison metadata:

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
```

It does **not** automatically run a revenue check.

It means `revenue` is a numeric comparable column, and when a compatible check uses it, use `0.01` tolerance unless overridden.

This runs checks:

```yaml
metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
```

or:

```yaml
checks:
  - name: revenue_sum
    type: sum_diff
    column: revenue
```

## Metrics do run aggregate checks

Metrics are named aggregate comparisons. They compile into checks.

```yaml
metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01
```

This should compile into an aggregate check such as:

```yaml
compiled_checks:
  - name: revenue_by_month
    type: grouped_aggregate_diff
    metric: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01
```

## Source and target

Contracts should support relations first:

```yaml
source:
  connection: sqlserver_orders
  relation: recon.v_orders_compare
```

They must also support custom queries:

```yaml
target:
  connection: snowflake_wh
  query: |
    select
      fo.order_number,
      dc.customer_external_id as customer_business_key,
      fo.total_amount
    from analytics.fact_orders fo
    join analytics.dim_customer dc
      on fo.customer_sk = dc.customer_sk
```

Custom queries are required when source and target schemas differ, target uses generated surrogate keys, comparison requires joins, canonical outputs must be created dynamically, migration/refactor logic needs explicit filters, or source and target need different normalization steps.

Exactly one of `relation` or `query` should be provided for each endpoint.

## Relation-first, query-capable

The recommended production pattern is to compare existing source and target compare views.

This keeps business mapping visible and independently testable.

Query support remains part of the product direction because real reconciliation often needs flexibility.

## Grain and keys

The `grain` section defines how records match:

```yaml
grain:
  keys:
    - customer_business_key
    - month
```

Guidelines:

- use business keys,
- support composite keys,
- avoid comparing generated surrogate keys unless explicitly intended,
- require keys for row-level checks.

`grain.keys` are a uniqueness claim. Recon must validate uniqueness before row-level checks.

If keys are null or duplicated in source or target, row-level value checks should be blocked. Aggregate checks may still run.

`grain.keys` define comparison identity, not necessarily database primary keys. They should normally be business keys or canonical keys exposed by compare views or queries.

For MVP behavior, source and target should expose the same key column names in their comparable outputs. Recon must not silently guess source-target key mappings.

The current contract model supports one default grain per contract. Future
advanced contracts may add optional named grains for checks that need different
row identities, such as order-level checks using `order_id` and line-level
checks using `order_id, line_id`. That syntax is not implemented and requires a
future decision.

## Columns

Columns define value comparison rules and eligible comparison surface.
Column behavior is governed by ADR 0019.

```yaml
columns:
  exact:
    - customer_status
    - name: country_code

  numeric:
    - name: lifetime_value
      tolerance: 0.01

  timestamp:
    - name: updated_at
      tolerance: 5 seconds

  string:
    - name: customer_name
      normalization: trim_lower
```

Supported categories are `exact`, `numeric`, `timestamp`, and `string`.

String entries are shorthand for `{name: <column_name>}`.

Columns do not create checks. They define the columns that generated,
metric-derived, or explicit value checks may use.

If a contract has no `columns` block, explicit metrics and explicit checks may
still name columns directly. Existence and physical type validation may be
deferred until adapter metadata is available.

If a contract has a `columns` block, that block is the explicit comparison
surface. Explicit checks and metrics that reference columns outside that
surface should fail validation.

Recon should never silently compare all columns. If users want all columns, they must request it explicitly:

```yaml
columns:
  include: "*"
```

or:

```yaml
checks:
  - type: row_diff
    columns: "*"
```

All-column comparison requires adapter metadata and compiled artifact
visibility. Raw `*` must never appear in typed check plans; it must resolve to
concrete column names before execution.

For MVP behavior, source and target comparable outputs should expose the same
canonical column names. Source-target column mapping is a future feature and
must be explicit if added.

## Column-level check eligibility

A column may optionally specify which checks it participates in.

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
      checks:
        - sum_diff
        - sampled_value_match
```

This is useful when a numeric column should be included in aggregate checks but excluded from row-level value comparison, or vice versa.

Column-level `checks` is a filter. It does not create checks. A generated,
metric-derived, or explicit check that uses the column should be one of the
listed check types.

## Metrics

Metrics are explicit aggregate comparisons.

```yaml
metrics:
  - name: revenue_sum
    type: sum
    column: revenue
    tolerance: 0.01

  - name: distinct_customers
    type: count_distinct
    column: customer_id
```

Use metrics when the aggregate itself is business-important and should appear by name in evidence.

## Checks

Checks may be declared through packs:

```yaml
checks:
  use:
    - recon_core.basic_equivalence
```

or explicitly:

```yaml
checks:
  - name: revenue_sum
    type: sum_diff
    column: revenue
    tolerance: 0.01
    severity: error
```

Check packs are preferred for standardization. Explicit checks are preferred when a contract needs precise behavior.

## Check packs and column metadata

A check pack may use column metadata only when that behavior is explicitly
documented by the pack.

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01

checks:
  use:
    - recon_core.aggregate_equivalence
```

Rejected implicit interpretation:

- `aggregate_equivalence` sees numeric column `revenue`,
- it creates a `sum_diff` check for `revenue`,
- it uses tolerance `0.01`.

Recon must not infer aggregate checks from numeric columns unless a future
decision explicitly enables that behavior. Prefer explicit metrics or explicit
aggregate checks for business-important aggregate comparisons.

Check-pack expansion must be visible in compiled artifacts.

## Empty check-pack expansion

If a check pack requires columns or metrics and none are available, the default should be an error, not a silent no-op.

```yaml
checks:
  use:
    - recon_core.some_future_pack
```

Default behavior:

```text
ERROR: recon_core.some_future_pack expanded to no checks.
```

A later escape hatch may allow:

```yaml
checks:
  use:
    - name: recon_core.some_future_pack
      on_empty: warn
```

ADR 0018 locks future `on_empty` values as `error`, `warn`, and `skip`.
Default behavior remains strict. Non-error empty expansion must be visible in
compiled artifacts and must not suppress invalid config, missing required keys,
or other safety validation failures.

## Check-pack invocation config

Check-pack invocation config is designed by ADR 0018 but is not implemented
yet. Current compilation accepts strings and mappings with only `name`.

Locked future shape:

```yaml
checks:
  use:
    - name: recon_core.some_pack
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

Unknown invocation fields and unknown config keys must fail. Package check
packs must declare config schemas before accepting config. Config must not
disable required safety checks unless a later ADR explicitly allows that
behavior.

## Explicit check configuration

Contracts should allow explicit configuration when users do not want inference.

```yaml
checks:
  - name: revenue_sum
    type: sum_diff
    column: revenue
    tolerance: 0.01
    sampling: full

  - name: revenue_sampled_values
    type: sampled_value_match
    columns:
      - revenue
    sampling: stable_hash_5_percent
```

## Sampling

Sampling can be defined as a contract default:

```yaml
sampling:
  default_policy: stable_hash_5_percent
```

Individual checks should be able to override sampling:

```yaml
checks:
  - name: revenue_sum
    type: sum_diff
    column: revenue
    sampling: full

  - name: sampled_row_diff
    type: row_diff
    sampling: stable_hash_5_percent
```

Different checks need different scopes:

- `row_count_diff` may run on full data,
- `sum_diff` may run on full data,
- `row_diff` may run on a deterministic sample,
- CDC checks may run on an incremental window,
- previous-failure checks may run only on failed keys.

Sampling does not remove the uniqueness requirement for row-level value comparison.

## Tolerances and normalization

Contracts may reference a tolerance policy:

```yaml
tolerance_policy: finance
```

Column-level tolerance:

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
```

Check-level override:

```yaml
checks:
  - type: sum_diff
    column: revenue
    tolerance: 0.001
```

Recommended precedence:

1. check-level override,
2. column-level setting,
3. contract-level policy,
4. project-level default,
5. framework default.

Null and empty-string behavior should be explicit. Default should be strict: `NULL != ''`.

```yaml
nulls:
  empty_string_equals_null: true
```

This is important for pipelines where systems such as SQL Server, AWS DMS, file formats, and Snowflake may handle empty strings differently.

## Schema policy

Contracts may define schema behavior.

```yaml
schema:
  ignore_target_columns:
    - _dms_operation
    - _dms_timestamp
    - _loaded_at
  ignore_patterns:
    - "_metadata_*"
```

Schema checks should be strict by default, but support explicit ignored columns and patterns for CDC or ingestion metadata.

## CDC policy

CDC contracts should define the CDC mode when CDC-specific checks are used.

```yaml
cdc:
  mode: upsert
  timestamp_column: updated_at
```

Soft delete example:

```yaml
cdc:
  delete_mode: soft_delete
  source_deleted_column: is_deleted
  target_deleted_column: is_deleted
```

This example assumes source and target both expose soft-delete indicators.
Asymmetric delete representation, such as source hard delete to target soft
delete or source operation column to target soft delete, is not defined yet and
requires a future decision before delete propagation checks are implemented.

Operation-column example:

```yaml
cdc:
  mode: append_only_events
  operation_column: operation
  insert_value: I
  update_value: U
  delete_value: D
```

CDC check packs must not assume one CDC shape.

CDC checks that validate update, delete, or change propagation should also define CDC identity:

```yaml
cdc:
  mode: upsert
  timestamp_column: updated_at
  keys:
    same_as: grain
```

or:

```yaml
cdc:
  mode: operation_column
  operation_column: operation
  keys:
    - source_order_id
```

`cdc.keys` are separate from `grain.keys`. They may be the same, but Recon should require that choice to be explicit for CDC checks that depend on change identity.

The current contract model supports one default CDC identity per contract.
Future advanced contracts may add optional named CDC identities for checks that
need different CDC roles, such as event identity and changed-row identity. That
syntax is not implemented and requires a future decision.

If delete propagation is intentionally not validated, say so explicitly:

```yaml
cdc:
  delete_mode: none
```

## Evidence

Evidence settings define output behavior.

```yaml
evidence:
  level: detailed
  store_failures: true
  max_failure_rows: 1000
  report: html
```

Checks may override evidence later.

```yaml
checks:
  - type: row_diff
    evidence:
      store_failures: true
      max_failure_rows: 500
```

## Owners and tags

Contracts may include owners and tags.

```yaml
owners:
  business: analytics_team
  engineering: data_platform

tags:
  - cdc
  - revenue
  - critical
```

## Severity

Checks may define severity:

```yaml
checks:
  - type: row_count_diff
    severity: error

  - type: sampled_row_diff
    severity: warn
```

Expected behavior:

- `error` failures cause non-zero exit,
- `warn` failures are reported but may not fail the run,
- `info` checks produce evidence only.

## Validation rules

Recon should validate contracts before execution:

- `name` is required,
- contract names are unique in a project,
- source and target are required,
- exactly one of `relation` or `query` per endpoint,
- row-level checks require `grain.keys`,
- row-level checks require non-null and unique keys after filtering/sampling/windowing,
- CDC propagation checks require `cdc.keys`,
- CDC delete behavior is explicit when CDC checks are used,
- checks must be compatible with column types,
- metrics must be compatible with referenced columns,
- metric/check column references must stay inside the declared column surface
  when `columns` is present,
- all-column requests must resolve to concrete column names before execution,
- referenced sample policies exist,
- referenced check packs exist,
- tolerance syntax is valid,
- schema ignore rules are explicit,
- adapter capabilities are sufficient.

## Compiled contract

Recon should compile authored contracts into an explicit execution plan.

The compiled plan should show:

- which check packs expanded,
- which metrics compiled into checks,
- which atomic checks will run,
- which columns each check uses,
- which declared columns were selected, ignored, or excluded as identity
  columns,
- which sampling policy each check uses,
- which tolerances and null rules each check uses,
- which schema ignore rules apply,
- which CDC mode/delete behavior applies,
- which evidence will be captured.

This prevents ambiguity between columns, metrics, checks, sampling, tolerances, schema policies, and CDC rules.

## Design principle

Contracts should be readable and declarative, but execution should be explicit after compilation.

Users define the equivalence agreement. Recon validates unsafe assumptions, compiles explicit checks, runs them, and produces evidence.
