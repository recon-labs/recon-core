# Milestone 7.4 Prework

## Purpose

This is the lightweight prework artifact for Milestone 7.4: aggregate metric
execution.

Milestone 7.4 is high-risk because it touches aggregate execution, typed
operation execution, adapter capabilities, SQL rendering, execution placement,
scan and cost safety, numeric tolerance behavior, source/target privacy,
runtime diagnostics, result-model behavior, and future run/evidence
compatibility.

This artifact records the public scope and safety boundaries for the milestone.
Implementation must not start until the remaining high-risk prework artifacts
are complete: the dimension-expanded acceptance/conformance matrix, BDD
workflow scenarios, detailed test plan, implementation source map,
implementation responsibility map, docs drift check, and phase-exit checklist.

Split Decision: Already Split / Follow Existing Split.

## Status

Prework is in progress.

Current status:

- the Milestone 7 split already assigns aggregate metric execution to
  Milestone 7.4;
- the milestone stays limited to current compiled `sum` aggregate plans;
- research_decision: not-required;
- implementation remains blocked until this prework is expanded with the final
  matrix, BDD scenarios, test plan, source map, responsibility map, and docs
  drift alignment.

## Scope

Milestone 7.4 builds aggregate execution for already compiled checks.

Build scope:

- relation-backed execution for current ungrouped `sum_diff` compiled checks,
- relation-backed execution for current `grouped_aggregate_diff` compiled
  checks,
- numeric absolute tolerance for supported numeric aggregate comparisons,
- empty aggregate semantics for current `sum` metrics,
- aggregate input, aggregate result, and grouped-key type mismatch behavior,
- same-context relation-backed execution placement for the initial aggregate
  execution path,
- adapter capability validation before aggregate execution,
- scan and cost safety classification before aggregate execution,
- sanitized runtime diagnostics,
- in-memory `RunResult`, `ContractResult`, and `CheckResult` outcomes only,
- negative guarantees that prove the phase does not write generated result,
  evidence, report, failure-detail, state, or sink output.

Milestone 7.4 may execute only explicit `sum` metrics that already compile into
current `sum_diff` or `grouped_aggregate_diff` typed plans.

## Non-Goals

Milestone 7.4 must not implement:

- `min`, `max`, `avg`, or `count_distinct` metric execution,
- `recon_core.aggregate_equivalence`,
- aggregate check inference from numeric columns,
- generated aggregate suggestions,
- new authored YAML metric syntax,
- new typed operation names,
- new adapter capability names,
- timestamp tolerance execution,
- string tolerance execution,
- row-level null-equivalence execution,
- row-level normalization execution,
- schema policy execution,
- row-level value comparison,
- CDC execution,
- executable query endpoints,
- cross-adapter execution,
- cross-connection aggregate comparison when selected connection configs differ,
- side-local aggregate comparison with Recon-local comparison as the initial
  implementation path,
- third-engine comparison,
- adapter-managed intermediate comparison,
- materialization, staging, or temporary table requirements,
- hidden Python fallback,
- source or target row extraction into Recon Core,
- unbounded grouped aggregate result movement into Recon Core,
- grouped-key or grouped-value failure detail export,
- public scan-budget YAML, profile, project, run-policy, or CLI settings,
- broad allow-unestimated production scan overrides,
- production adapter execution compatibility claims,
- shared adapter test-kit publication,
- external adapter package behavior,
- `target/run_results.json`,
- terminal run-summary finalization,
- evidence artifacts,
- reports,
- failure-detail output,
- raw aggregate value export,
- raw grouped-key export,
- result/evidence sink writes,
- production result tables,
- state writes,
- generated compiled SQL writes from `recon run`,
- hosted upload or external result sync.

## Expected Behavior

`recon run` should move from row-count and bounded local/dev grain-key safety
execution toward the first supported aggregate execution surface for already
compiled relation-backed aggregate checks. It should not parse authored YAML or
compile contracts.

Milestone 7.4 should:

- load compiled-check artifacts and matching compiled-contract artifacts
  through the existing runtime boundary,
- preserve compile-time safe diagnostics already attached to compiled checks,
- execute only current explicit `sum` aggregate typed plans,
- validate required adapter capabilities before aggregate execution,
- execute aggregate checks only when source and target relations are
  addressable from the same approved adapter execution context,
- classify scan scope and budget status before aggregate execution,
- fail closed when scan scope, budget status, or placement cannot be proven,
- compare ungrouped source and target `sum` results with supported numeric
  tolerance,
- compare grouped aggregate results without fetching unbounded group rows,
  grouped keys, grouped values, or failure details into Recon Core,
- keep group presence separate from aggregate value nullness,
- treat empty aggregate `NULL` as different from numeric zero,
- treat two present `NULL` aggregate results as equal for the current aggregate
  comparison,
- treat a group present on one side and absent on the other side as a grouped
  aggregate mismatch rather than a value-equality pass,
- fail clearly on aggregate input, aggregate result, or grouped-key physical
  type mismatches,
- fail clearly for boolean or non-numeric `sum` inputs,
- preserve exact numeric aggregate differences for supported integer and
  decimal inputs,
- report `pass` when an executed aggregate check finds no violation,
- report `fail` when an executed aggregate check finds a data violation,
- report `not_executable` when capability, placement, materialization,
  scan-budget, implemented-surface, or privacy requirements are not satisfied,
- report `error` when artifact loading, adapter lifecycle, execution, result
  shape, or diagnostic handling fails before a trustworthy check outcome
  exists,
- return in-memory results only,
- keep artifact, evidence, failure-detail, state, and sink references empty.

Milestone 7.4 must not report aggregate equivalence unless the aggregate check
actually executed through the locked same-context relation-backed path.

## Status And Reason Taxonomy

Milestone 7.4 reuses the check statuses introduced by the check-engine
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

Milestone 7.4 adds factual `pass` and `fail` outcomes only for executed
relation-backed aggregate checks.

Data-failure outcomes:

- `sum_diff` fails when the executed ungrouped aggregate difference exceeds the
  supported numeric tolerance;
- `grouped_aggregate_diff` fails when at least one grouped aggregate comparison
  differs beyond the supported numeric tolerance;
- `grouped_aggregate_diff` fails when a group is present on only one side;
- `sum_diff` and `grouped_aggregate_diff` pass only when all required current
  aggregate comparisons execute and satisfy the configured comparison rules.

Not-executable outcomes reuse existing reason concepts where possible:

- `missing_engine_capability`,
- `unsupported_execution_placement`,
- `unsupported_materialization_policy`,
- `scan_estimate_unknown`,
- `scan_estimate_unsupported`,
- `scan_budget_exceeded`,
- `unsafe_scan_preflight`,
- `bounded_local_scan_required`,
- `not_implemented_in_current_phase`,
- `unsupported_check_type`,
- `unsupported_typed_operation`.

Milestone 7.4 should use clear runtime diagnostics for:

- unsupported aggregate execution placement,
- missing or malformed aggregate capabilities,
- scan-budget or scan-safety blockers,
- unsupported aggregate typed operations,
- aggregate input type mismatch,
- aggregate result type mismatch,
- grouped aggregate key type mismatch,
- unsupported or non-numeric `sum` inputs,
- aggregate execution result-shape errors,
- sanitized adapter/runtime execution errors.

Exact enum names and diagnostic-code names may be finalized during
implementation, but their behavior must remain compatible with this prework.

## Gate Satisfaction Proof

Gate status for implementation:

- Gate 3A, aggregate metrics expansion scope: satisfied for planning only while
  Milestone 7.4 stays limited to current explicit `sum` execution. Any metric
  expansion, aggregate inference, generated aggregate suggestion, or
  `recon_core.aggregate_equivalence` work reopens the gate and blocks this
  milestone.
