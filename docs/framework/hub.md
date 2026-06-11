# Recon Hub

## Purpose

Recon Hub is the future discovery and metadata layer for Recon packages, adapters, policies, templates, and examples.

## Why Hub matters

A framework becomes stronger when users can discover and reuse community standards.

Recon Hub should help users find adapters, check packs, sampling policies, tolerance policies, schema policies, evidence templates, domain packages, and examples.

## First implementation

Hub does not need to be a full app initially.

A first version can be a repo:

```text
recon-hub-index/
  packages/
  adapters/
  schemas/
```

Submissions can happen by pull request.

## Metadata example

```yaml
name: recon-labs/recon-checks-cdc
type: check_pack
description: Standard CDC reconciliation checks and policies.
repository: https://github.com/recon-labs/recon-checks-cdc
compatibility:
  recon_core: ">=0.1.0,<0.2.0"
resources:
  - check_packs
  - sample_policies
  - tolerance_policies
  - schema_policies
trust_level: official
```

## Trust levels

Possible levels:

- official,
- trusted,
- community,
- experimental.

## Package categories

Package categories may include adapter, check pack, sample policy, tolerance policy, schema policy, evidence template, example project, and domain package.

## Relationship to `recon deps`

Future `recon deps` may use Hub metadata to install packages.

## Relationship to adapters

Adapters may eventually be listed in Hub but installed through Python packaging
after adapter package and compatibility gates are satisfied.

```bash
pip install recon-snowflake
```

This package name is illustrative and does not imply an official external
adapter package is available today.

## Design principle

Recon Hub should help Recon become a community standard, but it should not block the core CLI.
