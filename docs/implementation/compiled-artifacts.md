# Compiled Artifacts

## Purpose

Compiled artifacts make resolved Recon behavior visible before execution.

They are generated outputs under `target/` and should not be committed.

See
`docs/decisions/adr-0015-compiled-artifact-schema-and-versioning.md`
for the durable artifact schema decision.

## Artifact paths

The compiler writes one compiled contract artifact and one compiled checks
artifact per contract:

```text
target/compiled_contracts/<contract_name>.yml
target/compiled_checks/<contract_name>.yml
```

Adapter-rendered SQL belongs under `target/compiled_sql/` when SQL rendering is
available:

```text
target/compiled_sql/<contract_name>/<check_name>/source.sql
target/compiled_sql/<contract_name>/<check_name>/target.sql
target/compiled_sql/<contract_name>/<check_name>/comparison.sql
```

When SQL rendering is not available, compiled checks still include typed plans
and should set `rendering.status: not_rendered`.

The current compiler writes compiled contract and compiled checks YAML artifacts
for supported check-pack and metric behavior. It does not write
`target/compiled_sql/` yet.

`recon compile` treats `target/compiled_contracts/` and
`target/compiled_checks/` as generated snapshots. After project configuration
loads and `target-path` is known, Recon removes existing top-level `*.yml` files
from those two directories before parsing and compilation continue. If parsing
or fatal compile validation fails, old compiled artifacts are therefore absent
instead of stale.

Compiled artifact directories must be real directories, not symlinks. Recon
rejects symlinked compiled artifact directories and symlinked `target-path`
ancestry rather than following those paths during cleanup or writes. Exact
compiled artifact output files must also not be symlinks, even when overwrite
behavior is explicitly enabled. Compiled artifact filenames are built from safe
single-segment artifact names; path-like names are invalid for standalone
artifact writers.

## Artifact header

Compiled artifacts use top-level artifact header fields:

```yaml
artifact_type: compiled_checks
artifact_version: 1
recon_version: "0.0.0"
generated_at: "2026-05-21T12:00:00Z"
invocation_id: "01HXAMPLEINVOCATION000000000"
```

`invocation_id` ties artifacts from the same compile or run invocation
together.

## Stable IDs

Compiled artifacts should use stable IDs:

```text
contract.<project>.<contract>
check.<project>.<contract>.<check>
plan.<project>.<contract>.<check>
```

Example:

```text
contract.cdc_validation.orders_cdc
check.cdc_validation.orders_cdc.row_count_diff
plan.cdc_validation.orders_cdc.row_count_diff
```

Because compiled artifact filenames are contract-name based, duplicate contract
names must fail validation before artifact writing. The compiler must not
silently overwrite one compiled contract or compiled checks artifact with
another.

Contract names must also be unique when compared case-insensitively for compiled
artifact filenames. For example, `Sales` and `sales` would produce filenames
that collide on common case-insensitive filesystems, so compile should report
`RC_VALIDATE_COMPILED_ARTIFACT_FILENAME_COLLISION` before writing artifacts.

Compiled artifact writers must not overwrite existing artifacts unless the
caller explicitly opts into overwrite behavior. Case-insensitive filename
collisions remain errors even when overwrite is enabled, because regenerating
`sales.yml` must not replace an existing `Sales.yml` artifact on
case-insensitive filesystems.

Names used in stable IDs must start with a letter or underscore and contain only
letters, numbers, and underscores. Invalid project, contract, check, or metric
name parts should produce `RC_VALIDATE_INVALID_STABLE_ID_PART` diagnostics
instead of unhandled exceptions.

## Compiled contract

A compiled contract is the resolved version of an authored contract.

It answers:

```text
What did Recon resolve this authored contract to mean?
```

It should include:

- project and contract metadata,
- stable contract ID,
- source file path,
- source endpoint,
- target endpoint,
- comparison identity from `grain.keys`,
- CDC identity from `cdc.keys` when relevant,
- columns,
- resolved column metadata after ADR 0019 is implemented,
- metrics,
- resolved defaults,
- resolved sampling policy,
- resolved tolerance policy,
- resolved null policy,
- resolved normalization policy,
- resolved schema policy,
- resolved CDC policy,
- resolved evidence policy,
- diagnostics.

Example:

```yaml
artifact_type: compiled_contract
artifact_version: 1
recon_version: "0.0.0"
generated_at: "2026-05-21T12:00:00Z"
invocation_id: "01HXAMPLEINVOCATION000000000"

project:
  name: cdc_validation
  version: null

contract:
  id: contract.cdc_validation.orders_cdc
  name: orders_cdc
  authored_version: 1
  source_file: contracts/orders_cdc.yml

source:
  connection: source_db
  relation: recon.v_orders_source_compare

target:
  connection: warehouse
  relation: recon.v_orders_target_compare

identity:
  grain:
    keys:
      - order_id
  cdc:
    declaration:
      same_as: grain
    resolved_keys:
      - order_id

policies:
  sampling:
    default_policy: latest_changed_records
  tolerance_policy: finance
  nulls:
    treat_as_null:
      values:
        - ""
      regex: []
  tolerance: null
  normalization: null
  schema:
    ignore_target_columns:
      - _dms_operation
      - _dms_timestamp
      - _loaded_at
  cdc:
    mode: upsert
    timestamp_column: updated_at
    delete_mode: soft_delete
    source_deleted_column: is_deleted
    target_deleted_column: is_deleted

diagnostics: []
```

Current policy field lock:

- `policies.tolerance_policy` is the authored named tolerance policy reference
  when present; it is not a resolved tolerance object.
- `policies.nulls` preserves the accepted contract-level null policy when
  present.
- `policies.tolerance` is reserved for resolved inline/default tolerance policy
  when a typed resolver exists.
- `policies.normalization` is reserved for an accepted and resolved
  normalization policy surface. The current contract parser does not accept
  top-level contract `normalization`.
- additive optional policy fields may keep `artifact_version: 1` only when
  existing field meanings do not change.
- renaming, removing, or changing the meaning of existing policy fields
  requires compatibility review and likely an artifact version bump.

## Compiled checks

A compiled checks artifact shows exactly what will run.

It answers:

```text
What exact checks and typed plans will Recon run?
```

Every compiled check should include:

- stable check ID,
- check name,
- check type,
- origin metadata,
- identity kind and keys,
- requirements,
- prerequisites,
- blocking policy,
- resolved sampling,
- resolved tolerance when applicable,
- resolved null policy when applicable,
- resolved normalization policy when applicable,
- typed check plan,
- rendering metadata,
- diagnostics.

Example:

```yaml
artifact_type: compiled_checks
artifact_version: 1
recon_version: "0.0.0"
generated_at: "2026-05-21T12:00:00Z"
invocation_id: "01HXAMPLEINVOCATION000000000"

project:
  name: cdc_validation
  version: null

contract:
  id: contract.cdc_validation.orders_cdc
  name: orders_cdc
  source_file: contracts/orders_cdc.yml

checks:
  - id: check.cdc_validation.orders_cdc.row_count_diff
    name: row_count_diff
    type: row_count_diff
    origin:
      kind: check_pack
      name: recon_core.basic_equivalence
    identity:
      kind: none
      keys: []
    requirements:
      requires_grain_keys: false
      requires_non_null_grain: false
      requires_unique_grain: false
      requires_cdc_keys: false
      required_columns: []
      required_metrics: []
      required_capabilities:
        - row_count
    prerequisites: []
    blocking_policy:
      on_prerequisite_failure: skipped
    sampling:
      mode: full
    tolerance: null
    plan:
      id: plan.cdc_validation.orders_cdc.row_count_diff
      operations:
        - type: row_count
          side: source
        - type: row_count
          side: target
        - type: compare_counts
      required_capabilities:
        - row_count
    rendering:
      status: not_rendered
      sql_paths: []
    diagnostics: []

diagnostics: []
```

