# Milestone 7.3 Prework

## Purpose

This is the lightweight prework artifact for Milestone 7.3: grain-key safety
execution.

Milestone 7.3 is high-risk because it touches check execution, typed check
plans, adapter capabilities, SQL rendering, execution placement, scan-budget
safety, source/target privacy, runtime diagnostics, prerequisite/blocking
semantics, future run-result compatibility, and future adapter compatibility.
This artifact is required before implementation, but it is not sufficient by
itself until the final acceptance/conformance matrix, BDD scenarios, test plan,
gate satisfaction proof, implementation map, prompt/docs drift check,
Definition of Done, and phase-exit checklist are complete.

Split Decision: Already Split / Follow Existing Split.

## Scope

Milestone 7.3 builds the first grain-key safety execution path for already
compiled checks.

Build scope:

- relation-backed execution for grain-key safety checks already present in
  compiled artifacts,
- runtime handling for `null_source_keys`,
- runtime handling for `null_target_keys`,
- runtime handling for `duplicate_source_keys`,
- runtime handling for `duplicate_target_keys`,
- runtime handling for `missing_keys`,
- runtime handling for `extra_keys`,
- prerequisite/blocking semantics for dependent future row-level value checks,
- `grain.keys` as the only comparison identity used by this phase,
- composite `grain.keys`,
- null-key detection when any declared grain-key component is null on the
  checked side,
- duplicate-key detection over fully non-null grain-key tuples on the checked
  side,
- missing/extra key coverage over distinct fully non-null grain-key tuples,
- same-context relation-backed execution placement,
- capability validation for key-check execution,
- bounded scan-budget policy for this phase,
- sanitized runtime diagnostics,
- in-memory `RunResult`, `ContractResult`, and `CheckResult` outcomes only,
- negative guarantees that prove the phase does not write generated result,
  evidence, report, failure-detail, state, or sink output.

## Non-Goals

Milestone 7.3 must not implement:

- authored YAML parsing inside `recon run`,
- recompilation inside `recon run`,
- public authored `checks: [...]` support,
- public check registry behavior,
- new contract YAML scan-budget settings,
- full user-facing scan-budget configuration,
- broad allow-unestimated production scan overrides,
- query endpoint execution,
- cross-adapter execution,
- cross-connection comparison when selected connection configs differ,
- side-local production key coverage as a separate placement claim,
- Python-side key-set comparison fallback,
- third-engine comparison,
- adapter-managed intermediate comparison,
- materialization or staging,
- temp table requirements,
- source or target row extraction into Recon Core,
- unbounded key-row movement into Recon Core,
- row-level value comparison,
- row-value hashing,
- tolerance, null-equivalence, or normalization execution,
- schema policy execution,
- CDC key execution,
- CDC propagation checks,
- named identities,
- per-check grains,
- inferred source-target key mappings,
- inferred grain keys,
- probabilistic, Bloom, sketch, checksum, hash-bisection, chunked, or
  threshold-based key-diff strategies,
- source-target filters, windows, selectors, or partial run,
- sampling bypass of non-null or uniqueness requirements,
- aggregate metric execution,
- `target/run_results.json`,
- terminal run-summary finalization,
- evidence artifacts,
- reports,
- failure-detail output,
- raw key export,
- failed-key samples,
- result/evidence sink writes,
- production result tables,
- state writes,
- generated compiled SQL writes from `recon run`,
- hosted upload or external result sync,
- shared adapter test-kit publication,
- external adapter compatibility claims,
- production adapter package split,
- adapter API version changes unless a later compatibility review requires one.

## Expected Behavior

`recon run` should move from row-count-only execution toward the first supported
grain-key safety execution surface for already compiled relation-backed key
checks. It should not parse authored YAML or compile contracts.

Milestone 7.3 should:

- load compiled-check artifacts and matching compiled-contract artifacts through
  the existing runtime boundary,
- preserve compile-time safe diagnostics already attached to compiled checks,
- use only declared `grain.keys` for comparison identity,
- fail null-key checks when any declared grain-key component is null on the
  checked side,
- fail duplicate-key checks when duplicate fully non-null grain-key tuples exist
  on the checked side,
- report null-containing tuples through null-key checks rather than duplicate
  semantics,
- still execute duplicate-key checks when null keys exist so both failure
  signals are visible,
- compare `missing_keys` and `extra_keys` over distinct fully non-null key
  tuples only,
