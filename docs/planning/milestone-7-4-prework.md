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
scenarios, detailed test plan, implementation source map, and responsibility
map, docs drift alignment, and final phase-exit validation. Implementation may
start only in a later coding session that rehydrates the required context,
confirms no new drift, and follows this prework.

Split Decision: Already Split / Follow Existing Split.

## Initial design checkpoint

The aggregate execution scope and numeric policy decisions are locked in this
prework and ADRs 0009 and 0021. Representative native engine-version
verification is complete for the tested cases. Runtime implementation
requires explicit approval of the test-first plan and a fresh drift check.

- The existing Milestone 7 split assigns explicit aggregate execution to
  Milestone 7.4; no further split is required.
- Only current compiled explicit `sum` checks are admitted.
- research_decision: completed for numeric domain and bounded comparison
  design and representative engine-version verification. All 86 current
  native probes passed on DuckDB 1.4.5 and 2.0.1; 76 selected ordinary-domain
  and availability probes passed on 1.0.0 and 1.3.2. Existing semantic
  coverage passed on all four pins.
- Strict floating-point tolerance, unresolved applicable named-policy blocking,
  private bounded runtime rendering, and capability preservation are locked.
- The acceptance matrix, BDD scenarios, test plan and responsibility map
  include these requirements; no aggregate runtime or implementation tests
  have been added in this prework update.
- The representative version review established the native operation
  boundaries below without changing the dependency floor or existing
  capability. Do not remove an existing supported type or raise the floor
  without explicit scope approval. Native proof is not runtime integration
  proof.

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

### Numeric and bounded result contracts

Use the existing compiled check `tolerance` field and compiled contract
`policies.tolerance_policy` metadata. The compiled contract loader must
preserve the named reference as private runtime metadata without changing
exported loaded-contract or execution-context dataclass shapes, validating its
existing shape without adding resource resolution. A valid explicit metric
tolerance overrides an applicable named policy. Otherwise a non-null
unresolved named policy blocks execution with a safe reason. If neither
applies, absent or null optional metric tolerance means zero. Malformed
tolerance or policy metadata is an artifact/validation error. Check admission
must reject these conditions before profile/adapter setup or data queries.
Do not parse authored YAML or recompile at run time. Share the existing
canonical numeric policy interpretation rather than duplicate divergent
compiler/runtime validation.

Exact integer and decimal arithmetic uses a context-independent exact
representation. Finite FLOAT and DOUBLE sums and signed differences use
the proven native arithmetic domain; the native computed magnitude and
compiled floating-point tolerance use their canonical shortest round-trip
decimal representation. Do not decimal-subtract independently converted
floating-point operands. Compare magnitude less than or equal to threshold;
zero means exact represented equality, including signed zero. No implicit
epsilon, relative tolerance, or rounding. Invalid, non-finite, or
unrepresentable results error without exposing values. Existing physical
type guards, supported numeric types and unsupported boolean, nonnumeric
and UHUGEINT boundaries are preserved. Native BIGNUM arithmetic and typed
transport passed on the tested 2.0.1 fixtures. Verify actual operation
availability and lossless transport on representative earlier versions.
Arbitrary numeric strings are not numeric evidence. Typed arbitrary-size
integer conversion must be exact beyond Python's ordinary integer-string
digit limit, independent of decimal context, without changing global
settings. A failing proof blocks readiness and triggers capability-
preserving review.

The private ungrouped result is one row with the source aggregate, target
aggregate and signed difference, with exact column and envelope validation.
Both-null aggregates with null difference pass; one null and one finite
value with null difference fail. Non-finite values, inconsistent null/diff
shapes or untrustworthy arithmetic error. Exact results validate signed
subtraction exactly; floating results validate it in the proven native
domain. This result is not public output.

The private grouped runtime result is exactly one row with the following
fields in this order:

| Field | Required representation |
| --- | --- |
| total_group_count | Nonnegative integer, complete group union count |
| source_only_group_count | Nonnegative integer |
| target_only_group_count | Nonnegative integer |
| both_null_group_count | Nonnegative integer |
| null_mismatch_group_count | Nonnegative integer, both groups present |
| valid_numeric_pair_count | Nonnegative integer, both groups present and valid finite values |
| invalid_numeric_count | Nonnegative integer, any present invalid/non-finite aggregate or invalid difference |
| min_signed_diff | Finite signed difference in the proven numeric domain, or null |
| max_signed_diff | Finite signed difference in the proven numeric domain, or null |

Classify invalid numeric outcomes first, then one-sided presence, then
both-null, one-null, and valid numeric pairs. Each group belongs to exactly
one category. Category counts sum to the total; booleans are not counts.
Extrema are both null exactly when there are no valid numeric pairs.
Otherwise both are finite, in the same proven domain, ordered min <= max,
and consistent with the numeric count (equal when there is only one pair).
Validate exact columns, row width, one-row envelope and count consistency;
reject unexpected/duplicate columns, missing/multiple rows, malformed values,
and contradictory extrema. The adapter must prove complete aggregation
across the group union, with independent source and target presence flags,
null-safe composite-key matching, and preflight physical type checks even
on empty relations. No detail-row limit, raw group fetch, Core SQL rewriting,
or fallback may substitute for a complete summary.

Core errors on malformed summary or any invalid numeric group before data
failure classification. Otherwise any one-sided group or null mismatch
fails regardless of tolerance. With no such mismatch, all-null or empty
groups pass; numeric pairs pass only when the larger absolute magnitude of
the signed extrema is within tolerance. Compute absolute magnitude safely
in Core, including the most negative signed integer, without adapter-side
absolute-value overflow. Only status and safe diagnostics reach public
results; all summary counts and extrema remain transient private data.
Native SUM and subtraction remain adapter mechanics. The bounded summary
does not waive the existing scan guard.

Preserve existing compile renderer output and tests. Use a narrow private
runtime rendering collaborator with an explicit bounded contract, supplied
by the existing lazy runtime renderer factory. Share SQL construction and
type guards with compile rendering. The private typed execution path uses
the already-open adapter connection and shared sanitized error handling;
preserve logical result type evidence before numeric normalization. Do not
infer a domain from raw strings or a generic DB-API type category. When a
private final query expects one row, read at most two rows to verify the
envelope; never fetch an unbounded detail result. The SQL must summarize
the full union without truncating comparison coverage. Do not change public `SqlRenderer`,
`BaseAdapter`, capability names, typed operation fields, artifact/API
versions, or public exports. Missing or unproven bounded rendering blocks
before aggregate queries, never falls back to detail rendering.

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
- Gate 3D, tolerance/null/normalization: ADR 0009 locks the approved numeric
  domain, inclusive threshold, and unresolved applicable named-policy rules.
  Representative native numeric-domain and availability feasibility is
  proven by the isolated probes; typed runtime transport and policy-admission
  integration remain required implementation tests.
- Gates 4B and 4C, adapter API and typed operations: preserve current compile
  renderer behavior, existing public interfaces and emitted payloads; prove
  the explicit private bounded runtime collaborator before execution.
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
- Gate 8C, native SQL optimization and dialect validation conformance:
  representative local numeric-domain proof is required before implementation
  readiness; production adapter and shared test-kit conformance remain
  future work.

Before implementation starts, the final high-risk prework must prove every gate
above through matrix rows, BDD scenarios where applicable, required tests,
source/responsibility maps, and phase-exit review requirements. Design locks
are not implementation proof. Representative native verification is complete;
actual runtime behavior must be proven during implementation.

### Representative engine-version proof

Preserve the declared `duckdb>=1.0` package dependency. Verify Python 3.11
with pinned DuckDB 1.0.0 (declared floor), 1.3.2 (earlier arbitrary-size
integer operation availability), 1.4.5 (patched 1.4 series), and 2.0.1
(previously verified engine). The existing mandatory semantic jobs on
Python 3.11, 3.12 and 3.13 retain full coverage with the resolved dependency.

The pinned lane runs the existing semantic suite and the numeric probes
separately, propagating either failure. Older versions explicitly select
ordinary numeric probes and an arbitrary-size operation-availability
assertion rather than execute modern BIGNUM-only fixtures against an
unavailable operation. This is not permission to drop existing supported
behavior or silently skip required proof. Verify actual native logical
types, exact SUM/difference availability, and lossless transport before
admitting the operation. A missing native exact operation is not a
successful comparison; do not substitute a floating-point cast. Preserve
other existing supported operations on those engines. Any necessary
dependency-floor or capability reduction requires explicit compatibility
review and approval.

