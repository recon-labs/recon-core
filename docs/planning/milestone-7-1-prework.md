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

## Acceptance And Conformance Matrix

Every row below must map to implementation tests before coding is considered
complete.

| Dimension | Cases | Expected behavior | Required test coverage | Docs or gate impact | Out-of-scope rationale |
| --- | --- | --- | --- | --- | --- |
| Service boundary and command/result separation | `recon run` service entry, command-level failure, in-memory run result creation. | `ServiceResult` owns CLI exit category and command diagnostics; reconciliation status lives in `RunResult`, `ContractResult`, and `CheckResult`. | Service tests for `RunService`; model tests proving `ServiceResult` is not reused as `CheckResult`. | Result-model docs and diagnostic output conformance gate. | Runner summary and stable run-result artifact belong to the future runner/result phase. |
| In-memory result model shape | `RunResult`, `ContractResult`, `CheckResult`, diagnostic lists, empty artifact/sink refs. | Models serialize deterministically with status, reason code, `executed`, `blocked_by`, safe diagnostics, and empty output references. | Unit tests for model construction and dictionary serialization. | Public contract inventory tracks this as planned pre-alpha surface. | Stable `target/run_results.json` schema and version constant are not 7.1 scope. |
| Status and reason taxonomy | `pass`, `fail`, `warn`, `error`, `skipped`, `blocked`, `not_executable`, aggregate `no_checks`, all first-boundary reason codes. | Statuses and reason codes match this prework; `unsupported` and `not_yet_executable` are not statuses. | Enum/model tests for every status, reason, invalid combination, and serialization value. | Compatibility matrix and result-model docs. | Additional execution statuses require compatibility review in later phases. |
| Aggregate status behavior | Empty scope, all blocked, all not executable, error plus other statuses, fail plus blocked, warning-only fixtures, all pass fixtures. | `no_checks` is not pass; precedence for non-empty scopes is `error > fail > blocked > not_executable > warn > skipped > pass`; mixed statuses remain visible in counts/results. | Pure aggregation tests using in-memory fixtures. | Result-model docs. | Real pass/fail/warn from database execution belongs to later execution phases. |
| Compiled-check loading boundary | Existing compiled-check artifact path, multiple contracts, source metadata, diagnostic-bearing compiled checks. | 7.1 consumes compiled artifacts or equivalent compiled fixtures only; it does not parse authored YAML or recompile contracts. | Service tests with temporary compiled artifacts and in-memory fixtures. | Parse/compile/run architecture and compiled artifact docs. | Artifact freshness, cache reuse, and selected-scope freshness are later work. |
| Missing, empty, or malformed compiled artifacts | Missing compiled-check directory/file, empty check list, invalid YAML, wrong artifact version, missing required fields. | Produce non-pass runtime diagnostics with locked codes; never report source-target equivalence. | Service/loader tests for each artifact error and safe diagnostic. | Runtime diagnostics docs. | Compile-time validation of authored YAML remains parser/compiler scope. |
| Internal dispatch boundary | Known compiled check type assigned to a later phase, unknown check type, unsupported typed operation. | Dispatch is internal only; unsupported or later-phase checks produce `not_executable` with reason and diagnostics. | Dispatch tests for known-later, unknown, and unsupported operation cases. | Explicit authored checks/check registry gate. | Public authored `checks: [...]`, package checks, and user-extensible registries remain future scope. |
| Prerequisite blocking | Prerequisite failed, errored, missing, duplicate `blocked_by`, multiple blockers. | Dependent check result is `blocked`, `executed=false`, includes `blocked_by`, reason code, and diagnostics. | Model/engine tests for `prerequisite_failed`, `prerequisite_error`, and `prerequisite_missing`. | ADR 0014 key semantics and check dependencies. | Executing grain-key safety checks that create prerequisite failures belongs to the grain-key safety phase. |
| Diagnostic preservation and sanitization | Code, severity, message, path, resource type/name, hint, unsafe raw exception text, unsafe source/target text. | Safe diagnostics preserve actionable fields; raw source/target values, query text, relation names, credentials, raw tracebacks, and database errors are not emitted. | Diagnostic tests for preserved safe fields and redaction/suppression cases. | Diagnostic output message conformance gate and source/target privacy gate. | Adapter/database runtime exception sanitization expands in adapter execution phases. |
| No adapter, profile, or SQL execution | Adapter registry/factory, profile loader, SQL renderer, source/target query call, relation access. | None are invoked by 7.1; compiled checks remain non-executed unless supplied as already evaluated in-memory fixtures. | Negative tests with fakes/mocks that would fail if adapter/profile/renderer/query calls occur. | ADR 0021 placement boundary and adapter/profile gates. | Row-count, grain-key, and aggregate execution belong to later split phases. |
| No generated outputs | `target/run_results.json`, reports, evidence, failure details, state files, result tables, sink writes, compiled SQL writes. | 7.1 writes none of these and records no path/table/object destination as written. | Temporary-directory tests proving no new files, state, reports, sink/table refs, or SQL output are produced. | Generated artifact lifecycle gate, ADR 0022 result/evidence boundary. | Local run-result artifact belongs to the runner/result phase; evidence/report output belongs to evidence phase. |
| Placement and materialization blockers | Unsupported execution placement, required materialization, third-engine comparison, Python fallback temptation. | 7.1 may reserve metadata only; unsupported placement/materialization produces `not_executable`; no fallback runs. | Model/dispatch tests for placement and materialization reason codes plus no-fallback negative tests. | Gate 4I and ADR 0021. | Actual placement policy for row count, key checks, and aggregates is owned by their execution phases. |
| Selector and partial-scope exclusion | `--select`, `--exclude`, partial compile/run, selected-scope metadata, selected-scope artifacts. | 7.1 does not implement selectors or partial run semantics and does not emit selected-scope output. | CLI/service negative tests if selector inputs are present; docs drift check for no selector claims. | Selector readiness gate and artifact freshness gate. | Selector readiness metadata belongs to later result/evidence phases; minimal selectors and rich selectors are future milestones. |
| Probabilistic and Bloom exclusion | Bloom filters, set sketches, probabilistic key coverage, candidate missing/extra records, serialized summaries. | 7.1 emits no probabilistic summaries, artifacts, sink rows, candidate records, or exact/probabilistic classifications beyond reserved empty metadata. | Negative tests proving no probabilistic fields/artifacts are produced and unsupported probabilistic typed ops are `not_executable`. | Gate 4K. | Probabilistic key-diff strategy is future-gated and requires exact/probabilistic semantics before implementation. |
| Privacy of non-executed results | Source/target values, normalized values, diff values, keys, relation names, query text, profile values. | Non-executed results keep data fields empty and diagnostics safe; no raw values leak through messages, refs, or metadata. | Model and service tests for empty value fields and safe diagnostics across blocked/not-executable/error cases. | ADR 0022 and source/target privacy gate. | Policy-controlled value capture belongs to future result/evidence phases. |

