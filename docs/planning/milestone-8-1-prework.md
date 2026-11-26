# Milestone 8.1 Prework: Scan Policy And Execution Advisories

**HISTORICAL UMBRELLA BASELINE - not implementation authority.** M8.1.1 and targeted M7.4 correction are verified on main; [M8.1.2 approved prework](milestone-8-1-2-prework.md) records the reopened whole resource design (2026-11-27); implementation suspended and prior mechanisms historical pending revision. The prior footprint-driven design below is retained for history, not coding authority.

## Status and approval boundary

Split Decision: Already Split / Follow Existing Split.
High-risk: project configuration, runtime admission, adapter evidence,
diagnostics, privacy and compatibility. Research decision: completed for the
strategy and representative connection-binding feasibility. The maintainer
approved the five directions and concrete syntax, local proxy policy and
intentional row-count admission restriction. Exact implementation and
conformance proof remain mandatory. This is locked design prework after
integration, not a claim of runtime completion or expanded compatibility.

Authority: [split assignment](milestone-8-split-assignment.md), ADR 0021,
0022, 0025, [ADR 0026](../decisions/adr-0026-local-execution-policy-and-scan-admission.md), and build order.
The previous combined scope remains divided; do not implement M8.2/M8.3.

## Scope, expected behavior and non-goals

Implement ADR 0026: typed project-local execution policy,
version-local footprint default and optional explicit estimated-input warning
threshold; same-context local base-table evidence bound to actual execution,
Core-owned fail-closed admission for row count, key safety and explicit sum,
sanitized structured advice and private metadata. Retain existing typed
plans, exact comparisons, native numeric support, prerequisites and result
transport. No production adapters, new check types, query endpoints, public
adapter API change, contract YAML execution policy, SQL rewrite, sampling,
windows, selectors, result/evidence/state/sink output, full CLI summary,
universal cost or actual resource guarantee. Do not add permanent CI
experiments. A local footprint limit is not an actual scan-cost limit.

## Compatibility, security and privacy

Current row-count project-run execution bypasses bounded local admission;
supported docs currently describe same-context relation-backed DuckDB, not
local base-table-only row count. The explicit approved change is to require
the same proven local scope as other scan-bearing operations, including
blocking view/external/non-project/unbounded contexts. Preserve positive
local row count, aliases, no materialization and all key/aggregate semantics.
Missing endpoint/file and setup error precedence must be resolved with
existing diagnostics where truthful, never query just to obtain a native
error. The direct prepared-adapter helper retains its pre-alpha signature
and semantics; not an admission API. Test doubles currently use recording
factories without real local files; use private explicit evidence fixtures,
not a production bypass, preserve lifecycle/renderer/result tests.

Configuration is additive; the runtime scope restriction has explicit
maintainer approval and requires implementation-time changelog/migration guidance.
No change to minimum DuckDB dependency, adapter API version, compiled
artifact versions, public result schema or operation catalog. Public
diagnostics must suppress relation names, profile values, raw SQL/plans,
native error messages, private result values/counts and paths where sensitive.
Only sanitized code/message/hint and non-sensitive policy explanation.
No automatic query rewrite, staging or hidden Python fallback.

## Gate review and outstanding proof

| Gate | Design disposition and remaining proof |
| --- | --- |
| 4L | ADR 0026 locks units, settings, default origin, limit semantics, evidence states and advisory distinction. Empirical metadata is advisory only. Required same-execution binding and local scope proof must be validated; no actual-cost promise. A1-A6/A9. |
| 4I | Existing ADR 0021 placement and bounded transport remain; prove all admitted checks keep same-context native execution and bounded envelopes. A4/A5/A7. |
| 4A / 4J | Preserve referenced profile resolution, secrets and setup/lifecycle diagnostic conformance; no new profile fields. A4.06/A8. |
| 4B | Private runtime-safety collaborator; preserve public BaseAdapter, QueryResult, SqlRenderer, compiled schemas and numeric renderer behavior. Stop if public signature change required. A7/A9. |
| 4C | No new or changed typed operations; retain plan shape and capability proof. A4.05/A7. |
| 3F2 / 6 | Preserve safe diagnostic code/message/hint, warning visibility, and public privacy; no raw plans/counts/values. A6/A8/A9. |
| 8C | Scoped native plan/transport proof only, no new production capability. A3/A5/A7. |
| 5E | No writer touched, negative output tests A9.02; re-open if writer changes. |
| 5 / selector / sink gates | Later phases own lifecycle/public results and selectors/sinks; private metadata reservation only. A9. |

