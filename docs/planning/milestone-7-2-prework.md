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

## Required Tests

Milestone 7.2 implementation must add tests for:

- compiled-contract artifact loading for runtime execution,
- missing compiled-contract artifact diagnostics,
- malformed, unsafe, incompatible, or mismatched compiled-contract artifact
  diagnostics,
- compiled-check to compiled-contract reference joining,
- row-count execution using only relation-backed compiled endpoints,
- selected-profile and selected-target loading at runtime,
- referenced-connection-only runtime profile loading,
- ignored environment-variable failures in unreferenced connections,
- missing environment-variable failures in referenced connections,
- templated or env-var-backed adapter `type` rejection before adapter
  resolution,
- adapter registry resolution for execution,
- unknown adapter type diagnostics,
- malformed or exception-raising adapter factory diagnostics,
- adapter metadata validation before execution,
- factory-returned adapter type mismatch before execution,
- adapter API version validation before execution,
- adapter capability validation before execution,
- `row_count` capability required for execution,
- `cte_support` capability required when final `compare_counts` SQL uses CTEs,
- adapter connection/open success and failure,
- adapter close success and failure,
- adapter close attempted after execution when an adapter was opened,
- adapter close failure preserving the primary execution failure when both
  occur,
- same-context DuckDB row-count pass,
- same-context DuckDB row-count fail,
- malformed adapter execution result shape,
- adapter/database execution failure sanitization,
- query endpoint blocked before execution,
- cross-adapter execution blocked before execution,
- cross-connection execution blocked when selected connection configs differ,
- unsupported placement blocked before execution,
- unsupported materialization/staging blocked before execution,
- no Python-side row-count comparison fallback,
- no source or target row transfer into Recon Core,
- no generated compiled SQL writes from `recon run`,
- no generated run-result/evidence/report/failure-detail/state/sink output,
- runtime diagnostic redaction for rendered profile keys and values,
- runtime diagnostic redaction for credentials, tokens, DSN fragments, raw
  adapter exception text, database error text, query text, rendered SQL,
  tracebacks, and short numeric rendered profile scalars,
- safe adapter diagnostic code preservation,
- unsafe adapter diagnostic code suppression,
- terminal/service diagnostics not printing source row count, target row count,
  or row-count difference,
- in-memory `CheckResult` carrying bounded policy-controlled row-count values
  for executed `row_count_diff` checks,
- existing later-phase checks remaining `not_executable`,
- negative proof that key checks, aggregate checks, query endpoints, evidence,
  result artifacts, selectors, state, and sinks remain out of scope.

The final high-risk acceptance/conformance matrix and BDD workflow scenarios
must map each required behavior to a test, an existing test, or explicit
out-of-scope rationale before implementation starts.

## Acceptance And Conformance Matrix

Every row below must map to implementation tests before Milestone 7.2 coding is
considered complete.

