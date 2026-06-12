# Quickstart

## Goal

This guide shows the intended first Recon workflow.

The user defines an equivalence contract, compiles it into an explicit execution plan, runs checks, and reviews evidence.

Current pre-alpha status:

- `recon init`, `recon parse`, and `recon compile` are implemented for the
  current compiler scope.
- `recon compile --render-sql` is implemented for DuckDB relation endpoints
  and the current typed check-plan operations.
- `recon run` loads existing compiled-check artifacts and returns explicit
  in-memory run/check statuses. It does not execute adapter-backed checks or
  write generated result, evidence, report, failure-detail, or state artifacts
  yet.
- Adapter-backed execution is planned to start with relation-backed row-count
  checks for source and target relations addressable from the same DuckDB
  connection context.

Install the DuckDB extra when you want to render SQL in this local workflow:

```bash
pip install -e ".[dev,duckdb]"
```

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
check_packs/
macros/
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
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: duckdb
            database: "{{ env_var('RECON_DUCKDB_PATH') }}"
          warehouse:
            type: duckdb
            database: "{{ env_var('RECON_DUCKDB_PATH') }}"
```

Do not commit real profiles.

The generated example profile uses `RECON_DUCKDB_PATH` for both named DuckDB
connections. Before running adapter-aware SQL rendering with that example, set
it to the same local DuckDB file path:

```bash
export RECON_DUCKDB_PATH=local.duckdb
```

You can also edit `connections/profiles.yml` to use a literal local path or an
`env_var` default instead.

For adapter-aware rendering, Recon renders only the selected profile target
and the named connections referenced by selected contracts. Missing
environment variables in unselected targets or unreferenced connections do not
fail contract-specific invocations.
For the current DuckDB renderer, source and target connection names may differ,
but they must resolve to the same DuckDB adapter connection config.

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

```bash
recon compile
```

Expected output:

```text
target/compiled_contracts/customer_revenue.yml
target/compiled_checks/customer_revenue.yml
```

Use compiled artifacts to inspect exactly what Recon will run. SQL files under
`target/compiled_sql/` are produced only by optional adapter-aware compile:

```bash
recon compile --render-sql
```

Current compile behavior expands `recon_core.basic_equivalence` and explicit
`sum` metrics into typed check plans. With `--render-sql`, Recon loads
`connections/profiles.yml`, validates the adapter boundary, and writes
DuckDB-rendered SQL for relation-backed source and target endpoints. Explicit
authored checks, adapter execution, run results, and evidence are still future
work.

## Run

Current `recon run` consumes compiled-check artifacts from
`target/compiled_checks/` and reports explicit in-memory results. Checks that
cannot execute in the current run boundary are reported as non-executable
instead of looking like passing evidence.

```bash
recon run
```

Current `recon run` does not parse authored contracts, recompile contracts,
open adapters, execute SQL, or write generated outputs.

Future generated result and evidence outputs remain planned for later result
and evidence work:

```text
target/run_results.json
target/failures/
reports/
```

## Review evidence

After run and evidence generation are implemented, review:

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
- which rows or metrics failed,
- which checks were blocked by key safety checks.

## Important safety rules

Recon should not silently compare all columns.

Recon should not run row-level comparisons unless keys are defined, non-null, and unique.

CDC propagation checks should declare `cdc.keys`; Recon should not silently
reuse `grain.keys` for CDC update or delete validation.

Recon should not hide check-pack expansion.

Recon should show generated behavior in compiled artifacts.
