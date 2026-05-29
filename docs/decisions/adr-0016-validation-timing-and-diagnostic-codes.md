# ADR 0016: Validation Timing and Diagnostic Codes

## Context

Recon is built around explicit parse, compile, run, and evidence artifacts.
Validation errors can change whether artifacts are written, whether checks are
safe to run, and whether generated evidence is trustworthy.

Before the Milestone 5 validation rulebook expands validation behavior, Recon
needs a durable rule for:

- which validation runs in each phase,
- how diagnostic code families map to those phases,
- when validation may be deferred,
- how warnings differ from errors and check failures,
- how diagnostics appear in artifacts.

dbt Core is the primary open-source reference for phase separation. dbt reads
files, parses resources through parser classes, processes references and docs,
then checks manifest consistency before writing its manifest. dbt also uses
structured events and warning/error handling for parse-time and manifest-time
conditions such as unused resource config paths, missing referenced nodes, and
duplicate resources.

Great Expectations and Soda are useful references for result surfaces: GX
validation results separate `success`, `result`, metadata, and exception
information; Soda distinguishes check result states such as pass, fail, error,
and explicit warn.

Recon should learn from those patterns without becoming a generic data quality
framework. Recon's trust boundary is source-target equivalence evidence, so
ambiguous reconciliation behavior must fail before execution whenever possible.

## Decision

Recon will use phase-owned validation and stable diagnostic code families.

Diagnostic shape remains:

```text
code
severity
message
resource_type
resource_name
path
line
column
hint
```

Do not add a `phase` field to the diagnostic model in this decision. The phase
is expressed by code family, artifact location, and command context. Adding a
diagnostic field would be an artifact schema change and requires a separate
compatibility review.

Diagnostic severities remain:

```text
info
warning
error
```

Check execution statuses remain separate:

```text
pass
fail
warn
error
skipped
```

An error diagnostic means the command must return a non-zero validation,
runtime, or configuration exit category. A check failure means a check executed
successfully and found a mismatch. A skipped check means a prerequisite failed
or an explicit future skip mode applies.

## Phase Ownership

### Configuration phase

Configuration validation happens before parse, compile, or run service logic can
use project state.

Owned by:

- project root discovery,
- `recon_project.yml` loading,
- future profile loading,
- future environment variable resolution,
- command setup such as `recon init` project name/path checks.

Diagnostic code family:

```text
RC_CONFIG_*
```

Configuration errors prevent generated artifact writes unless the command has a
specific safe artifact to write without project context. Current parse and
compile behavior does not write manifest or compiled artifacts when project
configuration fails.

### Parse phase

Parse validation is structural and authored-file oriented.

Owned by:

- resource discovery for resource kinds the loader currently supports,
- file read failures,
- duplicate-safe YAML loading,
- authored resource top-level shape,
- required fields that do not require resolution,
- scalar/list/object type checks,
- unknown fields in strict schema areas,
- duplicate resource names for loaded resource kinds.

Diagnostic code family:

```text
RC_PARSE_*
```

Parse must not expand check packs, compile metrics, choose executable checks,
resolve comparison policies, validate adapter capabilities, or execute queries.

`recon parse` should write `target/manifest.json` with parse diagnostics when
project configuration succeeded and manifest writing is safe. `recon compile`
must stop before compilation when parse diagnostics contain errors.

### Compile-resolution phase

Compile-resolution validation turns parsed authored intent into explicit
compiled intent and rejects unsupported or unresolved behavior.

Owned by:

- default and reference resolution,
- check-pack lookup and expansion,
- check-pack invocation shape that is supported in the current milestone,
- explicit metric compilation,
- supported sampling/tolerance/schema/CDC policy syntax once those resolvers
  exist,
- stable ID part validation,
- compiled artifact filename collision validation,
- no-contracts and no-compiled-checks validation,
- unsupported current surfaces such as explicit authored checks before they are
  implemented.

Diagnostic code families:

```text
RC_COMPILE_*
RC_VALIDATE_*
```

Use `RC_COMPILE_*` when the problem is expansion, resolution, unsupported
compiler input, or compiler-owned generated structure.