| Dimension | Cases | Expected behavior | Required test coverage | Docs or gate impact | Out-of-scope rationale |
| --- | --- | --- | --- | --- | --- |
| Run boundary and compiled inputs | Existing compiled-check artifacts, matching compiled-contract artifacts, multiple contracts, compile diagnostics. | `recon run` consumes already compiled artifacts only, joins each executable compiled check to its compiled contract, preserves safe diagnostics, and never parses authored YAML or recompiles contracts. | Service and artifact tests for compiled-check loading, compiled-contract loading, check-to-contract joins, and no parser/compiler invocation. | Check-engine docs and compiled artifact docs. | Recompilation, partial compile, selectors, and artifact freshness are later work. |
| Compiled-contract runtime loader | Missing compiled-contract path, invalid YAML, wrong artifact type/version, symlinked path, missing source/target metadata, check reference mismatch. | Runtime returns `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND` or `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID`; no adapter/profile resolution starts. | Artifact-loader tests for missing, malformed, unsafe, incompatible, and mismatched compiled contracts. | Runtime diagnostics docs and public contract inventory. | Changing compiled artifact schemas is out of scope unless a separate compatibility decision is made. |
| Executable check scope | `row_count_diff`, later-phase key checks, later-phase aggregate checks, unknown compiled check types, unsupported typed operations. | Only relation-backed `row_count_diff` may execute. Later-phase checks remain `not_executable`; unknown/unsupported checks retain existing dispatch diagnostics. | Dispatch/engine tests for executable row count, later-phase checks, unknown checks, and unsupported operations. | Milestone 7 split and check-engine docs. | Key checks belong to 7.3; aggregate checks belong to 7.4. |
| Typed row-count plan shape | Expected source `row_count`, target `row_count`, final `compare_counts`; missing, extra, reordered, malformed, or unknown operations. | Expected plan shape executes only through final same-context `compare_counts`; invalid or unsupported plan shape fails or remains non-executable with structured diagnostics. | Engine/executor tests for valid plan shape and invalid operation shape cases. | Typed check-plan compatibility docs. | New typed operations and changed operation payloads are public adapter changes outside 7.2. |
| Runtime profile loading | Selected profile, selected target, referenced connections, unreferenced connections, missing env vars, unsupported template fragments. | Runtime loads only selected profile/target and referenced connections. Referenced invalid config blocks before adapter resolution; unreferenced invalid config does not fail the run. | Profile/runtime tests for selected target, referenced-only loading, missing referenced env vars, ignored unreferenced env vars, and unsupported templates. | Adapter/Profile Diagnostic Conformance Gate. | Profile debug/validation commands remain future work. |
| Literal adapter type routing | Literal `type`, empty `type`, templated `type`, env-var-backed `type`, factory-returned type mismatch. | Adapter `type` must be literal and non-empty. Templated/env-var-backed `type` fails before adapter resolution. Factory metadata mismatch fails before execution. | Profile/adapter tests for invalid type forms and `RC_ADAPTER_TYPE_MISMATCH`. | Adapter API and profile docs. | Environment-specific adapter selection must use targets or named connections. |
| Adapter resolution | Registered adapter, unknown adapter, missing optional dependency, factory exception, empty result, malformed result, malformed diagnostics, factory returns adapter and diagnostics. | Core validates adapter factory behavior before execution. Failures produce sanitized `RC_ADAPTER_*` diagnostics and no connection is opened. | Adapter registry/runtime tests for each resolution failure and success path. | Adapter/Profile Diagnostic Conformance Gate. | External adapter compatibility claims remain future work. |
| Adapter metadata and API compatibility | Missing API version, unsupported API version, invalid metadata, exception-raising metadata, adapter type mismatch. | Runtime blocks before execution with structured sanitized diagnostics. | Adapter runtime tests for API and metadata failures. | Adapter API compatibility docs. | Adapter API version changes require separate compatibility review. |
| Adapter capabilities | `row_count`, `cte_support`, unsupported, unknown, malformed, exception-raising capability declarations. | Required capabilities must be present and compatible before execution. Unsupported or malformed capability states block execution; no fallback runs. | Capability tests for supported, unsupported, missing, malformed, and exception-raising capabilities. | Capability catalog and execution placement gate. | Broader capability catalog changes are outside 7.2 unless required for row count. |
| Adapter lifecycle | Connect/open success, connect/open failure, execute success, execute failure, close success, close failure, execute plus close failure. | Runtime connects only after validation, closes opened adapters, sanitizes lifecycle failures, and does not hide the primary execution failure with a close failure. | Adapter lifecycle tests with fakes for connect, execute, close, and combined failure paths. | Adapter/Profile Diagnostic Conformance Gate and diagnostics docs. | Connection pooling and long-lived adapter lifecycle are future work. |
| Same-context row-count execution | Source/target same selected DuckDB context, same adapter type/config, final `compare_counts` result. | `row_count_diff` executes through the same DuckDB context and returns one bounded scalar result row. | End-to-end service/engine tests using DuckDB relations for pass and fail. | Gate 4I and ADR 0021. | Side-local scalar count comparison is deferred to later placement work. |
| Cross-context blocking | Different adapter types, different DuckDB connection configs, query endpoints, unavailable relation context. | Runtime blocks before execution with structured diagnostics; no adapter-owned bridge, attach, staging, or fallback is attempted. | Negative tests for cross-adapter, differing configs, query endpoints, and invalid relation context. | Execution placement and adapter-interface docs. | Cross-adapter, cross-connection, and query endpoint execution are future gated work. |
| Placement and materialization blockers | Unsupported placement, materialization requested, staging requested, third-engine comparison requested, Python fallback temptation. | Runtime blocks before execution with `RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT` or `RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY`; no fallback executes. | Placement negative tests proving no Python, staging, temp table, or third-engine execution path is invoked. | Gate 4I. | Materialization, staging, and external comparison engines require later policy. |
| Row-count result semantics | Equal counts, unequal counts, one result row, zero rows, multiple rows, missing columns, non-integer values. | Equal counts produce `pass`; unequal counts produce `fail`; malformed result shape produces `error`, not mismatch evidence. | Row-count result tests for pass/fail and malformed adapter result shapes. | Result-model docs and privacy gate. | Failure details and evidence wording belong to later phases. |
| Runtime diagnostics and redaction | Profile values in code/message/hint/path/resource/line/column, raw SQL, rendered SQL, database error text, DSN fragments, tracebacks, short numeric secrets. | Unsafe data is suppressed or replaced; safe diagnostic code/severity/message/context are preserved where available. | Redaction tests across all diagnostic fields and lifecycle phases. | Gate 4J and Gate 6. | Rich debug output requires future privacy policy. |
| Row-count privacy | Source count, target count, diff, relation names, source/target identifiers, terminal output, service diagnostics, in-memory result. | Counts/diff may appear only as bounded policy-controlled in-memory check-result values. Terminal/service diagnostics do not print counts/diff. Relation names are avoided in diagnostics by default. | Privacy tests for in-memory value presence and public diagnostic absence. | Gate 6 and ADR 0022. | Durable publication of counts belongs to run-result/evidence/report phases. |
| No generated outputs | `target/run_results.json`, reports, evidence, failure details, state, result tables, sinks, compiled SQL writes, hosted sync. | 7.2 writes none of these and does not record any destination as written. Preexisting files are not mutated. | Temporary-directory tests proving absent writes and stale-file non-mutation. | ADR 0022 and generated artifact lifecycle gate. | Run-result artifacts belong to Milestone 8; evidence/report/failure details belong to Milestone 9. |
| Public contract minimality | Authored YAML, compiled artifact schemas, adapter API version, external adapter claims, test-kit snapshots. | 7.2 narrows public behavior to in-memory row-count execution and sanitized diagnostics; no schema or external compatibility claim is added. | Compatibility tests or doc checks proving no version constant/schema/API changes unless explicitly reviewed. | Public contract inventory and change checklist. | Stable result artifacts, adapter test kit, and external packages remain later work. |

