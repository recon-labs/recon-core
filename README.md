<h1 align="center">
  <img src="assets/recon-core-logo.png" alt="Recon Core logo" width="80"><br>
  Recon Core
</h1>

<p align="center">
  Open-source Reconciliation as Code framework for proving source-target data equivalence.
</p>

<p align="center">
  <img alt="Status" src="https://img.shields.io/badge/status-pre--alpha-orange">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue">
  <img alt="CI" src="https://github.com/recon-labs/recon-core/actions/workflows/ci.yml/badge.svg">
</p>

Recon Core helps data teams define equivalence in versioned contracts, compile
explicit execution plans, run repeatable checks, and generate evidence that
shows what matched, what failed, and why.

## Current Status

Recon Core is pre-alpha.

Implemented today:

- Python package skeleton,
- `recon --version`,
- `recon init <project_name>`,
- `recon parse`,
- duplicate-key-safe YAML loading for authored resources,
- structural equivalence contract parsing,
- `target/manifest.json` generation,
- structured service results and diagnostics,
- CLI command registration for `compile` and `run`.

Not implemented yet:

- `recon compile`,
- `recon run`,
- adapter execution,
- check engine,
- evidence writers.

The documentation in this repository defines the intended framework behavior.
The current implementation is being built milestone by milestone.

## What Recon Is For

Recon is for proving that one data output matches another according to an
explicit contract:

```text
source database -> warehouse replica
old warehouse output -> new warehouse output
Bronze layer -> Silver layer
old business metric -> new business metric
```

Good use cases include:

- CDC validation,
- source-target reconciliation,
- warehouse migration validation,
- pipeline refactor validation,
- medallion layer reconciliation,
- business logic equivalence,
- sign-off evidence before production cutover.

## What Recon Is Not

Recon is not:

- a generic data quality platform,
- an ingestion or CDC movement tool,
- a dbt replacement,
- an MDM or fuzzy matching platform,
- an automatic data repair tool.

Recon complements transformation, ingestion, and data quality tools by focusing
on source-target equivalence.

## Quick Start

For local development from this repository:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
recon --version
recon init ecommerce_recon
cd ecommerce_recon
recon parse
```

The generated starter project includes:

```text
ecommerce_recon/
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

`recon parse` now performs structural project parsing and writes
`target/manifest.json`. `recon compile` and `recon run` are registered commands,
but they currently return a clear not-implemented diagnostic.

## Core Idea

The main object in Recon is an **equivalence contract**.

An equivalence contract defines:

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

Example authored contract:

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

## Intended Workflow

Recon is designed around a parse, compile, run workflow:

```text
authored project files
  -> recon parse
  -> recon compile
  -> recon run
  -> results and evidence
```

The intended command responsibilities are:

- `recon parse` validates project files and writes `target/manifest.json`.
- `recon compile` expands contracts, defaults, check packs, metrics, sampling,
  tolerances, schema policies, and CDC settings into explicit artifacts.
- `recon run` executes compiled checks and writes results and evidence.

Current `recon parse` validation is intentionally structural. It validates YAML
syntax, contract file discovery, required contract fields, endpoint shape,
unknown top-level contract fields, simple multi-contract files, and duplicate
contract names. Compile-time behavior such as check-pack expansion, metric
compilation, sampling resolution, tolerance precedence, schema policy
resolution, CDC validation, adapter checks, and row-level key uniqueness is
still future work.

Expected generated artifacts:

```text
target/manifest.json
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
target/run_results.json
target/failures/
reports/
state/
```

Authored contracts are versioned. Generated artifacts are not.

## Repository Map

```text
src/recon_core/        Python package source
tests/                 Unit and CLI tests
docs/framework/        Framework concepts and public behavior
docs/architecture/     System boundaries and package layout
docs/implementation/   Implementation guidance and build order
docs/decisions/        Architecture decision records
examples/              Authored example Recon projects
```

## Documentation

Start here:

- [Quickstart](docs/getting-started/quickstart.md)
- [Installation](docs/getting-started/installation.md)
- [CLI guide](docs/user-guide/cli.md)
- [Equivalence contracts](docs/user-guide/equivalence-contracts.md)
- [Framework concepts](docs/framework/core-concepts.md)
- [MVP build order](docs/implementation/mvp-build-order.md)
- [Architecture decisions](docs/decisions/README.md)

## Contributing

Set up local development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
mypy src
```

Before opening a pull request, read [CONTRIBUTING.md](CONTRIBUTING.md) and the
relevant docs under `docs/framework/`, `docs/architecture/`, and
`docs/implementation/`.

Changes to public contract syntax, artifact formats, validation defaults,
adapter interfaces, or evidence behavior may need an ADR under
`docs/decisions/`.

## Security and Generated Artifacts

Do not commit credentials, connection profiles, secrets, customer data, or real
production evidence.

Keep these paths local or generated:

```text
connections/profiles.yml
.env
target/
reports/
state/
recon_packages/
```

Generated evidence can contain sensitive values. Use fake data in examples and
keep generated outputs out of Git.
