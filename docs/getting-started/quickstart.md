# Quickstart

## Goal

This guide shows the intended first Recon workflow.

The user defines an equivalence contract, compiles it into an explicit execution plan, runs checks, and reviews evidence.

Current pre-alpha status:

- `recon init` and `recon parse` are implemented.
- `recon compile` and `recon run` are not implemented yet.

## Create a project

Expected command:

```bash
recon init ecommerce_recon
cd ecommerce_recon
```

Expected starter structure:

```text
recon_project.yml
.gitignore
connections/
  profiles.yml.example
contracts/
sample_policies/
tolerances/
schema_policies/
target/
reports/
state/
```

## Configure connections

Copy the example profile:

```bash
cp connections/profiles.yml.example connections/profiles.yml
```

Use environment variables for secrets.

```yaml
legacy:
  type: postgres
  host: "{{ env_var('LEGACY_HOST') }}"
  user: "{{ env_var('LEGACY_USER') }}"
  password: "{{ env_var('LEGACY_PASSWORD') }}"
  database: analytics

warehouse:
  type: snowflake
  account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
  user: "{{ env_var('SNOWFLAKE_USER') }}"
  password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
  database: analytics
```

Do not commit real profiles.

## Create a contract

Create:

```text
contracts/customer_revenue.yml
```

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

## Parse

```bash
recon parse
```

Expected output:

```text
target/manifest.json
```

Current `recon parse` validates authored structure and writes a manifest. It
does not compile checks, run queries, or produce evidence.

## Compile

This command is planned but not implemented yet.

```bash
recon compile
```

Expected output:

```text
target/compiled_contracts/customer_revenue.yml
target/compiled_checks/customer_revenue.yml
target/compiled_sql/customer_revenue/
```

Use compiled artifacts to inspect exactly what Recon will run.

## Run

This command is planned but not implemented yet.

```bash
recon run
```

Expected output:

```text
target/run_results.json
target/failures/
reports/
```

## Review evidence

Review:

```text
target/run_results.json
reports/customer_revenue.html
```

The report should show:

- which checks ran,
- which checks passed or failed,
- whether each check used full data or sampling,
- which tolerances applied,
- which schema ignores applied,
- which rows or metrics failed.
- which checks were blocked by key safety checks.

## Important safety rules

Recon should not silently compare all columns.

Recon should not run row-level comparisons unless keys are defined, non-null, and unique.

CDC propagation checks should declare `cdc.keys`; Recon should not silently
reuse `grain.keys` for CDC update or delete validation.

Recon should not hide check-pack expansion.

Recon should show generated behavior in compiled artifacts.