## Edge-Case Matrix

Each edge case below must either be covered by tests or explicitly marked out of
scope during implementation review.

| Edge case | Expected 7.1 behavior | Required coverage |
| --- | --- | --- |
| Compiled-check artifact path is missing. | Command-level runtime failure with `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND`; no run pass and no generated output. | Service test with missing target artifact. |
| Compiled-check artifact exists but is unreadable or invalid YAML. | Runtime failure with `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID`; unsafe parser text is not emitted. | Loader/service test with malformed file. |
| Compiled-check artifact has unsupported or wrong artifact version. | Runtime failure with `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID`; no fallback parsing. | Loader/model test for version mismatch. |
| Compiled-check artifact has zero checks. | Aggregate status is `no_checks` or command failure with `RC_RUNTIME_NO_COMPILED_CHECKS`; never `pass`. | Aggregation/service test for empty scope. |
| Compiled check is missing required ID, name, type, or plan fields. | Runtime artifact-invalid diagnostic; no partial result that looks executable. | Loader validation test for each missing field group. |
| Duplicate compiled check IDs appear in one run scope. | Runtime artifact-invalid diagnostic; dispatch does not choose one silently. | Loader validation test. |
| Compiled check type is unknown. | Check result `not_executable`, reason `unsupported_check_type`, diagnostic `RC_RUNTIME_UNSUPPORTED_CHECK_TYPE`. | Dispatch test. |
| Compiled check has known type but operation belongs to later phase. | Check result `not_executable`, reason `not_implemented_in_current_phase` or `unsupported_typed_operation`. | Dispatch test using row-count/key/aggregate fixtures as appropriate. |
| Compiled typed operation is malformed or unrecognized. | Check result `not_executable` or artifact-invalid diagnostic, depending on whether the artifact shape is valid. | Dispatch/loader tests for valid-unknown versus malformed payload. |
| Required engine capability is absent or unknown. | Check result `not_executable`, reason `missing_engine_capability`; no fallback execution. | Capability-fit test with no adapter invocation. |
| Required execution placement is unsupported. | Check result `not_executable`, reason `unsupported_execution_placement`; no Python fallback. | Placement blocker test. |
| Required materialization or staging policy appears. | Check result `not_executable`, reason `unsupported_materialization_policy`; no staging output. | Materialization blocker test. |
| Prerequisite result failed. | Dependent result `blocked`, reason `prerequisite_failed`, `blocked_by` includes prerequisite ID. | Prerequisite model test. |
| Prerequisite result errored. | Dependent result `blocked`, reason `prerequisite_error`, `blocked_by` includes prerequisite ID. | Prerequisite model test. |
| Prerequisite result is missing from the run scope. | Dependent result `blocked`, reason `prerequisite_missing`; no dependency guessing. | Prerequisite model test. |
| Compiled check carries diagnostics from compile. | Runtime result preserves safe diagnostic code, severity, message, path, resource context, and hint. | Diagnostic preservation test. |
| Compiled check references rendered SQL paths from earlier compile output. | 7.1 may preserve references as inert metadata only; it must not open or execute SQL. | Negative file/renderer invocation test. |
| A stale `target/run_results.json` already exists. | 7.1 neither updates nor deletes it; no claim that it wrote a result artifact. | Temp-dir test with preexisting file hash. |
| Report, evidence, state, or sink directories already exist. | 7.1 does not mutate them and does not record destinations as written. | Temp-dir negative mutation test. |
| CLI receives future selector-like option. | 7.1 does not implement selection; unsupported option or unsupported API input fails clearly. | CLI/service negative test if such input is accepted by the implementation surface. |
| Bloom/sketch/probabilistic typed operation appears. | Check result `not_executable` with appropriate unsupported reason; no summary artifact or candidate records. | Dispatch negative test. |
| Source/target value fields would be tempting to fill for non-executed checks. | Values remain empty because no comparison ran. | Result serialization test for blocked and not-executable results. |
| Unexpected check-engine exception occurs. | Sanitized runtime diagnostic `RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR`; no raw traceback or private payload. | Exception sanitization test. |