- allow missing/extra key coverage to run when null or duplicate key checks
  fail, while making clear that row-level value matching is not safe,
- block dependent future row-level value checks when required null-key or
  duplicate-key prerequisites fail, error, are missing, or are not executable,
- keep missing/extra key failures as key-coverage failures that run before
  future row-level value checks,
- validate required adapter capabilities before execution,
- execute only when source and target relations are addressable from the same
  approved adapter execution context,
- classify scan scope and budget status before execution,
- report `pass` when an executed key-safety check finds no violation,
- report `fail` when an executed key-safety check finds a data violation,
- report `blocked` when a dependent future row-level check cannot run because
  a prerequisite key-safety check did not prove safe keys,
- report `not_executable` when capability, placement, materialization,
  scan-budget, or implemented-surface requirements are not satisfied,
- report `error` when artifact loading, adapter lifecycle, execution, result
  shape, or diagnostic handling fails before a trustworthy check outcome exists,
- return in-memory results only,
- keep artifact, evidence, failure-detail, state, and sink references empty.

Milestone 7.3 must not report source-target key equivalence unless the relevant
key-safety check actually executed through the locked same-context
relation-backed path.

## Status And Reason Taxonomy

Milestone 7.3 reuses the check statuses introduced by the first check-engine
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

Milestone 7.3 adds factual `pass` and `fail` outcomes only for executed
relation-backed grain-key safety checks.

Data-failure outcomes:

- `null_source_keys` fails when the source side has at least one null-containing
  grain-key tuple,
- `null_target_keys` fails when the target side has at least one null-containing
  grain-key tuple,
- `duplicate_source_keys` fails when the source side has at least one duplicate
  fully non-null grain-key tuple,
- `duplicate_target_keys` fails when the target side has at least one duplicate
  fully non-null grain-key tuple,
- `missing_keys` fails when at least one distinct fully non-null source key
  tuple is absent from the target side,
- `extra_keys` fails when at least one distinct fully non-null target key tuple
  is absent from the source side.

Blocked outcomes use existing prerequisite reason concepts:

- `prerequisite_failed`,
- `prerequisite_error`,
- `prerequisite_missing`,
- `prerequisite_not_executable`.

Not-executable outcomes reuse existing first-boundary reason concepts where
possible:

- `missing_engine_capability`,
- `unsupported_execution_placement`,
- `unsupported_materialization_policy`,
- `not_implemented_in_current_phase`,
- `unsupported_check_type`,
- `unsupported_typed_operation`.

Milestone 7.3 also needs machine-readable scan-budget reason concepts before
coding:

- `scan_estimate_unknown`,
- `scan_estimate_unsupported`,
- `scan_budget_exceeded`,
- `unsafe_scan_preflight`,
- `bounded_local_scan_required`.

These are reason concepts for `not_executable` or safe local classification,
not check statuses. Exact enum names and diagnostic-code names may be finalized
in implementation, but their behavior must remain compatible with this
prework.

`unsupported` and `not_yet_executable` remain reason-code concepts under
`not_executable`; they are not statuses.

## Runtime Diagnostics

Milestone 7.3 reuses first-boundary runtime diagnostic codes where applicable:

- `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND`,
- `RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID`,
- `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND`,
- `RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID`,
- `RC_RUNTIME_NO_COMPILED_CHECKS`,
- `RC_RUNTIME_CHECK_NOT_EXECUTABLE`,
- `RC_RUNTIME_UNSUPPORTED_CHECK_TYPE`,
- `RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION`,
- `RC_RUNTIME_MISSING_ENGINE_CAPABILITY`,
- `RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT`,
- `RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY`,
- `RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE`,
- `RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR`.

Milestone 7.3 should add or use key-safety runtime diagnostics for:

- null grain-key failure,
- duplicate grain-key failure,
- missing/extra key coverage failure,
- blocked dependent row-level checks,
- key-check result-shape errors.

Recommended existing or phase-owned diagnostic concepts include:

- `RC_RUNTIME_NULL_GRAIN_KEYS`,
- `RC_RUNTIME_DUPLICATE_GRAIN_KEYS`,
- `RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE`.

Milestone 7.3 also needs scan-budget diagnostics for:

- unknown scan estimate,
- unsupported scan estimate,
- scan budget exceeded,
- unsafe executing plan/profile mode,
- bounded local/dev fixture classification.

Exact diagnostic code names for scan-budget outcomes must be locked in Step 5
before implementation. They should use the runtime family unless the failure is
owned by adapter setup or capability validation.

