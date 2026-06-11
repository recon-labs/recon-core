# ADR 0007: Grain Keys and Row-Level Uniqueness

## Context

Row-level reconciliation requires matching a source row to a target row.

If keys are missing or duplicated, Recon cannot safely know which rows should be compared.

Developers may believe selected keys are unique, but the actual data may violate that assumption.

## Decision

`grain.keys` define source-target comparison row identity for row-level reconciliation.

They are not limited to database primary keys. They may be business keys, natural keys, composite keys, or canonical keys.

CDC change identity is separate. CDC checks that validate update, delete, or change propagation should use `cdc.keys` as defined in ADR 0014.

This ADR defines one contract-level comparison grain. It does not define
multiple named grains, per-check grain overrides, or per-check-pack grain
binding. Those are future advanced-contract features that require a separate
decision before implementation.

Row-level value and row-matching checks require:

- `grain.keys`,
- source uniqueness at that grain,
- target uniqueness at that grain.

If uniqueness fails, dependent row-level value checks must be blocked.

Aggregate checks may continue when they do not require row-level identity.

Missing key coverage checks such as `missing_keys` and `extra_keys` may still
run as distinct non-null key coverage when nulls or duplicates exist, but they
must not imply that row-level value matching is safe.

## Row-level checks affected

This applies to row-level value and row-matching checks such as:

- `row_diff`,
- `sampled_row_diff`,
- `sampled_value_match`,
- `full_value_match`,
- row-level exact value match,
- row-level numeric tolerance match,
- row-level timestamp tolerance match.

## Sampling does not remove the requirement

Sampled row-level value checks still require uniqueness inside the sampled
comparable output.

CDC latest-window row-level value checks require non-null keys and uniqueness
inside the incremental window.

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

The compiler should also generate required null-key and duplicate-key safety checks for row-level value checks when users did not author them explicitly. These generated checks must be visible in compiled artifacts.

Example behavior:

```text
FAIL duplicate_source_keys
PASS duplicate_target_keys
BLOCKED row_diff: source grain keys are not unique
```

The default uniqueness mode should be required.

Relaxed uniqueness behavior may be added later only with explicit configuration and strong warnings.

See ADR 0014 for the full key semantics, CDC key, check dependency, and blocked-result rules.
