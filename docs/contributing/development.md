# Development Guide

## Local setup

Expected local setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Test command

Expected test command:

```bash
pytest
```

Adapter-aware DuckDB SQL renderer semantics require the optional DuckDB extra.
Run the CI-equivalent renderer gate with:

```bash
pip install -e ".[dev,duckdb]"
RECON_REQUIRE_DUCKDB_TESTS=1 pytest tests/adapters/test_duckdb_sql_renderer.py
```

## Code quality

Expected checks may include:

```bash
ruff check .
ruff format --check .
mypy .
pytest
```

Exact tooling should be defined in `pyproject.toml`.

## Development principles

Use test-driven development for non-trivial framework behavior.

Implement behavior in small pieces:

1. define expected behavior,
2. write tests,
3. implement,
4. update docs,
5. update examples when useful.

## Areas that need strong tests

Strong test coverage is required for:

- YAML loading,
- contract parsing,
- contract validation,
- check-pack expansion,
- metric compilation,
- typed check plan generation,
- sampling resolution,
- tolerance precedence,
- schema policy resolution,
- CDC policy validation,
- compiled artifact generation,
- check result models,
- adapter capability validation,
- adapter SQL rendering.

## Refactoring

If a requested feature reveals a bad design, propose the refactor first.

Do not layer complex behavior on top of an unstable model.

## Documentation

Implementation and documentation should stay aligned.

When public behavior changes, update the relevant docs in the same change.
