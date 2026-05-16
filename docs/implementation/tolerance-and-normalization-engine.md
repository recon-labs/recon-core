# Tolerance and Normalization Engine

## Purpose

The tolerance and normalization engine resolves comparison rules for numeric, timestamp, string, and null behavior.

## Inputs

Inputs:

- compiled contract,
- compiled check,
- column definitions,
- tolerance policies,
- check-level overrides,
- adapter type metadata.

## Outputs

Outputs:

- resolved tolerance,
- resolved null policy,
- resolved string normalization,
- resolved timestamp policy,
- validation diagnostics.

## Precedence

Resolution order:

```text
check-level
column-level
contract-level policy
project-level policy
framework default
```

## Numeric tolerance

Numeric tolerance supports value comparisons.

Initial implementation should support absolute tolerance.

Example:

```yaml
tolerance:
  type: absolute
  value: 0.01
```

Invalid usage, such as numeric tolerance on a text column, should fail validation.

## Precision and scale

Precision and scale compatibility belongs to schema policy handling.

Do not mix numeric value tolerance with schema precision compatibility.

## Timestamp tolerance

Timestamp tolerance should support precision differences and lag checks.

Timestamp comparison should record timezone assumptions.

In strict mode, missing timezone behavior should be an error when systems differ.

## String normalization

Possible operations:

- trim,
- lower,
- upper,
- collapse whitespace,
- case sensitivity.

Normalization should be explicit and visible in compiled checks.

## Null equivalence

Default behavior:

```text
NULL != ''
```

Configurable behavior:

```yaml
nulls:
  empty_string_equals_null: true
```

This can be set at project, contract, column, or check level.

## SQL generation

Normalization may need adapter-specific SQL.

Examples:

```text
trim(column)
lower(column)
coalesce(...)
```

Adapters should provide dialect-specific helpers where needed.

## Evidence

Evidence should show:

- raw source value,
- raw target value,
- normalized source value when relevant,
- normalized target value when relevant,
- tolerance,
- pass/fail.

## Design principle

Tolerances and normalization make reconciliation practical, but they must remain explicit and reviewable.
