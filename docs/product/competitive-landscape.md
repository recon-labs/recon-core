# Adjacent Categories

## Purpose

This document explains how Recon relates to adjacent tool categories and why the
product should exist.

The goal is to position Recon clearly by category and product scope.

## Main categories

Recon overlaps with several categories:

1. data quality frameworks,
2. source-target validation tools,
3. table diff tools,
4. migration validation utilities,
5. observability platforms,
6. transformation and warehouse-testing tools,
7. custom SQL/Python scripts.

Recon should not try to replace all of them.

## Data Quality Frameworks

Data quality frameworks provide dataset-local checks and may include broader
validation workflows.

Where they are strong:

- data quality checks,
- YAML-like check definitions,
- history and alerts,
- validation workflows.

Recon opportunity:

- open-source-first Reconciliation as Code,
- developer-first equivalence contracts,
- project/package structure,
- evidence workflow,
- CDC/refactor/medallion use cases as first-class concepts.

Recon should not become a general data quality framework.

## Flexible Validation Frameworks

Flexible validation frameworks are useful when teams need programmable
dataset-local validation.

Where they are strong:

- expectations,
- validation results,
- Python flexibility,
- data quality workflows.

Recon opportunity:

- narrower focus on source-target equivalence,
- stronger reconciliation vocabulary,
- CDC and old-vs-new validation,
- evidence and equivalence contracts.

Recon should not become a general expectation framework.

## Transformation-Framework Tests

Transformation frameworks often provide warehouse-side assertions, project
structure, documentation, packages, and adapters.

Where they are strong:

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

Recon should not compete with the transformation domain.

## Data Diff Tools

Data diff tools provide value-level comparison and migration validation
capabilities.

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

## Migration Validation CLIs

Migration validation CLIs compare systems during platform changes.

Where they are strong:

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

Recon should be broader than a one-purpose migration validation CLI.

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

The biggest alternative is not always a product. It is internal scripts.

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