## BDD Workflow Scenarios

### Scenario 1: Missing Compiled Checks

Given a Recon project has no compiled-check artifact available.
When the user runs `recon run`.
Then Recon reports a runtime diagnostic
`RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND`.
And the command does not report source-target equivalence.
And no `target/run_results.json`, evidence, report, state, or sink output is
written.

### Scenario 2: Empty Compiled Check Scope

Given a compiled-check artifact is present but contains no checks in scope.
When the user runs `recon run`.
Then Recon reports `RC_RUNTIME_NO_COMPILED_CHECKS` or an aggregate `no_checks`
non-pass outcome.
And the result is not reported as `pass`.
And no evidence or run-result artifact is written.

### Scenario 3: Unsupported Compiled Check Type

Given a compiled-check artifact contains a check type with no internal handler.
When the check engine processes the compiled check.
Then the check result has status `not_executable`.
And the reason code is `unsupported_check_type`.
And the diagnostic code is `RC_RUNTIME_UNSUPPORTED_CHECK_TYPE`.
And no adapter, profile, renderer, query, artifact writer, evidence writer,
state backend, or sink writer runs.

### Scenario 4: Later-Phase Typed Operation

Given a compiled check is valid but its typed operation belongs to a later
execution phase.
When the check engine processes the compiled check during Milestone 7.1.
Then the check result has status `not_executable`.
And the reason code identifies unsupported operation or current-phase
non-implementation.
And the check result does not contain source value, target value, diff value,
failure rows, artifact refs, or sink refs.