The initial experiments established misleading/stale estimates, compressed
footprint limitations, plan-version differences and an unsafe storage-info
path. Representative supported-version feasibility checks established that
catalog inspection and reads can share an owned read-only connection and
transaction, that cooperating writable opens are rejected while it is live,
and that exact qualified binding avoids temporary name shadowing. A missing
read-only file is not created; observable path replacement and late sidecar
changes can be detected. This is not proof of exact generated Recon SQL,
all concurrent mutations or hostile filesystem races. The approved local
dev policy is explicitly a footprint proxy, not an actual-cost guarantee.
Before GREEN/exit, require real supported-version proofs of the implemented
binding, read-only operation and no data-query-after-block. No unsupported
fallback. If the existing connection lifecycle cannot establish the
proposed proof, stop before weakening admission and ask for scoped design
approval. No gate is marked satisfied merely by this document.

## Acceptance and conformance matrix

Each row lists sibling variants, expected behavior and proposed exact pytest
node or existing suite. Proposed names are planned, not existing test
claims; reconcile to actual nodes at implementation exit. All rows affect
ADR 0026/Gate 4L; use gate mapping above and docs mapping below. A1-A9 map
the split families. For each row retain current artifact/no-write,
diagnostic and privacy rules. Applicable shared adapter conformance is
deferred to test-kit ownership; preserve local proof.