The numeric tests are in
`tests/adapters/test_duckdb_aggregate_numeric_domains.py`.
The pinned versions are representative points, not proof of every version
within the dependency range. The verification completed successfully:

| DuckDB | Existing semantic cases | Native numeric cases | Arbitrary-size SUM and difference |
| --- | --- | --- | --- |
| 1.0.0 | 476 passed | 76 passed; 10 BIGNUM cases deselected | VARINT input unavailable |
| 1.3.2 | 476 passed | 76 passed; 10 BIGNUM cases deselected | VARINT binds to DOUBLE, not exact |
| 1.4.5 | 476 passed | 86 passed | BIGNUM exact native domain |
| 2.0.1 | 476 passed | 86 passed | BIGNUM exact native domain |

Both modern pins passed the beyond-5000-digit, cancellation and configured
multi-thread cases. The mandatory three-Python-version semantic jobs passed
562 cases each. The initial 1.0.0 baseline failures arose in tuple-batch test
fixture setup; list batches preserved the fixture values and assertions,
and the corrected baseline passed. The existing compile renderer contract
is unchanged. Do not infer an exact domain merely from matching physical
inputs or matching result types: the 1.3.2 binder evidence demonstrates
why actual logical type evidence is required. Runtime integration tests
must prove safe admission, typed transport and diagnostic behavior.

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
- no public generated result or evidence schema,
- existing compile-time grouped detail rendering and public adapter interfaces,
- the existing supported numeric input boundary, without lossy casts or
  silent capability reduction.

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
- private aggregate summary counts and extrema,
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
- `docs/compatibility/change-checklist.md`,
- `docs/decisions/adr-0009-tolerance-normalization-and-null-equivalence.md`,
- `docs/decisions/adr-0021-execution-placement-and-comparison-engine-strategy.md`,
- `docs/framework/tolerance-policies.md`,
- `docs/implementation/tolerance-and-normalization-engine.md`,
- `docs/compatibility/adapter-api.md`.

Docs that may need updates only if implementation changes behavior:

- `docs/implementation/errors-and-diagnostics.md`,
- `docs/compatibility/capability-catalog.md`,
- `docs/compatibility/artifact-versions.md`,
- `CHANGELOG.md`.

## Required Tests

The final Milestone 7.4 test plan must include tests for:

- ungrouped `sum_diff` pass, fail, and error outcomes,
- grouped aggregate diff pass, fail, and error outcomes,
- supported numeric tolerance behavior, including strict inclusive boundaries,
  invalid policies, unresolved named policy and explicit override,
- context-independent exact arithmetic, finite native floating-point result
  consistency, signed zero, non-finite values and overflow,
- representative DuckDB version availability and native type evidence,
  exact BIGNUM transport beyond 4300 digits, cancellation and multi-thread
  aggregation, and safe missing-native-operation behavior,
- fixed-size grouped summary partition, extrema and malformed result validation,
- preservation of compile detail rendering and missing private runtime renderer
  blockers,
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
| Numeric tolerance for current `sum` | Exact equality; zero tolerance; positive absolute tolerance pass; positive absolute tolerance fail; inclusive equality; absent/null optional metric tolerance; shorthand/object; negative, bool, string, non-finite, missing object value, unknown fields, relative, percentage or timestamp policy; unresolved named policy; explicit override. | Supported numeric absolute tolerance applies only to current numeric aggregate comparisons. Zero default applies only without an applicable unresolved policy. A valid metric override wins; otherwise unresolved applicable policy blocks. Invalid shapes error before setup/query. No implicit tolerance. | Aggregate helper, compiled-contract loader, and service admission tests for all listed cases. Existing policy validation tests continue to own malformed authored tolerance config. | ADR 0009; tolerance policy docs if implementation changes behavior. | Relative, percentage, timestamp, and string tolerance execution remain future policy work. |
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
| Future adapter/test-kit and carryover coverage | Pending carryover rows for check-engine semantics, adapter runtime scan policy, diagnostics privacy, parser/compiler contract behavior, and adapter test-kit SQL comparison conformance. | M7.4 implementation must review applicable pending rows and either map them to current tests, migrate them to future shared suites, defer them with rationale, or mark them not applicable. Docs-only prework updates do not change capture row status. | `python3 scripts/check_regression_capture.py` during prework validation; implementation must add/update test mappings where current M7.4 behavior covers a carryover row. | `docs/compatibility/regression-capture/index.yml`; compatibility matrix row `Regression capture carryover gates`. | Adapter test-kit, production adapter packages, and broad aggregate metrics expansion remain later gated surfaces. |
| Exact numeric domain and transport | Each existing integer/unsigned/decimal/BIGNUM input; values beyond 2^53; high width/scale; signed extrema; sum and subtraction overflow; malformed driver values; context precision. | Exact arithmetic and threshold comparison, no lossy cast; prove actual result domain and transport; unrepresentable or untrustworthy arithmetic errors. Capability-preserving review if BIGNUM or another supported type cannot be proven. | Aggregate helper unit tests; actual DuckDB renderer/service parameterized tests; numeric prework experiments. | ADR 0009; Gates 3D, 4B, 8C. | No new type allowlist or production compatibility claim. |
| Native floating-point domain | FLOAT and DOUBLE; valid 0.30000000000000004 minus 0.2; positive/negative differences; zero and signed zero; exact/adjacent tolerance; tiny and large finite values; sum/subtraction overflow; NaN and both infinities. | Native subtraction consistency, canonical computed magnitude, strict inclusive threshold; no epsilon or independent decimal operand subtraction. Non-finite/invalid/overflow results error before data mismatch. Grouped and ungrouped agree. | Aggregate helper and real DuckDB renderer/service tests, including historical tuple and boundary variants; numeric prework experiments. | ADR 0009; Gates 3D and 8C. | No relative tolerance or deterministic exact-decimal SUM claim for floating types. |
| Bounded grouped summary contract | Empty, both-null, null mismatch, one-sided, invalid numeric, finite numeric groups; nullable composite keys; high cardinality; zero/multiple rows, duplicate/extra/missing columns, invalid counts, partition mismatch, null/reversed/non-finite extrema, single-pair contradictions. | One complete fixed-size row; exclusive partition and valid extrema; error before data failure; no raw group transfer, truncation, or output of private summary values. | Aggregate helper shape tests, private runtime renderer semantic tests, actual DuckDB service and privacy tests. | ADR 0021 and 0022; Gates 4I, 4L, 6, 8C. | No detail export or hidden fallback. |
| Compile and runtime renderer separation | Existing compile/direct detail output; bounded runtime collaborator; missing/malformed/mismatched renderer; preflight guard order and step capabilities; lazy imports. | Preserve existing compile contract and proof. Runtime only uses explicit bounded renderer; unavailable or unproven contract blocks before aggregate queries; no public API or typed-plan change. | Existing compile and renderer tests; new runtime renderer tests; lifecycle and import boundary tests. | Gates 4B, 4C, 4I, 8C; adapter API compatibility. | No external adapter execution contract or new public interface. |
| Representative engine versions | Declared floor, pre-BIGNUM native overload, patched 1.4 series, current engine; logical type metadata; exact/absent/lossy native operation. | Preserve dependency floor and existing capabilities. Verify ordinary numeric behavior and explicit operation availability; no lossy fallback or blanket version rejection. | Pinned CI lane and native numeric probes; runtime adapter admission tests. | Gates 3D, 4B, 8C. | Representative evidence, not all-version or production compatibility claim. |
| Private typed transport and metadata | Native type evidence, generic driver type category, typed arbitrary-size integer beyond 4300 digits, low decimal context, zero/multiple rows, existing public loader/context shapes. | Normalize exact values at private adapter boundary, retain type evidence, read at most two final rows, load compiled policy metadata once without public shape change; no global setting changes. | Native probes, adapter private transport tests, artifact loader and import/contract compatibility tests. | ADR 0009 and 0021; Gates 3D, 4B, 4I. | Public QueryResult, BaseAdapter, SqlRenderer and exported dataclass shapes unchanged. |

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

### Numeric comparison preserves the configured tolerance

Given current compiled sum checks with exact or floating-point values and
an explicit valid metric tolerance, when allowed runtime execution computes
native sums and differences, then Core validates the domain and reports pass
only at or below the configured threshold without hidden rounding. A valid
native floating difference is not an invalid result merely because exact
decimal subtraction of independently converted operands differs.

