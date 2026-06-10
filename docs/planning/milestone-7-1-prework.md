# Milestone 7.1 Prework

## Purpose

This is the lightweight prework artifact for Milestone 7.1: check-engine
boundary and result model.

Milestone 7.1 is high-risk because it touches run behavior, check-engine
boundaries, result semantics, diagnostics, CLI-visible non-execution behavior,
and future generated result compatibility. This lightweight artifact is required
before implementation, but it is not sufficient by itself. Implementation must
also use the final acceptance/conformance matrix, BDD scenarios, gate
satisfaction proof, test plan, prompt/docs drift check, implementation map, and
phase-exit checklist before coding.

Split Decision: Already Split / Follow Existing Split.

## Scope

Milestone 7.1 builds the first check-engine boundary behind the existing
`recon run` command without executing source or target data checks.

Build scope:

- check-engine service boundary for already compiled checks,
- in-memory `RunResult`, `ContractResult`, and `CheckResult` model shape,
- check status taxonomy and run/contract aggregate status taxonomy,
- machine-readable reason-code taxonomy for non-executed checks,
- command/result separation between `ServiceResult` and reconciliation results,
- internal dispatch boundary for already compiled check types,
- prerequisite and blocking result representation,
- safe diagnostic/result serialization shape for in-memory results,
- runtime diagnostic codes for missing, invalid, empty, unsupported, blocked,
  or not-executable compiled check inputs,
- negative guarantees that prove the first boundary did not execute adapters or
  write generated output.

## Non-Goals

Milestone 7.1 must not implement:

- adapter SQL execution,
- profile-backed adapter lifecycle,
- runtime profile loading,
- source or target connections,
- SQL rendering,
- source or target queries,
- row-count execution,
- grain-key safety execution,
- aggregate metric execution,
- row-level value comparison,
- schema policy execution,
- tolerance, null, or normalization execution,
- CDC runtime behavior,
- public authored `checks: [...]` support,
- public check registry or package-provided check registration,
- `target/run_results.json`,
- terminal run-summary finalization,
- evidence artifacts,
- reports,
- failure-detail output,
- result/evidence sink writes,
- production result tables,
- state writes,
- materialized or staged data,
- probabilistic summaries,
- Bloom filters or sketch-based key coverage,
- selectors,
- partial compile or partial run,
- selected-scope generated outputs,
- selected-scope run results,
- selected-scope evidence.

## Expected Behavior

`recon run` should move from an unimplemented placeholder toward a real service
boundary that consumes already compiled check artifacts. It should not parse
authored YAML or recompile contracts.

The first boundary should:

- load already compiled check intent or receive equivalent in-memory compiled
  check fixtures in tests,
- route compiled checks through an internal dispatch boundary,
- return in-memory result objects with deterministic dictionary serialization,
- preserve safe diagnostics with code, severity, message, path, resource
  context, and hint where available,
- report unsupported compiled check types as `not_executable`,
- report unsupported typed operations as `not_executable`,
- report checks that belong to later execution phases as `not_executable`,
- report prerequisite dependency failures as `blocked`,
- report missing, malformed, incompatible, or empty compiled-check inputs as
  runtime diagnostics and non-pass outcomes,
- keep artifact, evidence, failure-detail, state, and sink references empty
  unless a later owning phase actually writes those outputs.

The first boundary must not report source-target equivalence unless an actual
comparison executed. Because Milestone 7.1 does not execute adapters or queries,
normal compiled checks should not produce factual `pass`, `fail`, or `warn`
results except in isolated model tests that explicitly supply already evaluated
in-memory fixtures.

## Status And Reason Taxonomy

Check statuses:

```text
pass
fail
warn
error
skipped
blocked
not_executable
```

Run and contract aggregate statuses:

```text
pass
fail
warn
error
skipped
blocked
not_executable
no_checks
```

`unsupported` and `not_yet_executable` are not statuses. They are reason-code
concepts under `not_executable`.

