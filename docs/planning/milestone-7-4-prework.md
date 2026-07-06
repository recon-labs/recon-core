# Milestone 7.4 Prework

## Purpose

This is the lightweight prework artifact for Milestone 7.4: aggregate metric
execution.

Milestone 7.4 is high-risk because it touches aggregate execution, typed
operation execution, adapter capabilities, SQL rendering, execution placement,
scan and cost safety, numeric tolerance behavior, source/target privacy,
runtime diagnostics, result-model behavior, and future run/evidence
compatibility.

This artifact records the public scope and safety boundaries for the milestone,
including the dimension-expanded acceptance/conformance matrix, BDD workflow
scenarios, and detailed test plan. Implementation must not start until the
remaining high-risk prework artifacts are complete: the implementation source
map, implementation responsibility map, docs drift check, and final phase-exit
review alignment.

Split Decision: Already Split / Follow Existing Split.

## Status

Prework is in progress.

Current status:

- the Milestone 7 split already assigns aggregate metric execution to
  Milestone 7.4;
- the milestone stays limited to current compiled `sum` aggregate plans;
- research_decision: not-required;
- the matrix, BDD scenarios, and detailed test plan are defined here;
- implementation remains blocked until this prework is expanded with the source
  map, responsibility map, and docs drift alignment.

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

## Acceptance And Conformance Matrix