## Check origin

Every compiled check should record why it exists.

Allowed origins:

```text
explicit_check
metric
check_pack
framework_required_safety_check
```

Generated safety checks for null and duplicate keys should use
`framework_required_safety_check` when they were required by another check. When
the same safety checks come directly from `recon_core.basic_equivalence`, their
origin is the check pack.

## Check-pack invocation visibility

Current compiled artifacts show generated checks and their `check_pack` origin.
They do not yet include check-pack invocation summaries because `config`,
`on_empty: warn`, and `on_empty: skip` are not implemented.

Before Recon accepts check-pack invocation config, compiled artifacts must add
visibility for each invocation:

```yaml
check_pack_invocations:
  - name: recon_core.some_pack
    on_empty: error
    authored_config: {}
    resolved_config: {}
    generated_check_ids:
      - check.project.contract.row_count_diff
    diagnostics: []
```

Invocation summaries should follow ADR 0018 and
`docs/compatibility/check-pack-invocation.md`. They must show authored config,
resolved config, generated check IDs, empty-expansion status when applicable,
and diagnostics attached to the invocation.

Adding optional invocation summaries may keep the same compiled artifact
version only when existing readers can ignore them safely and existing field
meanings do not change. Changing check origin, stable check IDs, or generated
check semantics requires compatibility review and may require an artifact
version bump.

## Built-in check-pack expansion

`recon_core.basic_equivalence` expands exactly to:

```text
row_count_diff
missing_keys
extra_keys
null_source_keys
null_target_keys
duplicate_source_keys
duplicate_target_keys
```

The pack requires `grain.keys`. It must not silently weaken to only
`row_count_diff` when grain is missing.

`missing_keys` and `extra_keys` use distinct non-null grain-key coverage. Null
and duplicate grain-key checks report key safety failures separately.

Empty check-pack expansion is an error. A contract that compiles into no checks
is also an error.

Future `on_empty: warn` and `on_empty: skip` behavior is locked by ADR 0018 but
requires invocation summaries before implementation.

Example null-key check plan:

```yaml
- id: check.cdc_validation.orders_cdc.null_source_keys
  name: null_source_keys
  type: null_source_keys
  origin:
    kind: check_pack
    name: recon_core.basic_equivalence
  identity:
    kind: grain
    keys:
      - order_id
  requirements:
    requires_grain_keys: true
    requires_non_null_grain: false
    requires_unique_grain: false
    requires_cdc_keys: false
    required_columns: []
    required_metrics: []
    required_capabilities:
      - null_key
  plan:
    id: plan.cdc_validation.orders_cdc.null_source_keys
    operations:
      - type: null_key
        side: source
        identity:
          kind: grain
          keys:
            - order_id
    required_capabilities:
      - null_key
```

## Metric compilation

Explicit metrics compile into aggregate checks.

Metrics do not require `grain.keys`. `metrics.group_by` is aggregate
segmentation, not row identity.

Ungrouped metrics compile to `sum_diff` checks with source and target
`aggregate` operations followed by `compare_aggregates`.

Example:

```yaml
- id: check.cdc_validation.orders_cdc.total_revenue
  name: total_revenue
  type: sum_diff
  origin:
    kind: metric
    name: total_revenue
  identity:
    kind: none
    keys: []
  requirements:
    requires_grain_keys: false
    requires_non_null_grain: false
    requires_unique_grain: false
    requires_cdc_keys: false
    required_columns:
      - revenue
    required_metrics:
      - total_revenue
    required_capabilities:
      - aggregate
  metric:
    type: sum
    column: revenue
    group_by: []
  plan:
    id: plan.cdc_validation.orders_cdc.total_revenue
    operations:
      - type: aggregate
        side: source
        aggregate: sum
        column: revenue
      - type: aggregate
        side: target
        aggregate: sum
        column: revenue
      - type: compare_aggregates
    required_capabilities:
      - aggregate
  rendering:
    status: not_rendered
    sql_paths: []
```