Runtime diagnostics explain check outcome, non-execution, lifecycle failure,
budget blocking, prerequisite blocking, or key-safety data failures. They are
not evidence artifacts and must not expose raw rows, raw keys, raw relation
data, source/target query text, rendered SQL, database error text, rendered
profile values, credentials, DSN fragments, raw adapter exception text,
tracebacks, or unredacted artifact contents.

Diagnostics must preserve:

- code,
- severity,
- safe message,
- safe resource context,
- path or check identity where available,
- actionable hint where available.

## Affected Docs And Decisions

Milestone 7.3 implementation must stay consistent with:

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
- `docs/framework/checks.md`,
- `docs/framework/check-packs.md`,
- `docs/framework/sampling-policies.md`,
- `docs/compatibility/adapter-api.md`,
- `docs/compatibility/capability-catalog.md`,
- `docs/compatibility/public-contract-inventory.md`,
- `docs/compatibility/compatibility-matrix.md`,
- `docs/compatibility/typed-check-plan.md`,
- `docs/compatibility/change-checklist.md`,
- `docs/decisions/adr-0007-grain-keys-and-row-level-uniqueness.md`,
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`,
- `docs/decisions/adr-0014-key-semantics-and-check-dependencies.md`,
- `docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`,
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`,
- `docs/decisions/adr-0021-execution-placement-and-comparison-engine-strategy.md`,
- `docs/decisions/adr-0022-evidence-privacy-failure-detail-and-result-sinks.md`.

No new ADR is required for Milestone 7.3 as long as the implementation follows
this prework, the existing ADRs, and the aligned public docs. A new or updated
ADR is required if implementation adds contract YAML scan-budget settings,
changes adapter API requirements, changes typed check-plan payloads, writes
durable result/evidence artifacts, introduces materialization/staging, or
changes execution-placement policy.

## Compatibility Impact

Milestone 7.3 is a planned public behavior change for `recon run`: supported
compiled, relation-backed grain-key safety checks may execute and produce
factual in-memory `pass` or `fail` results.

Public surfaces affected:

- `recon run` behavior for already compiled relation-backed grain-key safety
  checks,
- in-memory `RunResult`, `ContractResult`, and `CheckResult` outcomes,
- runtime diagnostic codes and messages,
- prerequisite and blocking behavior for dependent future row-level checks,
- adapter capability expectations for key-safety execution,
- scan-budget status and non-execution reasons,
- source/target privacy guarantees for key-check runtime diagnostics.

Public surfaces not changed:

- authored contract YAML schema,
- contract-level scan-budget settings,
- project/profile/run scan-budget configuration schema,
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

Milestone 7.3 must not claim external adapter compatibility, shared adapter
test-kit readiness, broad production adapter scan-budget conformance, or
general user-facing scan-budget configuration.

## Security And Privacy Impact

Milestone 7.3 queries source and target key columns through an adapter execution
context, so source/target data privacy applies before coding.

Public by default:

- run/check status,
- diagnostic code,
- severity,
- safe messages,
- adapter type label,
- non-secret artifact/version/status metadata,
- count-style summaries only when the owning surface explicitly allows them.

Policy-controlled in Milestone 7.3:

- null-key counts,
- duplicate-key counts,
- missing-key counts,
- extra-key counts,
- scan classification,
- budget status,
- estimate availability,
- relation names,
- source/target identifiers,
- connection names,
- profile/target names.

Sensitive by default:

- raw rows,
- raw comparison keys,
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
- failed-key samples,
- high-cardinality key lists,
- sample keys,
- CDC identifiers.

Milestone 7.3 may expose only safe statuses, reason codes, sanitized
diagnostics, and bounded count-style summaries inside in-memory check results.
Terminal/service diagnostics must not print raw key values, relation data,
source/target query text, rendered SQL, database error text, rendered profile
values, credentials, DSN fragments, tracebacks, or raw adapter exception text.

Omitted failure-key detail is intentionally assigned to later evidence and
failure-detail surfaces, not to the default 7.3 runtime diagnostic path.

## Placement Constraint

Milestone 7.3 locks grain-key safety execution placement to exact same-context
relation-backed execution.

Operation execution location:

- selected adapter execution context.

Comparison location:

- same selected adapter execution context.

Materialization and staging policy:

- none.

Allowed endpoint shape:

- source endpoint is relation-backed,
- target endpoint is relation-backed,
- source and target relations are addressable from the same selected adapter
  execution context.

Forbidden placement behavior:

- Python-side key-set comparison fallback,
- production side-local key-coverage comparison as a separate placement claim,
- cross-adapter execution,
- cross-connection comparison when selected connection configs differ,
- query endpoint execution,
- third-engine comparison,
- source or target data extraction into Recon Core,
- unbounded key-row movement,
- hash or bisection strategies,
- materialized diff output,
- staging or temp-table behavior,
- adapter-owned reconciliation semantics.

Required capabilities:

- `key_diff`,
- `null_key`,
- `duplicate_key`,
- `cte_support` when required by rendered operations,
- the selected same-context execution mechanics required by the implementation.

Unknown, unsupported, not-implemented, malformed, incompatible, or
exception-raising capability states do not satisfy Milestone 7.3 execution
requirements.

## Scan And Cost Constraint

Milestone 7.3 applies the execution cost, scan-budget, and query-plan safety
gate before key checks execute.

This phase locks a bounded policy only:

- scan scope and budget status must be explicit before execution,
- production unknown or unavailable scan estimates become `not_executable`,
- over-budget checks become `not_executable`, not data failures,
- unsupported or malformed estimate capability becomes `not_executable`,
- executing profile/analyze modes are not safe preflight by default,
- bounded local/dev fixture exceptions are allowed only if explicitly
  classified as local, relation-backed, and bounded,
- the full general user-facing scan-budget settings system remains future work.

Users may eventually configure scan limits or opt-ins through project,
profile/target, run-policy, command, or future contract policy surfaces, but
Milestone 7.3 adds no new contract YAML scan-budget settings. Contract-level
scan-budget policy requires a separate public schema decision. The preferred
future home for general execution-safety policy is project, profile/target, or
run policy unless a later decision explicitly chooses otherwise.

Recon computes budget status from adapter plan/estimate evidence, adapter
capability state, placement policy, configured limits, and bounded local/dev
classification. Users do not set final budget status directly.

## Evidence, Sink, And State Constraint

Milestone 7.3 may produce only:

- in-memory `RunResult`,
- in-memory `ContractResult`,
- in-memory `CheckResult`,
- sanitized diagnostics.

Milestone 7.3 must not produce:

- `target/run_results.json`,
- evidence artifacts,
- reports,
- failure-detail files,
- failed-key sample files,
- result tables,
- result sinks,
- evidence sinks,
- state files,
- previous-failure key stores,
- persisted sample keys,
- external uploads,
- hosted service sync,
- adapter test-kit snapshots that expose runtime source/target values.

Execution placement, scan-budget policy, and future sink placement remain
separate. A key-safety check may execute through one approved adapter context in
Milestone 7.3, but no result or evidence sink is configured, inferred, or
written in this phase.

## Public Contract Decision

Milestone 7.3 is a planned public behavior change for `recon run`: supported
compiled, relation-backed grain-key safety checks may now execute and produce
factual in-memory outcomes.

That public behavior is intentionally narrow:

- already compiled artifacts only,
- grain-key safety checks only,
- relation-backed endpoints only,
- same-context execution only,
- bounded scan-budget policy only,
- sanitized diagnostics only,
- in-memory results only.

The public contract does not include durable run-result artifacts, evidence,
reports, failure details, sink writes, query endpoint execution, cross-adapter
execution, production side-local key coverage, Python fallback, materialization,
staging, general scan-budget configuration, contract-level budget settings, or
external adapter compatibility.

## Changelog Decision

No changelog entry is required for this prework-only artifact.

Milestone 7.3 implementation may require a changelog entry when runtime behavior
actually changes. That decision belongs to the implementation or release-note
step, not this prework creation step.

## Required Tests

Milestone 7.3 implementation must add tests for:

- execution of `null_source_keys`,
- execution of `null_target_keys`,
- execution of `duplicate_source_keys`,
- execution of `duplicate_target_keys`,
- execution of `missing_keys`,
- execution of `extra_keys`,
- composite `grain.keys`,
- null in any component of a composite key,
- duplicate fully non-null composite key tuples,
- duplicate checks still executing when null-key failures exist,
- missing/extra coverage over distinct fully non-null key tuples,
- missing/extra results not implying row-level value matching is safe,
- dependent future row-level checks blocked by failed null-key prerequisites,
- dependent future row-level checks blocked by failed duplicate-key
  prerequisites,
