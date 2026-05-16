# Project Structure

## Purpose

This document defines the recommended structure of a Recon project.

A Recon project should scale from one contract to hundreds without becoming a folder of one-off scripts.

## Recommended structure

```text
recon_project/
  recon_project.yml
  packages.yml
  selectors.yml

  connections/
    profiles.yml.example

  endpoints/
    sources.yml
    targets.yml

  contracts/
    customer/
      customer_revenue.yml
      customer_status.yml
    orders/
      orders_cdc.yml
      order_lines.yml

  check_packs/
    company_standard.yml

  sample_policies/
    latest_changed_records.yml
    stable_hash_5_percent.yml
    previous_failures.yml

  tolerances/
    default.yml
    finance.yml

  schema_policies/
    default.yml
    cdc_metadata.yml

  macros/
    sql/
      normalize_string.sql
      canonical_timestamp.sql

  reports/
  target/
  state/
  docs/
```

## `recon_project.yml`

Project-level config.

```yaml
name: ecommerce_recon
version: 0.1.0
config-version: 1

profile: prod

contract-paths:
  - contracts

sample-policy-paths:
  - sample_policies

tolerance-policy-paths:
  - tolerances

schema-policy-paths:
  - schema_policies

check-pack-paths:
  - check_packs

macro-paths:
  - macros

target-path: target
report-path: reports
```

## `packages.yml`

Future dependency file for Recon packages.

## `selectors.yml`

Named selectors for running groups of contracts.

## `connections/`

Contains connection examples.

Commit `connections/profiles.yml.example`.

Ignore `connections/profiles.yml`.

## `endpoints/`

Optional reusable named source/target endpoints.

```yaml
endpoints:
  - name: legacy_customer_revenue
    connection: redshift_legacy
    relation: qa.v_customer_revenue_compare
```

Contracts may reference endpoints later.

## `contracts/`

Contains equivalence contracts.

One contract per file and multiple contracts per file should both be supported.

## `check_packs/`

Local reusable check packs.

## `sample_policies/`

Reusable sampling definitions.

Sampling should not be repeated in every contract.

## `tolerances/`

Reusable tolerance and normalization definitions.

## `schema_policies/`

Reusable schema comparison policies.

Useful for ignoring known CDC/ingestion metadata columns.

## `macros/`

Reusable SQL snippets or templates for normalization.

## `reports/`

Generated human reports. Should be gitignored.

## `target/`

Generated machine and human-readable compiled artifacts. Should be gitignored.

Possible contents:

```text
target/manifest.json
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
target/run_results.json
target/failures/
target/sample_keys/
```

## `state/`

Local state. Should be gitignored.

## `recon init`

The future command should create a starter project structure.

## Design principle

A Recon project should feel like a professional framework project, not a pile of ad hoc reconciliation scripts.