Grouped metrics compile to `grouped_aggregate_diff` checks with source and
target `grouped_aggregate` operations followed by
`compare_grouped_aggregates`.

Example:

```yaml
- id: check.cdc_validation.orders_cdc.revenue_by_month
  name: revenue_by_month
  type: grouped_aggregate_diff
  origin:
    kind: metric
    name: revenue_by_month
  identity:
    kind: none
    keys: []
  requirements:
    requires_grain_keys: false
    requires_non_null_grain: false
    requires_unique_grain: false
    requires_cdc_keys: false
    required_columns:
      - revenue
      - month
    required_metrics:
      - revenue_by_month
    required_capabilities:
      - grouped_aggregate
  metric:
    type: sum
    column: revenue
    group_by:
      - month
  tolerance:
    type: absolute
    value: 0.01
  nulls:
    treat_as_null:
      values: []
      regex: []
  normalization:
    steps: []
  plan:
    id: plan.cdc_validation.orders_cdc.revenue_by_month
    operations:
      - type: grouped_aggregate
        side: source
        aggregate: sum
        column: revenue
        group_by:
          - month
      - type: grouped_aggregate
        side: target
        aggregate: sum
        column: revenue
        group_by:
          - month
      - type: compare_grouped_aggregates
    required_capabilities:
      - grouped_aggregate
  rendering:
    status: not_rendered
    sql_paths: []
```

`recon_core.aggregate_equivalence` must not infer aggregate checks from numeric
columns unless a future decision explicitly enables that behavior. Explicit
metrics remain the first aggregate path.

## Column visibility

Current compiled contract artifacts preserve raw authored `columns`.

Before row-level value checks, all-column expansion, or column/type validation
are treated as implemented, compiled artifacts must also expose resolved column
metadata:

```yaml
resolved_columns:
  declared:
    - name: revenue
      category: numeric
  all_columns_request: false
  resolved_value_columns:
    - revenue
  excluded_identity_columns:
    - customer_id
  ignored_columns: []
  metadata_validation:
    status: deferred
    diagnostics: []
```

Typed check plans must contain concrete column names only. Raw `*` selectors
must be resolved before execution or reported as deferred/invalid through
diagnostics.

## Row-level prerequisites

Row-level value checks should include prerequisites and blocking policy:

```yaml
- name: sampled_value_match
  type: sampled_value_match
  identity:
    kind: grain
    keys:
      - customer_id
      - month
  prerequisites:
    - null_source_keys
    - null_target_keys
    - duplicate_source_keys
    - duplicate_target_keys
  blocking_policy:
    on_prerequisite_failure: skipped
```

If a prerequisite fails at runtime, dependent row-level value checks should be
skipped with `blocked_by` and `skip_reason` in run results.

## Compiled SQL

SQL is rendered from typed check plans by adapters. The typed plan remains the
core representation of comparison behavior; rendered SQL is the
dialect-specific execution artifact.

Compiled artifacts should preserve enough operation metadata to trace generated
SQL back to its typed plan.

Example after SQL rendering exists:

```yaml
checks:
  - name: row_count_diff
    type: row_count_diff
    plan:
      id: plan.cdc_validation.orders_cdc.row_count_diff
      operations:
        - type: row_count
          side: source
        - type: row_count
          side: target
    rendering:
      status: rendered
      sql_paths:
        - target/compiled_sql/orders_cdc/row_count_diff/source.sql
        - target/compiled_sql/orders_cdc/row_count_diff/target.sql
```

## Diagnostics in artifacts

Compiled artifacts should include structured diagnostics.

Errors should prevent execution unless explicitly allowed by a future mode.

Compiled check artifacts should include declared identities, check
requirements, prerequisites, and blocking policy so users can inspect why a
check can run or why it may be skipped later.

## Stability

Artifact formats can evolve before 1.0, but changes should be documented.

After artifact formats are used by CI or integrations, changes should be
versioned carefully.

## Design principle

Compiled artifacts are the bridge between readable contracts and trustworthy
execution.