| Dimension | Cases | Expected Behavior | Test Coverage | Docs Or Gate Impact | Out-Of-Scope Rationale |
| --- | --- | --- | --- | --- | --- |
| Current aggregate scope | Current explicit `sum_diff`; current explicit `grouped_aggregate_diff`; unsupported metric types such as `min`, `max`, `avg`, and `count_distinct`; `recon_core.aggregate_equivalence`; inferred aggregate checks. | Only current compiled `sum` aggregate plans are executable. Unsupported metrics, aggregate inference, aggregate suggestions, and `recon_core.aggregate_equivalence` do not execute or appear as successful evidence. | New M7.4 service/check-engine tests for executable current `sum` plans and negative unsupported-metric or unsupported-check-type cases. Existing compiler metric tests continue to cover current `sum` compilation. | Gate 3A; typed operation catalog re-check; public contract inventory row `Aggregate metric execution`. | Metric catalog expansion, aggregate inference, generated suggestions, and `recon_core.aggregate_equivalence` remain future aggregate expansion work. |
| Typed-plan shape and runtime input | Valid `aggregate` plus `compare_aggregates` operations; valid `grouped_aggregate` plus `compare_grouped_aggregates` operations; malformed operation payloads; unexpected operation order; missing aggregate, column, side, or group key fields; unsupported typed operation names. | Valid current aggregate plan shapes can enter aggregate execution. Malformed aggregate typed plans are invalid artifacts or clear non-execution outcomes before adapter queries. Unsupported valid operation names remain `not_executable` with safe diagnostics. | New M7.4 artifact/runtime shape tests. Existing compiled-check loader and compiler model tests continue to protect payload validation. | Typed check-plan compatibility; check-engine boundary; `check_engine_semantics_carryover` blocker-precedence review. | Changing typed operation payload schema or adding operation names is outside M7.4 unless compatibility review reopens the plan. |
| Run boundary and compiled inputs | Missing compiled checks; empty compiled-check scope; missing compiled contract; malformed compiled contract; compiled-check to compiled-contract mismatch; parser/compiler temptation. | `recon run` consumes already compiled artifacts only, joins each executable aggregate check to matching compiled-contract metadata, and never parses authored YAML or recompiles contracts. Missing, empty, malformed, or mismatched artifacts produce runtime diagnostics or `no_checks` behavior already defined by the result model. | Existing M7.1/M7.2 artifact-loader and empty-scope tests remain applicable; new M7.4 tests cover aggregate candidates joining to compiled-contract metadata before execution. | Check-engine docs; result-model docs; public contract inventory row `Check engine boundary and result model`. | Recompilation, artifact freshness, selectors, and authored YAML parsing remain later or separate surfaces. |
| Ungrouped aggregate pass/fail/error | Source sum equals target sum; source sum differs from target sum; adapter setup failure; query execution failure; result-shape failure. | Executed ungrouped aggregate checks report `pass` only when the current comparison condition is proven, `fail` only for data differences beyond tolerance, and `error` when preparation, adapter execution, unsafe type/result shape, or diagnostic handling prevents a trustworthy result. | New ungrouped aggregate execution tests for pass, fail, adapter setup error, SQL/runtime error sanitization, and malformed result shape. | Milestone 7.4 build-order required tests; result-model status semantics. | Generated run summaries and stable generated result artifacts remain Milestone 8. |
| Numeric tolerance for current `sum` | Exact equality; zero tolerance; positive absolute tolerance pass; positive absolute tolerance fail; negative, missing, string, relative, percentage, timestamp, or string tolerance shapes when encountered before execution. | Supported numeric absolute tolerance applies only to current numeric aggregate comparisons. Unsupported or unresolved tolerance behavior must not silently execute as a different policy. | New aggregate tolerance tests for exact, zero, within-tolerance, outside-tolerance, and unsupported policy blockers when reachable at runtime. Existing policy validation tests continue to own malformed authored tolerance config. | ADR 0009; tolerance policy docs if implementation changes behavior. | Relative, percentage, timestamp, and string tolerance execution remain future policy work. |
| Ungrouped empty aggregate semantics | Both sides empty; source empty only; target empty only; all-null aggregate column on one or both sides; `NULL` versus numeric zero. | Empty aggregate `NULL` is not numeric zero. Two present `NULL` aggregate results compare equal for the current aggregate comparison. One `NULL` and one numeric zero compare different. Empty/null outcomes do not leak raw rows or values. | New ungrouped aggregate tests for both-empty pass, one-side-empty fail, all-null cases, and `NULL` versus zero. | ADR 0009; Gate 8C; result/evidence privacy boundary. | Evidence wording for empty aggregate details remains Milestone 9 or later. |
| Grouped aggregate pass/fail/error | Matching groups equal; matching groups differ; source-only group; target-only group; both grouped sides empty; adapter/runtime error; malformed grouped result shape. | Grouped aggregate checks execute through the approved adapter path and report pass/fail/error without moving unbounded grouped rows into Core. Missing or extra groups are data failures when the grouped comparison executed. Both sides empty passes with no mismatches. | New grouped aggregate execution tests for pass, mismatch, source-only group, target-only group, both-empty pass, adapter error, and malformed result shape. | Milestone 7.4 build-order required tests; ADR 0021 grouped no-unbounded-fetch rule. | Grouped failure-detail exports and high-cardinality grouped output remain future evidence/failure-detail work. |
| Group presence versus aggregate nullness | Group present on both sides with both aggregate values `NULL`; group present on one side with `NULL`; group absent on the other side; nullable grouped keys. | Group presence is distinct from aggregate value nullness. A present `NULL` aggregate can compare equal to another present `NULL`; a present group with `NULL` aggregate does not equal an absent group. Nullable grouped keys compare only under explicit null-safe grouped-key semantics and must not become inferred missing/extra rows through type or null mishandling. | New grouped aggregate tests for present-null versus present-null, present-null versus absent, nullable grouped keys, and both grouped sides empty. | ADR 0009; ADR 0021; Gate 8C SQL comparison conformance expectations. | Raw grouped keys and grouped aggregate values are not exported in M7.4. |
| Grouped no-unbounded-fetch rule | High-cardinality group set; source-only many groups; target-only many groups; grouped mismatch details; grouped-key export temptation. | Grouped aggregate comparison must not fetch unbounded group rows, grouped keys, grouped values, or detailed failure rows into Recon Core. Runtime may return only bounded status, counts, or summaries allowed by privacy policy. Unsupported bounded summary behavior blocks execution. | New grouped aggregate tests or fixtures asserting bounded result shape and no grouped key/value details in in-memory public-like output, diagnostics, logs, or generated artifacts. | Gate 4I; Gate 4L; Gate 6; ADR 0021 and ADR 0022. | Detailed grouped evidence, failure-detail files, and large-result export remain future gated work. |
| Aggregate input and result type mismatch | Source and target aggregate input type mismatch; aggregate result type mismatch; empty relations with mismatched aggregate value types; same-type unsupported input; boolean `sum` input; numeric/string and decimal/float risk cases. | Type mismatches and unsupported inputs fail clearly as execution errors or non-execution outcomes, never as passing equality and never through silent dialect casts. Boolean/non-numeric `sum` inputs are unsupported. Empty relations with type mismatches still fail clearly. | Existing DuckDB renderer semantic tests cover many type-guard cases; new M7.4 runtime tests must prove sanitized execution outcomes and no misleading pass/fail data result. | ADR 0009 no silent type coercion; Gate 8C; typed check-plan compatibility. | Cross-adapter production SQL conformance remains future adapter test-kit work. |
| Exact numeric aggregate behavior | Supported integers; large signed integers; decimals; precision-sensitive differences; unsupported unsigned large integers. | Supported exact numeric inputs preserve exact aggregate differences. Unsupported unsigned large integers or unproven exactness fail clearly instead of widening, rounding, or casting silently. | Existing DuckDB renderer tests cover exact large integer and decimal rendering behavior; new M7.4 execution tests cover runtime outcomes for supported exact numeric values and unsupported unsigned large integers. | ADR 0009; Gate 8C native SQL conformance. | Production adapter claims for exact numeric aggregate behavior remain future adapter conformance. |
| Grouped key type mismatch | Source/target grouped-key type mismatch; empty grouped relations with mismatched key types; cross-type key coalescing temptation; multi-column group keys. | Grouped key type mismatches fail clearly with sanitized Recon or adapter-level diagnostics. Renderers and runtime must not coalesce source and target grouped keys across incompatible physical types, even when no rows are present. | Existing DuckDB renderer tests cover grouped-key mismatch rendering behavior; new M7.4 runtime tests cover sanitized execution outcome and empty-relation mismatch behavior. | Gate 8C; no silent type coercion; source/target privacy gate. | Cross-adapter grouped-key conformance remains future adapter test-kit work. |
| Execution placement and no fallback | Same-context relation-backed aggregate execution; cross-adapter execution; cross-connection mismatch; query endpoints; side-local scalar comparison; third-engine comparison; materialization/staging; Python fallback. | M7.4 executes only when same-context relation-backed placement can be proven. Unsupported placement returns `not_executable` before execution and never falls back to Python, staging, materialization, side-local comparison, or adapter-owned strategy changes. | New service/check-engine placement tests for supported same-context path, cross-context blockers, query endpoint blockers, materialization blockers, and no adapter query/Python fallback after hard blockers. | Gate 4I; ADR 0021; compatibility matrix row `Comparison execution placement`. | Side-local scalar aggregate comparison, materialization, third-engine comparison, and query endpoints remain future gated work. |
| Adapter capability and lifecycle preflight | Missing `aggregate` capability; missing `grouped_aggregate` capability; missing `cte_support`; unknown, unsupported, not implemented, versioned, malformed, or incompatible support states; adapter setup failure; cleanup after execution. | Core validates adapter API and required capabilities before aggregate execution. Missing or malformed capabilities produce `not_executable` before query execution. Adapter setup or lifecycle failures produce sanitized errors, and opened adapters are closed. | New service tests for aggregate and grouped capability blockers before connect, malformed support states, setup failure, cleanup, and distinct source/target connection diagnostics when applicable. | ADR 0013; ADR 0020; adapter API compatibility; regression capture carryover for adapter capability preflight. | New capability names or external adapter API changes are out of scope. |
| Scan-budget and query-plan safety | Bounded local/dev relation-backed allowed path; project-local database file; file-size cap; retained local DuckDB sidecars; views; external relations; missing metadata; production estimate present before user settings; unknown, unavailable, unsupported, malformed, unsafe, or over-budget estimates. | Aggregate execution may run only when scan scope and budget status are explicit. The initial path uses an internal bounded local/dev relation-backed guard equivalent to the key-safety guard, or returns `not_executable`. Hard blockers happen before adapter setup or source/target scans when possible. | New aggregate scan-safety tests mirroring the current key-safety guard: allowed bounded local/dev, sidecar blocked, view/external blocked, missing metadata blocked, production estimate-present blocked before M8 settings, unknown/unsupported/unsafe/over-budget `not_executable`, no scan after hard block. | Gate 4L; ADR 0021; ADR 0022; compatibility matrix row `Scan-budget and query-plan safety`; regression capture rows for bounded scan public wording and scan guard behavior. | Public scan-budget settings, production within-budget execution, and adapter scan-estimation compatibility remain future runner/results and adapter test-kit work. |
| Diagnostics and source/target privacy | Pass, fail, error, not executable, adapter setup failure, database error, raw adapter/runtime exception text, relation names, aggregate values, grouped keys, query text, rendered SQL, rendered profile values. | Public output, diagnostics, logs, and test snapshots stay sanitized. Aggregate values, grouped keys, relation names, source/target identifiers, query text, rendered SQL, database errors, and rendered profile values do not leak unless a later policy admits that surface. | New privacy tests for aggregate pass/fail/error/not-executable paths and raw exception sanitization. Existing profile/diagnostic redaction tests remain carryover protection for profile secrets. | Gate 6; ADR 0022; diagnostics privacy carryover; public contract inventory row `Source/target data privacy and public output`. | Evidence/report/failure-detail redaction and controlled value export remain later phases. |
| Public output and generated artifacts | Terminal output; logs; `target/run_results.json`; evidence reports; failure details; state; result/evidence sinks; compiled SQL writes from `recon run`. | M7.4 returns in-memory results only and does not write generated run-result, evidence, report, failure-detail, state, or sink artifacts. `recon run` does not write compiled SQL artifacts. Artifact and sink refs remain empty. | New negative tests for absent `target/run_results.json`, report/evidence/failure-detail/state/sink outputs, empty artifact refs, empty sink refs, and no `recon run` compiled SQL publication. | ADR 0022; generated artifact lifecycle; result-model boundary; M8/M9 ownership. | Durable run results belong to Milestone 8; evidence and failure details belong to Milestone 9. |
| Result aggregation and mixed outcomes | Mixed pass/fail aggregate checks; aggregate check plus not-executable check; aggregate check plus error; empty check scope; executed false for blockers. | Run and contract aggregate status precedence remains `error > fail > blocked > not_executable > warn > pass > skipped`; `no_checks` is not pass. Non-executed checks use `executed=false`, reason codes, safe messages, and no source/target values or artifact refs. | Existing check-engine aggregation tests remain applicable; new M7.4 tests cover mixed aggregate execution results and aggregate-specific not-executable/error interactions. | Result-model docs; check-engine semantics carryover. | Stable generated result schema remains future runner/results work. |
| Future adapter/test-kit and carryover coverage | Pending carryover rows for check-engine semantics, adapter runtime scan policy, diagnostics privacy, parser/compiler contract behavior, and adapter test-kit SQL comparison conformance. | M7.4 implementation must review applicable pending rows and either map them to current tests, migrate them to future shared suites, defer them with rationale, or mark them not applicable. M7.4 docs-only Step 3 does not change capture row status. | `python3 scripts/check_regression_capture.py` during prework validation; implementation must add/update test mappings where current M7.4 behavior covers a carryover row. | `docs/compatibility/regression-capture/index.yml`; compatibility matrix row `Regression capture carryover gates`. | Adapter test-kit, production adapter packages, and broad aggregate metrics expansion remain later gated surfaces. |

