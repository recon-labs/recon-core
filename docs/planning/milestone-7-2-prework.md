# Milestone 7.2 Prework

## Purpose

This is the lightweight prework artifact for Milestone 7.2: adapter execution
lifecycle and row-count execution.

Milestone 7.2 is high-risk because it touches runtime profile loading,
profiles/secrets, adapter lifecycle, adapter capability validation, adapter
execution, SQL execution placement, source/target privacy, runtime diagnostics,
CLI-visible run behavior, and future run-result compatibility. This artifact is
required before implementation, but it is not sufficient by itself until the
final acceptance/conformance matrix, BDD scenarios, test plan, implementation
map, prompt/docs drift check, Definition of Done, and phase-exit checklist are
complete.

Split Decision: Already Split / Follow Existing Split.

## Scope

Milestone 7.2 builds the first adapter-backed check execution path behind the
existing `recon run` service boundary.

Build scope:

- runtime loading of compiled-check artifacts,
- runtime loading of matching compiled-contract artifacts,
- runtime join between compiled checks and their compiled contract metadata,
- runtime selected-profile and selected-target loading,
- referenced-connection-only runtime profile loading for selected compiled
  contracts,
- literal adapter `type` routing at runtime,
- adapter factory resolution for execution,
- adapter metadata, API version, and capability validation before execution,
- adapter connection/open lifecycle,
- same-context DuckDB relation-backed row-count execution,
- final `compare_counts` execution through the same DuckDB adapter context,
- adapter close lifecycle,
- sanitized runtime adapter/profile diagnostics,
- in-memory `row_count_diff` check outcomes,
- negative guarantees that prove the phase does not write generated result,
  evidence, report, failure-detail, state, or sink output.

## Non-Goals

Milestone 7.2 must not implement:

- authored YAML parsing inside `recon run`,
- recompilation inside `recon run`,
- public authored `checks: [...]` support,
- public check registry behavior,
- query endpoint execution,
- cross-adapter execution,
- cross-connection comparison when selected connection configs differ,
- side-local scalar count comparison,
- Python-side row-count comparison fallback,
- third-engine comparison,
- adapter-managed intermediate comparison,
- materialization or staging,
- temp table requirements,
- source or target row extraction into Recon Core,
- row transfer into Recon Core,
- key checks,
- null-key checks,
- duplicate-key checks,
- missing-key checks,
- extra-key checks,
- row-level value comparison,
- aggregate metric execution,
- schema policy execution,
- tolerance, null-equivalence, or normalization execution,
- CDC runtime behavior,
- sampling runtime behavior,
- selectors,
- partial run,
- selected-scope run results,
- `target/run_results.json`,
- terminal run-summary finalization,
- evidence artifacts,
- reports,
- failure-detail output,
- result/evidence sink writes,
- production result tables,
- state writes,
- generated compiled SQL writes,
- generated SQL exposure from `recon run`,
- hosted upload or external result sync,
- shared adapter test-kit publication,
- external adapter compatibility claims,
- production adapter package split,
- adapter API version changes unless a later compatibility review requires one.

## Expected Behavior

`recon run` should move from non-execution to the first supported check
execution surface for already compiled relation-backed `row_count_diff` checks.
It should not parse authored YAML or compile contracts.

Milestone 7.2 should:

- load compiled-check artifacts from the existing compiled-check output
  location,
- load compiled-contract artifacts needed by those compiled checks,
- fail clearly if a needed compiled contract is missing, malformed, unsafe to
  load, incompatible, or mismatched with the compiled check reference,
- preserve compile-time safe diagnostics already attached to compiled checks,
- load only the selected profile and selected target,
- render/load only named profile connections referenced by selected compiled
  contracts,
- reject invalid referenced profile entries before adapter resolution,
- require runtime adapter `type` values to be literal non-empty adapter types,
- resolve adapters through the adapter registry,
- validate adapter metadata, adapter type, adapter API version, and required
  capabilities before execution,
- connect/open the adapter only after profile and adapter compatibility checks
  pass,
- execute only the final same-context DuckDB `compare_counts` operation for
  `row_count_diff`,
- close the adapter after execution when it was opened,
- report `pass` when source and target row counts are equal,
- report `fail` when source and target row counts differ,
- report `error` when profile loading, adapter resolution, adapter lifecycle,
  capability validation, SQL rendering, execution, close, or result-shape
  validation fails,
- report `not_executable` when a valid compiled check belongs outside the 7.2
  execution scope,
- keep unsupported placement, query endpoints, cross-context execution,
  materialization, and fallback paths explicit instead of silently changing
  strategy,
- return in-memory `RunResult`, `ContractResult`, and `CheckResult` objects
  only,
- keep artifact, evidence, failure-detail, state, and sink references empty.

Milestone 7.2 must not report source-target equivalence unless the row-count
comparison actually executed through the locked same-context adapter path.

## Status And Reason Taxonomy

Milestone 7.2 reuses the check statuses introduced by the first check-engine
boundary:

```text
pass
fail
warn
error
skipped
blocked
not_executable
```

Run and contract aggregate statuses remain:

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