## Edge-Case Matrix

Each edge case below must either be covered by tests or explicitly marked out of
scope during implementation review.

| Edge case | Expected 7.2 behavior | Required coverage |
| --- | --- | --- |
| Compiled-check artifacts are missing. | Existing `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND`; no execution and no generated output. | Run-service loader test. |
| Compiled-check artifacts are malformed or unsafe. | Existing `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID`; no compiled-contract/profile/adapter work starts. | Run-service/loader tests. |
| A compiled check references a compiled contract file that is missing. | `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND`; no profile or adapter resolution starts. | Compiled-contract loader/service test. |
| A compiled contract artifact has invalid YAML, wrong artifact type/version, missing source/target metadata, or unsafe symlink path. | `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID`; no adapter execution. | Loader tests for every invalid artifact case. |
| Compiled check contract reference and compiled contract identity disagree. | `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID`; no best-effort matching. | Join validation test. |
| A compiled contract uses query endpoints. | `RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED` or placement-blocking runtime diagnostic before execution. | Relation-only negative test. |
| Source and target adapter types differ. | Execution blocked before adapter execution; no bridge or fallback. | Cross-adapter negative test. |
| Source and target DuckDB configs differ. | Execution blocked before execution with same-context diagnostic. | Cross-context negative test. |
| Source and target relations share the same DuckDB context. | Runtime may execute final `compare_counts` through that context. | Row-count pass/fail tests. |
| Selected profile is missing. | Existing `RC_CONFIG_PROFILE_NOT_SELECTED` or `RC_CONFIG_PROFILE_NOT_FOUND`; no adapter factory call. | Runtime profile test. |
| Selected target is missing. | Existing `RC_CONFIG_PROFILE_TARGET_NOT_FOUND`; no adapter factory call. | Runtime profile test. |
| Referenced connection is missing. | Existing `RC_CONFIG_PROFILE_CONNECTION_NOT_FOUND`; affected check errors before adapter resolution. | Runtime profile test. |
| Unreferenced connection has missing env var. | Run does not fail because the connection is not referenced by selected compiled contracts. | Referenced-only profile test. |
| Referenced connection has missing env var. | Existing `RC_CONFIG_PROFILE_ENV_VAR_MISSING`; no adapter resolution. | Runtime profile test. |
| Connection `type` is empty, templated, or env-var-backed. | Existing profile config diagnostic before adapter resolution; no rendered value leak. | Runtime profile redaction test. |
| Adapter type is unknown. | `RC_ADAPTER_UNKNOWN_TYPE`; no execution. | Adapter registry test. |
| Adapter optional dependency is unavailable. | `RC_ADAPTER_DEPENDENCY_MISSING`; no execution. | Adapter factory test. |
| Adapter factory raises or returns malformed result. | `RC_ADAPTER_RESOLUTION_FAILED`; raw exception suppressed. | Adapter factory test. |
| Adapter factory returns both adapter and diagnostics. | `RC_ADAPTER_RESOLUTION_FAILED`; no execution. | Adapter factory test. |
| Factory diagnostic payload has malformed field values. | `RC_ADAPTER_RESOLUTION_FAILED`; malformed diagnostics do not leak. | Adapter diagnostic payload test. |
| Adapter metadata raises or is malformed. | `RC_ADAPTER_METADATA_INVALID`; no execution. | Adapter metadata test. |
| Factory-returned adapter type differs from profile `type`. | `RC_ADAPTER_TYPE_MISMATCH`; no execution. | Adapter metadata/type test. |
| Adapter API version is missing or unsupported. | `RC_ADAPTER_API_VERSION_UNSUPPORTED`; no execution. | API compatibility test. |
| Adapter capability declaration raises or is malformed. | `RC_ADAPTER_CAPABILITY_DECLARATION_FAILED`; no fallback. | Capability test. |
| Adapter lacks `row_count`. | `RC_ADAPTER_CAPABILITY_UNSUPPORTED`; no execution. | Capability test. |
| Adapter lacks required `cte_support`. | `RC_ADAPTER_CAPABILITY_UNSUPPORTED`; no final compare execution. | Capability test. |
| Adapter connect/open fails. | `RC_ADAPTER_CONNECTION_FAILED`; raw exception suppressed. | Lifecycle test. |
| Adapter execute/database call fails. | `RC_ADAPTER_QUERY_FAILED`; raw SQL and DB error text suppressed. | Execution failure redaction test. |
| Adapter close fails after successful execution. | `RC_ADAPTER_CLOSE_FAILED`; result aggregate reflects lifecycle error according to result rules. | Lifecycle close-failure test. |
| Adapter execute fails and close also fails. | Primary execution failure remains visible; close failure is sanitized and does not replace it. | Combined failure test. |
| Final result has no rows, multiple rows, missing columns, or non-integer counts. | Runtime reports `error`; no mismatch evidence. | Result-shape validation test. |
| Counts are equal. | `CheckResult.status == pass`; `executed=true`; bounded in-memory values may include source count, target count, and diff. | Row-count pass test. |
| Counts differ. | `CheckResult.status == fail`; `executed=true`; bounded in-memory values may include source count, target count, and diff. | Row-count fail test. |
| Terminal output would include row counts or diff. | Counts/diff are omitted from terminal/service diagnostics in 7.2. | CLI/service privacy test. |
| Adapter diagnostic code embeds rendered secret or config key. | Code is replaced with `RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED`. | Diagnostic-code redaction test. |
| Safe adapter diagnostic code contains incidental non-secret substring. | Safe code is preserved. | Diagnostic-code preservation test. |
| Diagnostic line or column matches rendered numeric profile value. | Numeric field is suppressed/redacted. | Numeric redaction test. |
| Preexisting `target/run_results.json` exists. | 7.2 does not update, delete, or claim it wrote the file. | Stale-output non-mutation test. |
| Preexisting reports, evidence, state, or sink-like files exist. | 7.2 does not mutate them or record them as written. | Temporary-directory non-mutation test. |
| Later-phase key or aggregate check appears beside row-count check. | Row count may execute if valid; later-phase check remains `not_executable`. | Mixed-scope dispatch/execution test. |
| Any source/target row, key, query text, rendered SQL, DB error, credential, DSN, or traceback appears in public output. | Test fails; sensitive value must be suppressed. | End-to-end privacy snapshot tests. |

