# ADR 0014: Key Semantics and Check Dependencies

## Context

Recon compares source and target outputs. Some checks only need counts or
aggregates. Other checks need to match one source row to one target row. CDC
checks may need a separate identity for insert, update, and delete propagation.

The existing design defines `grain.keys` as row identity for row-level
reconciliation. That is necessary, but not sufficient for CDC behavior. Many CDC
systems use the source table primary key, unique key, or event key to identify
changed rows. That CDC identity can differ from the business or canonical key
used to compare source and target outputs.

If Recon treats every key as the same concept, it can produce misleading
evidence. For example, a contract may compare rows by a business key while CDC
delete propagation depends on the source primary key. Those are related but not
identical assumptions.

Mature tools support this separation in different ways:

- dbt keeps tests explicit and records compiled/run artifacts.
- Data diff tools require primary-key-like columns for row-level diffing, even
  when those columns are not formal database primary keys.
- Data-quality tools model uniqueness as an explicit validation.
- CDC systems expose update/delete behavior through physical or event identity.

Recon should use those patterns without becoming a generic data-quality or CDC
movement tool.

## Decision

Recon will model comparison identity and CDC identity as separate concepts.

`grain.keys` define source-target comparison row identity.

`cdc.keys` define CDC or change propagation identity.

They may be the same, but Recon must never silently assume that they are the
same.

Checks and check packs must declare their identity requirements. The compiler
must validate requirements that can be checked before execution. The runner must
validate data-dependent requirements, such as null or duplicate keys, before
running dependent checks.

Recon must prefer blocked or failed checks with clear diagnostics over guessed
matching or misleading evidence.

## Identity Concepts

### Comparison identity

Comparison identity is the identity used to match source rows to target rows for
row-level reconciliation.

It is declared with `grain.keys`:

```yaml
grain:
  keys:
    - customer_business_key
    - month
```

`grain.keys` are not limited to database primary keys. They may be business
keys, natural keys, composite keys, or canonical keys exposed by compare views
or queries.

### CDC identity

CDC identity is the identity used to validate change propagation.

It is declared with `cdc.keys`:

```yaml
cdc:
  keys:
    - source_order_id
```

When CDC identity is intentionally the same as comparison identity, the contract
should say so explicitly:

```yaml
cdc:
  keys:
    same_as: grain
```

CDC keys are often source primary keys, source unique keys, or event keys from a
CDC stream. They may be physical keys rather than business comparison keys.

### Canonical output rule

For MVP behavior, keys refer to columns in the comparable source and target
outputs. If physical source and target key names differ, users should normalize
them through compare views or query endpoints.

Recon must not guess source-target key mappings.

Future versions may add explicit source/target key mapping, but it must be a
public schema change with validation and evidence support.

## Check Dependency Rules

Every check definition should declare requirements such as:

- `requires_grain_keys`,
- `requires_unique_grain`,
- `requires_non_null_grain`,
- `requires_cdc_keys`,
- `requires_cdc_ordering`,
- `requires_columns`,
- `requires_metrics`,
- required adapter capabilities.

Default requirements:

| Check family | Requires `grain.keys` | Requires non-null grain | Requires unique grain | Requires `cdc.keys` | Notes |
| --- | --- | --- | --- | --- | --- |
| `row_count_diff` | No | No | No | No | Counts comparable rows. |
| aggregate checks and metrics | No | No | No | No | `metrics.group_by` is segmentation, not row identity. |
| schema checks | No | No | No | No | Uses adapter metadata and schema policy. |
| `missing_keys` | Yes | No | No | No | Runs as distinct non-null key coverage at the declared grain. |
| `extra_keys` | Yes | No | No | No | Runs as distinct non-null key coverage at the declared grain. |
| `null_source_keys` | Yes | No | No | No | Safety check for row-level comparison. |
| `null_target_keys` | Yes | No | No | No | Safety check for row-level comparison. |
| `duplicate_source_keys` | Yes | No | No | No | Safety check for row-level comparison. |
| `duplicate_target_keys` | Yes | No | No | No | Safety check for row-level comparison. |
| row-level value checks | Yes | Yes | Yes | No | Blocked if null or duplicate grain checks fail. |
| CDC freshness and count checks | No | No | No | Sometimes | Require CDC mode/window/timestamp config. |
| CDC key coverage and propagation checks | Sometimes | Sometimes | Sometimes | Yes | Use change identity. |
| CDC row-value checks over changed records | Yes | Yes | Yes | Yes | Use CDC keys for change selection and grain keys for comparison. |

