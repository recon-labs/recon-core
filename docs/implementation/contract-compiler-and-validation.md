# Contract Compiler and Validation

## Purpose

The contract compiler turns authored contracts into explicit compiled contracts and compiled checks.

The validator rejects unsafe, ambiguous, incompatible, or underspecified behavior before execution whenever possible.

See
`docs/decisions/adr-0015-compiled-artifact-schema-and-versioning.md`
for the compiled artifact schema, versioning, stable ID, and compiler coding
pattern decision.

## Compiler inputs

Primary inputs:

- parsed project,
- manifest,
- parsed contracts,
- check packs,
- sample policies,
- tolerance policies,
- schema policies,
- endpoint resources,
- project defaults,
- package resources,
- adapter registry and capabilities when available.

## Compiler outputs

Primary outputs:

```text
target/compiled_contracts/*.yml
target/compiled_checks/*.yml
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

`target/compiled_sql/` is written when `recon compile --render-sql` succeeds.
When SQL rendering is not requested or cannot render a check, compiled checks
still include typed plans and explicit rendering metadata.

Internal outputs:

```text
CompiledProject
CompiledContract
CompiledCheck
CheckPlan
```

## Compiler phases

Recommended compile phases:

```text
1. load parsed resources
2. resolve project and file defaults
3. resolve endpoint refs
4. normalize contracts
5. resolve columns and metrics
6. expand check packs
7. compile metrics into checks
8. resolve sampling for each check
9. resolve tolerances and null rules
10. resolve schema policies
11. resolve CDC policies
12. validate check requirements
13. validate adapter capabilities
14. produce typed check plans
15. render adapter SQL where possible
16. write compiled artifacts
```

The compiler should not make database-specific SQL strings the primary internal
representation. It should create typed compiled checks and typed check plans.
Adapters render those plans into dialect-specific SQL when SQL output is needed.

The current compiler implementation supports the first end-to-end artifact
path:

- parse current authored contract files,
- expand supported check packs,
- compile explicit `sum` metrics,
- write compiled contract and compiled checks YAML artifacts,
- mark rendering as `not_rendered`.

Explicit authored checks outside supported check-pack and metric compilation
return a clear diagnostic until their typed plans are implemented.

Compiler entry points that build stable compiled contract, check, or plan IDs
should validate project, contract, check, and metric name parts before building
IDs. Invalid stable ID parts must return structured diagnostics instead of
allowing helper APIs to raise unhandled exceptions.

Compile should fail validation when no contracts are discovered. A successful
compile must represent at least one authored contract.

## Compiler validation boundaries

Compiler validation should follow the same separation used by mature
manifest-based tools: source-file discovery, parsed models, graph/resource
lookup, validation, and artifact writing stay separate. For Recon, the parser
remains responsible for structural authored-file parsing, while the compiler
owns validation that depends on compiled intent, check-pack expansion, metrics,
policies, or identity requirements.

Implementation guidance:

- add focused compiler validation/resolution modules before adding broad logic
  to `compiler/compile.py`,
- keep diagnostics structured and aligned with ADR 0016,
- validate against parsed/typed internal models rather than raw YAML where a
  typed model exists,
- preserve current strict rejection for unsupported check-pack invocation
  fields until ADR 0018 artifact visibility exists,
- validate duplicate same-pack invocations as errors until invocation aliasing
  is designed,
- do not resolve or validate references to local/package check-pack resources,
  sampling policies, tolerance policies, schema policies, endpoint resources,
  packages, or macros until those resources have typed loaders under ADR 0017;
  unsupported built-in check-pack names still fail validation instead of
  compiling as silent no-ops,
- keep top-level contract `normalization` unsupported until contract-level
  policy defaults are designed; validate normalization only on surfaces the
  current parser accepts,
- keep adapter metadata validation, all-column expansion, row-level value check
  execution, and CDC execution separate from compiler-only validation.

## Columns, metrics, and checks

Compiler rules:

```text
columns = eligible comparison fields and rules
metrics = named aggregate comparisons that compile into checks
checks = explicit execution intent
check packs = reusable execution intent that expands into checks
```

Columns do not create checks.

Metrics do create checks.

Check packs create checks through expansion.

## Column validation and value-comparison surface

Column behavior is governed by ADR 0019.

If no `columns` block is defined, explicit metrics and explicit checks may name
columns directly. Existence and physical type validation may be deferred until
adapter metadata is available.

If a `columns` block is defined, it is the explicit comparison surface.
Explicit checks and metrics that reference columns outside that surface should
fail validation.

Metric columns must be declared only when the contract has a `columns` block.
Group-by columns follow the same rule as metric value columns.

Check-level column selections narrow the declared surface. They do not mutate
contract-level column declarations.

Column validation should include:

- invalid column declarations,
- duplicate canonical column names,
- undeclared column references when a declared surface exists,
- invalid check-level selectors,
- column/check eligibility conflicts,
- incompatible authored column categories,
- unused declared columns as warnings.

The current compiler validates the supported authored declaration surface,
duplicate declared names, unsupported all-column requests, metric references
against declared columns, and `sum` metrics against declared `numeric` columns.
Column `description` must be a string when declared. Column `timezone` is
reserved for future timestamp policy support and is rejected until that gate is
implemented. The compiler does not yet enforce column-level `checks`
eligibility, emit unused-column warnings, resolve all-column expansion, or
validate physical adapter metadata.

Adapter metadata validation should cover physical column existence, physical
types, and unresolved all-column expansion.

## No silent all-column comparison

All-column comparison must be explicit:

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

When `*` is used, the compiler should resolve and write the actual column list into compiled artifacts when metadata is available.

Raw `*` must never appear in typed check plans. If adapter metadata is not
available, all-column expansion must remain deferred and visible through
diagnostics/artifacts; checks that need concrete columns must not execute.

## Check-pack expansion

Check packs must expand into explicit compiled checks.

Example authored contract:

```yaml
checks:
  use:
    - recon_core.basic_equivalence