## BDD Workflow Scenarios

### Scenario 1: Relation-Backed Row Count Passes

Given compiled-check and compiled-contract artifacts exist for a relation-backed
`row_count_diff`.
And the source and target relations are addressable from the same selected
DuckDB adapter context.
And both relations have the same row count.
When the user runs `recon run`.
Then Recon loads the compiled check and compiled contract.
And it loads only referenced profile connections.
And it validates adapter metadata, API version, and capabilities.
And it executes the final `compare_counts` operation through the same adapter
context.
And the check result is `pass`.
And no run-result, evidence, report, failure-detail, state, or sink output is
written.

### Scenario 2: Relation-Backed Row Count Fails

Given compiled artifacts exist for a relation-backed `row_count_diff`.
And the source and target relations are addressable from the same selected
DuckDB adapter context.
And the source and target row counts differ.
When the user runs `recon run`.
Then the check result is `fail`.
And the in-memory check result may include bounded policy-controlled count and
diff values.
And terminal/service diagnostics do not print the counts or diff.
And no evidence, report, failure-detail, state, or sink output is written.

### Scenario 3: Missing Compiled Contract Blocks Runtime Execution

Given a compiled-check artifact references a compiled contract that is missing.
When the user runs `recon run`.
Then Recon reports `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND`.
And it does not load runtime profiles.
And it does not resolve adapters.
And it does not report source-target equivalence.

### Scenario 4: Referenced Profile Connection Fails Before Adapter Resolution

Given a compiled contract references a profile connection.
And that referenced connection has an unsupported template or missing required
environment variable.
When the user runs `recon run`.
Then Recon reports the existing profile configuration diagnostic.
And it does not invoke the adapter factory for that connection.
And the diagnostic does not expose rendered profile values.

### Scenario 5: Unreferenced Profile Connection Does Not Fail The Run

Given the selected profile contains an unreferenced connection with a missing
environment variable.
And the compiled contracts reference only other valid connections.
When the user runs `recon run`.
Then Recon ignores the unreferenced connection for this run scope.
And execution is not blocked by the unreferenced missing environment variable.

