# Use Cases

## Overview

Recon is used whenever a team needs to prove that one data output matches another.

The most important phrase is:

> **old/source/expected output vs new/target/actual output**

## Use case 1: Continuous CDC validation

### Scenario

A company replicates operational data into a warehouse.

```text
SQL Server
  -> AWS DMS
  -> Snowpipe
  -> Snowflake Bronze
  -> Silver
  -> Gold
```

or:

```text
MongoDB
  -> CDC connector
  -> BigQuery
```

### Problem

The CDC job may show success, but records can still be missing, delayed, duplicated, or incorrectly updated.

### Recon value

Recon runs scheduled equivalence checks:

- count by time window,
- missing keys,
- extra keys,
- freshness lag,
- max updated timestamp,
- latest changed record comparison,
- previous failure retest,
- sample row/document diff.

### Example contract intent

```yaml
name: orders_cdc
source:
  relation: recon.v_orders_source_compare
target:
  relation: bronze.v_orders_target_compare
grain:
  keys:
    - order_id
sampling:
  policy: latest_changed_records
checks:
  use:
    - recon_core.cdc_equivalence
```

## Use case 2: Warehouse migration / platform modernization

### Scenario

A company moves from an old analytics platform to a new one.

```text
Redshift + Spark
  -> Snowflake + dbt/Snowpark
```

### Problem

The business expects the new platform to produce the same revenue, customer, order, and operational results as the old platform.

### Recon value

Recon validates old output vs new output:

- row count,
- missing business keys,
- extra keys,
- aggregate totals,
- numeric tolerances,
- sampled row diff,
- cutover evidence.

### Example language

This is a **data warehouse migration with parallel-run validation**.

## Use case 3: Pipeline refactor validation

### Scenario

A team rewrites a pipeline.

```text
old Spark job output
  vs
new dbt model output
```

### Problem

The implementation changed, but the expected business output did not.

### Recon value

Recon proves whether the new pipeline matches the old pipeline before cutover.

## Use case 4: Business logic rewrite validation

### Scenario

A company changes the implementation of a business metric.

Example:

```text
old revenue calculation
  vs
new revenue calculation
```

### Problem

The business needs to know whether the new logic intentionally or unintentionally changed outputs.

### Recon value

Recon compares metrics by grain:

- customer/month,
- country/date,
- product/category,
- account/period.

Recon captures mismatches and supports analyst-engineer fix loops.

## Use case 5: Medallion layer reconciliation

### Scenario

A data platform uses Bronze, Silver, and Gold layers.

```text
Bronze -> Silver -> Gold
```

### Problem

Each layer transforms data. Teams need to prove data is preserved, cleaned, reduced, or aggregated as expected.

### Recon value

Recon validates:

- Bronze matches source,
- Silver preserves key coverage,
- Gold aggregates match expected totals,
- freshness by layer,
- expected row reductions.

## Use case 6: Analyst QA automation

### Scenario

Analysts manually run SQL, compare spreadsheets, and file tickets when a new warehouse or model does not match the old one.

### Problem

The same checks are rerun manually after each engineering fix.

### Recon value

Recon turns analyst QA into versioned equivalence contracts and repeatable evidence.

## Use case 7: Regulatory or audit evidence

### Scenario

A regulated company changes a reporting pipeline or warehouse platform.

### Problem

The company needs evidence that the new system produces equivalent or approved results.

### Recon value

Recon produces structured run results, failure details, and sign-off-ready reports.

## Use case 8: Source-to-target monitoring for critical domains

### Scenario

A team has critical replicated domains:

- payments,
- orders,
- customers,
- claims,
- inventory,
- subscriptions.

### Problem

Missing or stale warehouse records create operational and business risk.

### Recon value

Recon runs recurring source-target equivalence checks with severity, sampling, and evidence.