### Scenario 5: Blocked Dependent Check

Given a compiled dependent check requires a prerequisite check result.
And the prerequisite failed, errored, or is missing.
When the check engine evaluates prerequisites.
Then the dependent check result has status `blocked`.
And `blocked_by` identifies the prerequisite.
And the reason code is `prerequisite_failed`, `prerequisite_error`, or
`prerequisite_missing`.
And the dependent check is not executed.

### Scenario 6: Diagnostic Preservation

Given a compiled check or run boundary produces a safe structured diagnostic.
When `recon run` returns a command result and in-memory reconciliation result.
Then the diagnostic preserves code, severity, message, path, resource context,
and hint where available.
And unsafe raw exception text, source/target query text, relation names,
credentials, profile values, row values, and raw tracebacks are not emitted.

### Scenario 7: No Adapter Execution

Given the project has profile configuration or adapter-capable compiled
metadata available.
When the Milestone 7.1 run boundary processes compiled checks.
Then it does not load profiles.
And it does not instantiate adapters.
And it does not render SQL.
And it does not execute source or target queries.
And any check requiring those capabilities is `not_executable`.

### Scenario 8: No Generated Output

Given the project has writable `target/`, `reports/`, and `state/`
directories.
When `recon run` completes in Milestone 7.1.
Then no `target/run_results.json` is created or modified.
And no evidence, report, failure-detail, state, result-table, sink, compiled
SQL, probabilistic summary, Bloom/sketch, selector, or selected-scope output is
created.

### Scenario 9: Unsupported Placement Or Materialization

Given a compiled check requires unsupported execution placement or
materialization.
When the check engine processes the check.
Then the result is `not_executable`.
And the reason code is `unsupported_execution_placement` or
`unsupported_materialization_policy`.
And Recon does not silently fall back to Python-side comparison or staging.

### Scenario 10: Selectors Are Not Implemented

Given a user or API caller attempts to provide selector or selected-scope input
to Milestone 7.1 run behavior.
When the run boundary receives that input.
Then Recon fails clearly if the implemented API surface accepts that input.
And Recon must not silently ignore selector or selected-scope input.
And it does not perform partial compile, partial run, selected-scope artifact
writing, selected-scope run results, or selected-scope evidence.

### Scenario 11: Probabilistic Key Coverage Is Not Implemented

Given a compiled check references Bloom-filter, sketch, or probabilistic
key-diff behavior.
When the check engine processes the check during Milestone 7.1.
Then the result is `not_executable`.
And Recon emits no serialized summary, candidate missing/extra rows,
probabilistic evidence, or exact/probabilistic proof claim.

### Scenario 12: Existing Output Is Not Mutated

Given stale or manually created `target/run_results.json`, report, evidence,
state, or sink-like files already exist.
When the Milestone 7.1 run boundary executes.
Then it does not update or delete those files.
And it does not record those paths or destinations as written by the current
run.

## Gate Satisfaction Proof

This section proves that the design gates needed for Milestone 7.1 are
represented before implementation. "Satisfied for 7.1 prework" means the
design and documentation are explicit enough for implementation planning.
Implementation must still prove each applicable row with tests and phase-exit
review.

