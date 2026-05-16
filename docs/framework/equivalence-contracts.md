# Equivalence Contracts

## Purpose

This document defines Recon’s core product object: the **equivalence contract**.

An equivalence contract tells Recon:

> Compare this source output to this target output at this grain, using these checks, tolerances, sampling rules, and evidence settings.

## Why contracts

A test usually checks one condition. A contract defines the whole comparison agreement between two outputs:

- what is being compared,
- how rows match,
- which values matter,
- what differences are acceptable,
- how much data to compare,
- what evidence to capture.

## Important semantic distinction

The contract has three related but different layers:

1. **Column definitions** describe comparable fields and their comparison rules.
2. **Checks** define what operations actually run.
3. **Sampling policies** define which records a check runs against.

These should not be confused.

Example:

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
```

This does **not** automatically run a check by itself.

It means:

> `revenue` is a numeric comparable column, and when a check compares this column, use `0.01` tolerance unless overridden.

Then:

```yaml
checks:
  use:
    - recon_core.aggregate_equivalence
```

means:

> Run the checks included in the aggregate equivalence pack.

If that check pack includes `sum_diff` for numeric columns, it may use the `revenue` column definition.

So:

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
```

is metadata/rule declaration.

```yaml
checks:
  use:
    - recon_core.aggregate_equivalence
```

is execution instruction.

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

checks:
  use:
    - recon_core.basic_equivalence
    - recon_core.aggregate_equivalence

sampling:
  default_policy: stable_hash_5_percent

evidence:
  level: detailed
  store_failures: true
```

In this example:

- `basic_equivalence` may run row count, missing keys, extra keys, and duplicate key checks.
- `aggregate_equivalence` may run aggregate checks such as `sum_diff` for numeric columns.
- `revenue` is available to those checks as a numeric comparable column with `0.01` tolerance.
- `stable_hash_5_percent` is the default sampling policy unless a check overrides it.

## Source and target

Contracts should support relations first:

```yaml
source:
  connection: sqlserver_orders
  relation: recon.v_orders_compare
```

But they must also support custom queries:

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

Custom queries are required when:

- source and target schemas differ,
- target uses generated surrogate keys,
- comparison requires joins,
- canonical outputs must be created dynamically,
- migration/refactor logic needs explicit filters.

## Relation-first, query-capable

The recommended production pattern is to compare existing source and target compare views.

This keeps business mapping visible and independently testable.

However, query support is part of the product direction because real reconciliation often needs flexibility.

Recon should support both patterns:

```yaml
source:
  relation: recon.v_customer_compare

target:
  relation: recon.v_customer_compare
```

and:

```yaml
source:
  query: |
    select ...

target:
  query: |
    select ...
```

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

## Columns

Columns define value comparison rules.

They do not necessarily define which checks run.

```yaml
columns:
  exact:
    - customer_status
    - country_code

  numeric:
    - name: lifetime_value
      tolerance: 0.01

  timestamp:
    - name: updated_at
      tolerance: 5 seconds
```

Column definitions may include:

- type/category,
- tolerance,
- normalization,
- null handling,
- inclusion/exclusion behavior,
- default check eligibility.

## Column-level check eligibility

A column may optionally specify which checks it participates in.

Example:

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
      checks:
        - sum_diff
        - sampled_value_match
```

This means `revenue` can be used by those checks.

This is useful when a numeric column should be included in aggregate checks but excluded from row-level value comparison, or vice versa.

## Metrics

Some reconciliation is metric-based rather than row-value based.

Metrics are explicit aggregate comparisons.

Example:

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

Grouped metric example:

```yaml
metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01
```

Use `metrics` when the contract should explicitly state aggregate comparisons rather than relying on a check pack to infer them from column metadata.

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
  - type: row_count_diff
    severity: error

  - type: sum_diff
    name: revenue_sum
    column: revenue
    tolerance: 0.01
    severity: error
```

Check packs are preferred for standardization. Explicit checks are preferred when a contract needs precise behavior.

## Check packs and column metadata

A check pack may use column metadata to decide which checks to run.

Example:

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01

checks:
  use:
    - recon_core.aggregate_equivalence
```

Possible interpretation:

- `aggregate_equivalence` sees numeric column `revenue`,
- it creates a `sum_diff` check for `revenue`,
- it uses tolerance `0.01`.

This behavior must be documented by each check pack.

Check packs should not silently run surprising checks. Their expansion should be visible in compiled artifacts.

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

This makes behavior unambiguous.

## Sampling

Sampling can be defined as a contract default:

```yaml
sampling:
  default_policy: stable_hash_5_percent
```

But individual checks should be able to override sampling:

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

This matters because different checks have different cost and meaning.

For example:

- `row_count_diff` may run on full data,
- `sum_diff` may run on full data,
- `row_diff` may run on a deterministic sample,
- CDC checks may run on an incremental window,
- previous-failure checks may run only on failed keys.

## Sampling levels

Recon should support sampling at multiple levels.

### Contract-level default

```yaml
sampling:
  default_policy: stable_hash_5_percent
```

### Check-level override

```yaml
checks:
  - type: row_diff
    sampling: stable_hash_5_percent
```

### Check-pack default

A check pack may define default sampling behavior.

Example:

```yaml
checks:
  use:
    - name: recon_core.cdc_equivalence
      sampling: latest_changed_records
```

### Full-data override

Some checks should explicitly use full data:

```yaml
checks:
  - type: sum_diff
    column: revenue
    sampling: full
```

## Tolerances

Contracts may reference a tolerance policy:

```yaml
tolerance_policy: finance
```

or define local overrides.

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

Precedence should be explicit. A recommended order:

1. check-level override,
2. column-level setting,
3. contract tolerance policy,
4. project default tolerance policy,
5. framework default.

## Evidence

Evidence settings define output behavior.

```yaml
evidence:
  level: detailed
  store_failures: true
  max_failure_rows: 1000
  report: html
```

Evidence settings may apply globally, but checks may need overrides later.

Example:

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

These help with filtering, routing, and reporting.

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

- `error` failures cause non-zero exit.
- `warn` failures are reported but may not fail the run.
- `info` checks produce evidence only.

## Validation rules

Recon should validate contracts before execution:

- `name` required,
- source and target required,
- exactly one of `relation` or `query` per endpoint,
- keys required for row-level checks,
- referenced sample policy exists,
- referenced check pack exists,
- tolerance syntax is valid,
- adapter capabilities are sufficient.

## Compiled contract

Recon should eventually compile contracts into an explicit execution plan.

The compiled plan should show:

- which check packs expanded,
- which atomic checks will run,
- which columns each check uses,
- which sampling policy each check uses,
- which tolerances each check uses,
- which evidence will be captured.

This prevents ambiguity between `columns`, `checks`, and `sampling`.

## Design principle

Contracts should be readable and declarative, but execution should be explicit after compilation.

Users define the equivalence agreement. Recon compiles it into checks and produces evidence.
