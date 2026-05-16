# Product Vision

## One-line vision

**Recon is the open-source Reconciliation as Code framework for proving data equivalence across CDC pipelines, migrations, refactors, medallion layers, and warehouse workflows.**

## Why Recon exists

Modern data systems constantly move and reshape data:

```text
source database
  -> CDC / ingestion / replication
  -> warehouse / lakehouse
  -> transformations
  -> analytics / AI / operations
```

Every movement creates a trust question:

> Does the target data still match what it is supposed to mirror, replace, or validate against?

Today, many teams answer that question manually with SQL, spreadsheets, screenshots, Slack threads, and Jira tickets. Recon exists to turn that work into a repeatable engineering practice.

## Product promise

Recon lets teams:

1. define source-target equivalence in code,
2. run repeatable reconciliation checks,
3. capture mismatch evidence,
4. rerun after fixes,
5. generate sign-off-ready artifacts.

## Category

Recon defines and serves the category:

> **Reconciliation as Code**

This means reconciliation logic should be versioned, reviewable, testable, reusable, automatable, and observable.

## Core object

The core object in Recon is the **equivalence contract**.

An equivalence contract defines:

- source dataset,
- target dataset,
- matching keys / grain,
- columns or metrics to compare,
- tolerances,
- sampling policy,
- evidence policy,
- ownership and severity.

Recon does not guess business meaning. Users define what equivalence means for their use case.

## Mental model

Data Quality asks:

> Is this dataset healthy?

Recon asks:

> Does this dataset match what it is supposed to mirror, replace, or validate against?

Both are important. Recon focuses on the second question.

## Strategic analogy

> dbt is for transforming data as code. Recon is for proving data equivalence as code.

This analogy is directional, not literal. Recon should learn from dbt’s mature open-source ergonomics: CLI-first workflow, project structure, packages, adapters, selectors, docs, and artifacts. Recon’s domain is different: equivalence, reconciliation, evidence, and source-target validation.

## Long-term vision

Recon should become the first tool data teams think of when they need to prove:

```text
source == target
old output == new output
replica == source
bronze/silver/gold layers reconcile
business metric rewrite is equivalent
```

Long term, Recon should support an ecosystem:

- `recon-core` as the framework brain,
- adapter packages such as `recon-snowflake`, `recon-postgres`, `recon-bigquery`,
- check-pack packages such as `recon-checks-cdc`,
- sampling and tolerance policy packages,
- Recon Hub for community discovery,
- optional cloud/evidence workflows later.

## Non-negotiable product principles

Recon must remain:

- open-source-first,
- developer-friendly,
- YAML/config-driven,
- evidence-producing,
- orchestration-friendly,
- adapter-based,
- package-extensible,
- clear about scope.

Recon must not drift into being:

- a generic data quality platform,
- a CDC/ingestion tool,
- a dbt replacement,
- a dashboarding product first,
- a fuzzy entity matching / MDM tool,
- a one-off table diff script.
