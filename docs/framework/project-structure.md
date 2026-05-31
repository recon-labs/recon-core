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

This file is a future project resource. Its syntax and semantics are not locked
yet. Before implementation, Recon should define how selectors match contracts,
how `--select` and `--exclude` compose, and how partial compile/run artifacts
record selected scope.

## `connections/`

Contains connection examples.

Commit `connections/profiles.yml.example`.

Ignore `connections/profiles.yml`.

Profile files follow the selected-profile and selected-target model defined by
ADR 0020. The selected target is the active environment and contains named
connections used by contract `source.connection` and `target.connection`
fields. Initial adapter-aware behavior renders only referenced named
connections and supports `env_var('NAME')` plus
`env_var('NAME', 'default')`.

## `endpoints/`

Optional reusable named source/target endpoints.

```yaml
endpoints:
  - name: legacy_customer_revenue
    connection: redshift_legacy
    relation: qa.v_customer_revenue_compare
```

Contracts may reference endpoints later.

Endpoint reference syntax and execution semantics are future work. Initial
endpoint resources are local-only because endpoints usually contain
project-specific connection names and relation/query assumptions.

## `contracts/`

Contains equivalence contracts.

One contract per file and multiple contracts per file should both be supported.
Parser support for multiple contract files and simple multi-contract YAML files
does not imply selector support; selecting subsets for compile/run is a
separate future CLI design.

## `check_packs/`

Local reusable check packs.

Package and framework check packs must be referenced with a namespace, such as
`recon_core.basic_equivalence`. Unqualified resource references resolve only to
local project resources.

Current `recon parse` behavior indexes local check-pack files as source-file
metadata in `target/manifest.json`. Local check-pack file schemas and execution
semantics are future work.

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

Macro files are a future extension surface. They may be discovered and
checksummed by the resource loader as source files, but Recon does not parse,
render, or execute macros until macro semantics are locked. Macros must not
become the primary comparison engine.

## `reports/`

Generated human reports. Should be gitignored.

## `target/`

Generated machine and human-readable compiled artifacts. Should be gitignored.

Possible contents:

```text
target/manifest.json
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/   # when recon compile --render-sql succeeds
target/run_results.json
target/failures/
target/sample_keys/
```

## `state/`

Local state. Should be gitignored.

## `recon init`

`recon init` creates the starter project structure for a new Recon project.

The starter includes the current contract-loading paths plus future
local-resource directories such as `check_packs/` and `macros/`. Those
directories are created for project consistency. Current parse behavior indexes
local resource source files in `target/manifest.json`; compile behavior still
parses and compiles contract resources only.

## Design principle

A Recon project should feel like a professional framework project, not a pile of ad hoc reconciliation scripts.