- dependent future row-level checks blocked by errored, missing, or
  not-executable prerequisites,
- capability validation for `key_diff`, `null_key`, `duplicate_key`, and
  required same-context mechanics,
- unsupported, unknown, malformed, or exception-raising capability states,
- same-context relation-backed execution,
- query endpoint block,
- cross-adapter block,
- cross-context block,
- unsupported placement block,
- unsupported materialization/staging block,
- no Python-side key-set comparison fallback,
- no unbounded key-row movement into Recon Core,
- no raw key export,
- no failure-detail output,
- no generated run-result/evidence/report/state/sink output,
- bounded local/dev scan-budget classification if allowed,
- production unknown estimate becoming `not_executable`,
- unsupported estimate capability becoming `not_executable`,
- over-budget estimate becoming `not_executable` rather than data failure,
- executing profile/analyze rejected as safe preflight unless explicitly
  classified and budgeted,
- sanitized diagnostics for key-safety failures and scan-budget blockers,
- terminal/service diagnostics not printing raw keys or key lists,
- existing row-count execution remaining in scope from the prior phase,
- aggregate checks remaining assigned to the later aggregate execution phase,
- row-level value checks remaining blocked or not executable until their
  assigned future phase.

The final high-risk acceptance/conformance matrix and BDD workflow scenarios
must map each required behavior to a test, an existing test, or explicit
out-of-scope rationale before implementation starts.

## Acceptance And Conformance Matrix

Step 5 must complete this section before Milestone 7.3 implementation starts.
The matrix must be dimension-expanded and must not rely on examples alone.

Required matrix placeholder dimensions:

| Dimension | Required cases to complete in Step 5 | Expected behavior to lock |
| --- | --- | --- |
| Null-key checks | Source side, target side, single key, composite key, any component null, no nulls. | Null-key checks fail on null-containing grain tuples and pass otherwise. |
| Duplicate-key checks | Source side, target side, fully non-null duplicate tuples, null-containing tuples, composite keys. | Duplicate checks operate on fully non-null tuples and do not absorb null-key semantics. |
| Missing/extra key coverage | Missing keys, extra keys, duplicates present, nulls present, empty sides, composite keys. | Coverage compares distinct fully non-null tuples and does not imply value matching is safe. |
| Prerequisite blocking | Failed, errored, missing, and not-executable null/duplicate prerequisites. | Dependent future row-level checks are `blocked` with `blocked_by` and safe diagnostics. |
| Capability validation | Required key capabilities present, missing, unknown, unsupported, malformed, versioned, exception-raising. | Unsupported capability states block before execution. |
| Placement | Same-context relation-backed, query endpoint, cross-adapter, cross-context, staging/materialization, Python fallback temptation. | Only same-context relation-backed execution may run. Other paths are `not_executable`. |
| Scan budget | Explicit allowed budget, production unknown estimate, unsupported estimate, over budget, unsafe executing profile, bounded local/dev exception. | Unsafe scan paths become `not_executable`; bounded local/dev is allowed only if explicitly classified. |
| Privacy | Counts/statuses, raw keys, raw rows, relation data, query text, DB errors, rendered profile values, failure samples. | Safe summaries only; sensitive values are not emitted. |
| Output side effects | In-memory results, run-result artifact, evidence, reports, failure details, state, sinks, generated SQL. | Only in-memory results and diagnostics may exist. |
| Future-scope exclusions | Row-level values, tolerance/null/normalization, schema, CDC, filters/windows, probabilistic key diff, aggregate execution. | Future behavior remains blocked, not executable, or out of scope with clear rationale. |

## Edge-Case Matrix

Step 5 must complete this section before implementation starts.

Required edge-case placeholders:

- source null key,
- target null key,
- null in one component of a composite grain,
- duplicate fully non-null source key,
- duplicate fully non-null target key,
- duplicate candidate containing a null component,
- missing key with duplicate source rows,
- extra key with duplicate target rows,
- missing/extra with null-containing tuples,
- empty source,
- empty target,
- both sides empty,
- source/target key physical type mismatch,
- unsupported key comparison capability,
- unsupported same-context execution,
- query endpoint check,
- cross-context check,
- production unknown scan estimate,
- over-budget scan estimate,
- unsafe executing profile/analyze preflight,
- bounded local/dev relation-backed fixture,
- dependent row-level value check blocked by failed prerequisite,
- no raw key output,
- no generated output.