| ID | Dimension/cases | Expected behavior | Required tests |
| --- | --- | --- | --- |
| A1.01 | Absent execution, empty execution, empty scan-budget, empty local | Internal footprint default; no row-warning threshold; existing init/parse/compile unchanged | `tests/config/test_project_config.py::test_local_execution_policy_defaults` |
| A1.02 | Authored integer footprint 1, 64, 128 and maximum representable MiB; optional positive rows | Exact integer conversion and authored origin; no threshold when absent | `tests/config/test_project_config.py::test_local_execution_policy_valid_limits` |
| A1.03 | Zero, negative, bool, float, string, null, overflow for each leaf; scalar/list/null at every mapping | RC_CONFIG_INVALID_PROJECT_CONFIG; exit 4; no profile/query | `tests/config/test_project_config.py::test_local_execution_policy_rejects_invalid_values` |
| A1.04 | Unknown and non-string keys at each level; duplicate YAML keys; user status/allow-unestimated fields | Existing strict YAML/config diagnostic; no leak of input value | `tests/config/test_project_config.py::test_local_execution_policy_rejects_unknown_or_duplicate_keys` |
| A1.05 | CLI/profile/env/contract/package override attempts, existing unrelated config and resource precedence | No new override surface; existing validation unchanged; authored project overrides only internal default | `tests/config/test_project_config.py::test_local_execution_policy_precedence` |
| A2.01 | Known local file below, exactly at, one byte above effective limit | Allow below/equal; over budget not_executable, no scan | `tests/adapters/test_runtime_safety.py::test_local_footprint_boundary` |
| A2.02 | Larger known local file below authored limit; tighter authored limit; zero config legacy fixture | Allow within limit, block tighter/over; no universal scan bound claim | `tests/services/test_run_service_duckdb_execution.py::test_local_limit_configuration_admission` |
| A2.03 | Highly compressed small file with large logical payload; repeated scan and join growth | Record footprint only; advisory estimate not actual work; no inferred hard physical bytes | `tests/adapters/test_runtime_safety.py::test_footprint_is_not_scan_bytes` |
| A3.01 | Catalog estimate valid positive/zero, stale after delete/checkpoint, source=target | Available estimate only; role sum checked; stale not exact or upper bound | `tests/adapters/test_runtime_safety.py::test_catalog_estimate_is_advisory` |
| A3.02 | Optional estimate missing/unsupported/malformed/negative/bool/overflow/exception for either endpoint | Unknown/unsupported/malformed, never zero; no fabricated warning; allow only independent required proof | `tests/check_engine/test_execution_boundaries.py::test_optional_estimate_unavailable` |
| A3.03 | Required metadata absent, invalid/ambiguous catalog, metadata failure vs missing adapter dependency | Fail closed with existing specific sanitized reason/lifecycle diagnostic; no data query | `tests/services/test_run_service_adapter_lifecycle.py::test_required_scope_proof_failure` |
| A3.04 | All pinned DuckDB lanes; non-executing catalog only; no pragma_storage_info, EXPLAIN ANALYZE or count-as-preflight | Preserve floor; spy forbidden operations never invoked | `tests/adapters/test_runtime_safety.py::test_safe_metadata_queries_only` |
| A4.01 | Project-local regular file no suffix, relative path/subdirectory, same-context aliases, case-insensitive qualified names | Admit proven local binding; preserve existing positive tests | `tests/services/test_run_service_duckdb_execution.py::test_local_admission_positive_variants` |
| A4.02 | Missing file, directory, memory, external path, symlink escape, permission/stat failure, WAL/tmp file/dir/symlink | Block before data scan; missing file not created; no raw paths | `tests/adapters/test_runtime_safety.py::test_local_scope_rejects_unsafe_files` |
| A4.03 | Views local/external, attached catalog, ambiguous schema, missing endpoint, malformed metadata | No data scan; preserve specific invalid-endpoint diagnostics; no raw metadata | `tests/services/test_run_service_duckdb_execution.py::test_local_admission_rejects_untrusted_relations` |
| A4.04 | File replacement, binding mismatch, stale proof, sidecar added after preliminary probe, changed catalog/snapshot | Revalidate path/identity and sidecars before/after open and before each data query on owned read-only execution context; fail closed on drift; no forged proof | `tests/adapters/test_runtime_safety.py::test_execution_binding_freshness` |
| A4.08 | Temporary table shadow, attached catalog, changed search path, qualified and unqualified authored relation, same-context aliases | Resolve unambiguous verified catalog/schema/table identity; runtime renderer consumes qualified binding without logical scope mutation; reject untrusted shadow/attachment/context; preserve public compile output | `tests/adapters/test_runtime_safety.py::test_runtime_binding_rejects_shadowing`; `tests/services/test_run_service_duckdb_execution.py::test_runtime_uses_verified_qualified_binding` |
| A4.09 | Real pinned-version read-only transaction, writer open in same/other process, missing database, cleanup on preflight rejection | Owned connection, no writes or missing file creation, cooperating writers blocked; rollback/close on failure; no hostile filesystem guarantee | `tests/adapters/test_runtime_safety.py::test_owned_read_only_execution_binding` |
| A4.05 | Mixed adapters/cross-context, unsupported placement/materialization, invalid typed operations, blocked compile rendering | Existing specific reason/precedence; no unsupported scan/bridge | `tests/check_engine/test_execution_boundaries.py::test_scan_admission_preserves_dispatch_precedence` |
| A4.06 | Missing dependency, metadata open failure, capability missing/malformed/exception, adapter connect/close failure | Preserve specific sanitized setup/runtime failures; no scan on failure; close only opened resources | `tests/services/test_run_service_adapter_lifecycle.py::test_scan_admission_lifecycle_precedence` |
| A4.07 | Hard decision missing, malformed, wrong check/contract/context, forged allowed, policy changed | No data query; reject mismatched proof at engine router and actual executor boundary | `tests/check_engine/test_execution_boundaries.py::test_runtime_rejects_invalid_admission_proof` |
| A5.01 | Single scalar count/sum, key-safety result, grouped bounded summary, repeated scans, large join | Result envelope independent of scan; enforce shape and bounded fetch without LIMIT rewriting comparison | `tests/adapters/test_runtime_safety.py::test_result_envelope_independent_of_scan` |
| A5.02 | Engine-native actual scan/cost/time/memory/transfer estimates not proven; estimate zero vs unknown | Explicit unavailable fields; no fabricated dollar/resource claim; local transport separate | `tests/check_engine/test_execution_boundaries.py::test_advisory_metadata_dimensions` |
| A6.01 | Estimated role sum below/equal/above optional threshold; no threshold | Only above triggers RC_RUNTIME_SCAN_ESTIMATED_INPUT_ROWS_WARNING; no hard block | `tests/check_engine/test_execution_boundaries.py::test_estimated_input_warning_boundary` |
| A6.02 | Warning plus pass/fail/error; hard block plus would-be warning; multiple checks | Status/exit mapping unchanged for warning, hard block wins; warning visibility on successful CLI | `tests/cli/test_main.py::test_run_advisory_warning_output` |
| A6.03 | Actionable advice for footprint excess, unknown proof, optional estimate warning, future subset capability | Safe conditional hints; no hidden filters/sample/SQL rewrite, no production advice as executable | `tests/services/test_run_service_duckdb_execution.py::test_advisory_does_not_mutate_scope` |
| A7.01 | Real local row-count pass/fail, empty, aliases, no materialization; all four versions | Preserve exact semantics; no metadata-only assumption | `tests/services/test_run_service_duckdb_execution.py::test_row_count_local_policy_semantics` |
| A7.02 | Previously bypassed row-count view, external/non-project, oversized, missing file/metadata, in-memory | Approved intentional project-run restriction; not_executable or specific existing error; no query | `tests/services/test_run_service_duckdb_execution.py::test_row_count_unsafe_scope_rejected` |
| A7.03 | Direct prepared-adapter helper, injected recording adapters, lifecycle/shape/error fixtures | Preserve helper API/semantics; explicit fixture proof for project run; no test-only production exemption | `tests/check_engine/test_row_count_execution.py::test_execute_row_count_check_passes_with_equal_counts` |
| A7.04 | All grain-key null/duplicate/missing/extra, empty sides, composite identity, prerequisite blocked, mixed row count | Preserve key semantics and prerequisite precedence; no bypass from other allowed checks | `tests/check_engine/test_key_safety_execution.py (existing suite plus admission cases)` |
| A7.05 | Scalar/grouped sum, exact/approximate domains, tolerance, empty groups, nulls, invalid transport, policy precedence | Preserve all M7.4 behavior and numeric lanes; no grouped detail fallback | `tests/check_engine/test_aggregate_execution.py; tests/services/test_run_service_aggregate_admission.py; tests/adapters/test_duckdb_aggregate_numeric_domains.py` |
| A8.01 | Secret/identifier/query/path/native error sentinels in every diagnostic field and advisory; malformed config input | Allowlisted safe output; code/message/hint actionable; no sensitive payload | `tests/services/test_run_service_adapter_lifecycle.py::test_scan_advisory_redaction` |
| A8.02 | Repeated identical warning, distinct source/target failure, mixed lifecycle errors | Dedup identical without suppressing distinct safe failure; no public numeric data | `tests/services/test_run_service_duckdb_execution.py::test_scan_diagnostic_preservation` |
| A9.01 | In-memory metadata role, evidence provenance/availability, policy origin, decision/reason and envelope | Private typed immutable decision; no generic serialization or public version changes | `tests/check_engine/test_execution_boundaries.py::test_scan_policy_metadata_handoff` |
| A9.02 | Allowed, blocked, warning, config/adapter/engine failure, stale target/report/state sentinel files | No run_results/evidence/state/SQL/sink writes or cleanup mutation; compile outputs unchanged | `tests/services/test_run_service_duckdb_execution.py::test_scan_policy_no_runtime_writes` |
| A9.03 | Existing API imports, adapter/renderer/compiled shapes, optional dependency absent; all CI versions | No public signature/API/format change without review; all preserved lanes | `tests/check_engine/test_execution_boundaries.py; existing import/API/compile/CI suites` |

