# ADR 0019: Column and Value Comparison Surface

## Status

Accepted.

## Context

Columns are the boundary between authored reconciliation intent and row/value
comparison behavior.

Recon already has durable rules that columns define eligible comparison fields
and rules, not actions. Metrics and checks create execution intent. Check packs
expand into execution intent. Recon must not silently compare every column, must
not silently coerce types, and must not guess source-target column mappings.

Current implementation preserves `columns` as raw authored data in compiled
contract artifacts and validates the supported authored column declaration and
reference surface during compile. It validates supported categories and fields,
duplicate declared names, metric references inside explicit declared surfaces,
unsupported wildcard requests, and supported metric/category compatibility.

It does not yet implement resolved column metadata in compiled artifacts,
all-column expansion, row-level value checks, column-level check eligibility,
unused-column warnings, or adapter metadata column/type validation.

dbt Core provides useful reference patterns:

- schema YAML patches parsed nodes with column metadata,
- column metadata is visible on manifest nodes,
- data tests are explicit resources rather than being created by column
  metadata alone,
- model contracts compare declared columns and data types as explicit contract
  state.

Great Expectations and Soda also support the principle that column-level checks
name the columns they validate. Recon should use that explicitness, but stay
focused on source-target equivalence rather than becoming a generic data
quality framework.

## Decision

Recon's column model has three jobs:

1. declare the eligible comparison surface,
2. attach comparison metadata to columns,
3. validate that checks and metrics use compatible columns.

Column declarations do not create checks.

Metrics and explicit checks may name columns directly. Check packs may use
column declarations only when the pack documents that behavior and compiled
artifacts show the generated checks.

## Authored Column Schema

The locked column categories are:

| Category | Intended use |
| --- | --- |
| `exact` | exact equality for pre-canonicalized scalar values such as codes, flags, statuses, and categories |
| `numeric` | numeric value checks and numeric aggregate metrics |
| `timestamp` | timestamp/date/time value checks that may need tolerance or timezone policy |
| `string` | string comparisons that may need explicit normalization |

String shorthand is allowed inside a category and is equivalent to a mapping
with `name`:

```yaml
columns:
  exact:
    - customer_status
  numeric:
    - name: revenue
```

Column entries use a canonical column name. For MVP behavior, that canonical
name must exist on both source and target comparable outputs. Source-target
column mapping is not part of this ADR. If mapping is added later, it must be
explicit, validated, and visible in artifacts.

Reserved column-entry fields are:

| Field | Meaning |
| --- | --- |
| `name` | required canonical column name |
| `description` | optional human documentation |
| `checks` | optional list of check types this column may participate in |
| `tolerance` | comparison tolerance; detailed semantics owned by the tolerance/null ADR |
| `nulls` | null-equivalence policy; detailed semantics owned by the tolerance/null ADR |
| `normalization` | string normalization policy; detailed semantics owned by the tolerance/null ADR |
| `timezone` | timestamp timezone policy; detailed semantics owned by a future timestamp policy decision |

Unknown column categories and unknown column-entry fields are compile validation
errors.

Current compiler validation also requires `description` to be a string when
declared and rejects `timezone` until timestamp policy syntax and validation are
implemented.

## Column Declarations and Explicit References

If a contract has no `columns` block, explicit metrics and explicit checks may
still name columns directly. Existence and physical type validation may be
deferred until adapter metadata is available.

If a contract has a `columns` block without `include: "*"`, declared columns are
the contract's explicit comparison surface. Explicit checks and metrics that
reference columns outside that surface fail validation.

Metric columns do not have to be declared when the contract has no `columns`
block. Metric columns must be declared when the contract has an explicit
columns block.

Group-by columns follow the same rule as metric value columns.

## Check-Level Column Selection

Checks that require columns must resolve to concrete column names before they
can execute.

Check-level `columns` narrows the contract-level column surface. It does not
mutate the contract-level declarations.

If a contract has no column declarations, an explicit check-level `columns` list
is allowed and becomes that check's explicit comparison surface.

If a contract has column declarations, check-level columns must be a subset of
the resolved declared surface unless a future ADR explicitly allows undeclared
check-local columns.

`columns: "*"` at check level is allowed only as an explicit all-column request.
It must resolve to concrete column names through adapter metadata before
execution. Raw `*` must never appear in typed check plans.

## All-Column Expansion

All-column comparison is supported only when explicitly requested:

```yaml
columns:
  include: "*"
```

or:

```yaml
checks:
  - type: row_diff
    columns: "*"
```

All-column expansion requires adapter metadata for both source and target. The
resolved column list must be written into compiled artifacts before execution.

All-column value comparison resolves to comparable non-identity columns:

- remove `grain.keys` used as comparison identity,
- remove explicit CDC keys when they are only change identity for the check,
- remove columns explicitly ignored by schema/value policy,
- require the remaining source and target column names to match after explicit
  ignores.

Recon must not silently compare only the source-target intersection while
ignoring extra source or target columns. Extra/missing columns must fail schema
or column validation unless an explicit ignore policy applies.

When adapter metadata is unavailable, all-column expansion is deferred and must
be visible through diagnostics/artifacts. Checks that need concrete columns may
not execute with unresolved `*`.

## Type Compatibility

Validation should happen in the earliest phase that has enough information:

