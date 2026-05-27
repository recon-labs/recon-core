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
- explicit string-like null sentinels by literal value and limited regex,
- explicit ordered string normalization steps,
- limited regex replacement normalization,
- diagnostics for malformed or unsupported policy config,
- resolved policy visibility in compiled artifacts once used by compiled
  checks.

Future policy scope:

- relative or percentage numeric tolerance,
- decimal-scale-aware tolerance,
- timestamp tolerance execution,
- locale-aware string behavior,
- unrestricted regex dialect features,
- custom SQL, macros, or arbitrary expression normalization,
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
  treat_as_null:
    values: []
    regex: []
```

Resolved value comparison uses null-safe equality:

- `NULL` equals `NULL`,
- `NULL` does not equal a non-null value,
- `NULL` does not equal a string sentinel such as `''`, `' '`, `'NULL'`,
  `'N/A'`, or `'none'` unless that sentinel is explicitly configured.

String-like null sentinels are configured with:

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

Rules:

- `treat_as_null.values` entries must be strings,
- `treat_as_null.regex` entries must be valid MVP regex patterns,
- sentinel matching applies only to string-like value comparison,
- literal sentinel values are compared after applying the same string
  normalization steps as the data value,
- sentinel regex patterns are evaluated against the normalized data value and
  must match the full normalized value,
- duplicate sentinel values after normalization are invalid,
- numeric and timestamp blank handling should be handled by canonical compare
  views, queries, or a separately designed type-normalization feature.

Do not implement a separate `empty_string_equals_null` boolean. The equivalent
explicit configuration is:

```yaml
nulls:
  treat_as_null:
    values:
      - ""
```

## String Normalization

Default normalization is none:

```yaml
normalization:
  steps: []
```

The supported explicit shape is ordered:

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

Rules:

- steps run in authored order,
- duplicate simple steps are invalid,
- `lower` and `upper` are mutually exclusive,
- `regex_replace` replaces all non-overlapping matches,
- `regex_replace.replacement` is a literal string in MVP,
- regex backreferences in replacement strings are not supported in MVP,
- regex flags, lookahead, lookbehind, backreferences, named groups, and
  database-specific regex features are not supported in MVP,
- locale-specific case folding is future gated,
- custom SQL, macros, and arbitrary expressions are future gated,
- adapters render normalization from typed operations; core owns the
  comparison semantics.

Recon should preserve the authored step order in resolved artifacts. Null
sentinel matching runs after the ordered normalization steps:

```text
raw string value
normalization.steps in authored order
nulls.treat_as_null matching
null-safe equality
```

Example for a common concatenation cleanup:

```yaml
normalization:
  steps:
    - trim
    - regex_replace:
        pattern: "\\s+-+$"
        replacement: ""
    - trim
```

This can normalize `available --` to `available` when an adapter supports the
locked regex profile.

## MVP Regex Profile

MVP regex support is intentionally limited.

It may be used only in:

- `nulls.treat_as_null.regex`,
- `normalization.steps[].regex_replace.pattern`.

MVP regex should support a portable subset:

- literals,
- escaped characters,
- character classes,
- anchors `^` and `$`,
- grouping and non-capturing grouping,
- alternation,
- quantifiers `*`, `+`, `?`, and `{m,n}`,
- common whitespace escapes such as `\s`.

Unsupported in MVP:

- lookahead,
- lookbehind,
- backreferences,
- named groups,
- inline flags,
- adapter-specific regex extensions,
- dynamic expressions,
- custom SQL.

Milestone 5 should validate regex syntax and reject features outside the MVP
profile when possible. Adapter execution must also require explicit regex
capability validation before a regex-dependent check runs.

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
- resolved normalization steps,
- normalized value became null because of the sentinel or regex rule, when that
  happens,
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
| `RC_VALIDATE_INVALID_NULL_SENTINEL` | compile validation | error | A string-like null sentinel is malformed, duplicated after normalization, or unsupported for the target column category. |
| `RC_VALIDATE_INVALID_NORMALIZATION` | compile validation | error | Normalization config is malformed, duplicates operations, combines incompatible operations, or uses unsupported operations. |
| `RC_VALIDATE_INVALID_REGEX_NORMALIZATION` | compile validation | error | A regex null sentinel or regex replacement uses invalid syntax or features outside the MVP regex profile. |
| `RC_VALIDATE_TIMESTAMP_TIMEZONE_REQUIRED` | compile or adapter metadata validation | error | Timestamp comparison requires explicit timezone behavior but none was provided. |

Use `RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE` when a valid policy is attached to
an incompatible declared or metadata-derived column category. Use
`RC_VALIDATE_METADATA_VALIDATION_DEFERRED` when physical metadata is genuinely
unavailable in the current phase. Use `RC_ADAPTER_CAPABILITY_UNSUPPORTED` when
a selected adapter cannot execute a regex-dependent or normalization-dependent
typed operation.

## Implementation Guidance

Use typed policy models:

- `TolerancePolicy`,
- `NullPolicy`,
- `NormalizationPolicy`,
- `ResolvedComparisonPolicy`.

Do not pass arbitrary YAML dictionaries through compiler, typed plans, adapters,
results, or evidence.

Null policies should carry typed literal and regex sentinel lists. Normalization
policies should carry ordered typed steps, including simple string operations
and limited `regex_replace` steps.

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

### Keep `empty_string_equals_null` As The MVP Shape

Rejected. It is too narrow for common migration cases where sources encode
missing strings as `''`, whitespace, `NULL`, `N/A`, `none`, or another
domain-specific sentinel. A typed `treat_as_null` policy is still explicit but
does not force a new boolean for every sentinel.

### Forbid Regex Until After MVP

Rejected for the narrow MVP regex profile. Literal sentinels cover many cases,
but common reconciliation cleanup also needs safe pattern replacement such as
removing trailing concatenation separators. MVP regex remains limited, typed,
artifact-visible, and adapter-capability-gated.

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
