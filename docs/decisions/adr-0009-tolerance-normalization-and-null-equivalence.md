# ADR 0009: Tolerance, Normalization, and Null Equivalence

## Context

Equivalent source and target data may differ because systems handle decimals,
floats, timestamps, strings, nulls, empty strings, file formats, and type
casting differently.

A common real case is:

```text
SQL Server source stores empty string ''
AWS DMS writes staged files
Snowflake file format loads empty field as NULL
```

Strict byte-for-byte comparison would fail. Silent equivalence would be unsafe.

Recon needs policy rules that make acceptable differences explicit, resolved
before execution, visible in artifacts, and testable.

## Decision

Tolerance, normalization, and null-equivalence behavior must be explicit and
visible.

Default behavior is strict:

- no numeric tolerance unless configured,
- no timestamp tolerance unless configured,
- no string normalization unless configured,
- two null values compare equal through null-safe equality,
- one null and one non-null value compare different,
- `NULL != ''`,
- no silent type coercion.

## Scope By Milestone

Milestone 5 may validate and resolve the MVP policy surface. It must not imply
that row-level value checks, adapter rendering, run results, or evidence are
implemented before their milestones exist.

MVP policy scope:

- numeric absolute tolerance,
- explicit null policy with `empty_string_equals_null`,
- explicit string normalization configuration shape,
- diagnostics for malformed or unsupported policy config,
- resolved policy visibility in compiled artifacts once used by compiled
  checks.

Future policy scope:

- relative or percentage numeric tolerance,
- decimal-scale-aware tolerance,
- timestamp tolerance execution,
- locale-aware string behavior,
- regex or custom normalization,
- reusable tolerance policy files,
- project-level default policy files,
- adapter-specific normalization optimizations.

Unsupported future policy config must fail validation when Recon can see it. It
must not be silently ignored.

## Precedence

Resolve tolerance, null, and normalization policies independently.

Precedence is:

1. check-level override,
2. column-level setting,
3. contract-level inline policy,
4. named contract policy reference,
5. project-level default policy,
6. framework default.

Named tolerance policy references require ADR 0017 resource loading before they
can be validated or resolved. Until that loader exists for tolerance policies,
Milestone 5 must not pretend a named policy was resolved.

## Numeric Tolerance

MVP numeric tolerance supports absolute tolerance only.

Authored shorthand:

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

- `value` must be a finite non-negative number,
- `0` means exact numeric equality,
- negative, infinite, missing, empty, string, relative, or percentage values
  are invalid until separately designed,
- numeric tolerance may apply only to numeric-compatible columns or numeric
  metrics,
- schema precision/scale compatibility remains a schema-policy concern, not a
  value tolerance rule.

When physical type metadata is needed to prove compatibility, validation may be
deferred to adapter metadata validation and must be visible before evidence is
trusted.

## Timestamp Tolerance

Timestamp tolerance is not MVP execution behavior.

When timestamp tolerance is implemented, the authored shape should be typed and
unit-explicit:

```yaml
tolerance:
  type: absolute_time
  value: 5
  unit: second
  timezone: UTC
```

Allowed units should be locked before implementation and should avoid ad hoc
duration-string parsing in typed artifacts.

Rules:

- timestamp comparison must not silently convert timezones,
- if source and target timestamp semantics differ, the contract or compare
  views must make timezone behavior explicit,
- adapter metadata may be required to know whether timestamp values are
  timezone-aware,
- missing timezone policy is an error when conversion is required and metadata
  proves the ambiguity,
- unresolved timezone compatibility must be visible as deferred metadata
  validation before execution evidence is trusted.

## Null Equivalence

Default null behavior is strict:

```yaml
nulls:
  empty_string_equals_null: false
```

Resolved value comparison uses null-safe equality:

- `NULL` equals `NULL`,
- `NULL` does not equal a non-null value,
- `NULL` does not equal `''` unless `empty_string_equals_null: true` is
  explicitly configured.

`empty_string_equals_null: true` may apply only to string-like value comparison
surface. Numeric and timestamp blank handling should be handled by canonical
compare views, queries, or a separately designed type-normalization feature.

