# ADR 0007: Grain Keys and Row-Level Uniqueness

## Context

Row-level reconciliation requires matching a source row to a target row.

If keys are missing or duplicated, Recon cannot safely know which rows should be compared.

Developers may believe selected keys are unique, but the actual data may violate that assumption.

## Decision

`grain.keys` define row identity for row-level reconciliation.

They are not limited to database primary keys. They may be business keys, natural keys, composite keys, or canonical keys.

Row-level checks require:

- `grain.keys`,
- source uniqueness at that grain,
- target uniqueness at that grain.

If uniqueness fails, row-level checks must be blocked.

Aggregate checks may continue when they do not require row-level identity.

## Row-level checks affected

This applies to checks such as:

- `missing_keys`,
- `extra_keys`,
- `row_diff`,
- `sampled_row_diff`,
- `sampled_value_match`,
- `full_value_match`,
- row-level exact value match,
- row-level numeric tolerance match,
- row-level timestamp tolerance match.

## Sampling does not remove the requirement

Sampled row-level checks still require uniqueness inside the sampled comparable output.

CDC latest-window row-level checks require uniqueness inside the incremental window.

## Segmenting columns

Segmenting columns should use `metrics.group_by`, not `grain.keys`, unless they truly identify one comparable row.

Example:

```yaml
metrics:
  - name: revenue_by_country_status
    type: sum
    column: revenue
    group_by:
      - country
      - status
```

Here `country` and `status` are dimensions, not row identity.

## Consequences

The compiler and runner should include duplicate-key checks before row-level value checks.

Example behavior:

```text
FAIL duplicate_source_keys
PASS duplicate_target_keys
SKIP row_diff: source grain keys are not unique
```

The default uniqueness mode should be required.

Relaxed uniqueness behavior may be added later only with explicit configuration and strong warnings.