### Scenario 6: Adapter Setup Failure Is Sanitized

Given profile loading succeeds for the referenced connection.
And adapter resolution fails because the adapter type is unknown, unavailable,
malformed, incompatible, or missing a required capability.
When the user runs `recon run`.
Then Recon reports the appropriate structured `RC_ADAPTER_*` diagnostic.
And the diagnostic does not include rendered profile values, credentials, DSN
fragments, raw exception text, query text, or tracebacks.
And no adapter execution starts.

### Scenario 7: Adapter Connection Failure Is Sanitized

Given adapter resolution and capability validation succeed.
And adapter connection/open fails.
When the user runs `recon run`.
Then Recon reports `RC_ADAPTER_CONNECTION_FAILED`.
And the raw adapter exception text is suppressed.
And no query execution occurs.

### Scenario 8: Adapter Execution Failure Is Sanitized

Given adapter connection succeeds.
And the adapter/database execution call fails.
When the user runs `recon run`.
Then Recon reports `RC_ADAPTER_QUERY_FAILED`.
And raw SQL, rendered SQL, database engine error text, profile values,
credentials, DSN fragments, and tracebacks are not emitted.

### Scenario 9: Adapter Close Failure Is Sanitized

Given an adapter was opened during row-count execution.
And adapter close fails.
When the run completes adapter lifecycle cleanup.
Then Recon reports `RC_ADAPTER_CLOSE_FAILED`.
And the close diagnostic is sanitized.
And a close failure does not replace a primary execution failure when both
occur.

### Scenario 10: Query Endpoint Remains Blocked

Given a compiled contract uses a source or target query endpoint.
When the user runs `recon run`.
Then Recon blocks before adapter execution.
And the diagnostic states that query endpoint execution is not supported in
this phase.
And Recon does not execute or print query text.

### Scenario 11: Cross-Context Execution Remains Blocked

Given source and target endpoints require different adapter types or different
DuckDB connection configs.
When the user runs `recon run`.
Then Recon blocks before execution.
And it does not bridge, attach, stage, move data, or fall back to Python.

### Scenario 12: Unsupported Placement Does Not Fall Back

Given a compiled check requires unsupported placement or materialization.
When the user runs `recon run`.
Then Recon reports unsupported placement or materialization diagnostics.
And no Python-side comparison, staging, temp table, third-engine comparison, or
row transfer occurs.

### Scenario 13: Later-Phase Checks Remain Non-Executable

Given a run scope includes `row_count_diff` and later-phase key or aggregate
checks.
When the user runs `recon run`.
Then the valid row-count check may execute.
And later-phase checks remain `not_executable` with explicit reason codes.
And their non-execution does not look like passing evidence.

### Scenario 14: No Generated Output Is Written

Given writable `target/`, `reports/`, and `state/` directories exist.
And stale `target/run_results.json` or report files may already exist.
When Milestone 7.2 row-count execution completes.
Then Recon does not create, update, delete, or claim any run-result, evidence,
report, failure-detail, state, compiled SQL, result-table, sink, or hosted-sync
output.

## Gate Satisfaction Proof

This section proves that the design gates needed for Milestone 7.2 are
represented before implementation. "Satisfied for 7.2 prework" means the
design and documentation are explicit enough for a TDD implementation plan; it
does not mean implementation has started.

| Gate | 7.2 status | Proof in this prework |
| --- | --- | --- |
| Split decision | Satisfied for 7.2 prework. | Milestone 7 remains split and 7.2 owns only adapter lifecycle and row-count execution. |
| High-risk milestone prework | Satisfied for Step 4; final coding still waits for Steps 5-8. | Scope, non-goals, expected behavior, diagnostics, compatibility, privacy, placement, required tests, matrix, scenarios, implementation map, DoD, and blocker report are documented here. |
| Gate 4I: comparison execution placement | Satisfied for 7.2 prework. | Same-context DuckDB relation-backed pushdown is the only allowed row-count placement. Operation location, comparison location, and materialization policy are explicit. Unsupported query, cross-context, materialization, third-engine, and Python fallback paths are forbidden and mapped to tests. |
| Gate 4J: profile rendering and adapter diagnostic redaction | Satisfied for 7.2 prework. | Runtime profile loading follows selected-profile/target and referenced-connection-only rules. Literal adapter type routing, factory validation, adapter metadata/API/capability checks, lifecycle diagnostics, and redaction requirements are documented and test-mapped. |
| Gate 6: source/target privacy, evidence, and failure-detail policy | Satisfied for 7.2 prework. | Counts/diff are policy-controlled and only allowed in bounded in-memory check results. Sensitive rows, keys, values, query text, rendered SQL, DB errors, profile values, credentials, DSN fragments, raw exceptions, and tracebacks are excluded from public output. No generated result/evidence/failure/state/sink output is allowed. |
| Adapter API compatibility | Satisfied for 7.2 prework. | Runtime validates adapter metadata, adapter type, API version, and capabilities before execution. No adapter API version change or external adapter compatibility claim is made. |
| Generated artifact lifecycle | Satisfied for 7.2 prework. | 7.2 writes no `target/run_results.json`, evidence, reports, failure details, state, compiled SQL, result tables, or sinks. Stale generated outputs must not be mutated. |
| Public contract compatibility | Satisfied for 7.2 prework. | The only planned behavior change is narrow in-memory row-count execution for supported compiled checks. Authored YAML, compiled artifact schemas, run-result schemas, evidence schemas, sink schemas, and adapter API versions remain unchanged unless later reviewed. |
| Prompt/docs drift | Not complete until Steps 5-7. | This artifact is complete for Step 4, but existing docs and private prompts still need alignment and drift checks before coding. |
| Phase-exit review | Not complete until Step 8. | The checklist is defined below; final validation belongs to Step 8. |