Use `RC_VALIDATE_*` when the problem is a semantic safety rule or public
validation rule, even if the rule runs during `recon compile`.

Compile may write diagnostic-bearing compiled artifacts for a contract when
doing so is safe and useful for inspection, but any error diagnostic prevents
run. Project-level fatal compile validation, such as no contracts found or
case-insensitive compiled artifact filename collisions, should write no compiled
artifacts.

### Adapter metadata and capability validation phase

Adapter validation starts when adapters, profiles, and capabilities exist.

Owned by:

- adapter type resolution,
- adapter API version compatibility,
- declared capability support,
- metadata availability,
- metadata-derived column/type/nullability validation,
- SQL rendering support for typed plans.

Diagnostic code family:

```text
RC_ADAPTER_*
```

If adapter facts are known before execution, unsupported capabilities should
fail before run. If metadata cannot be known until execution, validation may be
deferred only when compiled artifacts or run results visibly record the
deferred condition.

This decision does not define the final adapter validation artifact field. That
belongs with the adapter API, capability validation, and compiled SQL gate.

### Run phase

Run validation and runtime diagnostics happen after compiled intent exists and
execution begins.

Owned by:

- compiled artifact freshness or load errors once run supports artifacts,
- adapter connection and query execution errors,
- data-dependent safety check results,
- prerequisite blocking,
- run result writing,
- state and failure-detail writing.

Diagnostic code families:

```text
RC_RUNTIME_*
RC_ADAPTER_*
```

Data-dependent key problems are check results, not compile-time validation
errors:

- null key checks fail when data contains null keys,
- duplicate key checks fail when data contains duplicate keys,
- dependent row-level value checks are skipped when prerequisite safety checks
  fail.

The runner must not reinterpret raw authored YAML as the source of execution
behavior when compiled intent is available.

### Evidence phase

Evidence diagnostics happen while writing human-facing and machine-facing
evidence outputs.

Owned by:

- evidence/report rendering failures,
- evidence artifact write failures,
- failure-detail truncation reporting,
- redaction failures.

Diagnostic code family:

```text
RC_EVIDENCE_*
```

Core runtime may still surface evidence write failures through service results,
but evidence-specific behavior should use the `RC_EVIDENCE_*` family once the
evidence writer exists.

## Milestone 5 Diagnostic Catalog

Milestone 5 should use the following code catalog unless a later ADR changes it.