Milestone 7.2 adds factual `pass` and `fail` outcomes only for executed
relation-backed `row_count_diff` checks. All other currently compiled check
types remain assigned to their later execution phases unless explicitly handled
as existing non-execution cases.

`unsupported` and `not_yet_executable` remain reason-code concepts under
`not_executable`; they are not statuses.

## Runtime Diagnostics

Milestone 7.2 reuses these first-boundary runtime diagnostic codes where
applicable:

- `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND`,
- `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID`,
- `RC_RUNTIME_NO_COMPILED_CHECKS`,
- `RC_RUNTIME_CHECK_NOT_EXECUTABLE`,
- `RC_RUNTIME_UNSUPPORTED_CHECK_TYPE`,
- `RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION`,
- `RC_RUNTIME_MISSING_ENGINE_CAPABILITY`,
- `RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT`,
- `RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY`,
- `RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE`,
- `RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR`.

Milestone 7.2 adds runtime compiled-contract diagnostics:

- `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND`,
- `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID`.

These diagnostics cover missing, malformed, unsafe, incompatible, or mismatched
compiled-contract runtime inputs. They must not expose raw artifact contents.

Milestone 7.2 reuses existing profile diagnostics for selected-profile,
selected-target, and referenced-connection failures:

- `RC_CONFIG_PROFILE_FILE_NOT_FOUND`,
- `RC_CONFIG_INVALID_PROFILE_YAML`,
- `RC_CONFIG_INVALID_PROFILE_CONFIG`,
- `RC_CONFIG_PROFILE_NOT_SELECTED`,
- `RC_CONFIG_PROFILE_NOT_FOUND`,
- `RC_CONFIG_PROFILE_TARGET_NOT_FOUND`,
- `RC_CONFIG_PROFILE_CONNECTION_NOT_FOUND`,
- `RC_CONFIG_PROFILE_ENV_VAR_MISSING`.

Milestone 7.2 reuses existing adapter diagnostics where applicable:

- `RC_ADAPTER_UNKNOWN_TYPE`,
- `RC_ADAPTER_RESOLUTION_FAILED`,
- `RC_ADAPTER_API_VERSION_UNSUPPORTED`,
- `RC_ADAPTER_CAPABILITY_UNSUPPORTED`,
- `RC_ADAPTER_CAPABILITY_DECLARATION_FAILED`,
- `RC_ADAPTER_DEPENDENCY_MISSING`,
- `RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED`,
- `RC_ADAPTER_TYPE_MISMATCH`,
- `RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED`,
- `RC_ADAPTER_INVALID_RELATION`,
- `RC_ADAPTER_OPERATION_RENDER_FAILED`,
- `RC_ADAPTER_RENDERED_SQL_EMPTY`,
- `RC_ADAPTER_METADATA_INVALID`,
- `RC_ADAPTER_QUERY_FAILED`,
- `RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED`.

Milestone 7.2 adds adapter lifecycle diagnostics:

- `RC_ADAPTER_CONNECTION_FAILED`,
- `RC_ADAPTER_CLOSE_FAILED`.

Runtime diagnostics explain non-execution, lifecycle failure, execution failure,
or row-count mismatch context. They are not evidence artifacts and must not
expose raw rows, keys, source/target values, query text, rendered SQL, database
error text, rendered profile values, credentials, DSN fragments, raw adapter
exception text, tracebacks, or unredacted artifact contents.

## Affected Docs And Decisions

Milestone 7.2 implementation must stay consistent with:

- `docs/implementation/mvp-build-order.md`,
- `docs/implementation/testing-plan.md`,
- `docs/implementation/result-model.md`,
- `docs/implementation/check-engine.md`,
- `docs/implementation/errors-and-diagnostics.md`,
- `docs/architecture/check-engine.md`,
- `docs/architecture/adapter-interface.md`,
- `docs/implementation/adapter-interface-spec.md`,
- `docs/architecture/diagnostics-and-errors.md`,
- `docs/architecture/domain-models.md`,
- `docs/compatibility/adapter-api.md`,
- `docs/compatibility/public-contract-inventory.md`,
- `docs/compatibility/compatibility-matrix.md`,
- `docs/compatibility/change-checklist.md`,
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`,
- `docs/decisions/adr-0014-key-semantics-and-check-dependencies.md`,
- `docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`,
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`,
- `docs/decisions/adr-0021-execution-placement-and-comparison-engine-strategy.md`,
- `docs/decisions/adr-0022-evidence-privacy-failure-detail-and-result-sinks.md`.

No new ADR is required for Milestone 7.2 as long as the implementation follows
the locked decisions in this prework and the existing public docs are aligned
before coding.

## Compatibility Impact

Milestone 7.2 changes planned `recon run` behavior for supported compiled
checks from explicit non-execution to first adapter-backed row-count execution.

Public surfaces affected:

- `recon run` behavior for already compiled relation-backed `row_count_diff`
  checks,
- in-memory `RunResult`, `ContractResult`, and `CheckResult` outcomes,
- runtime diagnostic codes and messages,
- adapter lifecycle and adapter capability expectations,
- runtime profile loading and referenced-connection filtering,
- source/target privacy guarantees for runtime diagnostics.

