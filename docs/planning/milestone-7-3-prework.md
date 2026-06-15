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

- `RC_RUNTIME_SCAN_ESTIMATE_UNKNOWN`,
- `RC_RUNTIME_SCAN_ESTIMATE_UNSUPPORTED`,
- `RC_RUNTIME_SCAN_BUDGET_EXCEEDED`,
- `RC_RUNTIME_UNSAFE_SCAN_PREFLIGHT`,
- `RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED`,
- `RC_RUNTIME_BOUNDED_LOCAL_SCAN_ALLOWED`.

These phase-owned diagnostic code names are runtime-family names because the
failure is owned by execution policy. Adapter setup and malformed capability
diagnostics may still use the existing adapter/capability diagnostic family
when the failure is detected before runtime budget classification.

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

This matrix is the Step 5 high-risk control for Milestone 7.3. Every required
row maps to a new implementation test, an existing test, or an explicit
out-of-scope rationale. The implementation phase must not treat examples as
complete coverage unless the sibling cases in this matrix are also covered.

| Dimension | Cases | Expected behavior | Test coverage | Docs or gate impact | Out-of-scope rationale |
| --- | --- | --- | --- | --- | --- |
| Check-pack and typed-plan input | `recon_core.basic_equivalence`, explicit compiled key checks, source and target sides, `grain.keys` present, `grain.keys` missing at compile time. | 7.3 consumes already compiled key-safety checks. The pack still expands to row count, missing, extra, null, and duplicate checks. Missing grain remains a compile-time validation error, not a runtime downgrade. | Existing: `tests/compiler/test_check_packs.py` covers pack expansion, grain identity, key-diff directions, null-key operations, duplicate-key operations, and missing-grain rejection. Add no 7.3 runtime YAML parsing tests because run consumes compiled artifacts only. | Gate 1A, ADR 0007, ADR 0014, check-pack docs. | Authored `checks: [...]`, new check-pack config, and runtime recompilation remain outside 7.3. |
| Null-key checks | `null_source_keys`, `null_target_keys`, single key, composite keys, any component null, multiple null rows, no null rows, sampled metadata present. | A null-key check fails when any declared grain-key component is null on the checked side and passes when no checked tuple has a null component. Sampling does not remove the key-safety requirement. | Add check-engine and run-service tests for source, target, composite, any-component-null, no-null pass, and sampled contracts still requiring key safety. Renderer tests should assert null predicates for each grain component. | Gate 1A, Gate 6, sampling docs. | Raw null key examples and failed-key samples remain evidence/failure-detail scope. |
| Duplicate-key checks | `duplicate_source_keys`, `duplicate_target_keys`, single key, composite keys, duplicate fully non-null tuples, null-containing duplicate candidates, duplicate and null failures in the same side. | Duplicate checks fail only for duplicate fully non-null grain tuples. Null-containing tuples belong to null-key checks. Duplicate checks still run when null-key checks fail so both safety signals are visible. | Add check-engine and run-service tests for source, target, composite duplicate, null-containing duplicate candidate excluded, duplicate plus null in one run. Renderer tests should assert duplicate grouping excludes or is evaluated over fully non-null tuples before failure classification. | Gate 1A, ADR 0007, ADR 0014. | Relaxed uniqueness modes remain future advanced contract work. |
| Missing/extra key coverage | `missing_keys`, `extra_keys`, source-minus-target, target-minus-source, distinct fully non-null tuples, duplicates present, nulls present, composite keys, missing and extra in one run. | Missing/extra coverage compares distinct fully non-null grain tuples only. Nulls and duplicates are reported by their own safety checks and do not make missing/extra claim that row-level value matching is safe. | Existing: renderer tests assert key-diff direction, distinct non-null key CTEs, composite key comparison, and type checks. Add check-engine/run-service tests for missing, extra, duplicates present, nulls present, composite keys, and simultaneous missing/extra failures. | Gate 1A, Gate 4I, Gate 6. | Row-level value diff and failure-key export remain future evidence/value-comparison scope. |
| Empty sides | Empty source, empty target, both sides empty, null-key checks on empty sides, duplicate-key checks on empty sides, missing/extra over empty sides. | Empty checked sides pass null/duplicate checks. Missing fails when source has distinct non-null keys and target is empty. Extra fails when target has distinct non-null keys and source is empty. Both sides empty pass key coverage. | Add run-service or check-engine fixture tests for empty source, empty target, and both sides empty across null, duplicate, missing, and extra checks. | Gate 1A, result-model docs. | Empty aggregate semantics remain 7.4. |
| Key physical type mismatch | Source/target key type mismatch with rows, mismatch without rows, composite key with one mismatched component. | Recon must not silently coerce keys. A type mismatch fails closed as a sanitized runtime `error` or pre-execution `not_executable`, depending on where it is detected. It never becomes `pass` or a data mismatch. | Existing: `tests/adapters/test_duckdb_sql_renderer.py` covers key-diff type mismatch with and without rows. Add runtime tests that map adapter execution failure into safe diagnostics without raw query, relation data, or key values. | Gate 3F2, Gate 4I, no silent type coercion rule. | Portable cross-adapter key canonicalization and explicit type-cast policy remain future design work. |
| Dependent blocking | Failed null prerequisite, failed duplicate prerequisite, errored prerequisite, missing prerequisite, blocked prerequisite, not-executable prerequisite, multiple prerequisites, duplicate prerequisite IDs. | Dependent future row-level value checks are `blocked`, include `blocked_by`, and use machine-readable prerequisite reasons. A blocked dependent check never runs and never looks skipped or passing. | Existing: `tests/check_engine/test_engine.py` covers prerequisite failed, missing, error, blocked, not executable, and duplicate missing prerequisite IDs. Add 7.3-specific tests where key-safety check names are the prerequisites and failures come from executed null/duplicate checks. | Gate 1A, result-model docs, ADR 0014. | Actual row-level value comparison remains later work. |
| Capability block | `key_diff`, `null_key`, `duplicate_key`, same-context mechanics, `cte_support` where required, capability present, missing, unsupported, unknown, malformed, exception-raising, version-incompatible. | Unsupported capability states block before check execution and produce `not_executable` or configuration/runtime diagnostics according to existing adapter setup boundaries. No adapter query executes after a hard capability block. | Existing: run-service tests cover row-count capability support and missing required capability before connect. Add 7.3 tests for key capabilities and malformed or exception-raising capability declarations. | Gate 4I, compatibility capability catalog, adapter API compatibility docs. | External adapter test-kit conformance and production adapter execution claims remain future work. |
| Placement/materialization block | Same-context relation-backed allowed, query endpoint block, cross-context block, cross-adapter block, unsupported execution placement, unsupported materialization/staging, third engine, side-local production key diff, no hidden Python fallback. | Only same-context relation-backed key-safety execution may run. Query endpoints, cross-context, cross-adapter, materialization/staging, third-engine comparison, side-local production key diff, and Python fallback are `not_executable` before data movement. | Existing: run-service tests cover query endpoint block, cross-context block, different adapter type block, same-context aliases allowed, unsupported placement/materialization block, and no generated outputs. Add 7.3 versions for key operations and assert no hidden Python fallback. | Gate 4I, ADR 0021. | Generic placement syntax, staging, temp tables, external comparison engines, and query endpoint execution remain future work. |
| Scan-budget allowed path | Full scan allowed under explicit budget, bounded local/dev relation-backed fixture, scan classification present, non-executing estimate within limit when a production adapter can prove it. | A key-safety check may execute only when scope and budget status are explicit. Local/dev relation-backed fixtures may use the bounded exception if the context is explicitly classified local, relation-backed, and bounded. Production paths require non-executing estimate evidence inside the phase budget. | Add scan-budget policy tests for allowed bounded local/dev execution, explicit within-budget status, and recorded classification. No new contract YAML settings are used. | Gate 4L. | Full general user-facing budget settings remain future work. |
| Scan-budget fail-closed path | Scan blocked over budget as `not_executable`, production unknown estimate as `not_executable`, unavailable estimate, unsupported estimation/capability as `not_executable`, malformed estimate, executing profile/analyze as unsafe preflight. | Over-budget and unsafe-estimate outcomes are execution-policy outcomes, not data failures. Recon must not run the scan, must not report mismatch evidence, and must not use executing profile/analyze as safe preflight by default. | Add scan-budget tests for over budget, unknown production estimate, unsupported estimate capability, malformed estimate, unsafe executing preflight, and adapter estimate support states. | Gate 4L, Gate 4I, Gate 6. | Adapter test-kit rows for production scan-estimation compatibility remain future work. |
| Future user-facing budget settings boundary | No contract YAML scan-budget settings, no broad allow-unestimated production scan override, future project/profile/run policy or command option only after separate design, Recon-computed final budget status. | Milestone 7.3 does not add budget settings to contracts. Users may configure limits only in future designed surfaces; Recon computes final budget status from evidence and policy, not user-provided status text. | Add negative tests only if implementation introduces a parser/config surface by mistake. Otherwise this remains a prework/docs guardrail validated by docs scans and code review. | Gate 4L, public contract decision. | Contract-level budget policy requires a later public schema decision. |
| Privacy and diagnostics | Safe status/reason/diagnostic fields, raw keys, raw rows, key lists, relation data, query text, rendered SQL, raw database errors, rendered profile values, credentials, DSN fragments, tracebacks, failure samples. | Public/service diagnostics preserve code, severity, safe message, safe context, and hint where available. They do not emit raw keys, key lists, rows, query text, rendered SQL, raw database errors, rendered profile values, credentials, DSNs, tracebacks, or failure samples. | Existing: run-service and check-engine tests cover sanitized engine, adapter, database, query endpoint, connection, and close failures. Add key-check and scan-budget diagnostic tests for no raw key output and no raw database/query leakage. | Gate 3F2, Gate 6, ADR 0022. | Evidence redaction, failure-detail masking, and secure debug artifacts remain later work. |
| No-output side effects | In-memory results, `target/run_results.json`, `target/failures`, `reports`, `state`, compiled SQL, result tables, sink refs, artifact refs, stale preexisting outputs. | 7.3 writes no generated output and does not mutate stale generated output. In-memory results may carry empty artifact/sink references only. | Existing: check-engine and run-service tests cover no generated outputs and no stale-output mutation. Add 7.3 tests after key execution succeeds and fails. | Gate 6, ADR 0022, generated artifact lifecycle boundary. | Durable run results belong to Milestone 8; evidence and failure details belong to Milestone 9. |
| Sampling/key-safety interaction | Contract sampling metadata present, full sampling mode, sampled row-level dependency, deterministic/random/windowed policy metadata not executed. | Sampled contracts still requiring key safety is mandatory. Sampling metadata does not bypass non-null or uniqueness requirements. Unsupported sampling execution policies remain not executable or future scope. | Add tests that compiled key-safety checks with sampling metadata still execute key safety or block dependent checks; do not add deterministic/random/window execution tests in 7.3. | Sampling docs, Gate 1A, Gate 4L for scan scope. | Sampling execution, persisted sample keys, windows, and watermarks remain future state/window work. |
| Run-service boundary | Missing compiled checks, missing compiled contract, invalid/mismatched artifact, multiple contracts, one executable and one not executable, no parser/compiler invocation, profile resolution only for executable contracts. | `recon run` consumes compiled artifacts only and preserves existing artifact/runtime boundaries. Later-phase non-executable checks do not force unused profile rendering. | Existing: run-service tests cover missing artifacts, no parser fallback, empty check scope, mixed executable/later-phase checks, missing compiled contract, and ignored later-phase profile env. Add equivalent mixed row-count/key-safety cases where needed. | Runtime diagnostics docs, public contract inventory. | Selectors, partial compile, artifact freshness, and runtime recompilation remain future work. |
| Future-scope exclusions | Row-level values, tolerance/null/normalization execution, schema execution, CDC key execution, aggregate execution, query endpoints, filters/windows, probabilistic key diff, no unbounded row fetch, no unbounded key-row movement into Core. | These surfaces remain blocked, `not_executable`, or out of scope with clear rationale. 7.3 must not introduce hidden Python fallback, unbounded row fetch, or unbounded key-row movement into Core. | Add negative tests where an unsupported compiled operation appears beside 7.3 key checks. Use docs/code review for out-of-scope surfaces not reachable by current runtime. | Gate 4I, Gate 4K, Gate 4L, Gate 6, ADR 0021, ADR 0022. | Each future surface needs its own gate, matrix, and tests before implementation. |

