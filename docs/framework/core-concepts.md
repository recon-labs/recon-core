# Core Concepts

## Purpose

This document defines the core framework concepts in Recon Core.

Recon is a Reconciliation as Code framework. It is organized around **equivalence contracts**, not isolated one-off tests.

## Reconciliation as Code

Reconciliation as Code means reconciliation logic is versioned in Git, readable by humans, executable by a CLI, reusable through checks and packages, repeatable in CI or orchestration, and evidence-producing.

The goal is to replace one-off SQL, spreadsheet comparison, screenshots, and manual reruns with structured contracts, policies, checks, compiled plans, and evidence artifacts.

## Equivalence contract

The core object in Recon is the **equivalence contract**.

An equivalence contract defines what it means for a source and target output to match. It defines source output, target output, comparison grain, key columns, comparable columns, metrics, tolerances, checks and check packs, sampling policy, schema policy, CDC behavior, evidence policy, ownership, severity, and tags.

A contract is the durable definition of source-target equivalence.

## Source and target

A **source** is the baseline output. It may be an application table, warehouse table, view, query, old pipeline output, or previous business logic output.

A **target** is the output being validated. It may be a replicated warehouse table, new model output, transformed layer, or new platform output.

Source and target are roles in a contract. They do not always mean “application DB” and “warehouse.”

## Relation and query

A **relation** is a table or view address that Recon can query.

```yaml
source:
  relation: recon.v_orders_compare
```

A **query** is explicit SQL used as source or target output.

```yaml
target:
  query: |
    select ...
```

Recon should support both. The first implementation can prioritize relations/views, but custom query support is required for real-world flexibility, including surrogate-key translation and canonical comparison outputs.

## Grain and keys

The **grain** is the business level at which records are compared.

Examples include one row per customer, one row per order, or one row per customer/month.

`grain.keys` identify matching records at that grain.

```yaml
grain:
  keys:
    - customer_business_key
    - month
```

`grain.keys` are not trusted blindly. They are a claim that the selected keys uniquely identify comparable rows. Row-level checks must validate that claim before running.

## Keys versus segmenting columns

`grain.keys` are row identity.

`metrics.group_by` is segmentation for aggregate comparison.

```yaml
metrics:
  - name: revenue_by_country_status
    type: sum
    column: revenue
    group_by:
      - country
      - status
```

`country` and `status` are segmenting dimensions here, not row-level keys.

## Surrogate keys

A common reconciliation challenge is that source and target use different physical keys.

```text
source.customer_id != target.customer_sk
```

Recon should compare canonical business outputs instead of forcing generated surrogate keys to match. Users can expose canonical keys through source/target compare views or custom queries.

## Columns

Columns define eligible comparison fields and their rules.

Columns do **not** automatically cause checks to run.

If one or two columns are defined, check packs should use only those eligible columns. Recon should not silently compare every column in a relation.

If users want all columns, they must request that explicitly.

## Metrics

Metrics are named aggregate comparisons.

Unlike columns, metrics do cause aggregate checks to be compiled.

```yaml
metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
```

## Checks and check packs

A **check** is an atomic reconciliation operation such as row count diff, missing keys, aggregate sum diff, sampled value comparison, or schema compatibility.

A **check pack** is a reusable group of checks, such as a basic equivalence pack or CDC equivalence pack.

Check packs must expand into explicit compiled checks. Hidden behavior is not acceptable.

## Sampling policy

A **sampling policy** defines which records are included in comparison. It should be reusable and separate from individual checks.

Examples include deterministic hash, incremental window, persisted random, previous failures, and full data.

Sampling does not remove key uniqueness requirements for row-level value checks.

## Tolerance policy

A **tolerance policy** defines acceptable numeric, timestamp, string, or null differences.

Tolerance behavior should be explicit. Recon should not silently coerce incompatible types.

## Schema policy

A **schema policy** defines how structure should be compared, including expected columns, type compatibility, precision/scale compatibility, and explicitly ignored technical columns.

CDC tools often add target-only technical columns. Schema checks should be strict by default but support explicit ignore lists and patterns.

## CDC policy

A **CDC policy** defines how change data capture behavior is represented.

CDC reconciliation must not assume one delete mode or operation style. It should support explicit configuration for hard deletes, soft deletes, operation columns, tombstones, timestamp windows, batch IDs, and later SCD2-style history.

## Evidence

Evidence is the set of artifacts from a run: terminal summary, JSON results, CSV mismatches, HTML reports, result tables, compiled SQL, compiled checks, and sample keys.

Evidence is first-class.

## Parse, compile, and run

Recon should separate authored configuration from generated artifacts.

```text
parse   = project graph + structural validation
compile = human-readable resolved execution plan + compiled SQL/check queries
run     = execution + results + evidence
```

Generated artifacts should live under gitignored `target/` and `reports/`.

## Adapter

An adapter provides system-specific behavior: connection, dialect, metadata queries, quoting, hashing, timestamps, limits, and capability declarations.

Long term, adapters should split into packages such as `recon-snowflake` and `recon-postgres`.

## Package

A Recon package is a reusable bundle of check packs, sampling policies, tolerance policies, macros, evidence templates, schema policies, or examples.

## State

State stores information from prior runs: watermarks, sample keys, previous failures, and run history.

State is essential for CDC and continuous validation.

## Design principle

Recon compares canonical outputs. Users define business meaning; Recon validates unsafe assumptions, compiles explicit execution plans, runs checks, and produces evidence.