### Unresolved named tolerance blocks safely

Given compiled contract metadata references an unresolved named tolerance
policy, when no valid explicit metric override exists, then the aggregate
check is not executable before adapter setup or data queries. A valid
explicit override may execute; an invalid override errors instead of
falling back.

### Bounded runtime rendering preserves compile behavior

Given many nullable or composite groups, when an admitted grouped aggregate
check executes, then the private renderer returns one complete summary row,
presence is independent of nullness, and Core applies the tolerance.
Existing compile rendering still returns the documented detail shape.
If the bounded path is unavailable, no detail query executes.

### Invalid arithmetic cannot look like a data violation

Given any non-finite aggregate, unrepresentable arithmetic, or contradictory
summary, when Recon evaluates the result, then it returns a sanitized error
instead of pass or an ordinary data mismatch, even if another group differs.

### Native version availability and private transport remain explicit

Given an installed allowed DuckDB version, when an aggregate comparison is
admitted, then the actual native operation and exact or approximate domain
must be proven; unavailable exact operations cannot produce a successful
comparison. Given a driver result with logical type evidence and a large
exact integer, private transport preserves it without losing digits,
changing public interfaces or changing process-wide conversion settings.
A malformed or unbounded final envelope errors safely.

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
   - inclusive tolerance, adjacent threshold boundaries, strict zero, signed
     zero, shorthand/object parity, invalid shapes and unresolved named policy,
   - native float difference validation and malformed scalar results,
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
   - no unbounded grouped details returned to Core,
   - one-row summary schema, category partition, signed extrema and error
     precedence; high-cardinality complete comparison,
   - missing or invalid bounded renderer blocks before data queries; existing
     compile renderer behavior and SQL proof remain unchanged.

4. Type and exactness behavior:
   - aggregate input type mismatch,
   - aggregate result type mismatch,
   - grouped key type mismatch,
   - type mismatches on empty relations,
   - boolean `sum` input rejection,
   - same-type unsupported or non-numeric input rejection,
   - supported large integer exactness,
   - supported decimal exactness,
   - unsupported unsigned large-integer behavior unless exactness is proven,
   - exact high-width decimal and signed integer arithmetic independent of
     decimal context, including overflow and signed minimum magnitude,
   - representative version availability and logical type evidence,
   - current BIGNUM input/result/difference/extrema, transport beyond the
     ordinary Python digit limit, exact cancellation and multi-thread SUM,
   - private final result fetch at most two rows and public execute unchanged,
   - FLOAT/DOUBLE result domain, native subtraction, finite/subnormal/large
     values, non-finite operands or differences, and overflow,
   - grouped and ungrouped numeric-domain parity.

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

## Implementation Source Map

These rows constrain later implementation. A source-map row is not permission
for one module to absorb another boundary's work. If implementation discovers a
needed source surface outside this map, stop and update this prework before
coding that surface.

| Surface | Files | Allowed Milestone 7.4 implementation changes | Required tests | Explicitly forbidden in Milestone 7.4 |
| --- | --- | --- | --- | --- |
| Compiler aggregate plan source | `src/recon_core/compiler/metrics.py` | Only fix a discovered mismatch between the existing current `sum_diff` or `grouped_aggregate_diff` typed-plan shape and this prework. Keep the current `sum` metric catalog and current operation names. | `tests/compiler/test_metrics.py`, `tests/compiler/test_compile.py` | New metric types, new authored YAML syntax, inferred aggregate checks, source/target column guessing, new typed operation names, or compiler-owned runtime comparison semantics. |
| Run-service runtime admission and dependencies | `src/recon_core/services/run.py` | Admit only current compiled aggregate checks after compiled-check to compiled-contract joining, relation-backed same-context validation, runtime capability classification, and scan/cost safety classification. Add aggregate required-capability mapping equivalent to `aggregate` plus `cte_support` for ungrouped checks and `grouped_aggregate` plus `cte_support` for grouped checks. Open adapters only for admitted checks that are not hard-blocked. | `tests/services/test_run_service.py`, `tests/services/test_run_service_adapter_lifecycle.py`, `tests/services/test_run_service_duckdb_execution.py`, `tests/services/_run_service_fixtures.py` | YAML parsing, recompilation, aggregate pass/fail calculation, SQL rendering, raw row or grouped-result fetching, generated artifact writing, evidence/report/failure-detail output, concrete adapter imports, or adapter setup after a hard scan blocker when avoidable. |
| Runtime execution router | `src/recon_core/check_engine/runtime.py` | Add aggregate routing only after dispatcher classification and existing hard-block checks. Route valid current aggregate plans to the aggregate execution helper and preserve `not_executable` blockers for missing capabilities, unsupported placement, malformed plans, or unsafe scan contexts. | `tests/check_engine/test_engine.py`, `tests/check_engine/test_execution_boundaries.py`, new aggregate runtime tests | Profile loading, adapter lifecycle, scan probing, SQL semantics, tolerance math, result privacy policy, broad orchestration changes, or embedding aggregate family logic directly in `CheckEngine.run()`. |
| Aggregate execution helper | New `src/recon_core/check_engine/aggregate.py` | Own aggregate-family plan-shape validation, relation/query-endpoint rejection, renderer invocation, adapter query invocation, result-row shape validation, `sum` empty-result semantics, numeric absolute tolerance comparison, grouped pass/fail summary classification, and sanitized aggregate execution diagnostics. Re-export from `src/recon_core/check_engine/__init__.py` only if following the existing compatibility convenience pattern and updating import-surface tests. | New `tests/check_engine/test_aggregate_execution.py`, `tests/compatibility/test_python_package_exports.py` if exported | Public YAML behavior, compiler behavior, adapter capability declaration, dialect SQL generation, unbounded grouped details in Core memory, public grouped-key or value details, artifact references, sink references, evidence output, or concrete adapter imports. |
| Shared execution support and scan policy | `src/recon_core/check_engine/execution_support.py`, `src/recon_core/check_engine/scan_budget.py` | Reuse existing diagnostic, relation, reserved-metadata, materialization-policy, strict-result, and connection-context helpers. Generalize scan-budget wording only if aggregate diagnostics cannot otherwise stay accurate; any generalized helper must preserve key-safety behavior. | `tests/check_engine/test_key_safety_execution.py`, new aggregate execution tests, `tests/check_engine/test_execution_boundaries.py` | Moving aggregate semantics into generic helpers, duplicating divergent scan policy, emitting key-safety-specific messages for aggregate blockers, exposing user-facing scan-budget settings, or weakening existing key-safety guards. |
| Check-engine orchestration and result aggregation | `src/recon_core/check_engine/engine.py`, `src/recon_core/check_engine/models.py` | No broad change expected. Preserve current status taxonomy, prerequisite blocking, dispatcher ordering, runtime-router boundary, and result aggregation semantics. | `tests/check_engine/test_engine.py`, `tests/check_engine/test_models.py`, `tests/check_engine/test_aggregation.py` | New statuses, generated run-result schema, direct aggregate execution inside the engine loop, changed status precedence without compatibility review, or artifact/sink fields populated for this phase. |
| DuckDB aggregate SQL rendering | `src/recon_core/adapters/duckdb/renderer_operations.py`, `src/recon_core/adapters/duckdb/renderer.py`, `src/recon_core/adapters/duckdb/renderer_sql.py` | Render dialect SQL and type guards for existing aggregate operations only. Preserve compile detail rendering. Share SQL/type guard builders with the private runtime renderer; build one complete grouped summary query and prove numeric domain and exact transport. | `tests/adapters/test_duckdb_sql_renderer.py`, new `tests/adapters/test_duckdb_aggregate_runtime_renderer.py` | Pass/fail decisions, tolerance math, hidden casts, Python fallback, adapter-owned reconciliation semantics, new capabilities, new operations, query endpoint execution, materialization/staging, or public output/privacy decisions. |
| Adapter API and capability boundary | `src/recon_core/adapters/`, `src/recon_core/compiler/models.py` only if a compiled capability-shape bug is discovered | Preserve current capability names and support-state validation. M7.4 should consume existing `aggregate`, `grouped_aggregate`, and `cte_support` mechanics rather than inventing adapter API surface. | `tests/adapters/test_capabilities.py`, `tests/services/test_run_service_adapter_lifecycle.py`, compatibility import/export tests if touched | New adapter capability names, adapter API version changes, external adapter compatibility claims, shared adapter test-kit claims, or narrowing existing pre-alpha import aliases without compatibility review. |
| Public docs and compatibility records | `docs/planning/milestone-7-4-prework.md`, `docs/implementation/mvp-build-order.md`, `docs/implementation/testing-plan.md`, `docs/compatibility/*` | Update only when implementation discovers behavior drift or a compatibility-impacting decision that must be recorded before coding continues. Public docs must describe Recon-native decisions, not research attribution. | Docs drift check, `python3 scripts/check_regression_capture.py`, `python3 scripts/check_regression_capture_decisions.py --base-ref origin/main` during branch-wide/final validation | Runtime behavior that contradicts the matrix, stale milestone assignment, public mature-project attribution, or generated artifact/result/evidence claims before those surfaces exist. |
| Tests and fixtures | `tests/services/_run_service_fixtures.py`, new aggregate test helpers, existing check-engine/service/adapter tests | Add focused aggregate fixtures and table setups that make source/target relation, capability, scan, tolerance, empty, type, privacy, and no-output behavior explicit. | All aggregate tests listed in the Detailed Test Plan plus regression-capture checks | Fixture helpers that hide assertions, broad unrelated fixture rewrites, tests that pass by relying on hidden Python fallback, unbounded grouped-row transfer, or generated outputs. |
| Compiled policy metadata | `src/recon_core/artifacts/compiled_contract_loader.py`, `src/recon_core/artifacts/compiled_check_loader.py` only if shape validation is needed; `src/recon_core/compiler/policies.py` and a private shared policy helper only if required to avoid duplicate normalization | Preserve existing compiled named tolerance metadata and validate shape; reuse the existing policy interpretation. | `tests/artifacts/test_compiled_contract_loader.py`, `tests/artifacts/test_compiled_check_loader.py`, compiler policy tests, aggregate helper and service admission tests | Authored YAML parsing at runtime, resource resolution, new policy schema or compiler-owned runtime comparison. |
| Private runtime rendering collaborator | New `src/recon_core/adapters/_aggregate_runtime.py`, `src/recon_core/adapters/duckdb/_aggregate_runtime.py`, `src/recon_core/adapters/default_renderers.py` and existing DuckDB SQL builders | Define and wire a narrow private bounded renderer and typed execution contract, retain lazy imports, reuse shared type guards and SQL fragments. | New `tests/adapters/test_duckdb_aggregate_runtime_renderer.py`, existing renderer and compile service tests, lifecycle and import-surface tests | Public API expansion, new capability, unbounded detail rendering in runtime, Core SQL rewriting, adapter tolerance or status decisions. |
| Private numeric result transport | `src/recon_core/adapters/duckdb/adapter.py`, private runtime contract and narrow shared adapter helper if needed | Reuse opened connection and sanitized error handling; preserve native logical type evidence, normalize exact transport, validate bounded final envelope with at most two rows; preserve public execute. | `tests/adapters/test_duckdb_adapter.py`, native numeric probes, private runtime renderer tests, import/compatibility and service tests | New public query result fields, lifecycle bypass, unbounded fetch, comparison policy or lossy conversion. |
| Private compiled metadata and policy helper | Existing compiled contract loader, service preparation and private runtime context in `src/recon_core/check_engine/engine.py` if needed; proposed shared `src/recon_core/_numeric_policy.py` | Preserve compiled policy metadata once through a private envelope/context; reuse canonical threshold validation with compiler. | Existing loader, compiler policy, service and check engine tests, exported shape checks | Changing exported dataclass layouts, rereading YAML, resolving named resources or broad orchestration changes. |

