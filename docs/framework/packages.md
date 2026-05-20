# Packages

## Purpose

This document defines Recon packages.

A Recon package is a reusable bundle of framework resources. It is different from a Python adapter package.

## Adapter packages vs Recon packages

Adapter packages are Python packages installed with pip, such as `recon-snowflake`. They provide connectivity and dialect behavior.

Adapter packages implement connector types and render or execute typed check
plans for their system. They should not define Recon's comparison semantics.

Recon resource packages are installed by a future `recon deps` command. They provide check packs, sampling policies, tolerance policies, schema policies, macros, evidence templates, and examples.

## Why packages matter

Packages let the community share reconciliation standards such as CDC check packs, finance tolerance policies, medallion checks, migration validation packs, evidence templates, and schema ignore templates for common CDC tools.

## packages.yml

Future project file:

```yaml
packages:
  - package: recon-labs/recon-checks-cdc
    version: ">=0.1.0,<0.2.0"

  - git: "https://github.com/company/internal-recon-policies.git"
    revision: "v1.0.0"
```

## Installed directory

Packages may install into:

```text
recon_packages/
```

This should be gitignored.

## Package structure

```text
recon-checks-cdc/
  recon_package.yml
  check_packs/
    cdc_equivalence.yml
  sample_policies/
    latest_changed_records.yml
  tolerances/
    default_cdc.yml
  schema_policies/
    common_cdc_metadata.yml
  macros/
    normalize_timestamp.sql
  docs/
    README.md
```

## Official packages

Possible official packages include `recon-checks-cdc`, `recon-checks-migration`, `recon-checks-medallion`, `recon-policies-sampling`, `recon-policies-tolerances`, and `recon-evidence-templates`.

## Community packages

Community packages may include domain-specific standards such as healthcare claims, ERP ledger checks, insurance policy validation, or CDC metadata ignore policies for specific ingestion vendors.

## Design rule

Packages should share reusable logic, not private project mappings.

Good package content includes generic CDC check packs, standard sampling policies, evidence templates, and schema ignore policies for known technical metadata columns.

Bad package content includes private table names, credentials, and customer data.

## Design principle

Core provides primitives. Packages provide reusable standards.
