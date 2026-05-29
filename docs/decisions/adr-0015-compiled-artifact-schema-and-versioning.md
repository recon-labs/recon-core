# ADR 0015: Compiled Artifact Schema and Versioning

## Context

Recon separates authored contracts from generated execution intent. Users write
clean equivalence contracts, but before execution they need to inspect exactly
what Recon resolved, expanded, validated, and plans to run.

ADR 0003 established parse, compile, and run artifacts. ADR 0006 established
the compiler and validator pipeline. ADR 0013 established typed check plans and
adapter SQL rendering. ADR 0014 established separate comparison and CDC
identity semantics.

Milestone 4 introduces compiled contract and compiled check artifacts. Those
artifacts become user-facing and automation-facing generated files, so their
shape needs a durable decision before implementation.

Mature data tools informed this decision:

- dbt uses versioned generated artifacts and stable identifiers for automation.
- SQLMesh makes planned changes inspectable before execution.
- Great Expectations and Soda keep validation/check results structured.
- Data diff tools such as DVT show the importance of explicit keys for
  source-target comparison.
- OpenLineage shows a useful extensibility pattern through additive metadata,
  but Recon does not need a lineage-facet model for compiler artifacts yet.

Recon should adopt the artifact discipline without copying another project's
domain model.

## Decision

Recon will write two YAML compiled artifact types for each contract:

```text
target/compiled_contracts/<contract_name>.yml
target/compiled_checks/<contract_name>.yml
```

The compiled contract artifact answers:

```text
What did Recon resolve this authored contract to mean?
```

The compiled checks artifact answers:

```text
What exact checks and typed plans will Recon run?
```

`recon run` must use compiled intent instead of reinterpreting raw authored YAML
as the execution contract.

`recon compile` should treat `target/compiled_contracts/` and
`target/compiled_checks/` as generated snapshots. After project configuration
loads and `target-path` is known, Recon should remove existing top-level
`*.yml` files in those directories before parsing and compilation continue so
removed, renamed, or invalid current contracts do not leave stale executable
intent behind.

Compiled artifact directories and their `target-path` ancestry must be real
directories. Recon should reject symlinked compiled artifact directories or
symlinked ancestry rather than following them during cleanup or artifact writes.
Exact compiled artifact output files must also not be symlinks, even when
overwrite behavior is explicitly enabled. Compiled artifact filenames should be
built from safe single-segment names so standalone artifact writers cannot write
outside their generated artifact directories.

Compiled SQL is not required for the first compiler implementation. Until
adapter rendering exists, compiled checks must include typed plans and a
rendering status such as `not_rendered`. SQL files under
`target/compiled_sql/` are introduced when adapters can render typed plans.

## Artifact Header

Compiled artifacts use the existing Recon top-level artifact header style.
They must not introduce a nested `metadata` envelope.

Required top-level header fields:

```yaml
artifact_type: compiled_checks
artifact_version: 1
recon_version: "0.0.0"
generated_at: "2026-05-21T12:00:00Z"
invocation_id: "01HXAMPLEINVOCATION000000000"
```

Fields:

- `artifact_type` identifies the artifact kind.
- `artifact_version` identifies the artifact schema version.
- `recon_version` identifies the Recon Core version that wrote the artifact.
- `generated_at` is an ISO 8601 UTC timestamp.
- `invocation_id` ties artifacts written by the same compile or run invocation
  together.

`target/manifest.json` already uses top-level `artifact_type`,
`artifact_version`, `recon_version`, and `generated_at`. Compiled artifacts
extend that style with `invocation_id` rather than creating a second envelope
convention.

## Stable Identifiers

Compiled artifacts must include stable IDs.

ID formats:

```text
contract.<project>.<contract>
check.<project>.<contract>.<check>
plan.<project>.<contract>.<check>
```

Examples:

```text
contract.cdc_validation.orders_cdc
check.cdc_validation.orders_cdc.row_count_diff
plan.cdc_validation.orders_cdc.row_count_diff
```

The project, contract, and check name segments must be validated before they are
used in IDs or file paths. Recon should prefer a clear validation error over a
lossy sanitized ID that users cannot predict.

## Compiled Contract Shape

A compiled contract artifact should use this shape:

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

columns:
  exact:
    - status
  numeric:
    - name: total_amount
      tolerance: 0.01
  timestamp:
    - name: updated_at

metrics: []

policies:
  sampling:
    default_policy: latest_changed_records
  tolerance_policy: finance
  nulls:
    treat_as_null:
      values: []
      regex: []
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
  evidence:
    level: detailed
    store_failures: true
    max_failure_rows: 1000