Explicit out-of-scope rows: production estimate admission and financial
cost (adapter gates/M29), richer plan analysis and recommendations (M12.5),
query endpoints (M18), sampling/window execution (M24/M25), artifact
serialization/terminal finalization (M8.3), result/evidence/sink writes
(M8.3/M9/M25.5/M31), selectors (M10.6/M19). Negative A6/A9 tests prove
these surfaces are not enabled. No test skip can be used to drop currently
supported cases; the 1.0.0 unsafe metadata query is avoided in runtime, not
a dependency exclusion.

## BDD workflow scenarios

- Given an existing small local fixture and no policy, when recon run
  executes supported checks, then proven local admission permits exact
  comparison, the current status/exit behavior is preserved and no result
  artifacts are written.
- Given a known local database exceeding the default, when a valid explicit
  larger footprint limit covers it, then it may run only after all remaining
  safety evidence is proven; an unknown scope still blocks.
- Given a known local footprint over the effective limit, when recon run
  preflights, then it returns a structured non-execution reason with safe
  guidance and no data scan.
- Given a proven local scope and estimated input exceeding the optional
  threshold, when recon run succeeds, then a warning is visible without
  turning the check into a reconciliation warning/failure.
- Given missing/untrusted optional estimates, when the independent local
  proof passes, then the check may execute with unavailable advisory
  evidence; unknown required proof never becomes allowed.