| Code | Phase | Severity | Meaning |
| --- | --- | --- | --- |
| `RC_VALIDATE_CHECK_REQUIRES_GRAIN_KEYS` | compile validation | error | A check requiring comparison identity has no `grain.keys`. |
| `RC_VALIDATE_CHECK_REQUIRES_CDC_KEYS` | compile validation | error | A CDC propagation or CDC row-value check has no explicit `cdc.keys`. |
| `RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS` | compile validation | error | A check pack such as `recon_core.basic_equivalence` requires `grain.keys`. |
| `RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE` | compile or adapter metadata validation | error | A check or metric is incompatible with a declared or known column type. |
| `RC_VALIDATE_INVALID_COLUMN_DECLARATION` | compile validation | error | A column block, category, entry, or field has invalid shape. |
| `RC_VALIDATE_DUPLICATE_COLUMN_NAME` | compile validation | error | The same canonical column name is declared more than once. |
| `RC_VALIDATE_UNDECLARED_COLUMN_REFERENCE` | compile validation | error | A metric or check references a column outside an explicit declared surface. |
| `RC_VALIDATE_INVALID_COLUMN_SELECTION` | compile validation | error | A check-level column selector has invalid shape or unsupported wildcard placement. |
| `RC_VALIDATE_COLUMN_NOT_ELIGIBLE_FOR_CHECK` | compile validation | error | A check uses a column whose `checks` eligibility excludes that check. |
| `RC_VALIDATE_ALL_COLUMNS_REQUIRES_METADATA` | adapter metadata validation | error | An all-column request cannot be resolved because source/target metadata is unavailable. |
| `RC_VALIDATE_INVALID_SAMPLING` | compile validation | error | Sampling config is malformed or unsupported in the current milestone. |
| `RC_VALIDATE_RANDOM_SAMPLE_REQUIRES_PERSISTED_KEYS` | compile validation | error | Random row-level sampling lacks persisted sample keys. |
| `RC_VALIDATE_INVALID_CDC_KEYS` | compile validation | error | A declared CDC identity has missing, empty, or malformed `cdc.keys`. |
| `RC_VALIDATE_CDC_CONFIG_REQUIRED` | compile validation | error | A CDC check requires CDC mode/window config that is missing. |
| `RC_VALIDATE_CDC_DELETE_MODE_REQUIRED` | compile validation | error | CDC delete propagation is requested without explicit delete behavior. |
| `RC_VALIDATE_CDC_ORDERING_REQUIRED` | compile validation | error | A CDC check requires ordering or watermark config that is missing. |
| `RC_VALIDATE_SCHEMA_IGNORE_INVALID` | compile validation | error | Schema ignore configuration is malformed or unsafe. |
| `RC_VALIDATE_INVALID_TOLERANCE` | compile validation | error | Tolerance config is malformed or unsupported in the current milestone. |
| `RC_VALIDATE_INVALID_NULL_POLICY` | compile validation | error | Null policy config is malformed or uses unsupported keys or values. |
| `RC_VALIDATE_INVALID_NULL_SENTINEL` | compile validation | error | A string-like null sentinel is malformed, duplicated after normalization, or unsupported for the target column category. |
| `RC_VALIDATE_INVALID_NORMALIZATION` | compile validation | error | Normalization config is malformed or uses unsupported/incompatible operations. |
| `RC_VALIDATE_INVALID_REGEX_NORMALIZATION` | compile validation | error | A regex null sentinel or regex replacement uses invalid syntax or features outside the MVP regex profile. |
| `RC_VALIDATE_TIMESTAMP_TIMEZONE_REQUIRED` | compile or adapter metadata validation | error | Timestamp comparison requires explicit timezone behavior but none was provided. |
| `RC_VALIDATE_METADATA_VALIDATION_DEFERRED` | adapter metadata validation | warning | A metadata-dependent rule cannot be checked until adapter metadata is available. |
| `RC_VALIDATE_UNUSED_DECLARED_COLUMN` | compile validation | warning | A declared column is not used by any compiled check. |

Existing compiler-foundation codes remain valid:

```text
RC_VALIDATE_INVALID_CHECK_PACK_USE
RC_VALIDATE_INVALID_GRAIN_KEYS
RC_VALIDATE_INVALID_STABLE_ID_PART
RC_VALIDATE_COMPILED_ARTIFACT_FILENAME_COLLISION
RC_VALIDATE_NO_CONTRACTS_FOUND
RC_VALIDATE_NO_COMPILED_CHECKS
RC_VALIDATE_INVALID_METRIC
RC_VALIDATE_UNKNOWN_METRIC_FIELD
RC_VALIDATE_UNSUPPORTED_METRIC_TYPE
RC_VALIDATE_DUPLICATE_METRIC_NAME
RC_VALIDATE_METRIC_REQUIRES_NUMERIC_COLUMN
RC_COMPILE_UNKNOWN_CHECK_PACK
RC_COMPILE_EMPTY_CHECK_PACK
RC_COMPILE_UNSUPPORTED_CHECK_PACK_CONFIG
RC_COMPILE_UNSUPPORTED_EXPLICIT_CHECKS
RC_COMPILE_DUPLICATE_COMPILED_CHECK
```

Check-pack invocation config diagnostics are locked by ADR 0018:

```text
RC_VALIDATE_DUPLICATE_CHECK_PACK_INVOCATION
RC_VALIDATE_INVALID_CHECK_PACK_ON_EMPTY
RC_VALIDATE_INVALID_CHECK_PACK_CONFIG
RC_VALIDATE_UNKNOWN_CHECK_PACK_CONFIG_KEY
RC_VALIDATE_UNUSED_CHECK_PACK_CONFIG
RC_PARSE_INVALID_CHECK_PACK_CONFIG_SCHEMA
RC_COMPILE_EMPTY_CHECK_PACK_ALLOWED
RC_COMPILE_EMPTY_CHECK_PACK_SKIPPED
```