## BDD Workflow Scenarios

Step 5 must complete this section before implementation starts.

Required scenario placeholders:

### Scenario 1: Null-Key Check Fails

Given a compiled relation-backed key-safety check exists for declared
`grain.keys`.
And one side contains a null in any declared grain-key component.
When the user runs `recon run`.
Then the matching null-key check fails.
And the diagnostic is safe.
And no raw key value or row value is emitted.

### Scenario 2: Duplicate-Key Check Fails

Given a compiled duplicate-key safety check exists.
And one side contains a duplicate fully non-null grain-key tuple.
When the user runs `recon run`.
Then the matching duplicate-key check fails.
And null-containing tuples are not counted as duplicate-key identities.

### Scenario 3: Missing Or Extra Key Check Fails

Given compiled missing/extra key checks exist.
And a distinct fully non-null key tuple exists on only one side.
When the user runs `recon run`.
Then the matching key-coverage check fails.
And the result does not imply row-level value comparison is safe.

### Scenario 4: Dependent Row-Level Check Is Blocked

Given a future row-level value check depends on non-null and unique grain keys.
And a required key-safety prerequisite failed, errored, is missing, or is not
executable.
When the check engine evaluates dependencies.
Then the dependent check is `blocked`.
And `blocked_by` identifies the prerequisite.

### Scenario 5: Production Unknown Scan Estimate Is Blocked

Given a production adapter path cannot provide the required scan estimate.
When a grain-key safety check is prepared for execution.
Then the check is `not_executable`.
And the reason is scan-estimate related.
And Recon does not run the scan.

### Scenario 6: Over-Budget Scan Is Not Executable

Given a scan estimate exceeds the configured or phase-defined budget.
When a grain-key safety check is prepared for execution.
Then the check is `not_executable`.
And the outcome is not reported as a data failure.

### Scenario 7: Bounded Local Fixture May Execute

Given the execution context is explicitly classified as local, relation-backed,
and bounded.
When a grain-key safety check has no production scan estimate.
Then the check may execute under the bounded local/dev exception.
And the result must record that it used the bounded local classification.

### Scenario 8: Unsupported Placement Does Not Fall Back

Given a compiled key check requires query endpoints, cross-context execution,
materialization, staging, or Python fallback.
When the user runs `recon run`.
Then Recon reports `not_executable`.
And no alternate comparison strategy runs silently.

### Scenario 9: No Generated Output Is Written

Given writable `target/`, `reports/`, and `state/` directories exist.
When Milestone 7.3 grain-key safety execution completes.
Then Recon does not create, update, delete, or claim any run-result, evidence,
report, failure-detail, state, compiled SQL, result-table, sink, or hosted-sync
output.

## Gate Satisfaction Proof

This section proves that the design gates needed for Milestone 7.3 are
represented before implementation. Step 5 must complete the final proof table
before coding starts.

| Gate | Step 4 status | Proof in this prework |
| --- | --- | --- |
| Split decision | Satisfied for Step 4. | Milestone 7 remains split and 7.3 owns only grain-key safety execution. |
| High-risk milestone prework | Partially satisfied for Step 4. | Scope, non-goals, expected behavior, diagnostics, compatibility, privacy, placement, scan/cost, required tests, matrix placeholders, BDD placeholders, phase-exit placeholders, implementation-map placeholders, DoD, and blockers are documented. Step 5 must complete the full matrix and BDD content. |
| Gate 1A: key semantics | Partially satisfied for Step 4. | `grain.keys` is the only identity, `cdc.keys` is out of scope, and null/duplicate/missing/extra semantics are locked. Step 5 must map all cases to matrix rows and tests. |
| Gate 3F2: diagnostic output message conformance | Partially satisfied for Step 4. | Diagnostics must preserve code, severity, safe message, and useful context while suppressing unsafe data. Step 5 must map diagnostic cases to tests. |
| Gate 4I: comparison execution placement | Partially satisfied for Step 4. | Same-context relation-backed execution is the only allowed placement. Python fallback, query endpoints, staging, materialization, cross-adapter, and cross-context execution are forbidden. |
| Gate 4K: probabilistic key-diff | Not applicable to 7.3 as scoped. | Probabilistic, Bloom, sketch, checksum, bisection, and chunked key-diff strategies are out of scope. Gate 4K remains future if such strategies are proposed later. |
| Gate 4L: scan budget and query-plan safety | Partially satisfied for Step 4. | Bounded 7.3 policy is locked: production unknown estimates and over-budget scans become `not_executable`; bounded local/dev exceptions require explicit classification; full settings remain future work. Step 5 must map concrete rows and tests. |
| Gate 6: privacy, evidence, and failure detail | Partially satisfied for Step 4. | Raw keys, rows, query text, database errors, rendered profile values, failure details, evidence, and sinks remain out of scope. Counts/statuses/safe diagnostics only. |
| Adapter API and capability compatibility | Partially satisfied for Step 4. | Required capabilities are named and unsupported states fail closed. No adapter API version or external compatibility claim is made. |
| Generated artifact lifecycle | Partially satisfied for Step 4. | 7.3 writes no generated run results, evidence, failure details, reports, state, sinks, or compiled SQL. Step 5 must map no-output tests. |
| Public contract compatibility | Partially satisfied for Step 4. | Public behavior is narrow in-memory execution for compiled relation-backed key checks. No YAML, artifact schema, result schema, evidence schema, sink schema, or adapter API version change is planned. |