## Edge-Case Matrix

| Edge case | Expected behavior | Test mapping |
| --- | --- | --- |
| Source null key | `null_source_keys` fails with sanitized diagnostic and no raw key value. | Add check-engine/run-service key-safety test. |
| Target null key | `null_target_keys` fails with sanitized diagnostic and no raw key value. | Add check-engine/run-service key-safety test. |
| Null in one component of a composite grain | The relevant null-key check fails when any component is null. | Add composite key-safety test. |
| Duplicate fully non-null source key | `duplicate_source_keys` fails. | Add check-engine/run-service duplicate test. |
| Duplicate fully non-null target key | `duplicate_target_keys` fails. | Add check-engine/run-service duplicate test. |
| Duplicate candidate containing a null component | Not counted as duplicate-key identity; reported by null-key check. | Add duplicate-plus-null test. |
| Missing key with duplicate source rows | `missing_keys` compares distinct fully non-null source tuples and fails once for coverage. | Add key-diff result test. |
| Extra key with duplicate target rows | `extra_keys` compares distinct fully non-null target tuples and fails once for coverage. | Add key-diff result test. |
| Missing/extra with null-containing tuples | Null-containing tuples are excluded from key coverage and handled by null-key checks. | Add key-diff with null tuples test. |
| Empty source | Source null/duplicate pass; `extra_keys` may fail if target has keys. | Add empty-side tests. |
| Empty target | Target null/duplicate pass; `missing_keys` may fail if source has keys. | Add empty-side tests. |
| Both sides empty | Null, duplicate, missing, and extra key checks pass. | Add both-empty test. |
| Source/target key physical type mismatch | Fails closed as sanitized `error` or pre-execution `not_executable`; no coercion. | Existing renderer type-mismatch tests plus new runtime diagnostic test. |
| Unsupported key comparison capability | `not_executable` or configuration error before adapter query execution. | Add key capability tests. |
| Unsupported same-context execution | `not_executable`; no bridge, staging, or Python fallback. | Existing row-count placement tests plus new key-operation variants. |
| Query endpoint check | `not_executable` before adapter execution and query text is not printed. | Existing query endpoint run-service test plus key-operation variant. |
| Cross-context check | `not_executable`; no cross-context bridge or fallback. | Existing cross-context run-service test plus key-operation variant. |
| Cross-adapter check | `not_executable`; no adapter-owned strategy substitution. | Existing different-adapter run-service test plus key-operation variant. |
| Unsupported materialization/staging | `not_executable` before adapter setup where possible. | Existing placement/materialization test plus key-operation variant. |
| Production unknown scan estimate | `not_executable` and no scan runs. | Add scan-budget test. |
| Over-budget scan estimate | `not_executable`, not data failure. | Add scan-budget test. |
| Unsupported or malformed estimation/capability | `not_executable` and safe diagnostic. | Add scan-budget/capability tests. |
| Unsafe executing profile/analyze preflight | Rejected as safe preflight unless explicitly classified and budgeted. | Add scan-budget test. |
| Full scan allowed under explicit budget | Executes only when scan scope and policy budget are explicit and within limit. | Add scan-budget allowed-path test. |
| Bounded local/dev relation-backed fixture | May execute only when explicitly classified local, relation-backed, and bounded. | Add local/dev exception test. |
| Future user-facing budget settings boundary | No contract YAML scan-budget setting is introduced in 7.3. | Docs scan and parser/config negative test only if a new surface appears. |
| Dependent row-level check blocked by failed prerequisite | Dependent check is `blocked` with `blocked_by` and prerequisite reason. | Existing prerequisite tests plus key-safety prerequisite variants. |
| Dependent row-level check blocked by missing/error/not-executable prerequisite | Dependent check is `blocked` and never runs. | Existing prerequisite tests plus key-safety prerequisite variants. |
| Sampled contract with key-safety checks | Sampled contracts still require key safety; sampling does not bypass null/duplicate checks. | Add sampling metadata key-safety test. |
| No raw key output | Public diagnostics/results omit raw keys and key lists. | Add privacy test for each key-failure family. |
| No generated output | No run-result, evidence, report, failure-detail, compiled SQL, state, sink, or stale-output mutation. | Existing no-output tests plus 7.3 success/failure variants. |
| No hidden Python fallback | No key rows are fetched into Core for comparison. | Add adapter query-count/no-fetch test around key operations. |
| No unbounded row fetch | Adapter execution returns bounded status/count-style summaries only. | Add key-operation result-shape test. |
| No unbounded key-row movement into Core | Key diff does not stream full key sets into Core by default. | Add key-diff result-shape and no-failure-detail tests. |