## String Normalization

Default normalization is none:

```yaml
normalization:
  operations: []
```

The supported explicit shape is:

```yaml
normalization:
  operations:
    - trim
    - collapse_whitespace
    - lower
```

Allowed operations:

- `trim`,
- `collapse_whitespace`,
- `lower`,
- `upper`.

Rules:

- duplicate operations are invalid,
- `lower` and `upper` are mutually exclusive,
- locale-specific case folding is future gated,
- regex, custom SQL, macros, and arbitrary expressions are future gated,
- adapters render normalization from typed operations; core owns the
  comparison semantics.

Recon should normalize operations to a stable canonical order in resolved
artifacts:

```text
trim
collapse_whitespace
lower or upper
empty-string/null equivalence
```

## Artifact, Result, And Evidence Visibility

Compiled checks that use tolerance, null, or normalization policy must show the
resolved policy. Raw unresolved policy refs must not be the only visible
execution behavior.

Typed check plans must carry structured policy payloads or reference resolved
compiled-check policy data. They must not carry raw YAML strings such as
`5 seconds` or `trim_lower`.

Run results and evidence should show:

- resolved tolerance,
- resolved null policy,
- resolved normalization operations,
- source and target raw values when allowed by evidence policy,
- normalized source and target values when normalization changed comparison,
- diff value,
- pass/fail/warn status,
- blocked or deferred policy validation.

## Diagnostics

Milestone 5 and future policy implementations must reuse ADR 0016 phase
ownership and code-family rules.

Locked policy diagnostics:

| Code | Phase | Severity | Meaning |
| --- | --- | --- | --- |
| `RC_VALIDATE_INVALID_TOLERANCE` | compile validation | error | Tolerance config is malformed, unsupported in the current milestone, negative, non-finite, or missing required fields. |
| `RC_VALIDATE_INVALID_NULL_POLICY` | compile validation | error | Null policy config is malformed or uses unsupported keys or non-boolean values. |
| `RC_VALIDATE_INVALID_NORMALIZATION` | compile validation | error | Normalization config is malformed, duplicates operations, combines incompatible operations, or uses unsupported operations. |
| `RC_VALIDATE_TIMESTAMP_TIMEZONE_REQUIRED` | compile or adapter metadata validation | error | Timestamp comparison requires explicit timezone behavior but none was provided. |

Use `RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE` when a valid policy is attached to
an incompatible declared or metadata-derived column category. Use
`RC_VALIDATE_METADATA_VALIDATION_DEFERRED` when physical metadata is genuinely
unavailable in the current phase.

## Implementation Guidance

Use typed policy models:

- `TolerancePolicy`,
- `NullPolicy`,
- `NormalizationPolicy`,
- `ResolvedComparisonPolicy`.

Do not pass arbitrary YAML dictionaries through compiler, typed plans, adapters,
results, or evidence.

Do not implement tolerance or normalization through macro dispatch as the
primary comparison engine. Adapters may render typed operations in dialect SQL,
but core owns the resolved semantics.

## Alternatives Considered

### Allow Ad Hoc Duration Strings

Rejected for typed artifacts. Strings such as `5 seconds` are readable but
ambiguous for parsing, validation, and adapter compatibility. User-facing
shorthand can be reconsidered later, but resolved artifacts should use typed
unit fields.

### Treat Empty Strings As Null By Default

Rejected. It can hide real differences between systems and make evidence look
more trustworthy than it is.

### Let Adapters Decide Null Or Normalization Semantics

Rejected. Adapters own dialect rendering and execution mechanics. Core owns
reconciliation semantics.

### Support Relative Tolerance In MVP

Rejected. Relative tolerance is useful but needs denominator, zero-value, sign,
and metric-specific semantics. Absolute tolerance is the safe MVP.

## Consequences

Users must make tolerance, null, and normalization behavior explicit.

MVP may be stricter than some real projects need, but it avoids unsafe matches.
Projects can use compare views or queries for complex casting and normalization
until Recon implements richer typed policy support.

Future policy features must update framework, implementation, compatibility,
artifact, result, evidence, and diagnostic docs before implementation.