- Given a formerly admitted row-count view or external relation, when
  project run is attempted under the new approved policy, then it cannot
  scan; user receives migration/scope guidance without revealing its name.
- Given changed binding between preparation and execution, when the check
  reaches the actual connection, then stale evidence is rejected before
  the comparison query.
- Given a mixed run and a hard-blocked prerequisite, when the engine
  evaluates dependent checks, then existing prerequisite precedence holds,
  no blocked query executes, and independent admitted checks retain their
  comparison behavior.
- Given a malformed config or secret-bearing exception, when validation
  fails, then safe existing config/runtime diagnostics appear without
  raw input or native error text.

## Implementation source and responsibility map

| Owner / existing source | Allowed responsibility | Forbidden responsibility / boundary tests |
| --- | --- | --- |
| config/project_config.py (small private policy parser if needed) | Strict nested config, defaults/origin, immutable normalized policy | No adapter imports, execution, compiled fields. A1. Extract focused parser if loader grows. |
| adapters/runtime_safety.py | Private neutral request/evidence/registry and capability routing | No final policy decision or public API expansion. A3/A4/A9. |
| adapters/duckdb/runtime_scan_guard.py, duckdb/adapter.py | Local path/catalog proof, safe estimated input metadata, actual read-only binding/freshness and bounded transport on existing adapter | No user policy or Core status; no unsafe metadata, SQL rewrite, unbounded fetch, new executor. A2-A5/A7. Extract focused private collaborator rather than expanding generic adapter. |
| check_engine/scan_budget.py | Pure Core policy classification, typed proof validation, warning/blocked reasons and safe advice | No file/database I/O, dialect SQL, user asserted status or result comparison. A1-A6/A8. Share logic across families. |
| services/run.py | Existing profile/capability/lifecycle orchestration and policy/evidence handoff; actual binding proof before query | No numeric semantics, direct SQL, parallel runner, writer. A4/A7/A9. Extract bounded preparation collaborator rather than expanding existing large service. |
| check_engine/runtime.py, execution.py, key_safety.py, aggregate.py, engine.py | Route admitted checks, enforce matched proof, preserve existing check semantics and transport; private metadata handoff | No alternate policy, raw evidence exposure, direct public helper API break, hidden fallback. A4-A9. |
| cli/main.py, services/results.py | Preserve status/exit mapping; render safe run-only advisory warning | No general summary redesign, serialization change, warning-as-data-failure. A6/A8/A9. |

Allowed dependencies follow existing neutral Core/adapter boundaries;
avoid concrete DuckDB imports in service/engine. No public shape additions
without compatibility review. New helpers must be narrow and reusable,
not wrapper duplication. Review changed import/export surfaces and module
growth after GREEN; refactor same scope if owner boundaries drift.

## Implementation steps and detailed test plan

1. Config and pure policy RED/GREEN: A1, A2, A3.02, A5.02, A6.01,
   A9.01; preserve strict parser and no compiled schema changes.
2. Adapter evidence and binding RED/GREEN: A2-A5, actual pinned DuckDB
   tests; verify native read-only binding, no unsafe metadata call,
   no stale proof or unbounded result transport. Prove technical feasibility
   before expanding runtime admission; stop if a stronger public API or
   lifecycle refactor is required.
3. Runtime orchestration and row-count admission RED/GREEN: A4/A7;
   preserve existing dispatch, capability, lifecycle, prerequisite,
   aggregate precision and existing low-level helper tests. Apply the approved
   intentional row-count restriction and document migration.
4. Advisory/metadata and CLI RED/GREEN: A5/A6/A8/A9; exact warnings,
   hard blocks, redaction, no scope mutation or outputs; preserve
   non-run commands and existing exit mapping.
5. Cumulative integration: all rows, existing config/profile/adapter/
   compiler/check-engine/service/CLI suites, mandatory DuckDB semantics
   and pinned compatibility lanes. Run branch-wide regression decision
   advisory and pre-commit; remote fallback only under approved operational
   policy, no experimental machinery in final tree. Full CI and fresh
   cumulative review-fix until no actionable in-scope findings or blocker.

Each step requires current prework, RED evidence, GREEN and review before
advancing; do not infer passing tests from this test plan. Record actual
test nodes, revision, outcomes, gate evidence and remaining gaps. No
commit/push/merge without applicable approval.

## Regression carryover