## Implementation Responsibility Map

The implementation must preserve these owner boundaries.

| Component boundary | Owns | Must not own | Allowed dependencies | Refactor trigger | Boundary-protecting tests |
| --- | --- | --- | --- | --- | --- |
| Compiler metric planner | Current aggregate typed-plan construction for authored `sum` metrics. | Runtime admission, adapter lifecycle, scan policy, pass/fail calculation, tolerance execution, or result privacy. | Compiler model enums and operation builders. | Only if the existing emitted plan cannot represent the in-scope current aggregate behavior. | Compiler aggregate tests and compile artifact tests. |
| Run service | Runtime candidate selection, profile-backed adapter dependency preparation, connection opening, capability preflight, scan/cost preflight, and passing aggregate context into `CheckExecutionContext`. | Aggregate semantics, SQL rendering, raw result interpretation, generated outputs, or evidence/report behavior. | Compiled artifacts, adapter registry/setup APIs, scan-budget helpers, check-engine context. | If aggregate admission would otherwise duplicate row-count/key-safety lifecycle logic in a way that hides hard blockers or opens adapters too early. | Service lifecycle, no-adapter-on-blocker, and DuckDB run-service tests. |
| Runtime router | Turning dispatch output plus execution context into an aggregate execution attempt or a structured non-execution result. | Adapter setup, profile rendering, scan probing, tolerance math, grouped summary parsing, or generated output. | Dispatcher output, compiled checks/contracts, context adapters/renderers, aggregate helper. | If aggregate routing needs more than small family-specific routing helpers, create or extend the aggregate helper instead of growing the router. | Runtime/router tests and execution-boundary import tests. |
| Aggregate helper | Aggregate-family execution semantics for current compiled plans: plan validation, relation-backed checks, renderer invocation, adapter query execution, bounded result validation, empty/null semantics, tolerance comparison, grouped summary status, and sanitized errors. | Compiler changes, adapter lifecycle, dialect SQL construction, capability declarations, scan probing ownership, evidence output, or public result schema. | Shared execution support helpers, renderer interface, adapter query interface, compiled plan models, check-result models. | If grouped execution would require unbounded group movement, materialization, staging, or failure-detail export, block the behavior and update prework instead of expanding the helper. | New aggregate helper tests, privacy tests, boundary tests. |
| Shared execution support and scan policy | Generic relation parsing, safe diagnostics, strict scalar extraction, connection-context checks, and reusable scan classification primitives. | Aggregate pass/fail semantics, metric-specific rules, key-safety-only wording for aggregate blockers, or user-facing scan policy. | Check-engine models and adapter interfaces only. | If two check families need the same helper and copied code would drift, extract a narrow helper with tests for both families. | Key-safety regression tests plus aggregate helper tests. |
| Check-engine orchestrator | Stable execution flow, prerequisite blocking, dispatcher invocation, runtime-router invocation, and status aggregation. | Check-family semantics, aggregate result parsing, SQL rendering, service dependency setup, or generated artifacts. | Dispatcher, runtime router, result models. | If aggregate execution needs direct orchestration changes, first prove the existing runtime-router boundary is insufficient and update prework. | Engine, model, and aggregation tests. |
| DuckDB renderer | Dialect-specific SQL for existing aggregate typed operations, exact type-guard SQL, and rendered-step capability declarations. | Core comparison semantics, tolerance rules, scan/cost decisions, result privacy, hidden fallback behavior, or pass/fail classification. | Typed-operation payloads and renderer SQL helpers. | If current renderer SQL would require unbounded grouped data movement into Core, add a bounded renderer operation or block execution with a clear non-execution result before changing placement. | DuckDB renderer operation tests and service/runtime integration tests. |
| Adapter API/capability surface | Declaring and validating existing adapter mechanics. | New M7.4-specific public capabilities, stable external adapter claims, shared adapter test-kit behavior, or public result/evidence schema. | Existing adapter capability catalog and renderer/query interfaces. | If M7.4 cannot be implemented with existing `aggregate`, `grouped_aggregate`, and `cte_support`, stop for compatibility review. | Capability tests, adapter lifecycle tests, package export tests if touched. |
| Test fixtures | Minimal setup data and fake adapters/renderers that expose each required case. | Production behavior, hidden fallback, broad refactors, or silently changing public contracts. | Existing service/check-engine fixture patterns. | If aggregate tests need repeated setup across service and helper tests, extract a small helper with explicit assertions at call sites. | The aggregate test suite and regression-capture scripts. |
| Compiled policy metadata and normalization | Preserve current compiled metadata, validate existing shape, normalize existing policy consistently. | Runtime named-policy loading, authored YAML parsing, comparison or adapter lifecycle. | Compiled artifact/schema models and narrow shared policy validation helper. | Extract shared policy helper if compiler and runtime otherwise diverge; do not add a general resolver. | Loader, compiler-policy and aggregate admission tests. |
| Private runtime renderer | Explicit bounded runtime query contract, shared dialect SQL and exact/native result-domain proof. | Changing existing compile result shape, tolerance comparison, status decisions, scan admission, public exports. | Private protocol, existing lazy runtime renderer factory and dialect helpers. | Extract common SQL builders when duplicate guards or join policy would drift; stop if public API or capability changes become necessary. | Existing compile renderer and new private runtime semantic tests, lifecycle/import boundary tests. |
| Private typed result transport | Logical type evidence, exact value conversion, bounded final cursor envelope, shared adapter lifecycle/error handling. | Public interface changes, adapter comparison policy, global conversion settings, fallback. | Existing connection and private typed execution contract. | Extract narrow shared query mechanics if required; stop for public interface change. | Native probes, adapter transport and lifecycle tests, package exports. |
| Private loaded metadata | Preserve existing compiled policy reference once and pass trusted private runtime metadata. | Public dataclass shape change, authored YAML reread, general policy resolver. | Existing artifact loader and private service/context boundary. | Stop for compatibility review if private approach requires public shape change. | Loader, compiler policy, admission and compatibility tests. |