```

The current compiler supports check-pack names as strings and object entries
with only a `name` field. Check-pack invocation config and overrides are gated
by ADR 0018; fields other than `name` must fail validation instead of being
silently ignored until full support is implemented.

The current compiler also rejects duplicate invocations of the same check pack
within one contract. Multiple instances require a future invocation alias or
instance identity so compiled check origins and artifact summaries remain
unambiguous.

Contracts must compile into at least one check from supported check packs or
explicit metrics.

Compiled output should show checks such as:

```yaml
compiled_checks:
  - name: row_count_diff
    type: row_count_diff
  - name: missing_keys
    type: missing_keys
```

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

The expanded checks should lower to typed operations as follows:

| Check | Typed operation | Required capability |
| --- | --- | --- |
| `row_count_diff` | `row_count` on both sides, then `compare_counts` | `row_count` |
| `missing_keys` | `key_diff` with `source_minus_target` | `key_diff` |
| `extra_keys` | `key_diff` with `target_minus_source` | `key_diff` |
| `null_source_keys` | `null_key` with `side: source` | `null_key` |
| `null_target_keys` | `null_key` with `side: target` | `null_key` |
| `duplicate_source_keys` | `duplicate_key` with `side: source` | `duplicate_key` |
| `duplicate_target_keys` | `duplicate_key` with `side: target` | `duplicate_key` |

`null_key` checks actual data values in declared identity keys. It is not a
schema nullability check.

## Empty expansion

If a check pack requires inputs and expands to no checks, default behavior is error.

Example:

```yaml
checks:
  use:
    - recon_core.some_future_pack
```

Diagnostic:

```text
recon_core.some_future_pack expanded to no checks.
```

ADR 0018 locks future `on_empty` values as `error`, `warn`, and `skip`. The
default remains error. `warn` and `skip` must not suppress invalid config,
missing required keys, unknown packs, or other safety validation failures.

## Check-pack invocation config

The future typed invocation model should normalize both supported authored
forms into one internal model:

```yaml
checks:
  use:
    - recon_core.basic_equivalence
    - name: recon_core.some_pack
      on_empty: error
      config:
        severity: error
        sampling: full
        tolerance: null
        params: {}
        checks:
          row_count_diff:
            severity: warn