Preserve all current capture rows and statuses. Applicable A-phase rows:
duckdb-view-external-scan-guard, duckdb-wal-sidecar-scan-guard,
key-safety-duckdb-relative-path-project-root,
key-safety-duckdb-identifier-case-metadata,
key-safety-duckdb-local-database-filename-suffix (A4);
key-safety-duckdb-metadata-open-failure-adapter-diagnostic (A3/A4/A8);
bounded-scan-docs-no-user-provided-classification (A1/A4/A9);
duckdb-private-bounded-aggregate-transport,
duckdb-private-typed-numeric-transport,
duckdb-private-aggregate-native-domain-guards,
duckdb-private-bounded-grouped-summary,
duckdb-private-aggregate-renderer-separation,
aggregate-native-service-lifecycle (A4/A5/A7/A8);
key-safety-invalid-relation-diagnostic-precedence and all aggregate
admission/runtime/capability/numeric/group-presence captures (A4/A7/A8);
yaml-diagnostic-redaction, yaml-profile-and-source-privacy,
aggregate-core-result-privacy, aggregate-service-output-privacy (A8/A9).
Retain parser/compiler, artifact and CLI behavior and their existing
capture obligations; later M8.2/M8.3 own final lifecycle/publication
carryover. Re-read index/rows at each step, add reusable captures for
new proven regression/requirement, never promote deferred statuses
without exact proof. Future test-kit carryover remains required.

## Affected docs and contract impact

At implementation update architecture/project-loading-and-config,
user-guide/project-structure and CLI usage, implementation/check-engine,
cli-services, errors-and-diagnostics and testing-plan, adapter-interface
and compatibility/adapter-api where affected, compatibility inventory and
matrix, this prework and ADR 0026, CHANGELOG Unreleased and migration
guidance for row-count restriction. Keep current-behavior docs truthful
until implementation; do not prematurely advertise configuration syntax
or capabilities. Private gate and prompts route the approved exact plan
and research; public docs contain only Recon-native decisions.

## Definition of Done and exit review

- Exact configuration and compatibility restriction approved; ADR accepted,
  docs and prompts current; no unresolved pre-implementation design issue.
- Every matrix variant has actual test proof or explicit approved
  non-applicability; real cross-version proof of local scope, binding and
  no scan after hard block, independent bounded transport, correct warnings.
- Existing supported check semantics and dependency floor preserved;
  intentional restriction documented, migration and changelog handled.
- No raw evidence leaks, no artifact/output/sink writes, no scope mutation,
  no production claim; no temporary CI files on mergeable branch.
- Actual regression decision, capture statuses, full branch validation,
  review-fix loop, design-integrity/responsibility review, local-success
  second pass, exact latest validated revision and user approval recorded.
- Revised phase exit must map A1-A13 and each capture to tests, docs, gates and next
  handoff; no orphan requirement. M8.2 starts only after exit and its own
  prework; M8.3 owns serialized schema and final CLI.

## Readiness verdict

Blocked: the prior approved design is historical only. Representative binding
feasibility remains useful evidence, not proof of resource safety or calibrated
defaults. Complete the reopened research and design prerequisites, reassess
compatibility and split, revise ADR 0026 and A1-A13 prework, obtain explicit
approval and integrate before TDD. Do not proceed against PR #32 baseline.
No new ecosystem repository is due. No runtime or gate completion claim.

## Type compatibility delivery checkpoint

Apply [Gate 4P mandatory type compatibility assignments](type-compatibility-assignments.md). Current strict physical-type execution boundaries remain unchanged. Future operation-aware lossless comparison and explicit conversion policies must be designed, implemented and proven; structural schema equality is not the same as value comparability. Do not infer compatibility from implicit engine casts. The assignment defines delivery ownership, not approved runtime behavior.

## Mandatory M9.5 delivery checkpoint

M9.5 owns the pending lossless type compatibility implementation. Review shared binding and corrected grouped SQL dependencies before M8.1 lock; do not implement type expansion implicitly in the resource-policy correction.

## Reopened next-action dependency

