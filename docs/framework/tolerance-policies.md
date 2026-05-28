# Tolerance Policies

## Purpose

Tolerance policies define acceptable source-target value differences.

They also cover null equivalence and string normalization because those rules
change whether two values are considered equal.

Policy behavior is governed by
`docs/decisions/adr-0009-tolerance-normalization-and-null-equivalence.md`.

## Principle

Tolerance, null, and normalization rules must be explicit, resolved before
execution, visible in generated artifacts, and reviewable in evidence.

Recon must not silently coerce incompatible types or assume fuzzy equivalence.

## MVP Scope

MVP policy support should stay narrow:

- numeric absolute tolerance,
- explicit string-like null sentinels by literal value and limited regex,
- explicit ordered string normalization steps,
- limited regex replacement normalization,
- strict defaults,
- validation diagnostics for malformed or unsupported policy config.

Future support may add relative tolerance, percentage tolerance, timestamp
tolerance execution, reusable policy files, project-level defaults,
locale-aware string handling, unrestricted regex features, custom SQL/macros,
or adapter-specific optimizations.

Unsupported future policy config must fail validation when Recon can see it. It
must not be silently ignored.

## Precedence

Resolve tolerance, null, and normalization independently.

Precedence:

1. check-level override,
2. column-level setting,
3. contract-level inline policy,
4. named contract policy reference,
5. project-level default policy,
6. framework default.

Named tolerance policy files are future behavior and require the ADR 0017
resource-loading model before references can be validated or resolved.

Current contract YAML accepts a named `tolerance_policy` reference and
contract-level `nulls`. It does not accept a top-level contract
`normalization` field. Normalization is currently scoped to surfaces that
explicitly allow it, such as string column policy. Contract-level policy
defaults, including contract-level normalization, require a future design and
compatibility gate before implementation.

## Numeric Tolerance

MVP numeric tolerance is absolute tolerance.

Shorthand:

```yaml
tolerance: 0.01
```

is equivalent to:

```yaml
tolerance:
  type: absolute
  value: 0.01
```

Rules:

- the value must be finite and non-negative,
- `0` means exact numeric equality,
- numeric tolerance may apply only to numeric-compatible columns or metrics,
- relative tolerance, percentage tolerance, and decimal-scale-specific rules
  are future gated.

Precision/scale compatibility is schema policy behavior, not numeric value
tolerance.

## Timestamp Tolerance

Timestamp tolerance execution is future behavior.

When implemented, timestamp tolerance should use typed units rather than raw
duration strings:

```yaml
tolerance:
  type: absolute_time
  value: 5
  unit: second
  timezone: UTC
```

Timestamp comparison must not silently convert timezones. If source and target
timestamp semantics differ, users should canonicalize through compare views or
queries, or configure explicit timezone behavior once timestamp tolerance is
implemented.

## Null Equivalence

Default null behavior is strict:

```yaml
nulls:
  treat_as_null:
    values: []
    regex: []
```

Resolved comparisons use null-safe equality:

- `NULL` equals `NULL`,
- `NULL` does not equal a non-null value,
- `NULL` does not equal `''`, `' '`, `'NULL'`, `'N/A'`, or another sentinel
  unless that sentinel is explicit.

String-like null sentinels:

```yaml
nulls:
  treat_as_null:
    values:
      - ""
      - "NULL"
      - "N/A"
    regex:
      - "^\\s*$"
```

Sentinel matching applies only to string-like value comparison. Literal
sentinels and data values are compared after normalization steps run. Regex
sentinels match the full normalized value.

Numeric or timestamp blank handling should be done through canonical compare
views or a future typed normalization feature.

## String Normalization

Default normalization is none:

```yaml
normalization:
  steps: []
```

Supported explicit shape:

```yaml
normalization:
  steps:
    - trim
    - collapse_whitespace
    - lower
    - regex_replace:
        pattern: "\\s+-+$"
        replacement: ""
```

Allowed simple steps:

- `trim`,
- `collapse_whitespace`,
- `lower`,
- `upper`.

Allowed regex step:

```yaml
regex_replace:
  pattern: "\\s+-+$"
  replacement: ""
```

Steps run in authored order. `lower` and `upper` are mutually exclusive.
Duplicate simple steps are invalid.

MVP regex is limited to literal replacement with a portable regex subset.
Lookahead, lookbehind, backreferences, named groups, inline flags, custom SQL,
macros, and arbitrary expressions are future gated.

Resolved artifacts should show normalization in authored order:

```text
normalization.steps
nulls.treat_as_null matching
null-safe equality
```

## Scope Examples

Column level:

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
```

Check level:

```yaml
checks:
  - type: numeric_tolerance_match
    columns:
      - revenue
    tolerance:
      type: absolute
      value: 0.01
```

String/null policy:

```yaml
columns:
  string:
    - name: middle_name
      normalization:
        steps:
          - trim
          - lower
      nulls:
        treat_as_null:
          values:
            - ""
            - "null"
            - "n/a"
```

Concatenation cleanup:

```yaml
columns:
  string:
    - name: availability_status
      normalization:
        steps:
          - trim
          - regex_replace:
              pattern: "\\s+-+$"
              replacement: ""
          - trim
```

## Evidence

Reports and failure details should show:

- resolved tolerance,
- resolved null policy,
- resolved normalization steps,
- whether a string value became null because of a sentinel or regex rule,
- raw source and target values when evidence policy allows,
- normalized values when normalization changed comparison,
- diff values,
- whether validation was deferred or blocked.

## Errors

Invalid policy usage should fail validation.

Examples:

- numeric tolerance on a non-numeric column,
- negative tolerance,
- unsupported relative or percentage tolerance in MVP,
- malformed timestamp tolerance,
- missing timezone behavior when timestamp conversion is required,
- malformed null sentinel values or regexes,
- duplicate sentinel values after normalization,
- duplicate or incompatible normalization steps,
- unsupported regex features.