```

Implementation rules:

- keep current strict rejection until typed invocation config is implemented,
- accept only `name`, `on_empty`, and `config` as invocation fields,
- validate `on_empty` before expansion,
- validate `config` against the check pack schema before expansion,
- reject unknown config keys, unknown `params`, unknown generated check names,
  and config that cannot apply to generated checks,
- apply pack-wide config before `config.checks.<generated_check_name>`
  overrides,
- never let config bypass required grain keys, required CDC keys, key safety
  checks, adapter capability checks, or explicit schema-ignore rules,
- write invocation and resolved-config details into compiled artifacts before
  accepting `config`, `on_empty: warn`, or `on_empty: skip`.

## Metric compilation

Each explicit metric compiles into one aggregate comparison check. Metrics do
not require `grain.keys`; `metrics.group_by` is aggregate segmentation, not row
identity.

The current compiler supports these metric fields:

```text
name
type
column
group_by
tolerance
```

Unknown metric fields must fail validation so typos do not silently change
compiled intent.

Example:

```yaml
metrics:
  - name: total_revenue
    type: sum
    column: revenue
  - name: revenue_by_month
    type: sum
    column: revenue
    group_by:
      - month
    tolerance: 0.01
```

Compiled ungrouped metric check:

```yaml
- name: total_revenue
  type: sum_diff
  origin:
    kind: metric
    name: total_revenue
  identity:
    kind: none
    keys: []
  metric:
    type: sum
    column: revenue
    group_by: []
  plan:
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
```

Compiled grouped metric check:

```yaml
- name: revenue_by_month
  type: grouped_aggregate_diff
  origin:
    kind: metric
    name: revenue_by_month
  identity:
    kind: none
    keys: []
  metric:
    type: sum
    column: revenue
    group_by:
      - month
  tolerance: 0.01
  plan:
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
```

The first compiler implementation supports explicit `sum` metrics. Metric
names must be unique within a contract; duplicate names fail validation with
`RC_VALIDATE_DUPLICATE_METRIC_NAME`.

Metric column references follow ADR 0019. When a contract declares a `columns`
block, metric value and group-by columns must be inside that declared surface.
Metric column types must be compatible with metric type, using authored column
categories during compile validation and adapter metadata when physical types
are required.

Explicit metrics are the first aggregate compilation path. The compiler must
not infer aggregate checks from eligible numeric columns unless a future
decision explicitly enables that behavior and defines the artifact visibility.

## Sampling resolution

Sampling precedence:

```text
check-level
check-pack-level
contract-level
project-level
framework default
```

Every compiled check should have resolved sampling.

Examples:

```yaml
sampling: full
```

```yaml
sampling:
  policy: latest_changed_records
```

The current compiler supports contract-level `sampling.default_policy` as
`full` or a non-empty named sampling policy string. When a `sampling` block is
declared, `default_policy` is required. Unsupported sampling fields, missing or
non-string `default_policy` values, or empty policy names must fail validation
instead of compiling as full sampling.

Sampling does not remove non-null or uniqueness requirements for row-level checks.

## Tolerance and null resolution

Tolerance, null, and normalization behavior is governed by ADR 0009.

Resolve each policy family independently.

Precedence:

```text
check-level
column-level
contract-level inline policy
named contract policy reference
project-level default policy
framework default
```

Milestone 5 may validate and resolve MVP policy shapes, but named tolerance
policy references require the ADR 0017 resource loader before they can be
resolved.

Compiled checks should show resolved tolerance, null, and normalization
behavior when that policy affects a compiled check.

The current compiler validates supported MVP policy shapes but does not resolve
named policy references or execute row-level policy behavior. Contract-level
`nulls`, metric tolerance, and column-level tolerance/nulls/normalization are
validated where those surfaces are currently accepted.

MVP numeric tolerance supports absolute tolerance only:

```yaml
tolerance: 0.01
```

or:

```yaml
tolerance:
  type: absolute
  value: 0.01