| Gate or decision | 7.1 applicability | Proof in this prework | Implementation requirement |
| --- | --- | --- | --- |
| Split decision and lightweight prework | Milestone 7 is already split and 7.1 is the check-engine boundary/result-model slice. | This artifact states `Split Decision: Already Split / Follow Existing Split`, scope, non-goals, expected behavior, affected docs, required tests, compatibility, security, privacy, and Definition of Done. | Preserve 7.1 as a no-execution slice. Do not move row-count, key-safety, aggregate, runner artifact, or evidence behavior into 7.1. |
| High-risk acceptance and BDD planning | 7.1 touches result semantics, diagnostics, run behavior, and future public output surfaces. | The acceptance/conformance matrix, edge-case matrix, and BDD scenarios enumerate positive, negative, privacy, output, placement, selector, and probabilistic cases. | Every required row must map to a test, an existing test, or a documented out-of-scope decision before implementation is complete. |
| Check-engine execution boundary | 7.1 creates the first service boundary without data execution. | Scope and expected behavior require already compiled checks only and explicitly prohibit parsing, compiling, profile loading, adapter execution, SQL rendering, and source/target queries. | Implement only the compiled-check service/model boundary. Any check needing runtime execution must be `not_executable` or `blocked`, not silently executed. |
| Typed check-plan boundary | 7.1 may consume compiled typed intent but must not expand the typed operation catalog. | Non-goals exclude new runtime typed operations. The matrix covers unsupported typed operations and later-phase operations. | Preserve existing compiled intent shape unless a compatibility update is made. Unknown valid operations produce `not_executable`; malformed artifacts produce artifact diagnostics. |
| Key semantics and prerequisite blocking | 7.1 needs prerequisite result representation but does not execute key checks. | Status taxonomy includes `blocked`; reason codes include prerequisite failure, error, and missing cases; matrix and BDD scenarios require `blocked_by`. | Implement prerequisite blocking representation only. Do not execute grain-key checks or infer dependency success. |
| Runtime diagnostics and diagnostic output conformance | 7.1 owns first-boundary runtime diagnostic codes. | Runtime diagnostic codes are locked, and matrices require safe preservation of code, severity, message, path, resource context, and hint. | Tests must prove locked codes, deterministic serialization, and suppression of unsafe raw exceptions, query text, credentials, and source/target values. |
| Internal dispatch versus public check registry | 7.1 may introduce internal dispatch for compiled checks. | The matrix allows internal dispatch and explicitly excludes public authored `checks: [...]`, public registry behavior, package-provided checks, and user-extensible check registration. | Keep dispatch internal. Do not expose or stabilize authored check registry semantics in 7.1. |
| Execution placement and materialization | 7.1 may reserve in-memory placement/capability blockers only. | Placement constraints and matrix rows require unsupported placement/materialization to become `not_executable` and prohibit Python fallback, staging, and generated outputs. | Implement blocker metadata and diagnostics only. Do not decide or execute source-side, target-side, same-context, intermediate, external, or Recon-local comparison placement. |
| Evidence, sink, and state boundaries | 7.1 may reserve empty artifact and sink references only. | Evidence/sink/state constraints and no-generated-output scenarios prohibit result artifacts, evidence, reports, failure details, state, sink writes, result tables, and large-result stores. | Result objects may expose empty reference slots only. Tests must prove no files, tables, sinks, or state outputs are written or mutated. |
| Generated artifact lifecycle | 7.1 must not publish generated run outputs. | Non-goals and scenarios explicitly prohibit `target/run_results.json`, evidence, reports, state, selected-scope outputs, and mutation of stale outputs. | Do not add artifact writer behavior. If any implementation path writes generated outputs, 7.1 scope has been violated. |
| Selector readiness and subset execution | 7.1 must not implement selectors or partial run semantics. | Non-goals, matrix rows, and BDD scenarios exclude `--select`, `--exclude`, partial compile/run, selected-scope metadata, selected-scope run results, and selected-scope evidence. | Selector-like input must fail clearly if accepted by the API surface. Do not silently ignore selectors or emit scoped artifacts/results. |
| Probabilistic key-diff and sketch strategies | 7.1 must not implement compact probabilistic key coverage. | Non-goals, matrix rows, and BDD scenarios exclude probabilistic summaries, Bloom/sketch artifacts, candidate missing/extra rows, and probabilistic evidence claims. | Probabilistic typed operations must be unsupported in 7.1. Do not create summary artifacts, candidate failure rows, or exact/probabilistic classifications. |
| Source/target privacy | 7.1 should avoid data exposure by construction because no queries run. | Security/privacy requirements and matrices require empty source/target values, safe diagnostics, and no relation names, query text, profile values, credentials, or raw tracebacks. | Tests must prove non-executed results cannot carry source/target values through messages, metadata, diagnostics, refs, or serialized fields. |
| Public contract and changelog decision | 7.1 affects planned result/diagnostic surfaces but does not stabilize generated artifacts. | Public contract decision states no new YAML syntax, artifact version, adapter API change, selector claim, evidence schema, or sink/table schema. Changelog decision is not required for prework. | Implementation must update compatibility docs if status names, reason codes, diagnostic codes, CLI output, or serialized fields change from this prework. |

