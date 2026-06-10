# Positioning

## Category statement

**Recon is Reconciliation as Code for modern data teams.**

## Short positioning

Define source-target equivalence in YAML. Run repeatable checks across systems. Generate evidence for every CDC pipeline, migration, and data refactor.

## Longer positioning

Recon is an open-source framework that helps data teams prove that two data outputs are equivalent. It is designed for CDC validation, warehouse migrations, pipeline refactors, medallion-layer transformations, and business logic rewrites.

Recon turns manual SQL comparisons, spreadsheets, tickets, and reruns into versioned equivalence contracts and repeatable evidence.

## Framing

> Transformation as Code is for building data outputs. Reconciliation as Code is
> for proving data outputs are equivalent.

This explains the workflow ambition: make a messy data engineering practice
structured, versioned, reusable, and community-driven.

## What Recon should be first in mind for

Recon should be the first tool people think of when they say:

- “We need to prove the warehouse target matches the operational source after CDC.”
- “We need to prove the replicated target matches the source after migration.”
- “We need to compare old warehouse outputs to new warehouse outputs.”
- “We rewrote a batch job and need to prove the result is the same.”
- “Analysts are manually comparing old vs new pipeline outputs.”
- “We need audit evidence before cutover.”
- “We need continuous validation that source and warehouse stay aligned.”

## Tagline options

Primary:

> Reconciliation as Code.

Expanded:

> Define equivalence. Run checks. Generate evidence.

Developer-focused:

> Source-target validation, versioned in Git.

Migration-focused:

> Prove your new data output matches the old one.

CDC-focused:

> Continuously prove your warehouse matches the source.

## Differentiation

### Versus generic data quality

Generic DQ asks whether one dataset is healthy.

Recon asks whether two datasets are equivalent.

### Versus table diff tools

Table diff tools compare data.

Recon defines contracts, policies, reusable checks, evidence, and an open project structure.

### Versus migration validation CLIs

Migration validation CLIs can compare systems.

Recon aims to be a broader Reconciliation as Code framework for migrations, CDC, refactors, layers, packages, evidence, and community standards.

### Versus transformation-framework tests

Transformation-framework tests are useful for warehouse-side assertions.

Recon focuses on source-target and old-new equivalence across systems or outputs.

### Versus CDC monitoring

CDC monitoring tells whether ingestion is running.

Recon tells whether the warehouse target is complete, fresh, and equivalent.

## Positioning guardrails

Do not position Recon as:

- generic data quality,
- observability platform,
- ingestion system,
- CDC connector,
- BI metrics layer,
- MDM tool,
- financial close platform.

Position Recon as:

- equivalence validation,
- source-target reconciliation,
- repeatable evidence,
- open-source framework,
- developer-first standard.

## Ideal public sentence

> Recon is the open-source Reconciliation as Code framework for proving data equivalence across CDC pipelines, warehouse migrations, pipeline refactors, and medallion-layer transformations.
