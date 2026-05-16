# Tolerance Policies

## Purpose

This document defines tolerance policies.

A tolerance policy defines acceptable differences between source and target values.

## Why tolerances matter

Equivalent data may not be byte-for-byte identical because of:

- decimal precision,
- currency rounding,
- timestamp precision,
- timezone conversion,
- string normalization,
- null handling,
- type casting.

Recon needs explicit rules for acceptable differences.

## Principle

Tolerances should be reusable and visible.

Users should not repeat the same tolerance values in every contract.

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

strings:
  trim: true
  case_sensitive: false

nulls:
  empty_string_equals_null: false
```

## Contract usage

```yaml
tolerance_policy: finance
```

Column-level overrides should be allowed:

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
```

## Numeric tolerances

Initial support should focus on absolute tolerance.

Future support may include:

- relative tolerance,
- percentage tolerance,
- decimal-scale rules.

## Timestamp tolerances

Timestamp tolerance handles precision and lag.

```yaml
columns:
  timestamp:
    - name: updated_at
      tolerance: 5 seconds
```

Recon should distinguish event-time equality from ingestion-time lag.

## String normalization

Possible rules:

- trim,
- lower,
- upper,
- collapse whitespace,
- empty-string/null behavior.

## Null equivalence

Null rules must be explicit.

Recon should not silently assume null equals empty string.

## Evidence

Reports should show tolerance values used in comparisons:

- source value,
- target value,
- difference,
- tolerance,
- pass/fail.

## MVP recommendation

v0.1 should support:

- numeric absolute tolerance,
- column-level overrides,
- explicit null comparison rules.

v0.2 can add:

- reusable policy files,
- relative tolerance,
- timestamp tolerance,
- string normalization macros.

## Design principle

Tolerance policies make Recon practical while keeping comparison rules reviewable.
