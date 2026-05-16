# Recon Core

Recon Core is the open-source Reconciliation as Code framework for proving data equivalence across CDC pipelines, warehouse migrations, pipeline refactors, medallion layers, and business logic rewrites.

Recon helps data teams define source-target equivalence in code, run repeatable checks, and generate evidence that shows what matched, what failed, and why.

## Why Recon

Data teams often need to prove that one output matches another:

```text
source database -> warehouse replica
old warehouse output -> new warehouse output
Bronze layer -> Silver layer
old business metric -> new business metric
```

This work is often handled with ad hoc SQL, spreadsheets, screenshots, manual QA, and tickets.

Recon turns that workflow into versioned contracts, reusable checks, explicit sampling rules, tolerance policies, schema policies, and evidence artifacts.

## What Recon is for

Recon is for:

- CDC validation,
- source-target reconciliation,
- warehouse migration validation,
- pipeline refactor validation,
- medallion layer reconciliation,
- business logic equivalence,
- sign-off evidence before production cutover.

## What Recon is not

Recon is not:

- a generic data quality platform,
- an ingestion or CDC movement tool,
- an MDM or fuzzy matching platform,
- an automatic data repair tool.

Recon complements transformation, ingestion, and data quality tools by focusing on source-target equivalence.

## Core idea

The main object in Recon is an **equivalence contract**.

A contract defines:

- source output,
- target output,
- grain and keys,
- columns and metrics,
- checks and check packs,
- sampling,
- tolerances,
- schema behavior,
- CDC behavior,
- evidence.

Example:

```yaml
version: 1

name: customer_revenue

source:
  connection: legacy
  relation: qa.v_customer_revenue_compare

target:
  connection: warehouse
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
    - recon_core.aggregate_equivalence

sampling:
  default_policy: full

evidence:
  level: detailed
  store_failures: true
```

## Workflow

Recon is designed around a parse, compile, run workflow:

```text
authored project files
  -> recon parse
  -> recon compile
  -> recon run
  -> results and evidence
```

`recon parse` validates the project and writes a manifest.

`recon compile` expands contracts, defaults, check packs, metrics, sampling, tolerances, schema policies, and CDC settings into explicit artifacts.

`recon run` executes checks and writes results and evidence.

## Expected artifacts

Recon writes generated artifacts under gitignored directories:

```text
target/manifest.json
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
target/run_results.json
target/failures/
reports/
```

Authored contracts are versioned. Generated artifacts are not.

## Project status

Recon Core is being designed and built as an open-source framework. The public documentation in this repository defines the product direction, framework rules, and implementation expectations.

## Documentation

Start here:

- `docs/getting-started/quickstart.md`
- `docs/getting-started/installation.md`
- `docs/user-guide/equivalence-contracts.md`
- `docs/user-guide/cli.md`
- `docs/framework/`
- `docs/planning/`

## Contributing

Contributions should preserve Recon’s design principles:

- no silent all-column comparison,
- no hidden check-pack behavior,
- no unsafe row-level matching,
- no silent type coercion,
- evidence must show assumptions and scope,
- strict validation is better than misleading success.

Read `CONTRIBUTING.md` before contributing.