## Future Implementation Constraints

- Implementation must be test-first from the matrix and BDD scenarios in this
  document.
- Only current compiled `sum_diff` and `grouped_aggregate_diff` checks may
  execute in this milestone.
- Aggregate runtime must consume compiled artifacts. It must not parse authored
  YAML or invoke compilation during `recon run`.
- Aggregate execution must use adapter pushdown for aggregate mechanics and a
  Core-owned comparison decision for tolerance, empty/null semantics, and final
  status.
- Grouped aggregate execution must not fetch or store unbounded grouped details
  in Core. If bounded grouped summary execution cannot be proven with current
  SQL and result shapes, grouped execution must remain `not_executable` and this
  prework must be updated.
- Preserve compile renderer output; use only the explicitly bounded private
  runtime path for grouped execution. Reuse SQL/type guard builders rather
  than parsing or wrapping renderer SQL in Core.
- Preserve exact numeric and native floating-point domains under ADR 0009.
  Named policy applicability is checked before runtime admission. Empirical
  numeric proof is required before runtime implementation begins.
- Renderer code may render dialect SQL and type guards, but it must not decide
  aggregate pass/fail, tolerance, privacy, scan safety, or fallback behavior.
- Missing, unsupported, unknown, malformed, incompatible, or not-implemented
  capabilities must block execution clearly.
- Unsafe, unclassified, unavailable, unsupported, malformed, or over-budget scan
  contexts must block execution clearly.
- The implementation must not add public YAML schema, CLI behavior, generated
  artifacts, evidence, reports, failure details, state, sink output, adapter API
  versions, or adapter capability names unless compatibility review stops and
  expands the prework.
- Regression-capture rows must be added or updated only when implementation
  fixes a reusable bug, covers a pending row, or changes executable behavior
  covered by the capture process.

## Regression Capture Carryover Review

These prework documentation updates do not add or update regression-capture
rows because they change only planning documentation and do not fix a bug or add
executable behavior.

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

Carryover disposition requirements for the current design:

- `key-safety-shape-blocker-precedence` and
  `key-safety-invalid-relation-diagnostic-precedence`: map equivalent
  aggregate preflight precedence cases to the new helper/service tests.
- `duplicate-key-excludes-null-containing-tuples` and
  `key-safety-empty-grain-keys-shape-blocker`: preserve row-level proof;
  aggregate segmentation does not require grain or exclude nullable group
  keys. Record the row-level-only rationale when resolving the applicable
  gate; do not mark a future shared test-kit obligation covered by this alone.
- `key-safety-prerequisites-block-dependent-checks`: preserve orchestrator
  prerequisite behavior and prove aggregate checks do not invent grain
  prerequisites or bypass explicit dependencies.
- The pending scan/capability rows in `adapter-runtime.yml` carry over to
  aggregate admission tests: hidden fixture markers, view/external scans,
  WAL/sidecars, project-relative paths, identifier case, database suffix,
  capability preflight, lazy import surface, metadata-open error precedence,
  and no user-provided scan classification. Shared adapter test-kit proof
  remains with its existing future gate.
- Preserve pending YAML diagnostic/privacy and compiled-artifact loader
  safety proof when policy metadata is loaded. Parser/compiler and publication
  carryover remain assigned to their existing owners unless a current change
  touches those surfaces; review their exact routing before implementation.

These are proposed test mappings and deferral rationales, not claims that
pending capture rows are resolved. Before phase exit, record actual evidence
and row dispositions under the existing capture rules. Add reusable regression
rows after executable proof for numeric consistency, exact arithmetic,
bounded group presence/summary, renderer separation, pre-adapter blockers,
type guards, privacy and no generated outputs as applicable.

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
- approved numeric-domain and exact transport proof is recorded, no supported
  numeric input is silently removed, inclusive tolerance and unresolved policy
  rules are proven, and non-finite/overflow/invalid arithmetic errors are safe;
- existing compile detail behavior and private bounded runtime rendering
  separation are proven without new public API or typed operation fields;
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
- all numeric-domain, policy-admission, bounded-summary and renderer
  separation cases pass, including exact transport, BIGNUM, FLOAT/DOUBLE,
  overflow and malformed results; no scope reduction is hidden as a fix;
- no user-facing scan-budget setting was added;
- no public YAML, CLI, generated artifact, run-result, evidence, or adapter API
  surface changed without its required compatibility review;
- no source/target values or private context leak through diagnostics or output;
- docs, compatibility docs, gates, and regression-capture records are current;
- newly discovered conformance requirements are either added to the matrix or
  recorded as blockers before follow-on implementation.

### Admission implementation checkpoint

The compiled aggregate admission boundary now owns current explicit sum plan
shape, relation endpoints, shared absolute tolerance interpretation, and
private compiled-policy state. Admission does not enable aggregate queries
or replace prerequisite and rendering blockers. Existing public adapter,
loaded-contract, execution-context and typed-plan shapes remain unchanged.
The initial RED cases and the additional boundary tests reside in
`tests/services/test_run_service_aggregate_admission.py` and
`tests/check_engine/test_aggregate_execution.py`; loader shape/read-once
proof resides in `tests/artifacts/test_compiled_contract_loader.py`.
The later typed transport, renderer, comparison and service candidate steps
must retain these admission guarantees. Current regression capture rows
preserve these cases for subsequent phase-exit and shared-suite review.

### Private typed transport implementation checkpoint

The private adapter result contract and bounded DuckDB transport now preserve
verified numeric domains and normalized values, including exact typed
arbitrary-size integers, decimal values, native floating values and nulls.
The existing public query envelope and adapter lifecycle remain unchanged.
Transport accepts only one complete final row with exact expected columns;
legacy logical metadata is verified using the existing connection and bounded
metadata retrieval. Transport does not decide comparison status or enable
aggregate queries. The native result-domain and input compatibility checks
in the renderer and Core comparison steps remain required.
Focused coverage resides in
`tests/adapters/test_duckdb_aggregate_transport.py`; the representative
version matrix retains the existing native feasibility probes.

### Private bounded runtime renderer implementation checkpoint

The private neutral plan defines the scalar and grouped summary column
contracts, ordered physical-type guards and native-domain proof. DuckDB
renders standalone metadata-only guards before binding native SUM and
subtraction on empty relations. A verified integer, decimal or floating
domain selects the corresponding final SQL without a lossy exact-data cast.
Grouped SQL uses positional internal key aliases, independent side presence
and null-safe complete group union classification; invalid numeric outcomes
precede mismatch categories. The final query returns one bounded summary
row with signed extrema. Public compile detail output remains unchanged.
Native renderer coverage resides in
`tests/adapters/test_duckdb_aggregate_runtime_renderer.py`.
Runtime candidate selection, scan-budget checks, and service lifecycle
integration remain required implementation steps.

### Private Core comparison implementation checkpoint

Core consumes the typed scalar or complete grouped summary contract and the
admitted absolute tolerance. It validates numeric domains, exact result
shape, scalar subtraction and null consistency, grouped counts and extrema,
and finite numeric evidence before classifying data differences. Exact
integer and decimal subtraction and magnitude comparison are independent
of ambient decimal context; native floating-point subtraction and its
canonical computed magnitude preserve the configured threshold without an
implicit epsilon. Invalid or contradictory evidence produces a sanitized
error. Valid outcomes expose no private numeric evidence.
Focused tests reside in `tests/check_engine/test_aggregate_execution.py`;
regression capture rows preserve numeric, grouped and privacy cases for
later execution and shared-conformance review. This helper does not yet
enable aggregate execution; runtime routing and end-to-end lifecycle,
scan-safety and privacy proof remain required.