First-boundary reason codes:

- `prerequisite_failed`,
- `prerequisite_error`,
- `prerequisite_missing`,
- `unsupported_check_type`,
- `unsupported_typed_operation`,
- `missing_engine_capability`,
- `unsupported_execution_placement`,
- `unsupported_materialization_policy`,
- `not_implemented_in_current_phase`,
- `skipped_by_policy`, reserved until skip policy exists,
- `selected_out`, reserved until selectors exist.

`no_checks` is not equivalent to `pass`. Empty compiled-check scope must not
look like successful source-target reconciliation.

## Runtime Diagnostics

Milestone 7.1 owns these first-boundary runtime diagnostic codes:

- `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND`,
- `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID`,
- `RC_RUNTIME_NO_COMPILED_CHECKS`,
- `RC_RUNTIME_CHECK_NOT_EXECUTABLE`,
- `RC_RUNTIME_UNSUPPORTED_CHECK_TYPE`,
- `RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION`,
- `RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT`,
- `RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY`,
- `RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE`,
- `RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR`.

These diagnostics explain non-execution. They are not mismatch evidence and
must not expose raw source/target values, query text, relation names, rendered
profile values, credentials, raw database errors, raw tracebacks, or unredacted
artifact contents.

## Affected Docs And Decisions

Milestone 7.1 implementation must stay consistent with:

