# Adapters

## Purpose

This document defines Recon adapters.

Adapters allow Recon Core to work with different databases, warehouses, document stores, and query engines.

## Definition

An adapter handles system-specific behavior:

- connection,
- SQL dialect,
- identifier quoting,
- metadata queries,
- limit syntax,
- timestamp syntax,
- numeric casting,
- hashing syntax,
- temporary objects,
- capability declaration.

## Core vs adapter responsibilities

### recon-core owns

- CLI,
- project loading,
- contract parsing,
- check planning,
- result model,
- evidence generation,
- base adapter interface,
- extension mechanism.

### adapters own

- connection implementation,
- SQL compilation details,
- metadata access,
- dialect-specific functions,
- capability reporting,
- adapter-specific tests.

## Initial strategy

Early `recon-core` may include minimal internal adapters to prove the engine.

Long term, adapters should split into packages:

- `recon-postgres`,
- `recon-mysql`,
- `recon-snowflake`,
- `recon-sqlserver`,
- `recon-bigquery`,
- `recon-mongodb`,
- `recon-databricks`,
- `recon-redshift`,
- `recon-oracle`.

## Interface concepts

Illustrative interface:

```python
class Adapter:
    def connect(self): ...
    def execute_query(self, sql: str): ...
    def quote_identifier(self, name: str) -> str: ...
    def relation_exists(self, relation: str) -> bool: ...
    def get_columns(self, relation: str) -> list[Column]: ...
    def compile_limit(self, sql: str, limit: int) -> str: ...
    def compile_hash(self, columns: list[str]) -> str: ...
    def capabilities(self) -> AdapterCapabilities: ...
```

This is not final API.

## Capabilities

Adapters should declare capabilities:

```yaml
capabilities:
  relations: true
  queries: true
  temp_tables: true
  metadata_columns: true
  hash_expression: true
  timestamp_diff: true
  json_path: false
```

Capabilities allow Recon to fail early when a check cannot run.

## Hashing warning

Hash functions differ across databases.

Recon should not assume `hash()` in one system equals `hash()` in another.

Portable hashing or persisted sample keys may be required.

## Semi-structured adapters

MongoDB and similar systems are important later.

They require concepts like:

- document projection,
- nested fields,
- arrays,
- ObjectId handling,
- schema drift,
- CDC operation metadata.

Recon should compare canonical projections, not raw documents blindly.

## Adapter test kit

Future repo:

```text
recon-adapter-testkit
```

Purpose:

- adapter compliance tests,
- SQL compilation tests,
- metadata tests,
- capability validation.

## Design principle

Recon Core should be adapter-aware but not adapter-bloated. Core defines the contract; adapters handle systems.
