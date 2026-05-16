# Adapters

## Purpose

This document defines Recon adapters.

Adapters allow Recon Core to work with different databases, warehouses, document stores, and query engines.

## Definition

An adapter handles connection, SQL dialect, identifier quoting, metadata queries, limit syntax, timestamp syntax, numeric casting, hashing syntax, temporary objects, schema introspection, and capability declaration.

## Core vs adapter responsibilities

`recon-core` owns CLI, project loading, contract parsing, check planning, result model, evidence generation, base adapter interface, extension mechanism, and framework-level validation rules.

Adapters own connection implementation, SQL compilation details, metadata access, dialect-specific functions, capability reporting, and adapter-specific tests.

## Initial strategy

Early `recon-core` may include minimal internal adapters to prove the engine.

Long term, adapters should split into packages such as `recon-postgres`, `recon-mysql`, `recon-snowflake`, `recon-sqlserver`, `recon-bigquery`, `recon-mongodb`, `recon-databricks`, `recon-redshift`, and `recon-oracle`.

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

Adapters should declare capabilities such as relation support, query support, temp tables, metadata columns, hash expression, timestamp diff, precision/scale metadata, and JSON path support.

Capabilities allow Recon to fail early when a check cannot run.

## Capability validation

If an adapter cannot run a requested check, Recon should fail during compile/validation when possible.

If metadata is unavailable, the compiled plan should mark validation as deferred.

## Hashing warning

Hash functions differ across databases.

Recon should not assume `hash()` in one system equals `hash()` in another.

Safe approaches include persisted sample keys, sampling from source and applying keys to target, numeric modulo when valid, or adapter-declared portable hashing.

## Type and schema metadata

Adapters should expose normalized metadata where possible: column name, logical type, physical type, nullable, precision, scale, and timezone behavior when known.

This supports schema checks and validation.

## Semi-structured adapters

MongoDB and similar systems are important later.

They require document projection, nested fields, arrays, ObjectId handling, schema drift, and CDC operation metadata.

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
- capability validation,
- check compatibility tests.

## Design principle

Recon Core should be adapter-aware but not adapter-bloated. Core defines the framework contract; adapters handle system-specific behavior.
