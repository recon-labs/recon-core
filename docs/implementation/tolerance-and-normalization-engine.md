# Tolerance and Normalization Engine

## Purpose

The tolerance and normalization engine resolves comparison policy for numeric,
timestamp, string, and null behavior.

It converts authored YAML into typed resolved policy models used by compiled
checks, typed plans, adapters, results, and evidence.

## Inputs

Inputs:

- authored contract models,
- column definitions from ADR 0019,
- explicit checks and metric-derived checks,
- inline contract policies,
- future named tolerance policy resources,
- future project-level default policies,
- adapter metadata when physical type or timezone facts are required.

## Outputs

Outputs:

- resolved tolerance policy,
- resolved null policy,
- resolved string normalization policy,
- validation diagnostics,
- artifact-ready policy payloads.

The engine must not pass raw YAML dictionaries through compilation or adapter
execution.

## Typed Models

Implementation should use typed models equivalent to:

```python
@dataclass(frozen=True)
class NumericTolerance:
    type: Literal["absolute"]
    value: Decimal

@dataclass(frozen=True)
class NullPolicy:
    treat_as_null_values: tuple[str, ...] = ()
    treat_as_null_regex: tuple[str, ...] = ()

@dataclass(frozen=True)
class NormalizationPolicy:
    steps: tuple[NormalizationStep, ...] = ()

@dataclass(frozen=True)
class ResolvedComparisonPolicy:
    tolerance: NumericTolerance | None
    nulls: NullPolicy
    normalization: NormalizationPolicy
```

Timestamp tolerance should use a separate typed model when execution is added.

## Precedence

Resolve each policy family independently:

```text
check-level
column-level
contract-level inline policy
named contract policy reference
project-level default policy
framework default
```

Named policy references require ADR 0017 resource loading before they can be
resolved. If policy resources are not loaded, the compiler must not pretend a
reference was resolved.

## Numeric Tolerance

MVP supports absolute numeric tolerance:

```yaml
tolerance: 0.01
```

and:

```yaml
tolerance:
  type: absolute
  value: 0.01
```

Validation:

- value is required,
- value is finite,
- value is non-negative,
- tolerance is allowed only for numeric-compatible columns or numeric metrics,
- unsupported types such as `relative` or `percentage` fail validation until
  they are separately designed.

Use `Decimal` or an equivalent exact numeric representation for parsed policy
values. Do not parse tolerance through binary float if avoidable.

## Timestamp Tolerance

Timestamp tolerance execution is future behavior.

When implemented, the resolved shape should be typed:

```yaml
tolerance:
  type: absolute_time
  value: 5
  unit: second
  timezone: UTC
```

Adapter metadata may be required to determine timezone compatibility. If
metadata is unavailable, emit deferred metadata validation rather than assuming
timestamps are comparable.

## Null Policy

Default:

```yaml
nulls:
  treat_as_null:
    values: []
    regex: []
```

Runtime comparison should use null-safe equality:

- both null passes,
- one null and one non-null fails,
- configured string sentinels such as `""`, `" "`, `"NULL"`, or `"N/A"`
  become null only when explicitly configured.

Supported string-like sentinel shape:

```yaml
nulls:
  treat_as_null:
    values:
      - ""
      - "NULL"
    regex:
      - "^\\s*$"
```

Validation:

- reject non-string literal sentinels,
- reject invalid regex sentinels,
- reject duplicate sentinels after normalization,
- reject string sentinels on non-string column categories unless a future typed
  conversion feature expands the scope.

## String Normalization

Default:

```yaml
normalization:
  steps: []
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

Validation:

- reject unknown steps,
- reject duplicate simple steps,
- reject `lower` with `upper`,
- reject regex syntax outside the MVP regex profile,
- reject regex replacement backreferences,
- reject arbitrary SQL, macro references, custom expressions, and
  locale-specific rules until those features are designed.

Resolved operation order is authored order:

```text
normalization.steps
nulls.treat_as_null matching
null-safe equality
```

Adapters render these operations from typed operations. Core owns the semantics.

## MVP Regex Profile

MVP regex may be used only for:

- `nulls.treat_as_null.regex`,
- `normalization.steps[].regex_replace.pattern`.

The MVP profile should accept a portable subset: literals, escaped characters,
character classes, anchors, grouping, non-capturing grouping, alternation,
basic quantifiers, and common whitespace escapes such as `\s`.

Reject lookahead, lookbehind, backreferences, named groups, inline flags,
adapter-specific regex extensions, custom SQL, and dynamic expressions.

`regex_replace` replacement strings are literals. Replacement backreferences
are future gated.

## Diagnostics

Policy validation uses ADR 0016 diagnostic ownership.

| Code | Timing | Severity |
| --- | --- | --- |
| `RC_VALIDATE_INVALID_TOLERANCE` | compile validation | error |
| `RC_VALIDATE_INVALID_NULL_POLICY` | compile validation | error |
| `RC_VALIDATE_INVALID_NULL_SENTINEL` | compile validation | error |
| `RC_VALIDATE_INVALID_NORMALIZATION` | compile validation | error |
| `RC_VALIDATE_INVALID_REGEX_NORMALIZATION` | compile validation | error |
| `RC_VALIDATE_TIMESTAMP_TIMEZONE_REQUIRED` | compile or adapter metadata validation | error |
| `RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE` | compile or adapter metadata validation | error |
| `RC_VALIDATE_METADATA_VALIDATION_DEFERRED` | adapter metadata validation | warning |

Use `RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE` when the policy shape is valid but
the target column or metric category is incompatible.

## Artifact Visibility

Compiled checks that use policy behavior should include:

```yaml
tolerance:
  type: absolute
  value: 0.01
nulls:
  treat_as_null:
    values: []
    regex: []
normalization:
  steps: []
```

Per-column value checks should show resolved policy per compared column when
different columns use different policies.

Raw strings such as `5 seconds` or `trim_lower` must not appear as unresolved
policy in typed check plan payloads. Regex normalization must appear as typed
steps with explicit pattern and replacement fields.

## SQL Generation

Adapters may need dialect-specific rendering for:

- null-safe equality,
- string sentinel matching,
- numeric difference expressions,
- timestamp difference expressions,
- trim/lower/upper/collapse-whitespace operations,
- limited regex replacement.

Capability validation must fail before execution when a required operation is
not supported by the selected adapter.

## Result And Evidence

Run results, failure details, and reports should show:

- resolved policy,
- raw values when evidence policy permits,
- normalized values when normalization applies,
- whether a normalized value became null due to a sentinel rule,
- diff values,
- tolerance values,
- blocked or deferred validation.

Evidence must not imply that unsupported normalization or tolerance behavior was
applied.

## Tests

Implementation should add tests for:

- precedence resolution for each policy family,
- numeric shorthand and typed object equivalence,
- invalid numeric tolerance values,
- unsupported relative/percentage/timestamp tolerance in current scope,
- invalid null policy shape,
- invalid or duplicate null sentinels,
- invalid normalization steps,
- invalid or unsupported MVP regex,
- type incompatibility diagnostics,
- artifact payloads for resolved policies,
- deferred metadata validation where adapter facts are required.