### Runtime routing and scan-safety implementation checkpoint

The service selects admitted relation-backed aggregate candidates, uses the
existing bounded local/dev scan guard and validates capabilities per check
before opening eligible adapters. The private runtime renderer and typed
executor are required; the router executes ordered type guards, proves the
native numeric domain, and passes one bounded final result to Core. Missing
prerequisites, malformed scan approval, unsupported capability states and
missing private collaborators fail closed. Existing key-safety and row-count
behavior and the public execution-context shape remain unchanged.
Runtime routing, guard-order, scan-safety and mixed-run regression coverage
resides in the existing aggregate execution and service admission tests.
The full CI, end-to-end lifecycle, privacy and milestone carryover review
remain required before milestone exit.

### End-to-end execution and carryover checkpoint

The complete runtime and end-to-end semantic suite passed on
`3fa1fbbaf2ea3bdaa991589892b46846baa7a842` (CI run 45504491749).
All ten jobs passed: general Python 3.11-3.13 each ran 1,160 tests with
324 optional-test skips; mandatory DuckDB semantic jobs each ran 1,069 tests
without skips. DuckDB 1.0.0 and 1.3.2 each passed 983 semantic and 76 native
probe cases, with ten explicitly deselected BIGNUM probes; 1.4.5 and 2.0.1
each passed 983 semantic and 86 native probe cases. Ruff, mypy, pre-commit,
and regression-capture metadata passed. The 79 new end-to-end cases include
real adapter lifecycle, numeric behavior, bounded grouping, mixed execution,
sanitized failures and CLI/file immutability. No general production adapter
or generated output compatibility claim is made.

The following map names current test modules and representative test names
for all 25 acceptance dimensions. Prefixes denote files under `tests/`:
`S` = `services/test_run_service_aggregate_admission.py`;
`C` = `check_engine/test_aggregate_execution.py`;
`R` = `adapters/test_duckdb_aggregate_runtime_renderer.py`;
`T` = `adapters/test_duckdb_aggregate_transport.py`.
Names below omit the common `test_` prefix.

| Acceptance dimension | Current evidence |
| --- | --- |
| Current aggregate scope | S: aggregate_plan_rejects_unsupported_shape_before_profile; native_aggregate_service_numeric_outcomes_and_privacy. |
| Typed-plan shape and runtime input | C: injected_aggregate_plan_rejects_unsupported_fields; aggregate_unknown_private_metadata_blocks_even_with_override; S: aggregate_plan_rejects_unsupported_shape_before_profile. |
| Run boundary and compiled inputs | S: injected_public_loader_does_not_imply_verified_policy_absence; aggregate_invalid_relation_errors_before_profile; native_aggregate_named_policy_override. Existing compiled loader and service tests retain malformed-artifact coverage. |
| Ungrouped aggregate pass/fail/error | S: native_aggregate_service_numeric_outcomes_and_privacy; native_aggregate_lifecycle_and_failure_privacy. |
| Numeric tolerance for current sum | C: absolute_tolerance_is_context_independent; invalid_explicit_tolerance_agrees_with_compiler; aggregate_scalar_numeric_comparison; S: native_aggregate_named_policy_override; invalid_aggregate_tolerance_blocks_before_profile. |
| Ungrouped empty aggregate semantics | S: native_aggregate_service_null_and_empty_outcomes; C: aggregate_scalar_nulls_and_malformed_results. |
| Grouped aggregate pass/fail/error | S: native_aggregate_service_numeric_outcomes_and_privacy; native_grouped_service_distinguishes_absence_from_null; native_aggregate_lifecycle_and_failure_privacy. |
| Group presence versus aggregate nullness | S: native_grouped_service_distinguishes_absence_from_null; native_aggregate_service_null_and_empty_outcomes; R: runtime_renderer_all_null_groups. |
| Grouped no-unbounded-fetch rule | S: native_grouped_service_high_cardinality_remains_private; native_aggregate_lifecycle_and_failure_privacy; T: private_transport_preserves_complete_nine_field_envelope. |
| Aggregate input and result type mismatch | R: runtime_renderer_input_guards_fail_before_sum_binding; C: aggregate_scalar_invalid_metadata; aggregate_grouped_invalid_metadata; S: native_aggregate_lifecycle_and_failure_privacy. |
| Exact numeric aggregate behavior | S: native_aggregate_service_exact_overflow; native_aggregate_service_numeric_outcomes_and_privacy; C: aggregate_comparison_ignores_decimal_context_limits. |
| Grouped key type mismatch | S: native_grouped_service_rejects_incompatible_key_types; R: runtime_renderer_empty_group_key_mismatch. |
| Execution placement and no fallback | S: aggregate_service_blocks_cross_context_before_adapter_setup; aggregate_query_endpoint_is_not_executable_before_profile; C: aggregate_runtime_rejects_unproven_private_collaborators; aggregate_reserved_metadata_precedes_rendering_and_policy_blockers. |
| Adapter capability and lifecycle preflight | S: aggregate_service_requires_capabilities_before_connect; aggregate_capability_blocker_preserves_unrelated_row_count; aggregate_invalid_capability_declaration_is_non_executable; native_aggregate_lifecycle_and_failure_privacy; blocked_aggregate_shared_connection_preserves_lifecycle_privacy; aggregate_lifecycle_preserves_distinct_connection_failures. |
| Scan-budget and query-plan safety | S: aggregate_scan_safety_blocks_before_adapter_setup; C: aggregate_runtime_preserves_scan_blocker; aggregate_runtime_rejects_malformed_scan_approval. Existing shared key-safety guard tests retain path, suffix, identifier and metadata-open cases. |
| Diagnostics and source/target privacy | S: aggregate_factory_diagnostics_do_not_publish_private_data; aggregate_setup_preserves_distinct_connection_failures; aggregate_unknown_required_capability_is_sanitized; native_aggregate_lifecycle_and_failure_privacy; blocked_aggregate_shared_connection_preserves_lifecycle_privacy; aggregate_lifecycle_preserves_distinct_connection_failures; native_aggregate_cli_privacy_and_artifact_immutability. |
| Public output and generated artifacts | S: native_aggregate_cli_privacy_and_artifact_immutability; native_grouped_service_high_cardinality_remains_private. |
| Result aggregation and mixed outcomes | S: native_aggregate_same_context_alias_and_mixed_checks; aggregate_capability_blocker_preserves_unrelated_row_count; mixed_run_preserves_aggregate_policy_error_and_row_count. Existing engine status aggregation tests remain authoritative. |
| Future adapter/test-kit and carryover coverage | Capture rows and dispositions below; future shared conformance is explicitly deferred, not claimed covered. |
| Exact numeric domain and transport | S: native_aggregate_service_arbitrary_integer_availability; native_aggregate_service_exact_overflow; T: private_transport_large_typed_integer_ignores_decimal_context; R: runtime_renderer_native_domains. |
| Native floating-point domain | S: native_aggregate_service_numeric_outcomes_and_privacy; R: runtime_renderer_native_float_subtraction_regression; C: aggregate_scalar_invalid_arithmetic; aggregate_grouped_nonfinite_extrema. |
| Bounded grouped summary contract | C: aggregate_grouped_comparison; aggregate_grouped_invalid_summary; R: runtime_renderer_full_union_is_bounded; T: private_transport_rejects_invalid_envelope_without_leaking_values. |
| Compile and runtime renderer separation | R: runtime_renderer_does_not_replace_public_detail_renderer; C: aggregate_runtime_executes_only_ordered_private_queries; aggregate_runtime_rejects_duplicate_rendered_capabilities. |
| Representative engine versions | CI 45504491749 version matrix; S: native_aggregate_service_arbitrary_integer_availability; R: runtime_renderer_arbitrary_integer_version_availability. |
| Private typed transport and metadata | T: private_transport_resolves_legacy_logical_metadata; private_transport_rejects_conflicting_mixed_metadata; private_transport_real_driver_rejects_multiple_rows; C: public_execution_context_fields_remain_unchanged. |