Existing parser and configuration codes remain owned by their current phases.

## Deferred Validation

Deferred validation is allowed only when a rule genuinely requires information
that is unavailable in the current phase, usually adapter metadata or execution
results.

Deferred validation must be visible before users trust evidence. It must appear
in at least one generated surface that survives the command:

- manifest diagnostics for parse-time deferred parser information,
- compiled checks diagnostics or requirement metadata for compile-time deferred
  adapter metadata,
- run results for runtime deferred or skipped checks,
- evidence reports for user-facing interpretation.

Deferred validation is not allowed for authored YAML semantics that Recon can
validate locally. Unknown fields, unsupported check-pack config, missing keys,
ambiguous CDC behavior, and unsafe defaults should fail rather than defer.

## Diagnostic Code Policy

Diagnostic codes are not a separate versioned API before 1.0, but they are
public enough that users, CI workflows, and future tools may rely on them.

Rules:

- add new codes to implementation docs before or with implementation,
- future sampling, tolerance, column, check-pack config, resource-reference,
  adapter, result, and evidence validation expansions must reuse this ADR's
  phase ownership and code-family rules,
- each future design phase must lock its rule-specific diagnostics before
  implementation, including code, severity, phase, artifact visibility, and
  test expectations,
- do not reuse a code for a different meaning,
- avoid renaming existing codes without compatibility review,
- test expected codes for each locked validation rule,
- use hints for actionable user repair steps,
- do not include secrets in diagnostic messages, paths, hints, or metadata.

## Consequences

Milestone 5 implementation must add tests for the expected code, severity, and
phase of each locked validation rule.

Parser, compiler, adapter, runner, and evidence code should remain separate.
CLI code should render diagnostics but must not own validation decisions.

Future adapter and evidence work must update this ADR or add a newer ADR if it
changes validation timing, deferred validation behavior, diagnostic fields, or
code-family ownership.

## Alternatives Considered

### Add a `phase` field to every diagnostic

Rejected for this phase.

It may be useful later, but adding it changes generated artifact schemas. Code
families and artifact context are enough for Milestone 5.

### Use only one `RC_ERROR_*` code family

Rejected.

Phase-specific code families make diagnostics easier to route, test, document,
and understand.

### Let validators warn for ambiguous behavior

Rejected as the default.

Recon should prefer a clear error over evidence that looks trustworthy but was
compiled from ambiguous behavior.

### Treat data-dependent key failures as compile-time validation errors

Rejected.

Null and duplicate key data must be checked against the source and target data.
Those are check results and prerequisite blockers, not local compile-time
diagnostics.

## Implementation Guidance

Milestone 5 should implement validation through parser/compiler/validator
modules, not CLI modules.

Recommended implementation shape:

- keep `Diagnostic` as the shared model,
- add code constants close to the validator that emits them,
- keep diagnostic messages specific to contract/check/resource context,
- add focused tests for valid and invalid inputs,
- assert diagnostic code and severity in tests,
- update compiled artifact expectations only when artifact shape changes.

## References

- ADR 0005: Strict Validation and No Silent Magic
- ADR 0006: Contract Compiler and Validation Rules
- ADR 0014: Key Semantics and Check Dependencies
- ADR 0015: Compiled Artifact Schema and Versioning
- dbt Core parser README:
  `https://github.com/dbt-labs/dbt-core/blob/main/core/dbt/parser/README.md`
- dbt Core ManifestLoader:
  `https://github.com/dbt-labs/dbt-core/blob/main/core/dbt/parser/manifest.py`
- dbt Core events:
  `https://github.com/dbt-labs/dbt-core/blob/main/core/dbt/events/types.py`
- Great Expectations `ExpectationValidationResult`:
  `https://docs.greatexpectations.io/docs/reference/api/core/expectationvalidationresult_class/`
- Soda scan result states:
  `https://docs.soda.io/soda-v3/run-a-scan`