## BDD Workflow Scenarios

### Ungrouped aggregate check executes safely

Given a compiled contract and compiled check artifact contain a current
`sum_diff` check for relation-backed source and target tables in the same
approved execution context,
when `recon run` evaluates the check and the internal scan guard allows the
relations,
then Recon validates capabilities before execution, executes the aggregate
through the approved adapter path, and returns an in-memory `pass` or `fail`
result without writing run-result or evidence artifacts.

### Grouped aggregate check avoids unbounded detail movement

Given a compiled `grouped_aggregate_diff` check can produce multiple source and
target groups,
when `recon run` evaluates the grouped aggregate check,
then the grouped comparison runs through approved same-context adapter
placement and returns only bounded status or summary data allowed by policy,
without exposing grouped keys, grouped aggregate values, or failure details in
public output.

### Empty aggregate semantics are explicit

Given a current `sum_diff` or `grouped_aggregate_diff` check observes empty or
all-null aggregate inputs,
when Recon compares the aggregate results,
then two present `NULL` aggregate results compare equal for the current
aggregate comparison, `NULL` does not equal numeric zero, and a present grouped
aggregate row does not equal an absent group.

### Type mismatches do not become misleading evidence

Given aggregate input types, aggregate result types, or grouped key types are
incompatible,
when Recon prepares or evaluates the aggregate check,
then it reports a clear sanitized error or non-execution outcome before
trustworthy equality is claimed, and it does not silently coerce values or emit
raw database errors.