Current Core check-engine carryover is covered by the existing key-safety
captures and aggregate admission, comparison, routing and end-to-end
captures. The two key-safety shape/endpoint precedence rows retain their
original proof and have aggregate counterparts in
`aggregate-admission-typed-plan-boundary` and
`aggregate-admission-endpoint-precedence`. Duplicate-key exclusion and
empty grain-key rejection remain row-level semantics; nullable aggregate
group keys and ungrouped sums do not acquire grain prerequisites.
The original prerequisite rows retain their proof, with aggregate
prerequisite coverage in `aggregate-runtime-capability-isolation`.

Adapter-runtime rows retain their current Core evidence, including shared
scan guards, metadata diagnostics, lazy imports and private transport and
renderer conformance. Future adapter test-kit obligations are deferred with
rationale, not marked covered by Core-only tests. Diagnostic/YAML privacy
rows retain their current proof; future runner/results privacy is deferred.
Parser/compiler carryover linked to these rows remains deferred to its
existing expansion owner. The existing compiled-loader, compile CLI, parser/compiler and metadata
captures are explicitly deferred to their owning future surfaces after
reviewing current passing tests. The aggregate CLI/immutability capture
likewise defers final runner outputs. Current implementation requirements
are covered by current tests, not deferred. No generated
output or new public capability has been introduced.

regression_capture_decision: required.

Current implementation gate disposition (local Core scope only):

| Gate | Evidence and disposition |
| --- | --- |
| 3A | Current explicit sum scope preserved; expansion remains outside M7.4. |
| 3D | Canonical tolerance, exact/native domain, null/overflow and named-policy tests pass. |
| 4B/4C | Private transport and renderer tests, public adapter/context shape and compile detail regression tests pass; no new operation or capability. |
| 4I | Same-context execution, alias and mixed-check tests, cross-context blockers and no public query fallback pass. |
| 4L | Shared bounded local/dev scan guard and malformed approval tests pass; production budget settings remain future. |
| 6 | Real scalar/grouped lifecycle, factory/capability diagnostics, CLI, logs and file immutability tests pass; later output surfaces remain gated. |
| 8C | Native semantic and four-version probe matrix pass; shared external adapter conformance remains future. |

Final branch-wide advisory, cumulative public-contract review, and final
phase-exit decision remain required before milestone exit.

## Initial implementation readiness requirements

The approved design and its acceptance requirements are documented.
Representative version verification and the compatibility review are complete
for the tested native cases. The implementation plan must assign all 25
acceptance dimensions and applicable carryover obligations to concrete tests,
preserve public renderer behavior, and rehydrate required context before
coding. Runtime changes require explicit implementation approval. Private
typed transport, compiled policy metadata and the full aggregate runtime
contract must be proven by test-first implementation. Do not interpret
this initial planning update or passing pre-implementation CI as proof of new
aggregate execution.

## Current implementation evidence

The bounded explicit sum runtime is integrated and tested. Review iteration 4
passed all ten CI jobs at `740ebab02651bf74bfc78c0481f54ff4f4c8d6cf`
(run 45678586734): the three mandatory semantic jobs each passed 1,093 tests;
the four pinned jobs passed 1,007 semantic tests plus 76 legacy or 86 modern
native probes. The general jobs passed 1,164 tests each, with 344 optional
skips; formatting, lint, typing, pre-commit and regression metadata passed.
The distinct-connection diagnostic regression retains separate sanitized
setup failures without publishing connection identifiers. Cumulative review,
final validation and phase-exit evidence remain required; this checkpoint is
not a milestone completion claim.

## Type compatibility delivery checkpoint

Apply [Gate 4P mandatory type compatibility assignments](type-compatibility-assignments.md). Current strict physical-type execution boundaries remain unchanged. Future operation-aware lossless comparison and explicit conversion policies must be designed, implemented and proven; structural schema equality is not the same as value comparability. Do not infer compatibility from implicit engine casts. The assignment defines delivery ownership, not approved runtime behavior.

## Mandatory M9.5 delivery checkpoint

Historical completion is unchanged. Mandatory pending M9.5 owns the explicit retrofit of existing key and aggregate checks for losslessly compatible physical types; M10 exit is blocked until M9.5 is verified.

## Reopened next-action dependency