## Phase-Exit Checklist

Step 5 must complete this checklist before implementation starts:

- [ ] Split Decision remains `Already Split / Follow Existing Split`.
- [ ] `docs/planning/milestone-7-3-prework.md` contains complete scope,
  non-goals, expected behavior, diagnostics, compatibility, privacy, placement,
  scan/cost, evidence/sink/state constraints, matrix, BDD scenarios,
  implementation map, and DoD.
- [ ] Gate 4L scan-budget rows are mapped to tests.
- [ ] Gate 4I placement rows are mapped to tests.
- [ ] Gate 6 privacy/output rows are mapped to tests.
- [ ] Null-key, duplicate-key, missing-key, and extra-key semantics are mapped
  to tests.
- [ ] Dependent row-level blocking semantics are mapped to tests.
- [ ] No public doc contains external research attribution introduced during
  this session.
- [ ] No hard milestone labels were added to prohibited durable docs.
- [ ] No authored YAML schema change is proposed for 7.3.
- [ ] No contract-level scan-budget setting is proposed for 7.3.
- [ ] No compiled artifact schema change is proposed for 7.3 unless a separate
  compatibility review documents it.
- [ ] No adapter API version change is proposed for 7.3 unless a separate
  compatibility review documents it.
- [ ] No run-result, evidence, report, failure-detail, state, sink, or
  result-table output is assigned to 7.3.
- [ ] Future implementation tests are planned before source changes.
- [ ] Validation commands for the prework session pass or any skipped
  validation is explicitly justified.

## Implementation Map

Step 7 must complete this section with the exact future implementation plan.
This Step 4 skeleton records the likely implementation surfaces only.

### Source Map

Likely future source surfaces:

- `src/recon_core/services/run.py`,
- `src/recon_core/check_engine/engine.py`,
- `src/recon_core/check_engine/execution.py`,
- `src/recon_core/check_engine/dispatch.py`,
- `src/recon_core/check_engine/models.py`,
- `src/recon_core/adapters/duckdb/adapter.py`,
- `src/recon_core/compiler/check_packs.py`,
- `src/recon_core/compiler/models.py`,
- runtime diagnostic helpers if scan-budget or key-safety diagnostics need
  new constants.

Step 7 must define exact file changes, guardrails, sequencing, and rollback
points before implementation starts.

### Test-First Map

Likely future tests:

- `tests/compiler/test_check_packs.py`,
- `tests/adapters/test_duckdb_sql_renderer.py`,
- `tests/check_engine/test_engine.py`,
- `tests/check_engine/test_row_count_execution.py`,
- `tests/services/test_run_service.py`,
- targeted adapter/runtime tests for scan-budget classification if a new helper
  is introduced.

Step 5 must map matrix rows to tests; Step 7 must order those tests before
implementation.

### Implementation Sequence

Step 7 must complete the implementation sequence. The first implementation
phase should remain test-first and should not start until Steps 5 and 6 are
complete.

### Validation Commands

Minimum future validation will include targeted tests for compiler check-pack
emission, SQL rendering, check-engine dispatch/execution, run service behavior,
and adapter runtime behavior. Step 7 must lock exact commands.

### Risks And Rollback Points

Step 7 must complete the risk and rollback table. Known Step 4 risks are:

- duplicate-key semantics could accidentally include null-containing tuples,
- missing/extra semantics could accidentally compare duplicate rows instead of
  distinct non-null key tuples,
