# ADR 0009: Tolerance, Normalization, and Null Equivalence

## Context

Equivalent data may differ because systems handle decimals, floats, timestamps, strings, nulls, empty strings, file formats, and type casting differently.

A common real case is:

```text
SQL Server source stores empty string ''
AWS DMS writes staged files
Snowflake file format loads empty field as NULL
```

Strict equality would fail. Silent equivalence would be unsafe.

## Decision

Tolerance, normalization, and null-equivalence behavior must be explicit and visible.

Default null behavior should be strict:

```text
NULL != ''
```

Users may configure empty-string/null equivalence at project, contract, column, or check level.

## Precedence

Resolved behavior should follow this order:

1. check-level override,
2. column-level setting,
3. contract-level policy,
4. project-level policy,
5. framework default.

## Numeric tolerance

Numeric tolerance applies to value comparisons.

It is not the same as schema precision/scale compatibility.

Numeric tolerance should be compatible with numeric columns only.

## Timestamp tolerance

Timestamp tolerance should distinguish:

- event-time equivalence,
- ingestion-time lag,
- target processing time,
- CDC arrival time.

Timezone behavior should be explicit when systems differ.

## String normalization

String normalization may include:

- trim,
- lower,
- upper,
- whitespace normalization,
- case sensitivity,
- empty-string/null behavior.

## Consequences

Compiled artifacts and evidence should show resolved tolerance, null, and normalization rules.

Invalid tolerance usage should fail validation.

Recon should not silently coerce incompatible types.