## BDD Workflow Scenarios

### Scenario 1: Null-Key Check Fails

Given a compiled relation-backed key-safety check exists for declared
`grain.keys`.
And one side contains a null in any declared grain-key component, including a
composite-key component.
When the user runs `recon run`.
Then the matching null-key check fails.
And the result status is `fail`.
And the diagnostic is safe and machine-readable.
And no raw key value or row value is emitted.
And no generated output is written.

### Scenario 2: Duplicate-Key Check Fails

Given a compiled duplicate-key safety check exists.
And one side contains a duplicate fully non-null grain-key tuple.
And another tuple may contain a null component.
When the user runs `recon run`.
Then the matching duplicate-key check fails.
And null-containing tuples are not counted as duplicate-key identities.
And null-containing tuples are handled by the null-key check.
And both safety signals remain visible when both problems exist.

### Scenario 3: Missing Or Extra Key Check Fails

Given compiled missing/extra key checks exist.
And a distinct fully non-null key tuple exists on only one side.
And duplicate or null-containing tuples may also exist.
When the user runs `recon run`.
Then the matching key-coverage check fails.
And coverage is computed over distinct fully non-null tuples only.
And the result does not imply row-level value comparison is safe.

### Scenario 4: Dependent Row-Level Check Is Blocked

Given a future row-level value check depends on non-null and unique grain keys.
And a required key-safety prerequisite failed, errored, is missing, or is not
executable.
When the check engine evaluates dependencies.
Then the dependent check is `blocked`.
And `blocked_by` identifies the prerequisite.
And the dependent check does not execute.
And the outcome is not reported as `skipped`, `pass`, or `fail`.