- scan-budget blockers could be misreported as data failures,
- unknown estimate could become an implicit production allow path,
- Python key-set fallback could move unbounded keys into Core,
- diagnostics could leak raw keys or database errors,
- generated output could appear before its owning milestone.

### Future-Owned Items Not Implemented In 7.3

| Item | Owning phase or gate |
| --- | --- |
| General user-facing scan-budget configuration | Future Gate 4L work |
| Contract-level scan-budget policy | Future public schema decision under Gate 4L |
| Production adapter scan-estimation/test-kit conformance | Future adapter test-kit and adapter package work |
| Row-level value comparison | Later row-level comparison work |
| Tolerance/null/normalization execution | Later row-level comparison work |
| Schema policy execution | Later schema execution work |
| CDC key execution and CDC propagation checks | Later CDC work |
| Query endpoint execution | Later query endpoint work |
| Filters, windows, selectors, and partial run | Later selector/window/state work |
| Probabilistic, Bloom, sketch, checksum, bisection, or chunked key diff | Future Gate 4K/Gate 4L/Gate 4I work |
| Materialization, staging, intermediate engines, and external comparison engines | Later execution-placement work |
| Local `target/run_results.json` and durable result schema | Milestone 8 |
| Evidence, reports, and bounded failure details | Milestone 9 |
| Result/evidence sinks and production result tables | Later sink/result-store work |
| State, watermarks, persisted samples, and previous-failure keys | Later state work |
| External adapter packages and shared adapter test kit | Later adapter ecosystem work |

### Future Implementation Commit Message

Recommended future implementation commit message:

```text
feat: execute grain-key safety checks
```

## Implementation Readiness Report

Split Decision: Already Split / Follow Existing Split.

Readiness status after Step 4: not implementation-ready yet.

This artifact now locks the public Step 4 behavior for Milestone 7.3:

- scope,
- non-goals,
- expected behavior,
- status and reason taxonomy,
- diagnostics,
- compatibility impact,
- privacy/security rules,
- placement constraints,
- scan/cost constraints,
- evidence/sink/state constraints,
- public contract decision,
- changelog decision,
- required tests,
- matrix placeholders,
- BDD placeholders,
- gate proof placeholders,
- phase-exit checklist,
- implementation-map placeholders,
- Definition of Done,
- remaining blockers.

Implementation must not start until Steps 5, 6, 7, and 8 complete the matrix,
BDD scenarios, gate proof, public-doc alignment, exact implementation plan, and
final validation.

## Definition Of Done

Milestone 7.3 prework is complete only when:

- this prework artifact is complete,
- existing public docs align with this prework,
- the final acceptance/conformance matrix maps every required behavior to a
  test, existing test, or explicit out-of-scope rationale,
- BDD workflow scenarios cover the user-facing runtime paths,
- gate satisfaction proof is complete,
- phase-exit checklist is complete,
- exact future implementation plan is complete,
- prompt/docs drift check passes,
- final validation passes or skipped checks are explicitly justified.

Milestone 7.3 implementation is complete only when:

- supported relation-backed grain-key safety checks execute through the locked
  same-context adapter path,
- null-key checks fail on null-containing grain tuples,
- duplicate-key checks fail on duplicate fully non-null grain tuples,
- missing/extra checks compare distinct fully non-null grain tuples,
- dependent future row-level checks are blocked when key prerequisites fail,
  error, are missing, or are not executable,
- unsupported capabilities, unsupported placement, unsupported materialization,
  unknown production estimates, unsupported estimates, over-budget scans, query
  endpoints, cross-context execution, and Python fallback remain blocked or
  not executable,
- runtime diagnostics are sanitized,
- raw keys and raw rows do not appear in public output,
- no generated result/evidence/report/failure/state/sink output is written,
- required targeted tests pass,
- full phase-exit validation passes or deviations are explicitly approved.

## Remaining Blockers

Milestone 7.3 is not implementation-ready after Step 4.

Remaining prework blockers:

- Step 5 must complete the acceptance/conformance matrix, edge-case matrix,
  BDD scenarios, gate satisfaction proof, phase-exit checklist, and concrete
  scan-budget status/test rows.
- Step 6 must align existing public planning and compatibility docs after this
  prework artifact becomes authoritative.
- Step 7 must complete the exact future implementation plan and readiness
  report.
- Step 8 must run final validation, close out the companion brain dump, and
  report what is locked for 7.3.