## Phase-Exit Checklist

Milestone 7.2 implementation must not start until all items below are checked:

- Split Decision remains `Already Split / Follow Existing Split`.
- No item remains assigned only to umbrella Milestone 7.
- `docs/planning/milestone-7-2-prework.md` contains complete scope,
  non-goals, expected behavior, diagnostics, compatibility, privacy,
  placement, matrix, BDD scenarios, implementation map, and DoD.
- Existing public docs are aligned with this prework.
- Private companion prompts are split-aware and do not instruct direct umbrella
  Milestone 7 implementation.
- Gate 4I placement rows are mapped to tests.
- Gate 4J profile/adapter diagnostic rows are mapped to tests.
- Gate 6 privacy/output rows are mapped to tests.
- No public doc contains external research attribution introduced during this
  session.
- No hard milestone labels were added to prohibited durable docs.
- No authored YAML schema change is proposed for 7.2.
- No compiled artifact schema change is proposed for 7.2 unless a separate
  compatibility review documents it.
- No adapter API version change is proposed for 7.2 unless a separate
  compatibility review documents it.
- No run-result, evidence, report, failure-detail, state, sink, or result-table
  output is assigned to 7.2.
- Future implementation tests are planned before source changes.
- Validation commands for the prework session pass or any skipped validation is
  explicitly justified.

## Implementation Map

This is a future implementation map only. Do not implement source/runtime/test
code during this prework session.

### Source Map

| File or module | Expected future change | Guardrails |
| --- | --- | --- |
| `src/recon_core/artifacts/compiled_contract_loader.py` | Add a runtime loader for `target/compiled_contracts/*.yml`, mirroring compiled-check loader safety rules. | Validate artifact type/version/shape, reject unsafe paths/symlinks, do not expose raw artifact contents, do not change compiled contract writer output unless separately reviewed. |
| `src/recon_core/artifacts/__init__.py` | Export compiled-contract loader types if created. | Keep writer behavior unchanged. |
| `src/recon_core/artifacts/compiled_check_loader.py` | Add only the minimal contract-reference data needed to join checks to compiled contracts, if not already exposed. | Do not change compiled check artifact serialization or artifact version. |
| `src/recon_core/check_engine/dispatch.py` | Route `row_count_diff` from `not_implemented_in_current_phase` into the 7.2 executor when all placement/profile/adapter preconditions pass. | Keep later-phase key and aggregate checks `not_executable`. |
| `src/recon_core/check_engine/engine.py` | Orchestrate executable row-count checks, preserve non-executable behavior for later checks, aggregate mixed results, and surface sanitized diagnostics. | Do not parse YAML, compile contracts, write artifacts, or expose source/target data. |
| `src/recon_core/check_engine/execution.py` or equivalent focused module | Add row-count execution orchestration if a new helper keeps `engine.py` cohesive. | Keep scope to `row_count_diff`; no key/aggregate/query/fallback execution. |
| `src/recon_core/check_engine/diagnostics.py` or existing diagnostic helpers | Add runtime diagnostic constants/helpers for compiled-contract loading and adapter lifecycle failures if needed. | Do not emit raw exception text, query text, rendered SQL, relation names, profile values, credentials, DB errors, or tracebacks. |
| `src/recon_core/services/run.py` | Load project context, compiled checks, compiled contracts, selected profile/target, and invoke check engine with execution dependencies. | `RunService` remains command-level. Do not write run-result artifacts or evidence. |
| `src/recon_core/profiles/loader.py` | Reuse existing selected-profile/target and referenced-connection behavior at runtime. | Do not broaden supported template syntax or allow rendered `type`. |
| `src/recon_core/adapters/registry.py` | Reuse adapter resolution, API validation, diagnostic validation, and redaction paths. | Preserve malformed factory result handling and type mismatch protection. |
| `src/recon_core/adapters/capabilities.py` | Reuse capability validation for `row_count` and `cte_support`. | Unknown/unsupported/malformed capability states do not satisfy execution. |
| `src/recon_core/adapters/rendering.py` | Reuse rendering validation for relation endpoints and operation rendering if runtime renders final SQL in memory. | Do not write compiled SQL from `recon run`; query endpoints remain unsupported. |
| `src/recon_core/adapters/duckdb/adapter.py` | Implement minimal connect/execute/close behavior needed for local same-context relation-backed row-count execution. | No cross-file attach/bridge unless already same context; no query endpoint execution; sanitize lifecycle failures. |
| `src/recon_core/adapters/duckdb/__init__.py` | Export any new DuckDB adapter execution types if needed. | Keep adapter API version stable unless reviewed. |
| `src/recon_core/cli/main.py` | Update only if command message/exit mapping must reflect row-count execution. | Do not add run-result, evidence, selector, profile debug, or sink CLI options in 7.2. |
| `docs/implementation/errors-and-diagnostics.md` | Step 5 should add/align 7.2 diagnostic codes. | Public docs must remain Recon-native and contain no research attribution. |