Follow the [M8 split assignment](milestone-8-split-assignment.md#reopened-execution-dependency-and-next-action): shared binding design and verified implementation precede the targeted M7.4 correction, which precedes remaining M8.1 calibration. Historical prework and experimental evidence do not authorize coding. The split and detailed M8.1.2 design are approved; implementation authorization remains separate.

## Execution scope restoration checkpoint

Apply [Gate 4Q execution scope restoration assignments](execution-scope-assignments.md). M8.1.1 temporary protected local base-table scope is implemented and verified on main (PR #38). Pending M10.8 owns S1-S5 local restoration/expansion, M13.5 S5 remote/S6 cross-context, M18 S7, M29 S8. No silent deferral, permanent scope restriction or unproven capability claim.

## M8.1.1 detailed prework checkpoint

See [M8.1.1 prework and exit evidence](milestone-8-1-1-prework.md) for private binding integration,
expanded acceptance/test matrix, approved lifecycle decision L1 and exit
proof. Scoped exit complete. M8.1.2 and targeted M7.4 correction retain separate owners and require their own design and coding approvals.

## Historical M8.1.2 resource policy handoff (superseded by approved checkpoint below)

M8.1.2 is the mandatory implementation owner of the reopened resource/default
design, not an optional later optimization. Execution order: M8.1.1
binding preflight (what will actually run) -> verified targeted M7.4
grouped SQL correction -> M8.1.2 resource preflight/admission (whether
the bound workload may run under effective policy) -> M8.2. M8.1 cannot
exit until both children and the correction are verified. M8.1.1 retains
the legacy 64 MiB key/SUM-only guard temporarily; neither it nor earlier
40/20 MiB proposals or experimental control values are approved defaults.
No footprint-derived universal workload ceiling, arbitrary replacement
threshold, or blanket rejection solely because an advisory estimate is
unknown. Scope proof and proven enforceable safeguards remain mandatory;
unknown required safety evidence fails closed. Reassess admission by
operation and actual available RAM/CPU/container/disk/headroom, explicit
user limits, engine-specific control guarantees and workload evidence.
Prove useful zero-config behavior for representative capable and constrained
machines, larger safe files/workloads and small expensive workloads, across
the pinned versions; avoid unnecessary restrictions without weakening safety.
Distinguish estimates/advisories, physical footprint, actual resource use,
bounded transport and engine/process controls. No executing production
preflight, silent sampling or fallback. Resolve R1-R10 and A1-A13, including
calibrated defaults, override precedence, unknown/unsupported cases,
native-control limits and earlier required cancellation/containment.
Use corrected actual Recon SQL and previous private research/CI evidence;
do not infer defaults from earlier experiments. If M8.2 protections are
required for admission, explicitly pull them forward with approved split
changes. Exact settings, thresholds, controls and detailed M8.1.2 prework
remain open; separate design approval, implementation and native exit proof
required.

## Historical adaptive resource direction and adapter carryover (see approved checkpoint below)

Maintainer-approved adaptive, adapter-aware, minimally restrictive local execution with portable best-effort protection, strict controls only when proven and isolation where necessary. Preserve native spilling and larger-than-memory work. No universal CI-derived ratios or caps. Distinguish execution scope from client transport, use engine-specific mechanisms and never downgrade required enforcement. Apply [Gate 4L adapter-specific resource applicability and proof](execution-resource-safety-assignments.md#mandatory-adapter-specific-resource-applicability-and-proof) to all future adapters and expansions. Exact settings, defaults, worker design and pulled-forward lifecycle requirements remain pending detailed prework and separate approval. No successor implementation authorized.

## Historical approved M8.1.2 integration checkpoint (2026-11-26; reopened 2026-11-27)

The maintainer-approved detailed design is in [M8.1.2 approved prework](milestone-8-1-2-prework.md); it supersedes
historical footprint-driven resource decisions and earlier pending-design
statements. Design approval is not implementation or exit approval. Existing
runtime remains unchanged until implementation. M8.1.1 and targeted M7.4
correction are verified on main. No default database size or workload timeout;
optional authored footprint ceiling applies to all nine local project check
families. Native managed resource targets are not physical quotas. The
DuckDB-specific 25% memory and 10% disk reserve candidates require actual
combined calibration before default lock; no universal ratio. Required scope
and controls fail closed; optional estimate uncertainty is not a blanket block.
M8.1.2 owns B8 one-worker cancellation/confirmed exit/parent liveness, B9
native/IPC/owned scratch cleanup and crash-safe recovery, B10 serial per-check
worker and re-observation prerequisites. M8.2 owns remaining run-wide
lifecycle, deadlines, retry, cumulative resources and concurrency; M8.3 C10
publication. Preserve all future adapter applicability, type and scope gates.
No gate closed; separate implementation authorization required.
