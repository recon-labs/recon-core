# Repository Strategy

## Purpose

This document defines Recon Labs’ intended multi-repo strategy.

`recon-core` is the first repo and source of truth, but Recon is designed to become an ecosystem.

## Current decision

Start with `recon-core`.

This repo contains CLI, framework concepts, core docs, contract model, check engine, result model, evidence generation, base adapter interface, early examples, and foundational ADRs.

## Long-term repo categories

### Core runtime

```text
recon-core
```

### Adapter packages

```text
recon-postgres
recon-snowflake
recon-sqlserver
recon-bigquery
recon-mongodb
recon-databricks
recon-redshift
recon-oracle
```

### Adapter test kit

```text
recon-adapter-testkit
```

### Check and policy packages

```text
recon-checks-cdc
recon-checks-migration
recon-checks-medallion
recon-policies-sampling
recon-policies-tolerances
recon-evidence-templates
```

### Examples and docs

```text
recon-examples
recon-docs
```

These may split later if they grow large.

### Hub

```text
recon-hub-index
```

## Why not one repo forever

One repo forever creates unnecessary dependencies, adapter release coupling, CI complexity, core bloat, and harder community ownership.

## Why not many repos immediately

Many repos too early create coordination overhead, unstable interfaces, empty repos, and release complexity.

## Rollout

1. Start with `recon-core`.
2. Split `recon-postgres`, `recon-snowflake`, and `recon-adapter-testkit` after adapter interface stabilizes.
3. Add official check/policy packages.
4. Add `recon-hub-index`.
5. Add integrations such as `recon-airflow`.

## Source of truth

`recon-core` remains the source of truth for product definition, framework concepts, contract syntax, validation rules, ADRs, base interfaces, package rules, and adapter rules.

Other repos should reference `recon-core` rather than redefining the product model.

## Design principle

Build one serious core first, but design for an ecosystem from day one.