### Test-First Map

Write tests before implementation in this order:

| Test path | Coverage |
| --- | --- |
| `tests/artifacts/test_compiled_contract_loader.py` | Missing, malformed, unsafe, incompatible, and mismatched compiled-contract artifacts. |
| `tests/services/test_run_service.py` | Runtime joins compiled checks/contracts, loads referenced profiles only, maps runtime diagnostics, writes no generated outputs, and invokes no parser/compiler. |
| `tests/check_engine/test_row_count_execution.py` | Row-count pass/fail, result shape validation, mixed executable and later-phase checks, no Python fallback, no generated outputs. |
| `tests/check_engine/test_dispatch.py` | `row_count_diff` becomes executable only in 7.2; key and aggregate checks remain later-phase non-executable. |
| `tests/adapters/test_runtime_profile_diagnostics.py` or existing adapter/profile test file | Runtime profile redaction, literal adapter type, referenced-only loading, safe/unsafe diagnostic code behavior. |
| `tests/adapters/test_duckdb_adapter.py` | DuckDB connect/execute/close behavior, dependency failures, lifecycle errors, sanitized exceptions. |
| `tests/adapters/test_runtime_capabilities.py` or existing capability tests | `row_count` and `cte_support` required; unsupported, unknown, malformed, and exception-raising capability states block execution. |
| `tests/cli/test_main.py` | CLI/service output stays concise, does not print counts/diffs, and does not claim run-result/evidence artifacts. |
| `tests/services/test_command_services.py` | Keep command-service placeholder expectations aligned if `RunService` behavior changes from 7.1 boundary to 7.2 execution. |

Negative tests must fail if any 7.2 path parses authored YAML, recompiles
contracts, executes query endpoints, performs cross-context execution, compares
counts in Python, stages/materializes data, transfers source/target rows into
Core, writes generated SQL, writes run results, writes evidence, writes
reports, writes failure details, writes state, writes sinks, or exposes
sensitive runtime values.

### Implementation Sequence

Use this sequence when the user explicitly starts Milestone 7.2 implementation:

1. Add compiled-contract loader tests and loader implementation.
2. Add run-service tests for compiled-check/contract joins and referenced
   runtime profile loading.
3. Add adapter resolution/capability/lifecycle tests for runtime execution.
4. Add DuckDB adapter connect/execute/close tests and minimal implementation.
5. Add row-count executor tests for pass, fail, malformed result shape, and
   execution errors.
6. Wire `row_count_diff` dispatch from not-executable to executable only when
   all 7.2 preconditions pass.
7. Add privacy/redaction tests across service, diagnostics, adapter lifecycle,
   and CLI output.
8. Add no-output and stale-output non-mutation tests.
9. Run targeted validation, then full validation before phase exit.

### Validation Commands

Minimum targeted validation for Milestone 7.2 implementation:

```bash
python -m pytest tests/artifacts/test_compiled_contract_loader.py tests/check_engine tests/services/test_run_service.py tests/adapters tests/cli/test_main.py
```

Run full validation before phase exit:

```bash
python -m pytest
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy src
pre-commit run --all-files
```

If any tool is not configured or unavailable in the current environment, the
implementation final report must state that explicitly and include the highest
confidence validation that did run.

### Risks And Rollback Points

