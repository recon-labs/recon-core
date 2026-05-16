# Tolerance Policies

## Purpose

This document defines tolerance, normalization, and null-equivalence policies.

A tolerance policy defines acceptable differences between source and target values.

## Why tolerances matter

Equivalent data may not be byte-for-byte identical because of decimal precision, currency rounding, timestamp precision, timezone conversion, string normalization, null handling, type casting, file format behavior, or ingestion/CDC transformations.

Recon needs explicit rules for acceptable differences.

## Principle

Tolerances should be reusable, visible, and overrideable.

Recon should not silently coerce incompatible types or assume fuzzy equivalence.

## Recommended location

```text
tolerances/
  default.yml
  finance.yml
  timestamps.yml
```

## Example policy

```yaml
name: finance

numeric:
  default_tolerance: 0.01
  currency_tolerance: 0.01
  percentage_tolerance: 0.0001

timestamp:
  default_tolerance: 5 seconds
  timezone: UTC

strings:
  trim: true
  case_sensitive: false

nulls:
  empty_string_equals_null: false
```

## Precedence

Recommended precedence:

1. check-level override,
2. column-level setting,
3. contract-level policy,
4. project-level default,
5. framework default.

## Numeric tolerances

Initial support should focus on absolute tolerance.

Future support may include relative tolerance, percentage tolerance, and decimal-scale rules.

A numeric tolerance should only be applied to numeric-compatible columns.

## Precision and scale

Precision/scale compatibility is a schema concern, not the same as numeric value tolerance.

Value tolerance answers whether actual values differ acceptably.

Schema precision/scale checks answer whether types are compatible.

## Timestamp tolerances

Timestamp tolerance handles precision and lag.

```yaml
columns:
  timestamp:
    - name: updated_at
      tolerance: 5 seconds
```

Recon should distinguish event-time equivalence, ingestion-time lag, target processing time, and CDC arrival time.

Timezone behavior should be explicit when systems differ.

## String normalization

Possible rules include trim, lower, upper, collapse whitespace, case sensitivity, and empty-string/null behavior.

## Null equivalence

Null rules must be explicit.

Default should be strict:

```text
NULL != ''
```

Example scenario:

```text
SQL Server table contains empty string ''
AWS DMS writes staged files
Snowflake file format loads empty field as NULL
```

Recon should support this explicitly:

```yaml
nulls:
  empty_string_equals_null: true
```

## Scope of null/normalization policy

Null and normalization rules should be configurable at multiple levels.

Project or contract level:

```yaml
nulls:
  empty_string_equals_null: true
```

Column level:

```yaml
columns:
  exact:
    - name: middle_name
      nulls:
        empty_string_equals_null: true
```

Check level:

```yaml
checks:
  - type: exact_value_match
    columns:
      - middle_name
    nulls:
      empty_string_equals_null: true
```

## Evidence

Reports should show tolerance and normalization rules used in comparisons.

## Errors

Invalid tolerance usage should fail validation.

Examples include numeric tolerance on text column, timestamp tolerance on non-timestamp column, invalid tolerance syntax, and ambiguous timezone behavior in strict mode.

## MVP recommendation

v0.1 should support numeric absolute tolerance, column-level overrides, and explicit null comparison rules.

v0.2 can add reusable policy files, relative tolerance, timestamp tolerance, string normalization macros, and project-level default policies.

## Design principle

Tolerance policies make Recon practical while keeping comparison rules explicit, reviewable, and visible in compiled artifacts.