### Placement, capability, or scan blockers fail closed

Given an aggregate check cannot prove same-context relation-backed placement,
required adapter capabilities, or bounded scan safety,
when `recon run` evaluates the check,
then the check returns `not_executable` with a structured reason and safe
diagnostics before source/target query execution, without opening adapters after
hard scan blockers and without falling back to Python or another engine.

### Public output stays privacy-safe

Given an aggregate check passes, fails, errors, or is not executable,
when Recon renders service diagnostics, logs, or test-observable public output,
then aggregate values, grouped keys, relation names, source/target identifiers,
query text, rendered SQL, rendered profile values, raw adapter errors, and raw
database errors are absent unless a later privacy policy explicitly admits that
surface.

## Detailed Test Plan

Write implementation tests before runtime code changes. The exact file map is
owned by the source/responsibility-map step, but the implementation test suite
must cover these groups.

1. Aggregate candidate admission and typed-plan shape:
   - valid current `sum_diff` and `grouped_aggregate_diff` plan admission,
   - malformed aggregate operation payloads,
   - unsupported known-later or unknown typed operations,
   - no authored YAML parsing or recompilation during `recon run`,
   - compiled-check to compiled-contract joins before profile or adapter work.

2. Ungrouped aggregate execution:
   - pass, fail, and error outcomes,
   - exact equality and zero tolerance,
   - within-tolerance and outside-tolerance numeric differences,
   - both-empty and all-null aggregate inputs,
   - source-empty-only and target-empty-only cases,
   - `NULL` versus zero.