| Risk | Guardrail | Rollback point |
| --- | --- | --- |
| Runtime compiles authored YAML instead of using compiled artifacts. | Tests fail on parser/compiler invocation. | Revert run-service integration and keep loader tests isolated. |
| Compiled contract loading changes artifact schemas silently. | Loader parses existing artifacts only; schema changes require compatibility review. | Revert compiler/writer changes; keep runtime parser internal. |
| Adapter diagnostics leak secrets or source/target data. | Redaction tests include credentials, DSNs, transformed values, short numerics, SQL, DB errors, and tracebacks. | Revert to safe generic diagnostics. |
| Python fallback sneaks in for count comparison. | Tests assert no Python comparison path is called; final compare runs through adapter. | Revert executor fallback branch. |
| Query endpoint support appears accidentally. | Query endpoint tests block before execution. | Revert endpoint execution branch. |
| DuckDB bridges different connection configs silently. | Same-context tests require identical selected connection context. | Revert attach/bridge logic. |
| Close failure hides primary execution failure. | Combined failure tests assert primary execution failure remains visible. | Rework lifecycle error aggregation. |
| Counts leak through terminal output. | CLI/service privacy tests assert counts/diffs absent. | Revert CLI output changes. |
| Generated outputs appear before their milestones. | Temp-dir tests assert no run/evidence/report/failure/state/sink writes. | Revert writer calls and schema constants. |

### Future-Owned Items Not Implemented In 7.2

| Item | Owning phase |
| --- | --- |
| Grain-key null, duplicate, missing, and extra key execution | Milestone 7.3 |
| Aggregate metric execution | Milestone 7.4 |
| Local `target/run_results.json`, terminal summary finalization, run-result artifact versioning, and durable placement/capability metadata | Milestone 8 |
| Basic local evidence, reports, bounded failure details, and evidence links | Milestone 9 |
| Query endpoint execution | Later query execution work |
| Row-level value comparison | Later row-level comparison work |
| Sampling execution and persisted sample keys | Later sampling/state work |
| CDC propagation execution | Later CDC work |
| Result/evidence sinks and production result tables | Later sink/result-store work |
| External adapter packages and shared adapter test kit | Later adapter ecosystem work |
| Materialization, staging, intermediate engines, external comparison engines, and Python fallback policies | Later execution-placement work |

### Future Implementation Commit Message

Recommended future implementation commit message:

```text
feat: execute row-count checks through DuckDB adapter
```

## Implementation Readiness Report

Split Decision: Already Split / Follow Existing Split.

Readiness status after Step 4: the 7.2 prework artifact now contains the
scope, non-goals, expected behavior, diagnostics, compatibility impact,
privacy/security rules, placement constraints, evidence/sink/state constraints,
required tests, acceptance/conformance matrix, edge-case matrix, BDD scenarios,
gate satisfaction proof, phase-exit checklist, implementation map, public
contract decision, changelog decision, and Definition of Done.

Implementation is not yet ready to start because the session still has required
prework outside this artifact:

- Step 5: align existing public docs with this artifact.
- Step 6: fix companion prompt drift.
- Step 7: run orphan and drift audit.
- Step 8: run final validation and readiness report.

No open design question remains inside the Step 4 artifact. Remaining work is
publication alignment, prompt hygiene, orphan/drift verification, and final
validation.

## Definition Of Done

Milestone 7.2 is implementation-ready only when:

- this prework artifact is complete,
- existing public docs align with this prework,
- companion prompts are split-aware and do not instruct umbrella Milestone 7
  implementation,
- orphan/drift audit passes,
- final validation passes or skipped checks are explicitly justified,
- compiled-contract runtime loading has a test-first implementation plan,
- runtime profile loading has referenced-only tests,
- adapter resolution/lifecycle tests cover success and failure,
- row-count pass/fail/error tests are planned,
- privacy/redaction tests cover profile, adapter, database, SQL, and
  source/target sensitive values,
- no-output tests cover run results, evidence, reports, failure details, state,
  sinks, result tables, and compiled SQL writes,
- same-context placement tests cover supported and blocked cases,
- no public schema/API/artifact version change is introduced without explicit
  compatibility review,
- all matrix rows map to tests, existing coverage, or explicit out-of-scope
  rationale.

Milestone 7.2 implementation is complete only when:

- `recon run` executes supported compiled relation-backed `row_count_diff`
  checks through same-context DuckDB pushdown,
- equal counts produce `pass`,
- unequal counts produce `fail`,
- runtime/profile/adapter/execution/result-shape failures produce sanitized
  `error` outcomes,
- later-phase checks remain explicitly `not_executable`,
- query endpoints, cross-context execution, materialization, staging, Python
  fallback, and row transfer remain blocked,
- runtime diagnostics are sanitized,
- counts/diff do not appear in terminal/service diagnostics,
- no generated result/evidence/report/failure/state/sink output is written,
- required targeted tests pass,
- full phase-exit validation passes or deviations are explicitly approved.

## Remaining Blockers

No Step 4 design blocker remains inside this artifact.

Coding remains blocked until the rest of the prework session is complete:

- Step 5 must align existing public docs with this artifact.
- Step 6 must fix companion prompt drift.
- Step 7 must prove there are no orphan umbrella Milestone 7 assignments or
  stale public/private guidance.
- Step 8 must run final validation and produce the final readiness report.