- Gate 4I, comparison execution placement: satisfied for planning only by
  locking the initial aggregate execution path to same-context relation-backed
  placement with no hidden Python, cross-engine, cross-adapter, materialization,
  staging, or adapter-owned fallback.
- Gate 4L, execution cost, scan budget, and query-plan safety: satisfied for
  planning only if aggregate execution uses an internal bounded local/dev
  relation-backed guard or returns `not_executable`. Public scan-budget
  settings remain future work.
- Gate 6, source/target data privacy, evidence, and failure-detail policy:
  satisfied for planning only if aggregate values, grouped keys, relation
  names, source/target identifiers, query text, rendered SQL, raw adapter
  errors, database errors, and grouped failure details remain absent from public
  output unless a later privacy policy explicitly admits a surface.
- Gate 8C, native SQL optimization and dialect validation conformance: not a
  blocker for the in-core local/dev aggregate execution phase, but production
  adapter execution compatibility remains future adapter conformance work.

Before implementation starts, the final high-risk prework must prove every gate
above through matrix rows, BDD scenarios where applicable, required tests,
source/responsibility maps, and phase-exit review requirements.

## Public Contract Impact

Affected public contract surfaces:

- aggregate metric execution,
- typed check plans,
- adapter capabilities,
- adapter execution lifecycle and current check execution,
- comparison execution placement,
- source/target data privacy and public output,
- check-engine boundary and result model,
- scan-budget and query-plan safety.

No new public contract surface should be added by Milestone 7.4 prework alone.

Milestone 7.4 must not add:

- a new typed check-plan version constant,
- a generated run-result version,
- an evidence or failure-detail schema version,
- new public YAML syntax,
- new public CLI options,
- new adapter capability names,
- new stable result artifact fields.

If implementation changes typed operation payloads, adapter capability
semantics, generated artifact shapes, public result behavior, CLI behavior, or
compatibility promises, stop and complete the compatibility review before
coding.

Changelog Decision: Not Required for this prework artifact because it documents
planned implementation scope and does not change user-visible behavior.

## Compatibility Impact

Current compatibility position:

- typed aggregate plans are draft compiled-check artifact content;
- aggregate runtime execution is planned, not implemented;
- existing typed operation names remain the current aggregate operation subset;
- current adapter execution compatibility is limited to already implemented
  row-count and bounded local/dev grain-key safety surfaces;
- aggregate execution introduces no external adapter production compatibility
  claim.

Milestone 7.4 implementation must preserve:

- Core-owned aggregate comparison semantics,
- adapter-owned mechanics and SQL rendering,
- explicit capability validation before execution,
- same-context relation-backed placement for the initial path,
- no silent fallback,
- no silent type coercion,
- no public generated result or evidence schema.

Future adapter test-kit and production adapter work must re-prove aggregate SQL
semantics before external adapters claim aggregate execution compatibility.

## Security And Privacy Impact

Aggregate execution observes source/target-derived data. Default handling must
be privacy-safe.

Milestone 7.4 must not expose through terminal output, diagnostics, logs,
generated artifacts, test snapshots, or public result surfaces:

- raw source or target rows,
- raw source or target values,
- grouped keys,
- grouped aggregate values,
- unbounded grouped result details,
- relation names,
- source or target identifiers,
- query text,
- rendered SQL,
- raw adapter errors,
- raw database errors,
- rendered profile values,
- credentials, tokens, or DSN fragments.

In-memory aggregate values and diffs may be used only as bounded,
policy-controlled execution data for the current phase. Grouped details must
remain absent or bounded summaries until future run-result, evidence, and
failure-detail policy admits controlled output.

## Affected Docs

This milestone prework adds:

```text
docs/planning/milestone-7-4-prework.md
```

Docs that must remain aligned before implementation:

- `docs/implementation/mvp-build-order.md`,
- `docs/implementation/testing-plan.md`,
- `docs/implementation/check-engine.md`,
- `docs/implementation/result-model.md`,
- `docs/compatibility/typed-check-plan.md`,
- `docs/compatibility/public-contract-inventory.md`,
- `docs/compatibility/compatibility-matrix.md`,
- `docs/compatibility/change-checklist.md`.