diagnostics: []
```

The compiled contract artifact records resolved meaning and policies. It should
not be the primary list of executable checks.

Policy field compatibility:

- `policies.tolerance_policy` is the authored named tolerance policy reference
  when present. It must not be silently reinterpreted as a resolved tolerance
  object.
- `policies.tolerance` is a future optional field reserved for resolved
  inline/default tolerance policy once a typed resolver exists.
- `policies.nulls` carries accepted contract-level null policy when present.
- `policies.normalization` is a future optional field reserved for an accepted and resolved
  normalization policy surface. The current contract parser does not accept
  top-level contract `normalization`.
- adding optional policy fields can remain `artifact_version: 1` only when the
  change is additive and existing field meanings stay stable.
- removing or renaming `policies.tolerance_policy`, or changing its meaning,
  requires compatibility review and likely a compiled artifact version bump.

## Compiled Checks Shape

A compiled checks artifact should use this shape:

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

Every compiled check must include:

- `id`,
- `name`,
- `type`,
- `origin`,
- `identity`,
- `requirements`,
- `prerequisites`,
- `blocking_policy`,
- resolved `sampling`,
- resolved `tolerance` when applicable,
- `plan`,
- `rendering`,
- `diagnostics`.

## Origin Metadata

Every compiled check must record why it exists.

Allowed origin kinds:

```text
explicit_check
metric
check_pack
framework_required_safety_check
```

Examples:

```yaml
origin:
  kind: explicit_check
```

```yaml
origin:
  kind: metric
  name: revenue_by_month
```

```yaml
origin:
  kind: check_pack
  name: recon_core.basic_equivalence
```

```yaml
origin:
  kind: framework_required_safety_check
  required_by:
    - sampled_value_match
```

Check-pack expansion and framework-generated safety checks must be visible in
compiled artifacts.

## Typed Check Plans

The typed check plan is the execution contract owned by Recon Core.

Plan fields:

```yaml
plan:
  id: plan.cdc_validation.orders_cdc.missing_keys
  operations:
    - type: key_diff
      direction: source_minus_target
      identity:
        kind: grain
        keys:
          - order_id
  required_capabilities:
    - key_diff
```

Typed operation payloads should be modeled explicitly in Python. They must not
be arbitrary ad hoc dictionaries passed through the compiler service.

Adapters render typed plans into SQL or equivalent execution requests. Adapter
rendering must not define reconciliation semantics.

For key safety checks, `null_source_keys` and `null_target_keys` use the
side-specific `null_key` operation. `null_key` checks data values for nulls in
declared identity keys; it is separate from schema nullability checks.

## Rendering Metadata

Compiled checks must include rendering metadata even when SQL is not generated.

Allowed rendering statuses:

```text
not_rendered
rendered
deferred
unsupported
```

Examples:

```yaml
rendering:
  status: not_rendered
  sql_paths: []
```

```yaml
rendering:
  status: rendered
  sql_paths:
    - target/compiled_sql/orders_cdc/row_count_diff/source.sql
    - target/compiled_sql/orders_cdc/row_count_diff/target.sql
```

The first compiler implementation should write `not_rendered` until adapter SQL
rendering exists.

## Built-in Check-Pack Scope

`recon_core.basic_equivalence` is the first built-in check pack that must be
compiled.

It expands exactly to:

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

`row_count_diff` itself can run without keys, but the pack is a row/key coverage
standard and therefore requires grain.

`missing_keys` and `extra_keys` use distinct non-null grain-key coverage. Null
and duplicate grain-key checks report key safety failures separately.

`recon_core.aggregate_equivalence` remains a design target. It must not infer
aggregate checks from numeric columns until a future decision explicitly enables
that behavior and defines artifact visibility. Explicit metrics compile into
aggregate checks without needing the aggregate check pack.

Empty check-pack expansion is an error.

Check-pack invocation config and non-error empty expansion are governed by ADR
0018. Compiled artifacts must include invocation summaries before accepting
`config`, `on_empty: warn`, or `on_empty: skip`.

Column/value comparison and all-column expansion are governed by ADR 0019.
Compiled artifacts must expose resolved column metadata before executing value
checks or accepting raw wildcard column selectors as resolved behavior.

## Metric Compilation Scope

Explicit metrics compile into aggregate checks.

Example authored metric:

```yaml
metrics:
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01
```

Example compiled check:

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
  prerequisites: []
  blocking_policy:
    on_prerequisite_failure: skipped
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
  diagnostics: []
```

Metric compilation must not depend on `grain.keys`.

Ungrouped aggregate metrics use `aggregate` operations followed by
`compare_aggregates`. Grouped aggregate metrics use `grouped_aggregate`
operations followed by `compare_grouped_aggregates`.

## Diagnostics

Compiled artifacts must embed structured diagnostics.

Root-level diagnostics describe contract-level or artifact-level issues.
Check-level diagnostics describe a specific compiled check.

ADR 0016 supersedes this section for diagnostic timing and code-family
ownership. The codes below were the compiler-artifact recommendation at the time
of this decision; use ADR 0016 when implementing new validation diagnostics.