Public surfaces not changed:

- authored contract YAML schema,
- check-pack authoring surface,
- public authored `checks: [...]`,
- compiled check artifact schema unless a later implementation blocker is
  explicitly documented,
- compiled contract artifact schema unless a later implementation blocker is
  explicitly documented,
- run-result artifact schema,
- evidence artifact schema,
- report schema,
- failure-detail schema,
- state schema,
- result/evidence sink schema,
- adapter API version unless a later compatibility review requires one.

Milestone 7.2 must not claim external adapter compatibility or shared adapter
test-kit readiness.

## Security And Privacy Impact

Milestone 7.2 queries source and target relations through an adapter execution
context, so source/target data privacy applies before coding.

Public by default:

- run/check status,
- diagnostic code,
- severity,
- safe messages,
- adapter type label,
- non-secret artifact/version/status metadata.

Policy-controlled in Milestone 7.2:

- source row count,
- target row count,
- row-count difference,
- relation names,
- source/target identifiers,
- connection names,
- profile/target names.

Sensitive by default:

- raw rows,
- comparison keys,
- raw source values,
- raw target values,
- normalized values,
- query text,
- rendered SQL,
- database error text,
- rendered profile values,
- credentials,
- tokens,
- DSN fragments,
- raw adapter exception text,
- tracebacks,
- failure details,
- failed-row samples,
- sample keys,
- CDC identifiers.

Scalar row counts and row-count differences are allowed only as bounded
policy-controlled values in the in-memory `CheckResult` for an executed
`row_count_diff`. Terminal/service diagnostics must not print source row count,
target row count, or row-count difference in Milestone 7.2.

Runtime diagnostics should prefer stable contract/check identity over physical
relation names. Physical relation names remain policy-controlled and must not
leak through adapter or database exception text.

## Placement Constraint

Milestone 7.2 locks row-count execution placement to same-context DuckDB
relation-backed pushdown.

Operation execution location:

- DuckDB adapter execution context.

Comparison location:

- same DuckDB adapter execution context.

Materialization and staging policy:

- none.

Allowed endpoint shape:

- source endpoint is relation-backed,
- target endpoint is relation-backed,
- source and target relations are addressable from the same selected DuckDB
  adapter execution context.

Forbidden placement behavior:

- Python-side comparison fallback,
- side-local scalar count comparison,
- cross-adapter execution,
- cross-connection comparison when selected connection configs differ,
- query endpoint execution,
- third-engine comparison,
- source or target data extraction into Recon Core,
- row transfer,
- hash or bisection strategies,
- materialized diff output,
- staging or temp-table behavior.

Required capabilities:

- `row_count`,
- `cte_support` when required by the rendered final `compare_counts` SQL.

Unknown, unsupported, not-implemented, malformed, incompatible, or
exception-raising capability states do not satisfy Milestone 7.2 execution
requirements.

## Evidence, Sink, And State Constraint

Milestone 7.2 may produce only:

- in-memory `RunResult`,
- in-memory `ContractResult`,
- in-memory `CheckResult`,
- sanitized diagnostics.

Milestone 7.2 must not produce:

- `target/run_results.json`,
- evidence artifacts,
- reports,
- failure-detail files,
- result tables,
- result sinks,
- evidence sinks,
- state files,
- external uploads,
- hosted service sync,
- adapter test-kit snapshots that expose runtime source/target values.

Execution placement and future sink placement remain separate. A row-count check
may execute through a DuckDB adapter context in Milestone 7.2, but no result or
evidence sink is configured, inferred, or written in this phase.

## Public Contract Decision

Milestone 7.2 is a planned public behavior change for `recon run`: a supported
compiled, relation-backed `row_count_diff` check may now execute and produce
factual in-memory `pass` or `fail` results.

That public behavior is intentionally narrow:

- already compiled artifacts only,
- `row_count_diff` only,
- relation-backed endpoints only,
- same-context DuckDB execution only,
- sanitized diagnostics only,
- in-memory results only.

The public contract does not include durable run-result artifacts, evidence,
reports, failure details, sink writes, query endpoint execution, cross-adapter
execution, side-local scalar count comparison, Python fallback, or external
adapter compatibility.

## Changelog Decision

No changelog entry is required for this prework-only artifact.

Milestone 7.2 implementation may require a changelog entry when runtime behavior
actually changes. That decision belongs to the implementation or release-note
step, not this prework creation step.

## Step 3 Readiness Status

This artifact records the Step 3 public prework decisions for scope,
non-goals, expected behavior, diagnostics, affected docs, compatibility,
security/privacy, placement, evidence/sink/state boundaries, public contract,
and changelog.

Implementation must not start yet. The remaining prework sections must still be
completed before coding:

- required tests,
- acceptance/conformance matrix,
- edge-case matrix,
- BDD workflow scenarios,
- gate satisfaction proof,
- phase-exit checklist,
- implementation map,
- implementation readiness report,
- Definition of Done,
- remaining-blocker report.