- `docs/implementation/mvp-build-order.md`,
- `docs/implementation/testing-plan.md`,
- `docs/implementation/result-model.md`,
- `docs/implementation/check-engine.md`,
- `docs/implementation/errors-and-diagnostics.md`,
- `docs/architecture/check-engine.md`,
- `docs/architecture/diagnostics-and-errors.md`,
- `docs/architecture/domain-models.md`,
- `docs/compatibility/public-contract-inventory.md`,
- `docs/compatibility/compatibility-matrix.md`,
- `docs/compatibility/change-checklist.md`,
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`,
- `docs/decisions/adr-0014-key-semantics-and-check-dependencies.md`,
- `docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`,
- `docs/decisions/adr-0021-execution-placement-and-comparison-engine-strategy.md`,
- `docs/decisions/adr-0022-evidence-privacy-failure-detail-and-result-sinks.md`.

## Required Tests

Milestone 7.1 implementation must add tests for:

- check status serialization,
- run and contract aggregate status serialization,
- `no_checks` aggregation and non-pass behavior,
- reason-code serialization,
- `blocked` prerequisite representation with `blocked_by`,
- `not_executable` representation for unsupported compiled check types,
- `not_executable` representation for unsupported typed operations,
- `not_executable` representation for behavior assigned to later execution
  phases,
- missing compiled-check artifact diagnostics,
- malformed or incompatible compiled-check artifact diagnostics,
- empty compiled-check scope diagnostics,
- safe diagnostic preservation for code, severity, message, path, resource
  context, and hint,
- separation between command-level `ServiceResult` and reconciliation result
  objects,
- internal dispatch for compiled check types without public authored check
  registry behavior,
- negative proof that no adapter/profile lifecycle starts,
- negative proof that no SQL is rendered or executed,
- negative proof that no `target/run_results.json` is written,
- negative proof that no evidence, report, failure-detail, state, result table,
  sink, probabilistic summary, Bloom/sketch artifact, selector output, or
  selected-scope output is written.

The final high-risk acceptance/conformance matrix and BDD scenarios must map
each required behavior to a test, an existing test, or explicit out-of-scope
rationale before implementation starts.

## Compatibility Impact

Milestone 7.1 touches planned public result and diagnostic surfaces, but it must
not stabilize a generated result artifact.

Compatibility decisions:

- no new public YAML syntax,
- no generated result artifact version,
- no `RUN_RESULT_VERSION`,
- no stable `target/run_results.json` schema,
- no adapter API change,
- no adapter capability claim,
- no package compatibility change,
- no selector compatibility claim,
- no evidence/report/failure-detail schema,
- no sink/table schema.

The in-memory result model and dictionary serialization are pre-alpha internal
surfaces for service and test plumbing. A stable machine-readable result schema
belongs to the future run-result artifact phase.

## Security And Privacy Impact

Milestone 7.1 must avoid source/target data exposure by construction.

Security and privacy requirements:

- do not load runtime profiles,
- do not resolve credentials,
- do not open source or target connections,
- do not execute source or target queries,
- do not emit raw source/target values,
- do not emit raw keys, relation rows, relation names, query text, rendered
  profile values, database errors, raw tracebacks, or credential-like text,
- preserve diagnostic messages after sanitization,
- keep artifact/evidence/sink references empty unless a later writer actually
  writes them.

## Placement Constraint

Milestone 7.1 may reserve internal in-memory placement and capability metadata,
but it must not implement execution placement.

It must not decide or execute:

- source-side operation execution,
- target-side operation execution,
- same-context comparison,
- adapter-managed intermediate comparison,
- external comparison engines,
- Recon-local Python fallback comparison,
- materialization or staging.

Unsupported placement or materialization requirements should produce
`not_executable` with machine-readable reason codes and diagnostics.

## Evidence, Sink, And State Constraint

Milestone 7.1 may reserve internal artifact-reference and sink-reference slots,
but those lists must remain empty unless a later owning phase writes outputs.

It must not write:

- local result artifacts,
- evidence artifacts,
- reports,
- failure details,
- result/evidence sinks,
- result tables,
- local state,
- remote or database-backed state,
- large-result stores.

Sink placement remains separate from execution placement.

## Public Contract Decision

Milestone 7.1 is a pre-alpha public-surface planning and implementation unit.
The check-engine service boundary, result status taxonomy, reason-code
taxonomy, prerequisite/blocking representation, and diagnostics are planned
public surfaces. The generated result artifact is not implemented or stabilized
in this milestone.

Implementation must update compatibility docs if it changes any status name,
reason code, diagnostic code, command output, or serialized dictionary field
from this prework.

## Changelog Decision

No changelog entry is required for this prework artifact.

During implementation, add a changelog entry only if user-visible behavior,
public contract semantics, CLI behavior, generated artifact behavior,
compatibility promises, release guidance, support ranges, or reconciliation
outcomes change.

## Definition Of Done

Milestone 7.1 is complete only when:

- the check-engine service boundary exists behind `recon run`,
- in-memory `RunResult`, `ContractResult`, and `CheckResult` models exist,
- status and reason-code enums match this prework,
- command-level `ServiceResult` remains separate from reconciliation results,
- internal dispatch handles already compiled check types without exposing a
  public authored check registry,
- unsupported and not-yet-executable compiled checks produce
  `not_executable` results with reason codes and diagnostics,
- prerequisite dependency failures produce `blocked` results with `blocked_by`
  and reason codes,
- missing, malformed, incompatible, and empty compiled-check inputs produce
  non-pass runtime diagnostics,
- diagnostics preserve safe code, severity, message, path, resource context,
  and hint where available,
- no adapter/profile lifecycle starts,
- no SQL is rendered or executed,
- no generated result artifact, evidence, report, failure detail, state, sink,
  table, probabilistic summary, Bloom/sketch artifact, selector output, or
  selected-scope output is written,
- required tests are implemented and pass,
- compatibility docs still match implemented behavior,
- the final acceptance/conformance matrix has no uncovered required rows,
- BDD workflow scenarios pass or are explicitly out of scope,
- the phase-exit checklist passes.

## Remaining Blockers Before Coding

Implementation must not start until the following follow-up prework is complete:

- final 7.1 acceptance/conformance matrix,
- final 7.1 edge-case matrix,
- final 7.1 BDD/workflow scenarios,
- gate satisfaction proof,
- phase-exit checklist,
- exact implementation file/test map,
- prompt/docs drift check.