| Rule | Earliest timing |
| --- | --- |
| column block has invalid structure | parse or compile validation, depending on current parser shape |
| duplicate declared column name | compile validation |
| explicit reference outside declared surface | compile validation |
| unknown column category or field | compile validation |
| check-level column selection has invalid shape | compile validation |
| metric/check incompatible with authored column category | compile validation |
| physical column missing from source or target | adapter metadata validation |
| physical type incompatible with required comparison | adapter metadata validation |
| all-column expansion unresolved because metadata is unavailable | adapter metadata validation |

Compatibility rules:

- `numeric_tolerance_match`, `sum_diff`, and numeric aggregate metrics require
  `numeric` columns or adapter metadata proving numeric compatibility.
- `timestamp_tolerance_match` requires `timestamp` columns or adapter metadata
  proving temporal compatibility.
- `normalized_string_match` requires `string` columns or adapter metadata
  proving string compatibility.
- `exact_value_match` should use `exact` columns unless a check explicitly
  declares that it can compare another category exactly.
- `row_diff` and `sampled_value_match` may use a mixed set of declared
  categories, with each column using its resolved comparison mode.
- `row_hash_match` requires a future adapter/canonicalization decision before
  cross-database hash equality can be trusted.

No check may rely on implicit type coercion.

## Column-Level Check Eligibility

The optional column `checks` field is a filter. It does not create checks.

If present, it limits which generated, explicit, or metric-derived checks may
use that column. A check that uses a column but is not listed in that column's
`checks` field fails validation.

Unknown check names in column eligibility lists are validation errors once the
check registry exists.

## Artifact Visibility

Compiled artifacts must keep raw authored `columns` until typed column
resolution exists.

Before value checks, all-column expansion, or column/type validation are treated
as implemented, compiled artifacts must expose resolved column metadata:

- declared categories,
- canonical column names,
- all-column requests,
- resolved concrete column lists,
- excluded identity columns,
- explicitly ignored columns,
- adapter metadata validation status,
- per-check required columns,
- deferred validation diagnostics.

Typed check plans must contain concrete column names only. They must not contain
raw wildcard selectors.

Adding resolved column metadata is a compiled artifact compatibility change.
Additive optional fields may keep the current artifact version only if existing
readers can ignore them safely and existing field meanings do not change.

## Diagnostics

The following codes are locked for this surface:

| Code | Timing | Severity | Meaning |
| --- | --- | --- | --- |
| `RC_VALIDATE_INVALID_COLUMN_DECLARATION` | compile validation | error | Column block, category, entry, or field has invalid shape. |
| `RC_VALIDATE_DUPLICATE_COLUMN_NAME` | compile validation | error | The same canonical column name is declared more than once. |
| `RC_VALIDATE_UNDECLARED_COLUMN_REFERENCE` | compile validation | error | A metric or check references a column outside an explicit declared surface. |
| `RC_VALIDATE_INVALID_COLUMN_SELECTION` | compile validation | error | A check-level column selector has invalid shape or unsupported wildcard placement. |
| `RC_VALIDATE_COLUMN_NOT_ELIGIBLE_FOR_CHECK` | compile validation | error | A check uses a column whose `checks` eligibility excludes that check. |
| `RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE` | compile or adapter metadata validation | error | Authored category or physical type is incompatible with the requested check or metric. |
| `RC_VALIDATE_ALL_COLUMNS_REQUIRES_METADATA` | adapter metadata validation | error | An all-column request cannot be resolved because source/target metadata is unavailable. |
| `RC_VALIDATE_METADATA_VALIDATION_DEFERRED` | adapter metadata validation | warning | Column existence or physical type validation is deferred until adapter metadata is available. |
| `RC_VALIDATE_UNUSED_DECLARED_COLUMN` | compile validation | warning | A declared column is not used by any compiled check. |

## Consequences

Current compiler validation covers authored column declarations, explicit metric
references, `sum` metric compatibility from declared categories, and invalid
wildcard usage without implementing row-level value checks.

Column-level check eligibility, unused declared-column warnings, all-column
expansion, resolved column artifact metadata, and physical type validation remain
future-gated on check registries, adapter metadata, and artifact visibility.

Future sampling, tolerance, null, normalization, schema ignore, row-hash, and
adapter metadata work must reuse this column surface instead of inventing
separate column-selection semantics.

## Alternatives Considered

### Require every metric column to be declared

Rejected. Explicit metrics already name the column they compare. Requiring a
separate column declaration when no `columns` block exists creates unnecessary
duplication.

### Let explicit checks bypass declared columns

Rejected. Once a contract declares a column surface, references outside that
surface are likely mistakes and can produce misleading evidence.

### Resolve `*` to the source-target intersection

Rejected. Comparing only the intersection silently ignores extra source or
target columns. Recon should fail unless differences are explicitly ignored.

### Allow source-target column mapping implicitly

Rejected. Mapping must be explicit because source-target guessing can make
unrelated columns look equivalent.

## Implementation Guidance

Implementation should continue to:

- use typed authored column models,
- normalize string shorthand into typed column declarations,
- keep parser structural validation separate from compiler semantic validation,
- keep a column registry/resolver used by metrics, explicit checks, and
  check-pack expansion,
- reject wildcard execution until adapter metadata can resolve concrete
  columns,
- write resolved column metadata into compiled artifacts before executing value
  checks,
- test current validation for duplicate columns, invalid categories, unknown
  fields, undeclared references, invalid wildcard selectors, and category/check
  compatibility,
- add future tests for column-level check eligibility, unused declared columns,
  metadata-deferred validation, resolved column artifact visibility, and
  all-column expansion when those features are implemented.
