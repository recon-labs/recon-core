# Project Structure

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
    orders/
      orders_cdc.yml

  check_packs/
    company_standard.yml

  sample_policies/
    full.yml
    stable_hash_5_percent.yml
    latest_changed_records.yml

  tolerances/
    default.yml
    finance.yml

  schema_policies/
    default.yml
    cdc_metadata.yml

  macros/
    sql/

  target/
  reports/
  state/
```

## Versioned files

Version these:

```text
recon_project.yml
packages.yml
selectors.yml
connections/profiles.yml.example
contracts/
check_packs/
sample_policies/
tolerances/
schema_policies/
macros/
docs/
```

`selectors.yml` is a future project resource. Its syntax is not locked yet, and
`recon run --select` / `recon compile --select` are not implemented.

Current parse and compile behavior loads contract files only. The other
versioned resource directories are part of the project structure and future
resource-loading surface. Their reference validation and precedence rules are
designed in ADR 0017 but are not implemented yet.

## Ignored files

Ignore these:

```text
connections/profiles.yml
.env
target/
reports/
state/
recon_packages/
```

## `contracts/`

Contracts are the main source files.

They define source-target equivalence.

Recon can parse multiple contract files in a project. Simple multi-contract
YAML files are also supported by parse. Selecting a subset of contracts to
compile or run is a separate future selector feature.

## `sample_policies/`

Reusable sampling policies.

## `tolerances/`

Reusable tolerance and normalization policies.

## `schema_policies/`

Reusable schema comparison policies.

Useful for CDC technical columns.

## `target/`

Generated parse/compile/run artifacts.

Do not commit.

## `reports/`

Generated human-readable evidence.

Do not commit.

## `state/`

Local run state.

Do not commit.
