# Installation

## Python package

Recon Core is intended to be installed as a Python package.

Expected install command:

```bash
pip install recon-core
```

During local development, install from the repository:

```bash
pip install -e ".[dev]"
```

Adapter-aware SQL rendering with the in-core DuckDB local development adapter
requires the DuckDB extra:

```bash
pip install -e ".[dev,duckdb]"
```

## Python version

The supported Python versions should be defined in `pyproject.toml`.

A modern Python version should be preferred for type hints, packaging, and maintainability.

## Adapter packages

Long-term, production adapters should be installed separately.

Examples:

```bash
pip install recon-postgres
pip install recon-mysql
pip install recon-snowflake
pip install recon-bigquery
```

Current local development extra:

```bash
pip install "recon-core[duckdb]"
```

Other adapter extras or external adapter packages are future work.

## Verify installation

Expected command:

```bash
recon --version
```

## Project initialization

Expected command:

```bash
recon init ecommerce_recon
```

The command should create a starter Recon project with contracts, policies, profiles examples, and generated artifact folders ignored.

## Generated files

Recon should write generated files under:

```text
target/
reports/
state/
```

These directories should not be committed.
