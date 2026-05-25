# ADR 0004: Columns, Metrics, and Checks Semantics

## Context

Recon contracts need to define fields, aggregate comparisons, and execution intent.

These concepts can be confused:

- defining a column,
- defining a metric,
- defining a check,
- using a check pack.

If the semantics are unclear, users may believe a column definition runs a check, or a check pack may silently do more than expected.

## Decision

Recon uses these semantics:

```text
columns = eligible comparison fields and rules
metrics = named aggregate comparisons that compile into checks
checks = explicit execution intent
check packs = reusable execution intent that expands into checks
```

Columns do not cause checks by themselves.

Metrics do cause aggregate checks by compiling into explicit check definitions.

Checks and check packs define what runs.

## Reasoning

This model keeps contracts readable while avoiding hidden behavior.

A column can define:

- type/category,
- tolerance,
- normalization,
- null handling,
- check eligibility.

A metric defines a business aggregate that should be compared and reported by name.

A check defines an operation.

A check pack defines reusable groups of operations.

## Examples

Column definition:

```yaml
columns:
  numeric:
    - name: revenue
      tolerance: 0.01
```

This makes `revenue` eligible for compatible checks. It does not run a check.

Metric definition:

```yaml
metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01
```

This compiles into an aggregate check.

Explicit check:

```yaml
checks:
  - name: revenue_sum
    type: sum_diff
    column: revenue
    tolerance: 0.01
```

Check pack:

```yaml
checks:
  use:
    - recon_core.aggregate_equivalence
```

This expands into explicit compiled checks.

## Consequences

The compiler must make all metric and check-pack expansion visible.

If a numeric column is defined but no compiled check uses it, Recon may warn.

If a check references an undefined or incompatible column, Recon should fail validation.

Recon must never silently compare every column unless the user explicitly requests all columns.

ADR 0019 defines the detailed column/value comparison surface, including
column categories, explicit column references, all-column expansion, and
diagnostic ownership.