### Scenario 5: Empty Sides Are Classified Correctly

Given compiled null, duplicate, missing, and extra key checks exist.
And source and target may be empty independently or both empty.
When the user runs `recon run`.
Then null and duplicate checks pass on empty sides.
And missing or extra checks fail only when the opposite side has distinct
fully non-null keys.
And both sides empty passes key coverage.

### Scenario 6: Key Type Mismatch Fails Closed

Given source and target expose the same grain-key name with incompatible
physical types.
When a key coverage check prepares or executes comparison.
Then Recon does not coerce values.
And the check fails closed as a sanitized runtime `error` or pre-execution
`not_executable`.
And no raw query, relation data, key value, or database error text is emitted.

### Scenario 7: Production Unknown Scan Estimate Is Blocked

Given a production adapter path cannot provide the required scan estimate.
When a grain-key safety check is prepared for execution.
Then the check is `not_executable`.
And the reason is scan-estimate related.
And Recon does not run the scan.

### Scenario 8: Over-Budget Scan Is Not Executable

Given a scan estimate exceeds the configured or phase-defined budget.
When a grain-key safety check is prepared for execution.
Then the check is `not_executable`.
And the outcome is not reported as a data failure.
And no source-target mismatch evidence is produced.

### Scenario 9: Bounded Local Fixture May Execute

Given the execution context is explicitly classified as local, relation-backed,
and bounded.
When a grain-key safety check has no production scan estimate.
Then the check may execute under the bounded local/dev exception.
And the result must record that it used the bounded local classification.

### Scenario 10: Unsupported Estimation Or Capability Is Not Executable

Given the adapter cannot provide required key-check capability or exposes an
unsupported, unknown, malformed, or unsafe estimate capability.
When a grain-key safety check is prepared for execution.
Then the check is `not_executable` or fails adapter setup with a sanitized
configuration diagnostic.
And no adapter query runs after the hard blocker is identified.

### Scenario 11: Unsupported Placement Does Not Fall Back

Given a compiled key check requires query endpoints, cross-context execution,
materialization, staging, or Python fallback.
When the user runs `recon run`.
Then Recon reports `not_executable`.
And no alternate comparison strategy runs silently.
And there is no hidden Python fallback, no unbounded row fetch, and no
unbounded key-row movement into Core.

### Scenario 12: Sampled Contracts Still Require Key Safety