Follow the [M8 split assignment](milestone-8-split-assignment.md#reopened-execution-dependency-and-next-action): shared binding design and verified implementation precede the targeted M7.4 correction, which precedes remaining M8.1 calibration. Historical prework and experimental evidence do not authorize coding. M8.1.1 is completed and verified on main; the targeted correction's own finalized prework and implementation approval remain pending.

## Targeted bound grouped runtime correction - proposed prework

Status: proposed, not approved for runtime implementation. M8.1.1 scoped exit
completed on main at 4d3ede5029a6f052d1c18c0ef62f176e0ae15868 (PR #38,
tested head d513a249b926f05c8264d6790af163911c90b3a1, CI 45815181891 10/10;
tested and merged trees identical). Split Decision: Already Split / Follow
Existing Split; reopen only the affected M7.4 regression, no new numbered
milestone. M8.1.2 remains mandatory afterward. High-risk: native SQL,
binding, strict comparison, resource behavior, privacy.

### Problem and proposed decision

The private grouped final join currently combines physical-type equality
and null-safe key equality on each positional key. The extra type expression
can prevent an efficient join on supported native engines. The normal
project path now owns a fresh read-only transaction and exact qualified
relations, and verifies a single-use binding lease before/after each
read and transport metadata read. It already executes ordered key-type,
input-type and native-domain guards before the final query. Low-level
prepared aggregate execution can still call the same renderer without
a bound runner. Public compile/detail rendering is a separate contract.

Propose an explicit private bound-grouped rendering entry point, reachable
in normal execution only inside the successful owned-binding evaluation
callback, with its existing canonical relations and bound reader. Keep the
existing private render_plan behavior strict for unbound callers and scalar
behavior unchanged. The bound renderer reuses the same private plan builder,
guard SQL, positional grouping, full outer join, presence markers, numeric
expressions and one-row summary; only its final grouped key predicate uses
null-safe equality without the redundant typeof conjunct. Both exact and
floating final variants follow the same rule. Keep the shared strict
helper, public compile/detail renderer and key checks unchanged. Use an
explicit private renderer contract for this operation, not a caller-supplied
public flag, adapter-name guess, connection mode guess or SQL text rewriting.
Missing/invalid bound collaborator uses the existing safe renderer error;
no fallback/retry with weaker proof. Verify collaborator availability before
opening native work where applicable without moving existing blocker
precedence. No proof may be inferred from method availability alone:
admission, verified lease, ordered guard results and final bound read are
all mandatory. The built-in adapter owns the SQL; Core owns orchestration
and outcomes. No concrete DuckDB imports in check-engine/services.

Non-goals: new types or casts, public API/schema/compile SQL changes,
duplicate transactions, optimizer directives, version-specific production
branches, staging, implicit sampling/filtering, new resource settings,
changed 64 MiB key/SUM-only temporary limit, changed execution scope,
new diagnostics or artifacts. No generic performance guarantee.
Do not optimize the unbound path on the basis of this proof.

### Expanded correction matrix and test plan

The existing M7.4 acceptance matrix remains authoritative for preserved
behavior. G rows below specify correction proof; node names prefixed
"new:" are planned, not passed. R = tests/adapters/test_duckdb_aggregate_runtime_renderer.py;
S = tests/services/test_run_service_aggregate_admission.py;
E = tests/check_engine/test_aggregate_execution.py;
B = tests/adapters/test_duckdb_bound_execution.py.

| ID | Required variants and behavior | Evidence owner |
| --- | --- | --- |
| G1 | Exact/floating single/composite bound join removes only redundant type conjunct; unbound final retains strict predicate; scalar, public detail and key SQL unchanged | R new: test_bound_grouped_join_uses_guarded_null_safe_equality; existing public separation and public renderer suites |
| G2 | Integer widths/signedness, decimal scale, text/numeric, partial composite mismatch, empty/nonempty; malformed guard, mismatch or error prevents final execution; preserve existing precedence | R test_runtime_renderer_empty_group_key_mismatch; S test_native_grouped_service_rejects_incompatible_key_types; E test_aggregate_runtime_stops_before_final_query_on_invalid_guard; new bound matrix in S |
| G3 | Canonical qualified relation/alias, actual owned session, guard/final/hidden DESCRIBE same lease; wrong context, shadowing, file/sidecar drift and invalidation fail closed; no legacy query on bound path | S test_all_nine_checks_use_owned_transaction_and_qualified_queries, test_binding_drift_between_aggregate_guards_stops_final_read; B binding/lease/cleanup matrix; new candidate-specific drift tests |
| G4 | Nullable single/composite keys, repeated/quoted keys, alias collisions, duplicate input rows, empty, matched/unmatched, both-null/null-mismatch, zero; known independent summary and strict-vs-bound differential | R existing composite/repeated/all-null/empty/null-zero tests; new native differential fixtures |
| G5 | All existing exact signed/unsigned integers, decimal scale/extrema, native float/double, BIGNUM where supported, nonfinite/overflow/invalid precedence, inclusive and named tolerance | R existing native domains; tests/adapters/test_duckdb_aggregate_numeric_domains.py; S numeric/overflow/tolerance; new bound differential numeric coverage; no new pin exclusions |
| G6 | Synthetic narrow/wide and skewed/composite group shapes, exact/floating, modest permanent regression fixture and bounded 1k/10k/50k/800k probes as feasible; actual native SQL, known truth, one-row transport, compare strict/candidate plan and elapsed/work, all four pins; no fixed runtime SLA or runtime plan parser | R new: test_bound_grouped_join_scale_regression; isolated bounded probe, record unavailable observations and file sizes/runner context separately |
| G7 | Admission/capability/preflight refusal, ordered guards/domain/final, malformed result/query/cleanup failure, prerequisite and unrelated-check isolation, no raw values/SQL/plan or generated output | E ordered/invalid guard and result tests; S lifecycle/privacy/immutability; B; existing transport and CLI |
| G8 | Reusable capture linked to actual tests, existing native-domain/bounded-summary/public-separation and owned-binding captures preserved; full branch advisory and compatibility | adapter-runtime capture and index; architecture and public exports tests |
| G9 | M8.1.2 uses exact corrected revision and affected workload for actual calibration; no resource containment/default claim from optimization | M8.1.2 prework and R1-R10; M29 shared conformance |
| G10 | Normal bound grouped path alone selects optimized entry; missing/malformed collaborator or lease prevents it; legacy prepared context cannot select it implicitly; scalar retains existing path and no SQL/text mutation shortcut | E new: test_grouped_runtime_selects_bound_renderer_only_in_owned_callback; S actual native trace; R strict/optimized variant |
| G11 | Native same-type temporal/boolean/string/binary/UUID and nested key forms where existing engine accepts them; explicit collated DDL versus binary case, collation/unsupported outcomes preserved by strict-vs-bound comparison plus independent truth; no implicit normalization or cross-type expansion | R/S native differential tests on four pins; investigate any disagreement, don't exclude a previously supported case |

### Gate and responsibility dispositions (planning, not exit proof)

- 3A/3D/3F2/6: G4/G5/G7/G11 retain existing metric, tolerance, outcome and privacy rules.
- 4B/4C/4I: G1/G2/G3/G7/G10 preserve private adapter-native SQL,
  typed operations, same-context placement and public signatures/compile.
- 4L/R1-R10: G6 distinguishes input/file/work/returned observations (R1),
  records environment (R2), does not introduce or claim native controls (R3)
  or defaults (R4), preserves actual ordered binding and admission (R5),
  reuses cleanup/failure semantics (R6), observes join work without adding
  scheduling (R7), no new projection (R8), measured plan improvement only
  (R9), four-pin bounded evidence (R10). Remaining controls, useful defaults
  and scheduling/publication stay assigned to M8.1.2/M8.2/M8.3.
- 4P/T1-T10: G2/G4/G5/G11 retain physical type/domain and identity
  (T1-T6), G3/G10 binding and typed mechanics (T7/T8), G7 safe outcomes
  (T9), G1-G8/G11 native/conformance proof (T10). M9.5 owns full
  lossless compatibility; no implicit casting or permanent scope decision.
- 4Q: G3/G7/G10 preserve temporary protected local scope; no S expansion.
  M10.8/M13.5/M18/M29 assignments unchanged.
- 1A/5/5E: G3/G7 preserve owned lifetime and no writes; no new publication.
- 8C: G1-G8/G10-G11 pinned semantics and scale; M29 retains shared proof.

Responsibility map: private neutral aggregate renderer contract
(src/recon_core/adapters/_aggregate_runtime.py) defines the explicit
bound-grouped entry; DuckDB private renderer
(src/recon_core/adapters/duckdb/_aggregate_runtime.py) owns common SQL and
predicate selection; check_engine/aggregate.py selects the private entry
only after the bound callback, validates plan/guards/domain and interprets
results; default_renderers.py supplies built-in collaborators. No lifecycle
or concrete engine dependencies in Core. Existing _bound_runner.py,
_bound_protocol.py, adapters/_project_binding.py and DuckDB _bound_execution.py
own binding/read/cleanup and should not require production changes. Do not
duplicate final-summary SQL or new binding state. Public renderer_sql.py,
renderer_operations.py and renderer.py remain unchanged. Test responsibility
matches G rows; add/update capture and docs/changelog at implementation.
If this narrow boundary cannot be maintained or existing supported semantics
differ, stop and revise design before coding; no broad refactor without approval.

BDD: (1) given an owned verified grouped check and valid guards, when
evaluated, then native null-safe join returns the same bounded truth more
efficiently; (2) given mismatched or stale proof, then no unproven final
read; (3) given prepared unbound or public compile, then strict SQL/behavior
unchanged; (4) given null/absence/numeric error or cleanup failure, then same
safe outcome and no publication; (5) given absent bound collaborator, then
safe error and no weaker fallback.

### Steps and Definition of Done

1. Preflight/research: audit the merged source and gates, compare actual
   old/candidate SQL using fresh owned native sessions on each pin including
   explicit collation DDL and bounded scale. Record actual outcomes and
   limitations, cleanup experiment-only files. Resolve any baseline or
   candidate discrepancy before locking design. Prior unbound experiments
   are not sufficient. Bound feasibility and independent native collation isolation have been observed on all four pins. The pre-existing legacy collation discrepancy below requires a maintainer disposition before design lock.
2. Finalize design, acceptance/source map and docs after evidence; obtain
   maintainer design/implementation approval. No implementation until then.
3. Test-first: actual RED evidence for critical path-selection/semantic
   regression and performance SQL structure; additive sibling proofs,
   preserve existing captures. Implement the smallest design-conformant
   shared renderer change and private selection. Verify GREEN.
4. Prove G1-G8/G10-G11 on actual native and pinned CI, bounded scale and
   public compile/API/diagnostic regressions; no new unsupported exclusions.
   Full branch carryover advisory (or documented equivalent), pre-commit,
   tests, lint/types, docs/changelog and capture review. Mandatory cumulative
   review-fix loop and semantic anti-pattern check; no unresolved material
   in-scope issue. Verify exact head and obtain exit/merge approval.
5. After verified integration, record G9 handoff; mandatory M8.1.2
   prework/calibration follows, not approved by this correction.

### Feasibility and remaining decision

On fresh actual owned read-only sessions, the existing strict and candidate
final SQL produced identical outcomes across all paired native cases
(9 semantic plus one 10,000-group case per pin, including mismatched key
refusals). Candidate-only 800,000-group synthetic fixtures completed with
the known union summary on every pin; the narrow compressed fixture does
not establish resource safety or general performance. Previous physical
plan evidence identified the redundant predicate regression on two pins.
The wide/skewed/floating scale and complete native-domain/route proof remain
implementation acceptance, not claimed by these probes.

Independent truth exposed one existing discrepancy: on DuckDB 1.0.0,
explicit case-insensitive text collation matches the two case variants
before grouping, but native equality and null-safe equality after grouping
both return unequal. The existing strict SQL and candidate both produce
two one-sided groups, while later tested pins match. This is not introduced
by the candidate and is not a universal statement about collations. The
correction must not silently change that baseline, exclude a version, or
introduce casts, case-folding or version-specific SQL. Proposed owner for
operation-aware collation metadata and grouped comparison semantics is
mandatory M9.5 (T1/T5/T6/T10); this disposition requires explicit
maintainer approval before design lock. If the existing contract requires
correction earlier, revise scope and prework instead. Carry the precise
native case into the assigned conformance plan and retain differential
proof on all four pins here. Do not claim portable collation support.
No production code or gate satisfaction claimed by this prework.