`missing_keys` and `extra_keys` may run as distinct non-null key coverage even
when nulls or duplicates exist. Null-key and duplicate-key safety checks must
report those failures separately, and key coverage must not claim that
row-level value matching is safe.

Duplicate-key checks should still run when null keys exist so users can see
both null-key and duplicate-key failure signals.

## Check-Pack Rules

`recon_core.basic_equivalence` requires `grain.keys`.

It must not silently weaken to `row_count_diff` when grain is missing. If users
want only row-count behavior, they should request `row_count_diff` explicitly.

It should compile row count, distinct non-null key coverage, null-key safety, and
duplicate-key safety checks.

`recon_core.value_equivalence` requires `grain.keys`, non-null grain keys, unique
source grain keys, unique target grain keys, and eligible value columns.

`recon_core.aggregate_equivalence` does not require `grain.keys` when it has
explicit metrics or aggregate-compatible columns.

`recon_core.schema_equivalence` does not require `grain.keys`.

`recon_core.cdc_equivalence` must declare which generated checks require
`cdc.keys`, `grain.keys`, CDC ordering, CDC window configuration, and delete-mode
configuration.

## Safety Check Generation

If a row-level value check requires non-null and unique grain keys, the compiler
should ensure that the required safety checks exist.

If the user did not author them explicitly, the compiler should generate visible
checks:

```text
null_source_keys
null_target_keys
duplicate_source_keys
duplicate_target_keys
```

Generated safety checks must have origin:

```text
framework_required_safety_check
```

They must appear in compiled artifacts, run results, and evidence.

## Blocking and Result Semantics

Missing key declarations are validation errors.

Data-dependent key problems are check failures:

- null grain keys fail the corresponding null-key safety check,
- duplicate grain keys fail the corresponding duplicate-key safety check,
- null CDC keys fail the corresponding CDC key safety check when required,
- duplicate CDC keys fail the corresponding CDC key safety check when required.

Dependent checks must be skipped when their prerequisites fail.

A skipped dependent check must include:

- status `skipped`,
- `blocked_by`,
- `skip_reason`,
- diagnostics or messages that identify the failed prerequisite,
- evidence links when available.

Recon must not run row-level value checks by arbitrarily choosing one of several
matching rows.

Aggregate, schema, row count, and other independent checks may continue when
their own requirements are satisfied.

## CDC Delete Semantics

CDC delete behavior must be explicit when CDC checks are used.

Supported delete-mode design targets:

```yaml
cdc:
  delete_mode: none
```

```yaml
cdc:
  delete_mode: hard_delete
```

```yaml
cdc:
  delete_mode: soft_delete
  source_deleted_column: is_deleted
  target_deleted_column: is_deleted
```

```yaml
cdc:
  delete_mode: operation_column
  operation_column: op
  delete_value: D
```

If `delete_mode: none` is configured, compiled artifacts and evidence must state
that delete propagation is not validated.

CDC update/delete propagation checks require `cdc.keys` unless a future mode
defines a different explicit identity mechanism.

CDC checks that depend on event ordering or incremental windows must require
explicit ordering or watermark configuration. Recon must not infer an ordering
column from names such as `updated_at` without configuration.

## Artifact and Evidence Visibility

Compiled checks should show:

- requirement metadata,
- identity kind used by the check,
- declared `grain.keys`,
- declared `cdc.keys`,
- generated prerequisite checks,
- blocking policy,
- origin metadata,
- adapter capability requirements.

Run results should show:

- whether a check used `grain.keys`, `cdc.keys`, or no key identity,
- prerequisite check results,
- `blocked_by`,
- `skip_reason`,
- key null counts,
- duplicate key counts,
- bounded example keys when evidence configuration allows them.

Evidence should show:

- declared comparison identity,
- declared CDC identity,
- CDC delete mode,
- CDC window and ordering assumptions,
- which CDC behavior was not validated,
- whether row-level checks were blocked.

## Diagnostics

Recommended diagnostic codes:

```text
RC_VALIDATE_CHECK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_CHECK_REQUIRES_CDC_KEYS
RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_CDC_DELETE_MODE_REQUIRED
RC_VALIDATE_CDC_ORDERING_REQUIRED
RC_RUNTIME_CHECK_BLOCKED_BY_FAILED_PREREQUISITE
RC_RUNTIME_NULL_GRAIN_KEYS
RC_RUNTIME_DUPLICATE_GRAIN_KEYS
RC_RUNTIME_NULL_CDC_KEYS
RC_RUNTIME_DUPLICATE_CDC_KEYS
```

Diagnostic messages must identify the check, contract, required identity, and
fix.

## Testing Strategy

Implementation should include tests for:

- missing `grain.keys` validation,
- missing `cdc.keys` validation,
- strict `basic_equivalence` behavior without grain,
- safety check generation,
- distinct non-null key behavior for `missing_keys` and `extra_keys`,
- null-key check failures,
- duplicate-key check failures,
- blocked row-level value checks,
- result `blocked_by` and `skip_reason` serialization,
- compiled artifact identity and requirement metadata,
- CDC delete-mode validation,
- CDC key requirement validation.

Adapter and end-to-end tests should prove that generated typed plans and
rendered SQL preserve these semantics.

## Alternatives Considered

### Use `grain.keys` for every key-dependent behavior

Rejected.

This conflates business comparison identity with CDC change identity and can
make update/delete validation unreliable.

### Infer CDC keys from `grain.keys`

Rejected as a default.

CDC systems often use primary keys or event keys that differ from comparison
keys. Inference would hide a critical assumption.

### Allow `basic_equivalence` to run only row count without grain

Rejected.

This would turn a key-coverage check pack into a weaker check pack without
making the downgrade obvious. Users should request `row_count_diff` explicitly
when they only want row counts.

### Block `missing_keys` and `extra_keys` whenever duplicates exist

Rejected as the default.

Distinct non-null key coverage is still useful evidence when nulls or duplicates
exist, as long as Recon clearly reports those safety failures and blocks
row-level value checks.

## Consequences

Contract syntax gains `cdc.keys`.

Compiler and check models need explicit requirement metadata.

Compiled artifacts and run results become more verbose, but safer and more
explainable.

The check engine needs prerequisite tracking before row-level value checks are
implemented.

CDC implementation becomes clearer because update/delete checks cannot run
without explicit change identity.

## Implementation Guidance

Milestone 4 should include identity and requirement metadata in compiled check
models even before every check type exists.

Milestone 5 should implement validation for missing `grain.keys`, missing
`cdc.keys`, strict `basic_equivalence`, CDC delete mode, and CDC ordering where
the relevant checks are compiled.

Milestone 7 should implement prerequisite tracking and blocked check results.

CDC check implementation should start with a small supported subset and keep
unsupported CDC modes explicit in diagnostics and evidence.

## References

- ADR 0007: Grain Keys and Row-Level Uniqueness
- ADR 0011: CDC Policy and Delete Modes
- ADR 0013: Typed Check Plans and Adapter SQL Rendering
- dbt data tests: https://docs.getdbt.com/reference/resource-properties/data-tests
- dbt artifacts: https://docs.getdbt.com/reference/artifacts/manifest-json
- dbt run results: https://docs.getdbt.com/reference/artifacts/run-results-json
- Datafold Data Diff: https://docs.datafold.com/data-diff/how-datafold-diffs-data
- Google Data Validation Tool: https://github.com/GoogleCloudPlatform/professional-services-data-validator
- Soda reconciliation checks: https://docs.soda.io/sodacl-reference/recon
- Great Expectations uniqueness: https://docs.greatexpectations.io/docs/reference/learn/data_quality_use_cases/uniqueness/
- AWS DMS validation: https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Validating.html
- AWS DMS PostgreSQL CDC limitations: https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Source.PostgreSQL.html
- Debezium PostgreSQL connector: https://debezium.io/documentation/reference/stable/connectors/postgresql.html