Given a compiled contract includes sampling metadata or a sampled future
row-level check depends on grain keys.
When grain-key safety checks run or dependency evaluation happens.
Then null-key and duplicate-key requirements still apply.
And sampled metadata does not permit row-level matching without non-null and
unique grain keys.

### Scenario 13: No Generated Output Is Written

Given writable `target/`, `reports/`, and `state/` directories exist.
When Milestone 7.3 grain-key safety execution completes.
Then Recon does not create, update, delete, or claim any run-result, evidence,
report, failure-detail, state, compiled SQL, result-table, sink, or hosted-sync
output.
And preexisting generated output remains untouched.

## Gate Satisfaction Proof

This section proves that Step 5 has mapped the design gates needed for
Milestone 7.3 into concrete matrix rows, scenarios, and tests. Step 8 completed
the prompt/docs drift validation and closeout report for this prework session.

| Gate | Step 5 status | Proof in this prework |
| --- | --- | --- |
| Split decision | Satisfied for Step 5. | Split Decision remains `Already Split / Follow Existing Split`. 7.3 owns only grain-key safety execution inside the existing Milestone 7 split. |
| High-risk milestone prework | Satisfied for Step 8 prework closeout. | Scope, non-goals, expected behavior, diagnostics, compatibility, privacy, placement, scan/cost, required tests, matrix, edge cases, BDD scenarios, gate proof, phase-exit checklist, DoD, public-doc alignment, exact implementation map, prompt/docs drift validation, and final closeout are now complete. |
| Gate 1A: key semantics | Satisfied for Step 5 design lock. | Matrix rows cover `grain.keys` only, null keys, duplicate keys, missing/extra keys, composite keys, empty sides, sampled contracts still requiring key safety, and dependent blocking. |
| Gate 3F2: diagnostic output message conformance | Satisfied for Step 5 design lock. | Matrix rows and scenarios require safe code/severity/message/context/hint behavior and no raw keys, raw rows, relation data, query text, rendered SQL, database errors, profile values, credentials, DSNs, or tracebacks. |
| Gate 4I: comparison execution placement | Satisfied for Step 5 design lock. | Matrix rows cover same-context relation-backed allowed path, query endpoint block, cross-context block, cross-adapter block, capability block, placement/materialization block, no hidden Python fallback, no unbounded row fetch, and no unbounded key-row movement into Core. |
| Gate 4K: probabilistic key-diff | Satisfied as not applicable to 7.3. | Matrix and non-goals explicitly exclude probabilistic, Bloom, sketch, checksum, bisection, chunked, and threshold-based key-diff strategies. Future use must reopen Gate 4K. |
| Gate 4L: scan budget and query-plan safety | Satisfied for Step 5 bounded policy. | Matrix rows cover full scan allowed under explicit budget, scan blocked over budget as `not_executable`, production unknown estimate as `not_executable`, bounded local/dev fixture exception, unsupported estimation/capability as `not_executable`, unsafe executing profile/analyze rejection, and future user-facing budget settings boundary. |
| Gate 6: privacy, evidence, and failure detail | Satisfied for Step 5 design lock. | Matrix rows cover privacy, no-output, no raw key output, no failure details, no generated run-result/evidence/report/state/sink output, and no stale generated output mutation. |
| Adapter API and capability compatibility | Satisfied for Step 5 design lock. | Matrix rows require key-diff, null-key, duplicate-key, same-context, and CTE capability checks while explicitly avoiding adapter API version changes, production adapter compatibility claims, and shared adapter test-kit publication. |
| Generated artifact lifecycle | Satisfied for Step 5 design lock. | Matrix and scenarios require only in-memory results and empty artifact/sink references. No runtime-generated `target/`, `reports/`, `state/`, compiled SQL, evidence, result table, or sink output is assigned to 7.3. |
| Public contract compatibility | Satisfied for Step 5 design lock. | Public change remains narrow: in-memory runtime execution of already compiled relation-backed grain-key safety checks. No YAML schema, durable artifact schema, evidence schema, sink schema, or adapter API version change is proposed. |

## Phase-Exit Checklist

This is the pre-implementation phase-exit checklist for Milestone 7.3. Step 5
completed the matrix, gate, BDD, and DoD portions. Step 6 aligned existing
public planning and compatibility docs. Step 7 completes the exact future
implementation map. Step 8 completed final validation and closeout.