Docs that may need updates only if implementation changes behavior:

- `docs/framework/tolerance-policies.md`,
- `docs/implementation/errors-and-diagnostics.md`,
- `docs/compatibility/adapter-api.md`,
- `docs/compatibility/capability-catalog.md`,
- `docs/compatibility/artifact-versions.md`,
- `CHANGELOG.md`.

## Required Tests

The final Milestone 7.4 test plan must include tests for:

- ungrouped `sum_diff` pass, fail, and error outcomes,
- grouped aggregate diff pass, fail, and error outcomes,
- supported numeric tolerance behavior,
- empty aggregate result semantics,
- `NULL` aggregate versus numeric zero,
- both grouped sides empty,
- group present on one side only,
- present group with `NULL` aggregate versus missing group,
- aggregate input type mismatch,
- aggregate result type mismatch,
- grouped key type mismatch,
- boolean `sum` input rejection,
- same-type unsupported or non-numeric aggregate input rejection,
- supported large integer and decimal exactness,
- unsupported unsigned large-integer behavior unless exactness is proven,
- missing capability blockers before execution,
- unsupported placement blockers before execution,
- scan-safety and scan-budget blockers before execution,
- no adapter setup after hard scan or placement blockers,
- no hidden Python fallback,
- no unbounded grouped fetch into Core,
- sanitized adapter/runtime diagnostics,
- no raw aggregate values, grouped keys, relation names, query text, rendered
  SQL, database errors, or profile values in public output,
- absent `target/run_results.json`, evidence, report, failure-detail, state,
  and sink output.

The final dimension-expanded matrix must map each required row to a new test,
existing test, or explicit out-of-scope rationale before coding starts.

## Definition Of Done

Milestone 7.4 implementation is done only when:

- the final prework matrix, BDD scenarios, test plan, source map, and
  responsibility map are complete and current;
- every required aggregate execution case maps to test coverage or a documented
  out-of-scope rationale;
- current `sum_diff` and `grouped_aggregate_diff` checks execute only through
  the approved same-context relation-backed path;
- unsupported placement, missing capability, unsafe scan, over-budget scan, and
  unclassified scan contexts return `not_executable` rather than data failures;
- aggregate input, aggregate result, and grouped-key type mismatches fail
  clearly without silent casts;
- empty aggregate behavior preserves the `NULL` versus zero distinction;
- grouped aggregate behavior preserves group presence separately from aggregate
  value nullness;
- aggregate output follows the source/target privacy policy;
- no run-result, evidence, report, failure-detail, state, or sink artifacts are
  written;
- docs and compatibility records match the implemented behavior;
- regression-capture carryover rows applicable to aggregate execution are
  resolved, mapped to tests, deferred, or marked not applicable with rationale;
- validation commands for the implementation and docs pass.

## Phase Exit Checklist

Before leaving the implementation phase, compare the completed work against the
final Milestone 7.4 matrix and confirm:

- every in-scope aggregate behavior is implemented or explicitly still blocked;
- every required test has passed;
- every non-execution outcome is represented as `blocked`, `not_executable`, or
  `error` as appropriate;
- no unsupported aggregate metric type executes;
- no unsupported placement falls back to another engine;
- no unbounded grouped details are moved into Core memory;
- no user-facing scan-budget setting was added;
- no public YAML, CLI, generated artifact, run-result, evidence, or adapter API
  surface changed without its required compatibility review;
- no source/target values or private context leak through diagnostics or output;
- docs, compatibility docs, gates, and regression-capture records are current;
- newly discovered conformance requirements are either added to the matrix or
  recorded as blockers before follow-on implementation.

## Implementation Readiness

Implementation is not ready yet.

Next prework must add the dimension-expanded matrix, BDD workflow scenarios,
detailed test plan, implementation source map, implementation responsibility
map, and docs drift alignment before any runtime/source/test code changes.
