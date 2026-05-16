# Packages

## Purpose

This document defines Recon packages.

A Recon package is a reusable bundle of framework resources. It is different from a Python adapter package.

## Adapter packages vs Recon packages

### Adapter packages

Python packages installed with pip:

```bash
pip install recon-snowflake
```

They provide connectivity and dialect behavior.

### Recon resource packages

Installed by a future `recon deps` command.

They provide:

- check packs,
- sampling policies,
- tolerance policies,
- macros,
- evidence templates,
- examples.

## Why packages matter

Packages let the community share reconciliation standards.

Examples:

- CDC check pack,
- finance tolerance policies,
- medallion checks,
- migration validation pack,
- evidence templates.

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
  macros/
    normalize_timestamp.sql
  docs/
    README.md
```

## Official packages

Possible official packages:

- `recon-checks-cdc`,
- `recon-checks-migration`,
- `recon-checks-medallion`,
- `recon-policies-sampling`,
- `recon-policies-tolerances`,
- `recon-evidence-templates`.

## Community packages

Community packages may include domain-specific standards.

Examples:

- healthcare claims,
- ERP ledger checks,
- insurance policy validation.

## Design rule

Packages should share reusable logic, not private project mappings.

Good:

- generic CDC check pack,
- standard sampling policy,
- evidence template.

Bad:

- private table names,
- credentials,
- customer data.

## Design principle

Core provides primitives. Packages provide reusable standards.
