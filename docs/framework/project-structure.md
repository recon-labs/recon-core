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

```yaml
selectors:
  - name: cdc_gold
    definition:
      tags:
        - cdc
        - gold
```

## `connections/`

Contains connection examples.

Commit:

```text
connections/profiles.yml.example
```

Ignore:

```text
connections/profiles.yml
```

## `contracts/`

Contains equivalence contracts.

Contracts are the main user-authored resource.

## `check_packs/`

Local reusable check packs.

## `sample_policies/`

Reusable sampling definitions.

Sampling should not be repeated in every contract.

## `tolerances/`

Reusable tolerance definitions.

## `macros/`

Reusable SQL snippets or templates for normalization.

## `reports/`

Generated human reports. Should be gitignored.

## `target/`

Generated machine artifacts. Should be gitignored.

## `state/`

Local state. Should be gitignored.

## `recon init`

The future command should create a starter project structure.

## Design principle

A Recon project should feel like a professional framework project, not a pile of ad hoc reconciliation scripts.