```

Relative tolerance, percentage tolerance, and timestamp tolerance execution are
future gated and must not be silently accepted as executable behavior.

Default null behavior:

```text
NULL != ''
```

Resolved comparisons use null-safe equality: two null values compare equal, one
null and one non-null value compare different, and string sentinels such as
`''`, `' '`, `'NULL'`, or `'N/A'` remain different from null unless
`nulls.treat_as_null` explicitly configures them.

String normalization defaults to no steps. The supported explicit shape is
ordered:

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

Allowed simple steps are `trim`, `collapse_whitespace`, `lower`, and `upper`.
Allowed MVP regex is limited `regex_replace` with literal replacement.
Duplicate simple steps, `lower` with `upper`, unsupported regex features,
arbitrary SQL, macro references, and locale-specific behavior must fail until
separately designed.

String-like null sentinels are configured as:

```yaml
nulls:
  treat_as_null:
    values:
      - ""
      - "NULL"
    regex:
      - "^\\s*$"
```

Sentinel matching runs after normalization steps and applies only to
string-like value comparison.

## Schema policy resolution

Schema policies should resolve:

- ignored source columns,
- ignored target columns,
- ignored patterns,
- type compatibility mode,
- precision/scale compatibility mode,
- nullable compatibility mode.

Schema ignore behavior must be visible in compiled artifacts.

## CDC policy resolution

CDC checks must have enough configuration to understand CDC mode.

Examples:

```yaml
cdc:
  mode: upsert
  timestamp_column: updated_at
```

```yaml
cdc:
  keys:
    same_as: grain
```

```yaml
cdc:
  keys:
    - source_order_id
```

```yaml
cdc:
  delete_mode: soft_delete
  source_deleted_column: is_deleted
  target_deleted_column: is_deleted
