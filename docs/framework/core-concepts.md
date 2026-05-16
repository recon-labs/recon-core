# Core Concepts

## Purpose

This document defines the core framework concepts in Recon Core.

Recon is a Reconciliation as Code framework. It is organized around **equivalence contracts**, not isolated one-off tests.

## Reconciliation as Code

Reconciliation as Code means reconciliation logic is:

- versioned in Git,
- readable by humans,
- executable by a CLI,
- reusable through checks and packages,
- repeatable in CI or orchestration,
- evidence-producing.

The goal is to replace one-off SQL, spreadsheet comparison, screenshots, and manual reruns with structured contracts, policies, checks, and artifacts.

## Equivalence contract

The core object in Recon is the **equivalence contract**.

An equivalence contract defines what it means for a source and target output to match.

It defines:

- source output,
- target output,
- comparison grain,
- key columns,
- compare columns,
- metrics,
- tolerances,
- checks,
- sampling policy,
- evidence policy,
- ownership and severity.

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

Recon should support both. The first implementation can prioritize relations/views, but custom query support is required for real-world flexibility.

## Grain and keys

The **grain** is the business level at which records are compared.

Examples:

- one row per customer,
- one row per order,
- one row per customer/month.

Keys identify matching records at that grain.

```yaml
grain:
  keys:
    - customer_business_key
    - month
```

Recon should prefer business keys or canonical keys, not generated surrogate keys.

## Surrogate keys

A common reconciliation challenge is that source and target use different physical keys.

Example:

```text
source.customer_id != target.customer_sk
```

Recon should compare canonical business outputs instead of forcing surrogate keys to match.

## Checks

A **check** is an atomic reconciliation operation such as row count diff, missing keys, aggregate sum diff, or sampled value comparison.

## Check pack

A **check pack** is a reusable group of checks, such as a basic equivalence pack or CDC equivalence pack.

## Sampling policy

A **sampling policy** defines which records are included in comparison. It should be reusable and separate from individual checks.

Examples:

- deterministic hash,
- incremental window,
- persisted random,
- previous failures.

## Tolerance policy

A **tolerance policy** defines acceptable numeric, timestamp, string, or null differences.

## Evidence

Evidence is the set of artifacts from a run: terminal summary, JSON results, CSV mismatches, HTML reports, result tables, compiled SQL, and sample keys.

Evidence is first-class.

## Adapter

An adapter provides system-specific behavior: connection, dialect, metadata queries, quoting, hashing, timestamps, limits, and capability declarations.

Long term, adapters should split into packages such as `recon-snowflake` and `recon-postgres`.

## Package

A Recon package is a reusable bundle of check packs, sampling policies, tolerance policies, macros, evidence templates, or examples.

## State

State stores information from prior runs: watermarks, sample keys, previous failures, and run history.

State is essential for CDC and continuous validation.

## Design principle

Recon compares canonical outputs. Users define business meaning; Recon executes the contract and produces evidence.
