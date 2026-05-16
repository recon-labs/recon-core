# Competitive Landscape

## Purpose

This document explains how Recon relates to existing tools and why the product should exist.

The goal is not to attack other tools. The goal is to position Recon clearly.

## Main categories

Recon overlaps with several categories:

1. data quality frameworks,
2. source-target validation tools,
3. table diff tools,
4. migration validation utilities,
5. observability platforms,
6. dbt-style transformation/testing tools,
7. custom SQL/Python scripts.

Recon should not try to replace all of them.

## Soda

Soda provides data quality checks and has reconciliation capabilities in its broader product ecosystem.

Where Soda is strong:

- data quality checks,
- YAML-like check definitions,
- cloud history/alerts,
- source-target reconciliation features in paid/library contexts.

Recon opportunity:

- open-source-first Reconciliation as Code,
- developer-first equivalence contracts,
- project/package structure,
- evidence workflow,
- CDC/refactor/medallion use cases as first-class concepts.

Recon should not claim Soda is irrelevant. Soda validates the market.

## Great Expectations / GX

GX is a flexible validation framework.

Where GX is strong:

- expectations,
- validation results,
- Data Docs,
- Python flexibility,
- data quality workflows.

Recon opportunity:

- narrower focus on source-target equivalence,
- stronger reconciliation vocabulary,
- CDC and old-vs-new validation,
- evidence and equivalence contracts.

Recon should not become a general expectation framework.

## dbt tests

dbt provides tests, docs, macros, packages, and a mature developer workflow.

Where dbt is strong:

- transformations,
- warehouse SQL modeling,
- generic tests,
- documentation,
- packages,
- adapters.

Recon opportunity:

- compare across source/target outputs,
- validate old/new equivalence,
- support CDC and migration evidence,
- package reusable reconciliation logic.

Recon should learn from dbt’s project maturity, not compete with dbt’s transformation domain.

## Datafold / data diff tools

Datafold and similar tools provide strong data diff and migration validation capabilities.

Where they are strong:

- value-level diffs,
- CI impact checks,
- migration validation,
- commercial workflows.

Recon opportunity:

- open-source framework,
- Reconciliation as Code standard,
- reusable check packs,
- policies,
- evidence artifacts,
- community-driven ecosystem.

Recon should not be only a diff engine.

## Google Data Validation Tool / DVT

DVT is a source-target validation CLI.

Where DVT is strong:

- heterogeneous source-target validation,
- migration validation,
- practical CLI usage,
- many connectors.

Recon opportunity:

- broader framework model,
- equivalence contracts,
- package ecosystem,
- sampling/tolerance/evidence policies,
- developer-first project structure,
- CDC/refactor/medallion workflows.

Recon should respect DVT as a strong technical reference.

## Vendor migration validation tools

Cloud vendors and migration products may offer validation tools.

Where they are strong:

- platform-specific migrations,
- native integration,
- enterprise workflows.

Recon opportunity:

- vendor-neutral,
- open-source,
- project-based,
- extensible across sources, targets, and use cases.

## Custom scripts

The biggest competitor is not always a product. It is internal scripts.

Where scripts are strong:

- fast to write,
- tailored,
- no adoption process,
- solve one immediate problem.

Recon opportunity:

- standardize repeated work,
- version contracts,
- reuse checks,
- capture evidence,
- support reruns,
- reduce manual analyst QA,
- create a shared practice.

## Recon’s defensible angle

Recon should own the phrase:

> **Reconciliation as Code**

Recon should compete by being:

- open-source-first,
- developer-friendly,
- contract-driven,
- evidence-oriented,
- ecosystem-ready,
- focused on source-target equivalence.

## Strategic warning

If Recon becomes only a table diff CLI, the market is crowded.

If Recon becomes the standard for equivalence contracts, reusable reconciliation checks, sampling policies, evidence, and source-target workflows, the gap is real.