```

Missing required CDC config should fail validation.

CDC checks that validate key coverage, update propagation, delete propagation,
or changed-row value comparison must resolve CDC identity. `cdc.keys` are
separate from `grain.keys`. The compiler must not silently copy `grain.keys`
into CDC checks unless the contract explicitly says `same_as: grain`.

The current compiler should resolve one default comparison identity and one
default CDC identity per contract. Multiple named grains, multiple named CDC
identities, and per-check or per-pack identity role binding require a future
decision before implementation.

The current compiler validates `cdc.keys` only when that field is declared. It
accepts explicit non-empty string key lists and `cdc.keys: {same_as: grain}`
when `grain.keys` exists. Missing, empty, or malformed declared CDC keys fail
with `RC_VALIDATE_INVALID_CDC_KEYS`. The compiler does not validate CDC modes,
delete behavior, ordering, windows, or CDC execution semantics yet.

## Grain and uniqueness validation

Row-level checks require `grain.keys`.

Row-level value checks require non-null and unique source and target keys after filters, sampling, or windows are applied.

The compiler can validate the presence of keys. The runner may need to validate actual uniqueness using duplicate-key checks.

Compiled plans should place null-key and duplicate-key checks before row-level value checks.

If row-level value checks require these safety checks and the user did not
author them explicitly, the compiler should generate them with origin
`framework_required_safety_check`.

`missing_keys` and `extra_keys` may compile as distinct non-null key coverage
checks even when null-key or duplicate-key safety checks also exist. Null and
duplicate failures still block row-level value checks.

`recon_core.basic_equivalence` requires `grain.keys`. It should fail validation
when grain is missing rather than silently compiling only `row_count_diff`.

## Adapter capability validation

Each check declares required adapter capabilities.

Compile should fail if required capabilities are known to be missing.

If capabilities are unknown until runtime, compiled artifacts should mark validation as deferred.

Capability validation should include typed operation requirements. For example,
a check plan that requires null-safe equality, timestamp diff, temporary tables,
or portable hashing must declare those requirements before adapter SQL is
rendered.

Adapter API version compatibility should be checked before execution. If an
adapter does not support the required adapter API version, Recon should return a
clear diagnostic rather than attempting a partial run.

## Typed check plans

Compiled checks should be lowered into typed check plans before execution.

Example operation families:

```text
row_count
aggregate
grouped_aggregate
key_diff
duplicate_key
null_safe_equal
cast
limit
hash
timestamp_diff
schema_metadata
```

The typed plan is owned by `recon-core`. SQL dialect rendering is owned by
adapters.

Generated SQL should be traceable back to the typed operations that produced it.
This keeps compiled artifacts debuggable and prevents adapter code from
silently changing comparison semantics.

## Diagnostics

Validation should produce structured diagnostics with stable codes. Diagnostic
timing and code ownership are locked in
`docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`.

Examples:

```text
RC_COMPILE_UNKNOWN_CHECK_PACK
RC_COMPILE_EMPTY_CHECK_PACK
RC_VALIDATE_CHECK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_CHECK_REQUIRES_CDC_KEYS
RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_NO_CONTRACTS_FOUND
RC_VALIDATE_NO_COMPILED_CHECKS
RC_VALIDATE_CDC_DELETE_MODE_REQUIRED
RC_VALIDATE_CDC_ORDERING_REQUIRED
RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE
RC_COMPILE_UNKNOWN_SAMPLE_POLICY
RC_ADAPTER_CAPABILITY_UNSUPPORTED
```

Use `RC_COMPILE_*` for compiler resolution problems and `RC_VALIDATE_*` for
semantic safety rules that run during compile. Use `RC_ADAPTER_*` for adapter
type, capability, metadata, rendering, or query failures.

## Compiled artifact requirements

Compiled artifacts should show:

- original resource name,
- source file path,
- source and target,
- identity kind and declared keys,
- resolved defaults,
- generated checks,
- check origins,
- check requirements,
- prerequisites and blocking policy,
- sampling,
- tolerances,
- null rules,
- schema rules,
- CDC rules,
- evidence behavior,
- diagnostics.

Compiled artifacts should use the top-level artifact header:

```text
artifact_type
artifact_version
recon_version
generated_at
invocation_id
```

Stable IDs should use these forms:

```text
contract.<project>.<contract>
check.<project>.<contract>.<check>
plan.<project>.<contract>.<check>
```

Stable ID parts must be safe before the compiler builds IDs. Project names,
contract names, check names, and metric names that cannot be represented in
stable IDs must produce structured validation diagnostics instead of unhandled
exceptions.

Current stable ID parts must:

- start with a letter or underscore,
- contain only letters, numbers, and underscores.

Invalid stable ID parts should report `RC_VALIDATE_INVALID_STABLE_ID_PART`.

Duplicate contract names make compiled artifact paths ambiguous because
compiled contract and compiled checks filenames are contract-name based. Compile
must report duplicate contract names before artifact writing and must not
silently overwrite generated artifacts.

Contract names must also be unique when compared case-insensitively for compiled
artifact filenames. Names such as `Sales` and `sales` have distinct stable IDs
but can target the same filename on common case-insensitive filesystems. Compile
must report `RC_VALIDATE_COMPILED_ARTIFACT_FILENAME_COLLISION` before artifact
writing in this case.

## Implementation pattern

The compiler should follow the existing parser and manifest style:

- frozen slotted dataclasses for compiler and artifact models,
- `StrEnum` for statuses, kinds, operation types, and artifact types,
- `TypedDict` for serialized public shapes,
- explicit `to_dict()` serialization,
- thin CLI modules,
- services that orchestrate rather than build ad hoc artifacts,
- dedicated artifact writer classes.

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

Tests should cover model serialization, stable ID helpers, check-pack
expansion, explicit metric compilation, typed plan generation, artifact
writers, compile service behavior, and CLI behavior. Golden tests should be
reserved for final artifact snapshots.

## Design principle

The compiler is the safety layer between clean authored YAML and executable reconciliation checks.