Gate status for this prework: satisfied for 7.1 implementation planning.
Remaining pre-implementation work is the exact implementation file/test map
and the final prompt/docs drift check.

## Phase-Exit Checklist

Use this checklist before considering Milestone 7.1 implementation complete.

### Scope And Inputs

- [ ] Implementation consumes already compiled checks or equivalent compiled
  in-memory fixtures only.
- [ ] No authored YAML parsing, compilation, profile loading, adapter
  lifecycle, SQL rendering, source/target query, or runtime execution path is
  invoked.
- [ ] Multiple compiled contracts, empty scopes, malformed artifacts, and
  missing artifacts are handled explicitly.

### Result Model And Status Semantics

- [ ] `RunResult`, `ContractResult`, and `CheckResult` serialize
  deterministically.
- [ ] Check statuses, aggregate statuses, and reason codes exactly match this
  prework.
- [ ] `no_checks` never aggregates to `pass`.
- [ ] `blocked` results include `blocked_by` and a prerequisite reason.
- [ ] Unsupported compiled checks, unsupported typed operations, later-phase
  operations, missing capabilities, unsupported placement, and unsupported
  materialization all become explicit non-pass outcomes.

### Diagnostics, Security, And Privacy

- [ ] Runtime diagnostic codes match the locked 7.1 list.
- [ ] Safe diagnostic fields are preserved where available.
- [ ] Unsafe raw exception text, tracebacks, query text, relation names,
  credentials, profile values, source/target values, keys, rows, normalized
  values, and diff values are absent from diagnostics and result serialization.
- [ ] Unexpected check-engine errors produce sanitized diagnostics.

### Negative Output And Side-Effect Proof

- [ ] No adapter, profile, renderer, query, artifact writer, evidence writer,
  report writer, state backend, sink writer, or result-table writer is invoked.
- [ ] No `target/run_results.json`, evidence, report, failure-detail, state,
  result table, sink output, compiled SQL output, probabilistic summary,
  Bloom/sketch artifact, selector output, or selected-scope output is created.
- [ ] Preexisting generated files and directories are not mutated or deleted by
  the 7.1 run boundary.
- [ ] Artifact, evidence, state, failure-detail, and sink references remain
  empty unless a later owning phase writes them.

### Future-Gated Surface Proof

- [ ] Execution placement and materialization are represented only as blockers
  or metadata; no fallback comparison runs.
- [ ] Evidence/result sink placement remains separate from execution placement
  and is not implemented.
- [ ] Selector and selected-scope inputs fail clearly if they reach 7.1
  surfaces; no partial run behavior appears.
- [ ] Probabilistic, Bloom, sketch, and approximate key-diff behavior remains
  unsupported and produces no artifacts, candidate rows, or evidence claims.

### Docs, Compatibility, And Review

- [ ] Implementation tests cover every required acceptance/conformance row and
  edge-case row, or explicitly document any row that remains out of scope.
- [ ] BDD workflow scenarios pass or have an explicit out-of-scope rationale.
- [ ] Compatibility docs still match implemented status names, reason codes,
  diagnostics, serialized fields, and command behavior.
- [ ] No changelog entry is needed, or a changelog entry has been added because
  implementation changed user-visible behavior or a public contract surface.
- [ ] Phase-exit review records tests run, uncovered rows, docs status, newly
  discovered conformance requirements, and whether the next 7.x phase is safe
  to start.

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

- exact implementation file/test map,
- final prompt/docs drift check and implementation-readiness report.