Recommended compiler diagnostic codes:

```text
RC_COMPILE_UNKNOWN_CHECK_PACK
RC_COMPILE_UNSUPPORTED_CHECK_PACK
RC_COMPILE_EMPTY_CHECK_PACK
RC_COMPILE_DUPLICATE_COMPILED_CHECK
RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_CHECK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_CHECK_REQUIRES_CDC_KEYS
RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE
RC_VALIDATE_UNSUPPORTED_ADAPTER_CAPABILITY
```

Errors must prevent execution unless a future explicit mode allows deferred
execution with visible diagnostics.

## Python Implementation Pattern

The compiler implementation should follow the existing parser and manifest
style.

Required coding patterns:

- use `@dataclass(frozen=True, slots=True)` for compiler and artifact models,
- use `StrEnum` for statuses, kinds, operation types, and artifact types,
- use `TypedDict` for public serialized shapes,
- use explicit `to_dict()` methods for artifact serialization,
- keep CLI modules thin,
- keep services as orchestration boundaries,
- keep artifact writing in writer classes,
- keep compiler modules small and focused.

Recommended module shape:

```text
src/recon_core/compiler/models.py
src/recon_core/compiler/ids.py
src/recon_core/compiler/check_packs.py
src/recon_core/compiler/metrics.py
src/recon_core/compiler/plans.py
src/recon_core/compiler/compile.py
src/recon_core/artifacts/compiled_contract_writer.py
src/recon_core/artifacts/compiled_check_writer.py
```

The compile service should orchestrate project loading, parsing, compilation,
and artifact writing. It should not build ad hoc artifact dictionaries inline.

## Testing Strategy

Compiler implementation should include focused tests for:

- model serialization,
- stable ID helpers,
- `recon_core.basic_equivalence` expansion,
- missing grain behavior for `recon_core.basic_equivalence`,
- explicit metric compilation,
- columns not creating checks by themselves,
- empty check-pack expansion errors,
- no-check compiled contracts,
- typed plan generation,
- compiled artifact writers,
- compile service behavior,
- CLI command behavior.

Golden artifact tests should be limited to final compiled artifact shapes.
Most tests should assert structured models and dictionaries directly so they do
not become brittle.

## Versioning and Compatibility

Artifact versions start at `1`.

Additive fields are allowed within the same artifact version when they do not
change existing field meaning.

Renaming fields, removing fields, changing field meaning, or changing required
field semantics requires an artifact version bump and a decision update.

Generated artifacts should remain under ignored paths such as `target/`.

## Alternatives Considered

### One compiled artifact per contract

Rejected.

A single artifact would mix resolved contract meaning with executable check
plans. Keeping compiled contracts and compiled checks separate makes review,
runner behavior, and future evidence generation cleaner.

### JSON-only compiled artifacts

Rejected for the initial compiler artifacts.

JSON is useful for machine integration, but compiled contract and check
artifacts are meant to be inspected by humans before execution. YAML is easier
to read while still being structured.

### Nested metadata envelope

Rejected.

The existing manifest uses top-level artifact header fields. Compiled artifacts
should extend that convention rather than introducing a second envelope pattern.

### Generate SQL as the primary compile output

Rejected.

Recon's execution contract is the typed check plan. SQL is an adapter-rendered
artifact derived from typed plans.

### Infer aggregate checks from numeric columns immediately

Rejected for the first compiler implementation.

Implicit aggregate inference can surprise users and create noisy evidence.
Explicit metrics are clearer and preserve business intent.

## Consequences

Milestone 4 has a concrete artifact contract to implement.

The runner can use compiled intent instead of raw YAML.

The artifact model remains consistent with the existing manifest header style.

The compiler implementation gets explicit coding patterns and test boundaries.

Future SQL rendering, adapters, and evidence can attach to typed plans without
changing core reconciliation semantics.

## References

- dbt manifest artifact: `https://docs.getdbt.com/reference/artifacts/manifest-json`
- dbt run results artifact: `https://docs.getdbt.com/reference/artifacts/run-results-json`
- dbt adapter creation: `https://docs.getdbt.com/guides/adapter-creation`
- SQLMesh plans: `https://sqlmesh.readthedocs.io/en/stable/concepts/plans/`
- SQLMesh snapshots: `https://sqlmesh.readthedocs.io/en/stable/concepts/architecture/snapshots/`
- Great Expectations validation result:
  `https://docs.greatexpectations.io/docs/reference/api/core/expectationvalidationresult_class/`
- Soda metrics and checks:
  `https://docs.soda.io/soda-documentation/soda-v3/sodacl-reference/metrics-and-checks`
- Google DVT:
  `https://github.com/GoogleCloudPlatform/professional-services-data-validator`
- OpenLineage object model: `https://openlineage.io/docs/spec/object-model/`