| Check | Status after Step 5 | Owner before coding |
| --- | --- | --- |
| Split Decision remains `Already Split / Follow Existing Split`. | Done. | Step 5 |
| Scope, non-goals, expected behavior, diagnostics, compatibility, privacy, placement, scan/cost, evidence/sink/state constraints, matrix, BDD scenarios, gate proof, and DoD are complete. | Done for Step 5-owned sections. | Step 5 |
| Acceptance/conformance matrix maps every required 7.3 behavior to a test, existing test, or out-of-scope rationale. | Done. | Step 5 |
| Edge-case matrix covers null keys, duplicate keys, missing/extra keys, composite keys, empty sides, type mismatch, capability block, placement block, scan-budget block, sampling, privacy, and no-output. | Done. | Step 5 |
| BDD scenarios cover user-facing runtime paths. | Done. | Step 5 |
| Gate 4L scan-budget rows are mapped to tests. | Done. | Step 5 |
| Gate 4I placement rows are mapped to tests. | Done. | Step 5 |
| Gate 6 privacy/output rows are mapped to tests. | Done. | Step 5 |
| Null-key, duplicate-key, missing-key, and extra-key semantics are mapped to tests. | Done. | Step 5 |
| Dependent row-level blocking semantics are mapped to tests. | Done. | Step 5 |
| Existing public planning and compatibility docs are aligned with the new prework. | Done. | Step 6 |
| Exact source map, test-first map, implementation sequence, validation commands, risks, and rollback points are complete. | Done. | Step 7 |
| Prompt/docs drift check and final validation pass. | Done. | Step 8 |
| No public doc contains external research attribution introduced during this session. | Done for touched public docs in final validation. | Step 8 |
| No hard milestone labels were added to prohibited durable docs. | Done for touched public docs in final validation. | Step 8 |
| No authored YAML schema change is proposed for 7.3. | Done. | Step 5 |
| No contract-level scan-budget setting is proposed for 7.3. | Done. | Step 5 |
| No compiled artifact schema change is proposed for 7.3 unless a separate compatibility review documents it. | Done for current plan. | Step 7 recheck found no schema change needed. |
| No adapter API version change is proposed for 7.3 unless a separate compatibility review documents it. | Done for current plan. | Step 7 recheck found no adapter API version change needed. |
| No run-result, evidence, report, failure-detail, state, sink, or result-table output is assigned to 7.3. | Done. | Step 5 |
| Future implementation tests are planned before source changes. | Done. | Step 7 |
| Validation commands for the prework session pass or any skipped validation is explicitly justified. | Done. | Step 8 |

## Implementation Map

This is the exact future implementation plan for Milestone 7.3. It is a
test-first plan for later coding; this prework session does not implement
runtime code or tests.

### Source Map

Planned source changes:

| File | Planned change | Guardrail |
| --- | --- | --- |
| `src/recon_core/check_engine/models.py` | Add scan-budget `CheckReason` values for unknown estimate, unsupported estimate, budget exceeded, unsafe preflight, and bounded-local classification requirements. Keep them under `not_executable`; do not add new statuses. | Existing status taxonomy remains unchanged. No durable result artifact schema is introduced. |
| `src/recon_core/check_engine/scan_budget.py` | Add a small internal scan-budget classifier for this phase. It should produce an allow/block decision plus safe diagnostics. The only allowed no-estimate path is explicit local, relation-backed, bounded execution. | No public YAML, profile, project, run-policy, or CLI setting is added. Users do not set final budget status directly. |
| `src/recon_core/check_engine/key_safety.py` | Add key-safety execution helpers for `null_source_keys`, `null_target_keys`, `duplicate_source_keys`, `duplicate_target_keys`, `missing_keys`, and `extra_keys`. The helpers should render the current typed operation, wrap the rendered key-row query in a count query, execute only the bounded count query, parse a single violation count, and return `pass` or `fail` in-memory results. | Runtime must not fetch raw keys, raw rows, or failure samples into Core. Data failures are counted, not exported. |
| `src/recon_core/check_engine/execution.py` | Reuse existing row-count placement, relation-endpoint, same-context, renderer, and diagnostic patterns where practical. If shared helpers are extracted to support key safety, keep row-count behavior byte-for-byte compatible in tests. | Row-count execution must remain unchanged except for intentional helper extraction covered by existing tests. |
| `src/recon_core/check_engine/engine.py` | Add key-safety execution dispatch beside the current row-count execution hook. Execute key checks only after generic dispatch says the compiled check is otherwise a later-phase non-executable check and no hard blocker applies. Pass scan-budget decisions through the execution context. | Do not execute unknown check types, unsupported typed operations, unsupported placement, unsupported materialization, or missing hard capabilities. |
| `src/recon_core/check_engine/__init__.py` | Export new internal execution helpers or diagnostic constants only if tests need the same package-level import style used by row-count execution. | Avoid creating a stable public API promise beyond the current pre-alpha check-engine surface. |
| `src/recon_core/services/run.py` | Replace row-count-only runtime candidate discovery with executable runtime candidates for row-count plus 7.3 key-safety checks. Load profiles, resolve adapters, validate required capabilities, open adapters, and build scan-budget decisions for only executable candidate contracts. | `recon run` still consumes compiled artifacts only. It must not parse YAML, recompile, load unused later-phase profile values, or write generated outputs. |
| `src/recon_core/adapters/duckdb/adapter.py` | Update `duplicate_key` rendering so duplicate checks operate over fully non-null grain-key tuples. Keep `key_diff` distinct non-null behavior and `null_key` any-null behavior. | Do not add adapter-owned reconciliation semantics. Do not introduce production adapter compatibility claims. |
| `src/recon_core/compiler/check_packs.py` | No planned behavior change. Current `recon_core.basic_equivalence` already emits row count, missing, extra, null, and duplicate checks. Change only if implementation discovers a concrete mismatch with the matrix. | Authored `checks: [...]`, new check-pack config, and runtime recompilation remain out of scope. |
| `src/recon_core/compiler/models.py` | No planned behavior change. Current typed operations and capabilities already include `key_diff`, `null_key`, and `duplicate_key`. Change only if implementation discovers a concrete typed-plan validation gap. | No typed check-plan version or artifact schema change is planned. |

### Test-First Map

Write or update tests in this order before source changes:

1. `tests/adapters/test_duckdb_sql_renderer.py`
   - update the duplicate-key SQL expectation to exclude null-containing grain
     tuples before grouping,
   - add a DuckDB semantic test proving null-containing duplicate candidates do
     not trigger duplicate-key failure,
   - keep existing key-diff distinct non-null, target-minus-source, and
     type-mismatch tests passing.
2. New `tests/check_engine/test_key_safety_execution.py`
   - add unit tests for each key check type passing and failing from a
     single-count adapter result,
   - cover composite keys, null in any component, duplicate fully non-null
     tuples, missing and extra over distinct fully non-null keys, empty source,
     empty target, and both-empty cases,
   - assert count-query wrapping and no raw key rows returned to `CheckResult`,
   - assert malformed count result, key type mismatch, adapter query failure,
     query endpoint, cross-context, unsupported placement, unsupported
     materialization, missing renderer, and renderer failure handling,
   - assert sanitized diagnostics and no raw keys, query text, relation data,
     profile values, database errors, or tracebacks in public result text,
   - assert scan-budget allowed, unknown estimate, unsupported estimate,
     malformed estimate, unsafe preflight, over-budget, and missing bounded
     local classification cases.
3. `tests/check_engine/test_engine.py`
   - add engine tests proving key-safety checks execute through the execution
     context, mixed row-count/key-safety checks both run when eligible, and
     later unsupported checks remain `not_executable`,
   - add dependent row-level check tests where executed null/duplicate key
     failures block future value checks,
   - add hard-blocker tests proving unsupported placement/materialization and
     scan-budget blockers prevent adapter queries.
4. `tests/services/test_run_service.py`
   - add service tests with actual DuckDB relation-backed fixtures for null,
     duplicate, missing, extra, empty-side, pass, and fail outcomes,
   - add service tests for mixed row-count plus key-safety artifacts,
   - add service tests for query endpoint, cross-context, cross-adapter,
     unsupported materialization, missing key capability, scan-budget blocked,
     and bounded local/dev allowed paths,
   - assert no `target/run_results.json`, failure details, reports, state,
     compiled SQL, result tables, or sink output is created or mutated,
   - assert terminal/service diagnostics do not print raw keys or raw database
     payloads.
5. `tests/check_engine/test_row_count_execution.py`
   - keep the existing row-count tests passing. Add regression tests only if a
     shared helper extraction changes code paths.
6. `tests/compiler/test_check_packs.py`
   - keep existing check-pack expansion tests passing. Add tests only if the
     implementation changes prerequisites or requirements; no such change is
     currently planned.

### Implementation Sequence

Future coding should proceed in this order:

1. Add the renderer regression test for duplicate-key non-null grouping, then
   update DuckDB duplicate-key rendering.
2. Add key-safety execution unit tests, then implement `key_safety.py` with
   count-wrapped execution, result parsing, safe diagnostics, and no raw-key
   payloads.
3. Add scan-budget tests, then implement the internal scan-budget classifier
   and new `CheckReason` values. Keep blocked scan outcomes as
   `not_executable`.
4. Add engine integration tests, then wire key-safety execution into
   `CheckEngine` beside row-count execution.
5. Add run-service tests, then generalize runtime candidate discovery,
   capability validation, profile loading, adapter opening, and scan-budget
   decision construction in `RunService`.
6. Run the row-count regression suite and fix only intentional fallout from
   shared helper extraction.
7. Update implementation docs and changelog if runtime behavior actually ships.
   Do not update public YAML, artifact schemas, adapter API version, evidence
   docs, or run-result docs unless implementation discovers a real
   compatibility blocker and a separate review approves it.
8. Run the phase-exit review against the acceptance/conformance matrix before
   considering Milestone 7.3 implementation complete.

Implementation must stop and return to design if it requires contract YAML
scan-budget settings, adapter API version changes, compiled artifact schema
changes, durable run-result/evidence artifacts, raw key export, production
adapter scan-estimation compatibility claims, materialization/staging, query
endpoint execution, or Python-side key-set fallback.

### Public Artifacts Affected

Milestone 7.3 implementation is planned to affect only in-memory runtime result
surfaces:

- `RunResult`,
- `ContractResult`,
- `CheckResult`,
- terminal/service diagnostics derived from those result objects.

Milestone 7.3 must not create, write, or change:

- authored contract YAML schema,
- compiled artifact schema or typed check-plan version,
- adapter API version,
- local `target/run_results.json`,
- evidence artifacts,
- report artifacts,
- failure-detail artifacts,
- state or watermark artifacts,
- result or evidence sinks,
- result tables,
- generated SQL artifacts.

If implementation discovers that any durable artifact or public schema must
change, Milestone 7.3 must stop and run a separate compatibility review before
coding continues.

### Docs During Implementation

When runtime behavior ships, future implementation should update only the docs
whose public behavior statements change:

- `docs/implementation/check-engine.md`,
- `docs/implementation/result-model.md`,
- `docs/implementation/errors-and-diagnostics.md`,
- `docs/compatibility/public-contract-inventory.md`,
- `docs/compatibility/compatibility-matrix.md`,
- `CHANGELOG.md` if implemented user-visible behavior changes.

Do not update framework YAML docs, evidence docs, run-result artifact docs,
adapter API docs, or capability catalog docs during 7.3 unless implementation
discovers a real compatibility blocker and the separate review approves the
expanded scope.

### Validation Commands

Future implementation validation commands:

```bash
pytest tests/adapters/test_duckdb_sql_renderer.py
pytest tests/check_engine/test_key_safety_execution.py
pytest tests/check_engine/test_engine.py
pytest tests/check_engine/test_row_count_execution.py
pytest tests/services/test_run_service.py
pytest tests/compiler/test_check_packs.py
pytest
ruff check .
ruff format --check .
mypy src
```

If optional DuckDB is unavailable, the implementation must not silently skip
required DuckDB semantic coverage. Install the `duckdb` extra in the validation
environment or report the missing dependency as a blocker.

### Risks And Rollback Points

| Risk | Mitigation | Rollback point |
| --- | --- | --- |
| Duplicate-key semantics include null-containing tuples. | Renderer and runtime tests must prove duplicate checks count only fully non-null tuples and nulls are owned by null-key checks. | Revert DuckDB duplicate-key rendering and key-safety execution changes if the non-null invariant cannot be preserved. |
| Missing/extra semantics compare duplicate rows instead of distinct fully non-null tuples. | Keep the existing key-diff renderer distinct/non-null CTEs and add runtime count tests with duplicates and nulls present. | Disable key-diff execution and leave key coverage `not_executable` until distinct/non-null semantics are proven. |
| Runtime fetches raw keys into Core. | Execute only count-wrapped key queries and assert `CheckResult` contains count-style summaries, not key rows or key lists. | Revert key execution helper and keep compiled key checks non-executable. |
| Scan-budget blockers become data failures. | Add explicit scan-budget `CheckReason` values and tests asserting `not_executable`, `executed=False`, and no adapter scan after hard blocks. | Revert scan-budget classifier and keep key checks non-executable. |
| Unknown estimates become an implicit production allow path. | Allow no-estimate execution only through explicit local, relation-backed, bounded classification. All other unknowns are `not_executable`. | Remove bounded exception or restrict it further to test/local DuckDB fixtures. |
| Python fallback or cross-engine comparison appears. | Keep same-context relation-backed checks and assert no row/key movement into Core and no alternate adapter strategy. | Revert run-service candidate expansion and execution hook. |
| Diagnostics leak raw keys, SQL, relation data, profile values, database errors, or tracebacks. | Add diagnostic text scans for every failure family and reuse existing redaction helpers. | Replace detailed diagnostics with safe runtime-family fallback diagnostics. |
| Generated output appears before its owning milestone. | Reuse existing no-output assertions and add 7.3 success/failure variants. | Revert any writer or artifact-reference changes. |
| Row-count behavior regresses while extracting helpers. | Run row-count service and execution tests after each phase. | Revert shared helper extraction and keep row-count path isolated. |

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

Readiness status after Step 8: implementation prework complete for future
Milestone 7.3 coding.

This artifact now locks the public behavior, planning controls, and future
implementation plan for Milestone 7.3:

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
- dimension-expanded acceptance/conformance matrix,
- edge-case matrix,
- BDD workflow scenarios,
- gate satisfaction proof,
- phase-exit checklist with remaining owners,
- exact source map,
- exact test-first map,
- exact implementation sequence,
- public artifacts affected,
- docs during implementation,
- validation commands,
- risks and rollback points,
- Definition of Done,
- remaining blockers.

No known design, gate, public-doc alignment, source-map, test-map, sequencing,
prompt/docs drift, or final-validation blocker remains after Step 8.
Implementation remains a separate future task and must start from this prework,
the companion closeout, and the required routed context reads before coding.

## Definition Of Done

Milestone 7.3 prework is complete only when:

- this prework artifact is complete,
- existing public docs align with this prework,
- the final acceptance/conformance matrix maps every required behavior to a new
  test, an existing test, or explicit out-of-scope rationale,
- the edge-case matrix covers null keys, duplicate keys, missing/extra keys,
  composite keys, empty sides, type mismatch, capability block,
  placement/materialization block, scan-budget block, sampling, privacy, and
  no-output behavior,
- BDD workflow scenarios cover the user-facing runtime paths and safety
  blockers,
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
- empty source, empty target, and both-empty cases follow the accepted
  key-safety matrix,
- source/target key physical type mismatches fail closed without type coercion,
- dependent future row-level checks are blocked when key prerequisites fail,
  error, are missing, or are not executable,
- unsupported capabilities, unsupported placement, unsupported materialization,
  unknown production estimates, unsupported estimates, malformed estimates,
  over-budget scans, unsafe executing profile/analyze preflight, query
  endpoints, cross-context execution, cross-adapter execution, and Python
  fallback remain blocked or not executable,
- full scan allowed under explicit budget works only when scan scope and budget
  status are explicit,
- bounded local/dev fixture execution works only when explicitly classified as
  local, relation-backed, and bounded,
- future user-facing budget settings remain outside 7.3,
- sampled contracts still require key safety,
- runtime diagnostics are sanitized,
- raw keys and raw rows do not appear in public output,
- no unbounded row fetch or unbounded key-row movement into Core occurs,
- no generated result/evidence/report/failure/state/sink output is written,
- required targeted tests pass,
- full phase-exit validation passes or deviations are explicitly approved.

## Remaining Blockers

No prework blockers remain for Milestone 7.3 after Step 8.

Implementation remains a separate future coding session. It must still follow
the test-first implementation sequence, required routed instructions, public
contract review, and phase-exit validation in this artifact.