3. Grouped aggregate execution:
   - pass, fail, and error outcomes,
   - matching groups with equal aggregate values,
   - matching groups with aggregate differences,
   - source-only and target-only groups,
   - nullable grouped keys,
   - both grouped sides empty,
   - present `NULL` aggregate group versus absent group,
   - no unbounded grouped details returned to Core.

4. Type and exactness behavior:
   - aggregate input type mismatch,
   - aggregate result type mismatch,
   - grouped key type mismatch,
   - type mismatches on empty relations,
   - boolean `sum` input rejection,
   - same-type unsupported or non-numeric input rejection,
   - supported large integer exactness,
   - supported decimal exactness,
   - unsupported unsigned large-integer behavior unless exactness is proven.

5. Placement and capability blockers:
   - supported same-context relation-backed path,
   - cross-connection or cross-adapter placement blocked,
   - query endpoint input blocked,
   - materialization, staging, and third-engine requests blocked,
   - no Python fallback,
   - missing `aggregate`, `grouped_aggregate`, or `cte_support` capability,
   - unknown, unsupported, not implemented, versioned, malformed, or
     incompatible capability states,
   - adapter setup failure and cleanup behavior.

6. Scan-budget and query-plan safety:
   - bounded local/dev relation-backed allowed path,
   - project-local file and size-cap classification,
   - retained sidecar files blocked,
   - views and externally backed relations blocked,
   - missing or failed metadata proof blocked,
   - production estimate-present path blocked before user-facing settings,
   - unknown, unavailable, unsupported, malformed, unsafe, or over-budget scan
     preflight returns `not_executable`,
   - hard scan blockers prevent adapter setup or query execution when possible.

7. Diagnostics, privacy, and generated output:
   - sanitized adapter setup diagnostics,
   - sanitized SQL/runtime/database errors,
   - safe messages for pass, fail, error, and not-executable paths,
   - no aggregate values, grouped keys, relation names, source/target
     identifiers, query text, rendered SQL, rendered profile values, raw
     adapter errors, or raw database errors in public output,
   - absent `target/run_results.json`,
   - absent reports, evidence, failure details, state, and sink output,
   - empty artifact and sink references for M7.4 execution results.

8. Result-model aggregation and carryover:
   - mixed aggregate pass/fail/error/not-executable outcomes preserve status
     precedence,
   - non-executed aggregate checks use `executed=false` and structured reason
     codes,
   - applicable regression-capture carryover rows are reviewed and mapped,
     migrated, deferred, or marked not applicable before implementation is
     called complete.

## Regression Capture Carryover Review

Step 3 does not add or update regression-capture rows because it changes only
planning documentation and does not fix a bug or add executable behavior.

regression_capture_decision: not-required.

Carryover gates to re-check during implementation:

- `check_engine_semantics_carryover` is primary for aggregate metric execution.
  M7.4 implementation must review pending check-engine rows for blocker
  precedence, typed-plan shape, execution-result semantics, and prerequisite
  behavior. Rows that become covered by aggregate execution tests must be
  updated or mapped according to the regression-capture rules.
- `adapter_testkit_regression_carryover` remains future adapter/test-kit work,
  but M7.4 runtime scan-safety and capability tests must not contradict those
  pending scan and adapter-runtime rows.
- `diagnostics_privacy_carryover` remains primary for runner/results and later
  output surfaces, but M7.4 aggregate diagnostics and test snapshots must follow
  the same privacy expectations.
- `parser_compiler_contract_carryover` remains future aggregate metrics
  expansion or parser/compiler contract work unless M7.4 changes typed-plan
  schema, YAML behavior, compiler validation, or scan-policy public contracts.

## Definition Of Done

Milestone 7.4 implementation is done only when:

- the matrix, BDD scenarios, and detailed test plan remain complete and current;
- the source map and responsibility map are complete and current;
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

Next prework must add the implementation source map, implementation
responsibility map, and docs drift alignment before any runtime/source/test code
changes.
