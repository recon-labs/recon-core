# M8.1.1 - Shared Database Binding Prework

Status: completed and merged in PR #38; exact tested head d513a249b926f05c8264d6790af163911c90b3a1, CI 45815181891 10/10, main merge 4d3ede5029a6f052d1c18c0ef62f176e0ae15868 with identical tree. Scoped J1-J12 exit approved; broader gates remain open. Historical design baseline
e89838985ff5906f2ec5e3aa393c9ba11dff60f5 (merged PR #35).
Split Decision: Already Split / Follow Existing Split. M8.1.1 -> targeted
M7.4 correction -> M8.1.2. Gate 4Q/S1-S8, 4L/R1-R10, 4P/T1-T10 apply.
ADR 0026 remains reopened for resource defaults.

## Approved scope and proposed binding contract

- Project-run typed same-context DuckDB row count, null/duplicate/missing/
  extra key checks and scalar/grouped SUM only. Uniform local base-table
  scope. Temporary row-count narrowing (views, outside-project files,
  external/attached/borrowed/in-memory contexts) approved; S1-S8 owners
  mandatory. Existing low-level prepared-adapter helpers unchanged and
  not safe project-run bypasses. No new query endpoint or type support.
- Fresh privately owned read-only connection per eligible check; one
  transaction for actual catalog proof, guards and final native comparison;
  rollback and close before final result. No writable fallback, arbitrary
  SQL, concurrent sharing or reuse. Per-check, not run-wide snapshot.
- Resolve existing regular file within project root. Verify resolved path,
  device/inode where meaningful, size, mtime_ns and sidecar absence before
  and after opening and before every data query; catalog path must identify
  the same approved file. Reject missing, invalid or observed drift.
  Trusted filesystem/cooperating processes only; not hostile race defense
  or an OS sandbox. Exact platform evidence failures fail closed.
- Existing 64 MiB key/SUM cap only; do not add row-count footprint limit.
  No new resource settings, estimates, deadlines or hard resource claims.
  M8.1.2 replaces legacy policy after corrected grouped SQL. No executing
  preflight.
- On actual owned transaction, parameterized native catalog lookup and
  unique local base-table match. ASCII-only identifier case normalization
  (not Unicode lower/casefold), actual catalog/schema/table spelling and
  existing quote escaping. Conservative ambiguity rejection retained;
  no guessing default schema or new dotted identifier grammar.
- Private ephemeral lease bound to check, typed operation, session and
  transaction generation, approved config, and two canonical Relation
  values. Core classifies admission from evidence; adapter enforces active
  lease and freshness immediately before each native query. Detached
  probe or caller-provided bool insufficient. No serialized lease/path/SQL.
- Preserve current strict key/numeric type guards, exact arithmetic, null/
  group semantics, bounded transport and public compile SQL. M9.5 owns
  cross-type retrofit. M7.4 optimization requires proven same binding.

## Integration and remaining decision

RunService keeps profile/capability setup, but replace detached final
admission with preliminary non-opening path/shape checks and actual
session-bound catalog proof. Preserve early path/cap blockers before
factory where possible; catalog-only blockers now require metadata open,
not data scan. Retain prerequisite, dispatch, plan and capability order.
Use private project-run context derived from _AggregateExecutionContext
or equivalent private collaborator, without public CheckExecutionContext,
CheckEngine.run or BaseAdapter signature change. runtime.py dispatches
eligible checks through shared private bound executor; existing family
logic consumes canonical relations and narrow bound query callable.
No duplicate runner, contract mutation or public renderer change.
Existing standalone adapter connect/execute/close stays as-is; private
native RO session must not call public writable connect. Injected
collaborators cannot bypass actual native proof. Private test seam only;
if public interface change is necessary, stop for compatibility review.

Order: preliminary scope -> setup/capabilities -> prerequisites/dispatch
-> open RO -> verify file -> BEGIN -> verify actual catalog and resolve exact relations ->
Core admission -> render existing typed plan -> verify active proof before
each native read -> evaluate bounded result -> rollback -> close -> finalize.
On error invalidate lease, rollback if begun, close if opened, preserve
primary and cleanup diagnostics, no retry/reuse.

## L1 - approved failure isolation and cleanup semantics

Maintainer approved check-local native failures on 2026-11-26. Preserve
existing service-level configuration failures (profile/factory/legacy
capability setup), aggregate check-level capability blocker, artifact,
plan, placement, rendering and prerequisite precedence. No native open
for checks that are blocked at dispatch or prerequisite stage. Other
eligible checks continue after a native failure only if all acquired
resources are confirmed released. Do not reuse sessions or retry a failed
check. For this initial in-process implementation no independent
containment is assumed when close is uncertain: latch a run-local native
execution stop, do not open any further native session, retain structural
and prerequisite blockers and previously finalized results. M8.2 can
extend isolation only with proof. Never report whole-run success.

All ERROR results below have executed=false, reason_code=None,
blocked_by empty and no value/failure-count or output references. The flag
means no trustworthy completed check result, not no SQL attempted.
NOT_EXECUTABLE has an existing reason and zero data SQL for scope refusal.
BLOCKED is reserved for actual prerequisite IDs; do not fabricate a
prerequisite for cleanup quarantine. Run/contract aggregate precedence
remains ERROR > FAIL > BLOCKED > NOT_EXECUTABLE > WARN > PASS > SKIPPED;
ERROR maps to RUNTIME_ERROR. Preserve existing distinct safe run-local
connection ordinals where required; no raw native exception, path,
relation, key, value, SQL or profile content in new diagnostics.

| Stage | Status/reason | Diagnostic code and fixed safe message |
| --- | --- | --- |
| Unsupported cross-context placement | not_executable / unsupported_execution_placement | RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED (existing) |
| Missing/outside/non-file/unapproved scope, sidecar, ambiguous/view/temp/external/catalog mismatch before lease | not_executable / bounded_local_scan_required | RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED: Check requires a verified local base-table execution scope. |
| Key/SUM file exceeds legacy cap | not_executable / scan_budget_exceeded | RC_RUNTIME_SCAN_BUDGET_EXCEEDED: Check exceeds the temporary local file limit. |
| Executing preflight requested | not_executable / unsafe_scan_preflight | RC_RUNTIME_UNSAFE_SCAN_PREFLIGHT (existing); no scan |
| Native open or BEGIN failure | error / none | RC_ADAPTER_CONNECTION_FAILED: Read-only execution session could not be opened or initialized. |
| Required metadata operation raises or returns malformed evidence | error / none | RC_RUNTIME_BINDING_PROOF_FAILED: Execution binding could not be verified. |
| Active lease wrong, ended, missing, drifted or invalidated | error / none | RC_RUNTIME_BINDING_PROOF_FAILED: Execution binding could not be verified. |
| Native read or strict type-guard query raises | error / none | RC_ADAPTER_QUERY_FAILED (existing sanitized family message) |
| Aggregate guard result not valid | error / none | RC_RUNTIME_AGGREGATE_RESULT_INVALID (existing) |
| Invalid row/key/aggregate result envelope | error / none | Existing family result-invalid diagnostic |
| ROLLBACK fails | error / none | RC_ADAPTER_CLOSE_FAILED: Read-only transaction cleanup failed. |
| CLOSE fails | error / none | RC_ADAPTER_CLOSE_FAILED: Read-only execution session cleanup failed. |
| Later eligible native work stopped by uncertain cleanup | error / none | RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE: Execution stopped because prior session cleanup could not be confirmed. |
| Failed/errored/non-executable prerequisite | blocked / prerequisite_failed, prerequisite_error or prerequisite_not_executable | RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE (existing, actual IDs) |

New diagnostic proposals are two Core-owned run codes above; use fixed
actionable hints (verify local file and supported relation, close other
writer if present, resolve cleanup before retrying) and error severity.
Do not copy exception messages. If a trustworthy data FAIL was evaluated
but cleanup fails, overall check becomes ERROR with no values, retain
safe primary failure diagnostic or fixed safe outcome note (including
row-count FAIL which may have no failure diagnostic), plus distinct
rollback/close diagnostics. If primary ERROR or scope refusal preceded
cleanup failure, retain its safe diagnostics and report ERROR.
If ROLLBACK fails but CLOSE succeeds, session released; unrelated
eligible checks may continue. If CLOSE is uncertain, stop subsequent
native work as above. Close attempt after rollback failure is required;
no claim of confirmed release from clearing a Python reference. A
finally-based ownership path closes on exceptions; a failed close is
reported, never hidden. On interrupted execution, preserve existing
interrupt behavior and attempt cleanup; no confirmed cancellation or
worker containment claim (M8.2). No new public result fields/statuses.

## Acceptance matrix and planned test nodes

New tests/adapters/test_duckdb_bound_execution.py and
tests/services/test_run_service_bound_execution.py. Names below are
planned nodes, not claimed existing tests. Use the expanded variant table below for exact outcomes, zero data SQL
where blocked, native truth and cleanup assertions; bind actual test node
IDs at RED/GREEN, not before tests exist. Four existing
pins 1.0.0/1.3.2/1.4.5/2.0.1.

| ID | Test and variants | Expected behavior |
| --- | --- | --- |
| J1 | test_preflight_never_opens_session: malformed artifact, shape, placement, query, prerequisite, tolerance, capability | Existing blocker; no native session/data |
| J2 | test_file_scope_admission: relative, absolute, suffix, missing, outside, symlink escape, directory, WAL/tmp, stat failure | Valid local succeeds; invalid scope blocks, no created file |
| J3 | test_legacy_footprint_policy: row_count/key/scalar/grouped, below/at/above 64 MiB | No row-count footprint block; key/SUM cap unchanged |
| J4 | test_qualified_relation_binding: one/two/three parts, non-main, ASCII case, Unicode distinct, quote, ambiguity, wrong catalog, view, temp, missing | Exact local identity or block; no first-match guessing |
| J5 | test_actual_session_and_aliases: same name, equal config alias, wrong config/adapter/file, RO/RW conflict | One owned RO session; no fallback |
| J6 | test_lease_invalidation: wrong check/operation/relation/session, ended transaction, path replacement, sidecar, metadata drift | No data SQL after invalidation; no stale pass |
| J7 | test_snapshot_and_guard_sequence: row/key/scalar/grouped, stable, writer conflict, same-type replacement, injected mutation | Native consistent result or explicit error |
| J8 | test_read_only_and_cleanup: success, open/begin/metadata/guard/query/rollback/close, primary plus cleanup | Approved L1 semantics; primary error retained; no leak/reuse |
| J9 | test_mixed_checks_and_prerequisites: failed predecessor, connection failure, unrelated success, uncertain cleanup, alias | Approved L1 precedence; no dependent SQL |
| J10 | test_bound_native_semantics: all nine existing check types; pass/fail, empty, null, composite, type mismatch, numeric boundaries | Current supported semantics, bounded transport, strict guards |
| J11 | test_scope_restrictions_and_public_contracts: view/outside/attached/external/memory/borrowed/helper/compile SQL | Explicit temporary blocks; no API/compile/artifact regressions |
| J12 | test_sensitive_diagnostics_and_no_writes: config, path, catalog, SQL, native error, values, keys, stale outputs | Safe output; source and compiled artifacts unchanged |

Existing carryover suites: tests/adapters/test_runtime_safety.py,
test_duckdb_adapter.py, test_duckdb_sql_renderer.py,
test_duckdb_aggregate_runtime_renderer.py, test_duckdb_aggregate_numeric_domains.py,
test_duckdb_aggregate_transport.py; tests/check_engine/test_row_count_execution.py,
test_key_safety_execution.py, test_aggregate_execution.py; tests/services/
test_run_service_duckdb_execution.py, test_run_service_adapter_lifecycle.py,
test_run_service_aggregate_admission.py; tests/compatibility/test_python_package_exports.py.
In particular existing tests for view/external, WAL, metadata case, suffix,
same-context aliases, wrong factory connection, metadata probe failure,
connect failure before engine, close failure, mixed native aggregates
and privacy must be reviewed. No deletion or weakening except explicit
approved stage/scope reclassification with equivalent no-data proof.

## BDD and ownership

Valid local check uses one verified snapshot and cleanup before final result.
Unsupported/ambiguous/stale scope never executes data SQL. Writer conflict
never falls back. Invalid plan or blocked prerequisite never opens a native
session. Failure plus cleanup preserves primary outcome and truthful
overall error. Matching and differing data retain current native semantics
and privacy. Mixed checks obey L1.

| Source | Responsibility |
| --- | --- |
| services/run.py | setup/prechecks/private context/failsafe cleanup/service status |
| check_engine/engine.py, runtime.py | prerequisites/dispatch/check-scoped orchestration |
| adapters/duckdb/runtime_scan_guard.py, adapter.py, private proposed _bound_execution.py | native evidence, owned transaction/lease/query |
| check_engine/scan_budget.py | Core admission and temporary cap classification |
| execution_support.py, execution.py, key_safety.py, aggregate.py | bound inputs and existing comparison semantics |
| existing runtime renderers | qualified typed SQL, no compile changes |
| compatibility and tests | public contract review, native and negative conformance |

## Split, gates and exit

M8.1.1: A4/A7/A8/A13 binding portions, B9 prerequisite cleanup,
T7/T8/T9/T10, temporary S restrictions, applicable R5/R6/R8/R10.
M7.4 correction: grouped SQL and pinned semantic/scale proof.
M8.1.2: remaining A1-A13/R1-R10 and any B8-B10 controls required earlier.
M8.2: full lifecycle and remaining B1-B10; M8.3: C1-C10.
Gate 4Q/4I/4L primary; 4A/4B/4C/4J, 5, 3F2/6, 8C, 4P,
1A, 4O/3A numeric preservation applicable; 5E no new writer.
ADRs 0021/0026/0022/0014/0009/0020 as applicable. Review matching capture
routes and rows: view-external, WAL, relative path, identifier case, suffix,
capability, metadata-open, bounded docs, native transport/domain/summary/
renderer/lifecycle and privacy/check-engine/CLI. No status change on planning.
Assignment-family orphan check complete; expanded matrix and public
compatibility disposition below. Gate implementation proof remains pending.

Research: prior pinned feasibility runs 45789213714, 45790491531 and
45798041091 justify dependency and native design, not actual Recon
integration, full compatibility or hard resource controls. Test actual
generated SQL and supported versions before exit. No extra experiment
needed to approve direction; stop if feasibility fails.

Implementation order after approval: (1) RED/GREEN native path/catalog/
transaction/cleanup, (2) RED/GREEN lease/qualified binding/admission,
(3) RED/GREEN service integration and L1/prerequisites/all check families,
(4) native semantic/privacy/public contract regression + docs/changelog,
(5) full required CI, regression-capture decision, cumulative review,
gate proof and exit approval. Review the expanded variants and test references below,
finalize compatibility and design review before code. Ruff format/lint, mypy, pytest,
pinned native suites, pre-commit and capture routing required. When local validation is unavailable, follow the equivalent validation
policy in milestone-process.md; required runtime proof cannot be waived. M7.4 correction
blocked until verified M8.1.1 exit. The original prework required separate
implementation approval; that approval was granted before PR #38.


## Expanded acceptance requirements (original plan)

Codes below refer to L1 or existing family-specific validation. Each
failure variant asserts safe messages, no source values on non-executed
results, no fallback/retry, and appropriate resource ownership counts.
N = new native adapter test file; S = new RunService integration test file
named above. Parameterized names are planned test IDs; all four pins must
execute native coverage with RECON_REQUIRE_DUCKDB_TESTS=1, not skip it.

| Family / planned node | Required independent variants and truth | Expected result / no-data proof |
| --- | --- | --- |
| J1 S::test_preflight_never_opens_session | invalid artifact, invalid typed shape, reserved placement/materialization, unsupported query, malformed relation, blocked rendering, unresolved tolerance, missing prerequisite, unsupported capability | existing family-specific error/not_executable/blocked or service configuration error; zero owned open, no data SQL; for each compare to existing baseline node |
| J2 N/S::test_file_scope_admission | local relative, local absolute, arbitrary suffix, same canonical symlink inside root | admit; same actual canonical file and identity; no created file; 1 RO open/BEGIN/ROLLBACK/CLOSE |
| J2 N/S::test_file_scope_admission | missing, directory, nonregular, outside, symlink escape, retained WAL/tmp, inaccessible stat | scope refusal, bounded_local_scan_required; no data SQL; early path checks before factory/open where possible; no new DB |
| J3 N/S::test_legacy_footprint_policy | size cap-1, cap, cap+1 (unit policy evidence); native representative below and above cap using bounded fixture | key/SUM allowed at/below, scan_budget_exceeded above; row count still admitted all sizes if scope proven; no physical scan-bound claim |
| J4 N/S::test_qualified_relation_binding | src, main.src, actual_catalog.main.src, explicit other.src, ASCII case variant, embedded quote, distinct non-ASCII tables | exact expected table by independent count/data truth, qualified identifiers; preserve existing parsing; no wrong-table match |
| J4 N/S::test_qualified_relation_binding | unqualified duplicates across schemas, wrong explicit catalog/schema, missing, ordinary and external-backed view, temp/attached | bounded_local_scan_required; no data SQL, no automatic attach/extension load |
| J5 S::test_actual_session_and_aliases | one profile name, two identical normalized config names, wrong factory config/name/type, different contexts | one fresh native RO connection per eligible check; wrong factory metadata existing config rejection, different context unsupported placement; no data on block |
| J5 N/S::test_actual_session_and_aliases | preexisting same-file RW connection, RO/RO coexistence, close then retry in independent invocation | RW conflict ERROR connection code, no fallback; allowed RO reads; fresh later invocation works |
| J6 N/S::test_lease_invalidation | mismatched check, operation, source/target, session token, ended transaction, replayed lease, file replacement/size/mtime drift, sidecar appears after admission | ERROR binding proof code; no subsequent native read (including hidden DESCRIBE); earlier attempted query not concealed |
| J7 N/S::test_snapshot_and_guard_sequence | row count, each key type, scalar and grouped sum; one native connection, actual guard SQL order, scope metadata read in transaction, final SQL qualified; stable input | exact native truth; one transaction, no mutation/intervening caller SQL, no stale proof |
| J7 N/S::test_snapshot_and_guard_sequence | conflicting writer/attempted temp shadow/DDL/replace via test seam, invalidated session between aggregate guards and final | native lock rejection, verified original snapshot, or explicit error before next data read; never wrong-table/false pass. Prior two-RW snapshot experiment not proof of RO/RW coexistence |
| J8 N/S::test_read_only_and_cleanup | normal pass/fail, open fails, BEGIN fails, metadata raises, guard raises, query raises, malformed result | exact L1 code/shape; rollback iff begun, close iff acquired; no publish before cleanup |
| J8 N/S::test_read_only_and_cleanup | rollback raises and close succeeds; close raises; rollback+close raise; primary error/fail plus each cleanup variant | ERROR no values; distinct cleanup and safe primary diagnostics; no repeat use; release only when close success |
| J9 S::test_mixed_checks_and_prerequisites | first check open/query error, dependent blocked, unrelated check same file and different file (cleanup confirmed) | ERROR, prerequisite_error, unrelated native pass/fail, run runtime error; no dependent data |
| J9 S::test_mixed_checks_and_prerequisites | first check close uncertain, independent and aliased remaining checks, dependent, malformed plan | first ERROR; later eligible native ERROR context unavailable without open; actual dependents BLOCKED, structural blockers unchanged; no continuation of native work |
| J10 S::test_bound_native_semantics | row_count_diff; null_source_keys/null_target_keys; duplicate_source_keys/duplicate_target_keys; missing_keys/extra_keys; sum_diff/grouped_aggregate_diff; matching and differing truth, empty, null and composite, exact domains, tolerance boundary/nonfinite as existing | baseline status/reason/value semantics where allowed; strict physical mismatches remain prior error; all nine types, preserve existing full native numeric suite |
| J11 S::test_scope_restrictions_and_public_contracts | previously executable ordinary row-count view/outside-root file/large local base table; attached/external/in-memory/borrowed; direct prepared low-level helper and unchanged compile SQL | first two now explicitly not_executable; large local row count not capped; unsupported contexts not newly admitted; legacy helper/API/compiled artifacts unchanged |
| J12 N/S::test_sensitive_diagnostics_and_no_writes | injected path/catalog/profile/SQL/key/value/error sentinels, same/different failed connections, stale generated outputs, actual source DB bytes | sanitized code/message/hint/context, distinct safe ordinals, immutable source/compiled artifacts and no new outputs |

Resource proof does not assume a test spy is production admission.
Keep old native tests for full numeric boundary matrix and exact SQL
renderer snapshots. Explicitly test every native read call site,
including metadata fallback in _read_aggregate_result's DESCRIBE
path. Use bounded metadata retrieval (at most two matches to reject
ambiguity), never fetch table rows to prove scope.

## Compatibility and regression carryover disposition

Reviewed public-contract-inventory.md, adapter-api.md, compatibility-matrix.md,
current CheckResult/CheckReason constraints, prerequisites and service exit
mapping. Preserve BaseAdapter, SqlRenderer, Relation, QueryResult, exported
prepared-helper and CheckExecutionContext/CheckEngine signatures,
ADAPTER_API_VERSION=1, compiled schema and SQL, check status/reason enums,
native type/transport contract and CLI categories. Intentional behavioral
changes: row-count scope restriction; native open/cleanup failure timing
and isolation; catalog refusal after metadata-only open rather than before
factory; explicit legacy cap diagnostic; two additive safe runtime
diagnostics. No version bump or new user config. Update actual capability,
CLI, errors, testing and changelog/known-limitations docs only with
verified implementation. No production claims. M10.8/M13.5/M18/M29 own S
delivery; M9.5 owns T expansion; M8.1.2 owns resource defaults.

| Capture rows (existing stable IDs) | Assigned proof |
| --- | --- |
| hidden-bounded-local-fixture-marker-removed; duckdb-view-external-scan-guard; duckdb-wal-sidecar-scan-guard; key-safety-duckdb-relative-path-project-root; key-safety-duckdb-identifier-case-metadata; key-safety-duckdb-local-database-filename-suffix; bounded-scan-docs-no-user-provided-classification | J2/J3/J4/J11, retain non-executing safety |
| key-safety-adapter-capability-preflight; key-safety-duckdb-metadata-open-failure-adapter-diagnostic; aggregate-native-service-lifecycle | J1/J5/J8/J9, stage change explicitly approved |
| duckdb-private-bounded-aggregate-transport; duckdb-private-typed-numeric-transport; duckdb-private-aggregate-native-domain-guards; duckdb-private-bounded-grouped-summary; duckdb-private-aggregate-renderer-separation | J6/J7/J10/J11, grouped optimization remains separate |
| python-package-import-surface-guard | J11 |
| key-safety-shape-blocker-precedence; duplicate-key-excludes-null-containing-tuples; key-safety-empty-grain-keys-shape-blocker; key-safety-invalid-relation-diagnostic-precedence; key-safety-prerequisites-block-dependent-checks | J1/J9/J10 |
| aggregate-admission-typed-plan-boundary; aggregate-admission-tolerance-policy; aggregate-admission-endpoint-precedence; aggregate-runtime-scan-preflight; aggregate-runtime-private-routing; aggregate-runtime-capability-isolation | J1/J3/J5/J6/J7/J9 |
| aggregate-core-numeric-comparison; aggregate-core-grouped-summary; aggregate-native-service-numeric-semantics; aggregate-native-service-group-presence | J7/J10 |
| aggregate-core-result-privacy; aggregate-service-output-privacy; yaml-diagnostic-redaction; yaml-profile-and-source-privacy | J8/J11/J12; retain original parse/compile fixtures |
| compiled-artifact-yaml-loader-diagnostics; compile-command-terminal-contract | J1/J11/J12; no writer or compile command changes |

All listed capture statuses unchanged. Review actual diff against routing
at each RED/GREEN and exit, including new service tests (explicit route if
not matched), record covered/migrated/deferred only under gate policy with
actual exact nodes. Existing primary-owner M8 carryovers for publication,
privacy and CLI remain assigned to M8.2/M8.3 where not touched. No orphaned
requirement at this prework assignment level. Final design integrity review
and separate implementation approval were required before coding. Exit review
remains required.

## Equivalent validation when local execution is unavailable

Local execution is preferred, not a prerequisite when unavailable. Required
validation and milestone gates remain unchanged. Use equivalent repository
revision/diff inspection and CI proof without a separate local-execution
waiver. Pin base/head, inspect complete changed surfaces, review all
applicable gates, acceptance/test ownership, compatibility, privacy,
design integrity and orphaned requirements. Review branch-wide regression
capture decisions using the actual advisory command or an explicitly
documented equivalent inspection of its routing and capture requirements;
never claim an unexecuted command ran.

Prefer existing CI on the exact revision, including required pre-commit,
lint, formatting, typing, tests and supported native-version suites. Verify
actual jobs, commands, results and skips; preserve test-first RED/GREEN
and cumulative review requirements. When required proof is unavailable
from existing jobs, use narrowly scoped temporary CI validation on an
isolated branch with bounded synthetic fixtures, exact revision/version
and commands, minimum permissions, no secrets or production data, and
verified removal of temporary files. No temporary execution infrastructure
on main or product branches. Respect repository security and branch
protection. Record exact evidence, equivalent checks, missing proof and
cleanup. Missing required proof remains a blocker to readiness or gate
satisfaction, not a reason to weaken tests. Ordinary design, implementation,
merge and release approval requirements are unaffected.


## Historical implementation checkpoint (superseded by verified exit)

Draft PR #38 implements the approved shared binding mechanism. The initial
integration baseline and expanded acceptance have passed full CI, including
all four supported DuckDB pins. The final branch revision, remaining
acceptance variants, cumulative gates and merge approval are not yet closed.

Verified baselines: 84f9f6a8a99f34b3820dc0b8c966401a37472d05 (CI 45808726861),
f4324161f7229d7b6325fd897b991be16363c599 (CI 45809322900), and
3391f9a19503ee9a937f3252ece3f5c3a680dd00 (CI 45809868971), all ten jobs
successful. New coverage and documentation after those revisions require
exact-head validation; baseline evidence does not substitute for it.

No resource-default or grouped SQL optimization has been implemented.
The temporary 64 MiB key/SUM footprint restriction and uncapped row count
remain as approved. This is not a resource bound or a filesystem sandbox.


## Exit acceptance evidence inventory (PR #38)

The implementation review retains the original J1-J12 requirements above.
The following is a mapping to actual tests, not a replacement acceptance
matrix. Prefixes: N = `tests/adapters/test_duckdb_bound_execution.py`;
S = `tests/services/test_run_service_bound_execution.py`;
A = `tests/services/test_run_service_aggregate_admission.py`;
D = `tests/services/test_run_service_duckdb_execution.py`;
L = `tests/services/test_run_service_adapter_lifecycle.py`.
Evidence was verified on the exact final PR head before exit (see status above).

| Requirement | Actual regression evidence |
| --- | --- |
| J1 | S::test_preflight_never_opens_session; A::test_aggregate_plan_rejects_unsupported_shape_before_profile, test_unresolved_named_aggregate_policy_blocks_before_profile, test_aggregate_missing_prerequisite_blocks_before_profile, test_aggregate_service_requires_capabilities_before_connect; D::test_run_service_blocks_unsupported_placement_or_materialization_before_adapter_setup, test_run_service_preserves_key_safety_invalid_relation_before_profile_loading; L::test_run_service_reports_missing_compiled_contract_before_profile_or_adapter_work. Existing artifact-loader negative tests retained. |
| J2 | N::test_file_scope_admission, test_local_file_identity_preserves_canonical_path, test_local_file_identity_refuses_stat_failure, test_nonregular_file_scope_is_refused; S::test_row_count_missing_file_does_not_create_database, test_outside_project_row_count_refuses_without_open; D::test_run_service_allows_key_safety_duckdb_local_database_without_duckdb_suffix, test_run_service_resolves_relative_duckdb_profile_paths_from_project_root. |
| J3 | A::test_legacy_footprint_policy (all four check families, cap-1/cap/cap+1), test_large_native_database_does_not_cap_row_count; actual local fixtures in the native suites. |
| J4 | N::test_qualified_relation_binding_and_owned_cleanup, test_qualified_relation_binding_preserves_distinct_unicode_tables, test_bound_query_reads_canonical_relation, test_quoted_relation_and_temp_shadow_keep_exact_binding, test_actual_attached_catalog_is_not_local_base_table, test_mismatched_table_metadata_is_invalid_evidence; S::test_row_count_refuses_view_scope; D::test_run_service_blocks_key_safety_duckdb_view_over_external_file_before_adapter_setup. |
| J5 | S::test_actual_session_and_aliases_writer_conflict, test_legacy_family_wrong_factory_binding_never_opens, test_project_run_never_borrows_or_closes_supplied_connection; A::test_aggregate_rejects_wrong_factory_connection_before_open, test_native_aggregate_same_context_alias_and_mixed_checks; D::test_run_service_executes_row_count_for_same_context_duckdb_aliases, test_run_service_executes_key_safety_for_same_context_duckdb_aliases, test_run_service_blocks_cross_context_duckdb_execution_without_bridge_or_fallback. |
| J6 | N::test_lease_invalidation, test_scope_refusal_cannot_be_rebound, test_file_drift_invalidates_active_lease, test_owned_session_refuses_new_sidecar, test_lease_rejects_wrong_transport_family, test_aggregate_describe_cannot_bypass_invalidated_binding, test_malformed_catalog_evidence_is_not_scope_refusal. |
| J7 | A::test_all_nine_checks_use_owned_transaction_and_qualified_queries, test_binding_drift_between_aggregate_guards_stops_final_read; N::test_quoted_relation_and_temp_shadow_keep_exact_binding, test_file_drift_invalidates_active_lease; S::test_actual_session_and_aliases_writer_conflict. |
| J8 | N::test_owned_session_cleanup_failures, test_malformed_catalog_evidence_is_not_scope_refusal; S::test_native_row_count_uses_owned_read_only_session, test_primary_outcome_retained_on_cleanup_failure (data failure, scope refusal and query error crossed with rollback, close and combined cleanup failures); A::test_native_aggregate_lifecycle_and_failure_privacy; L::test_run_service_preserves_execution_failure_when_close_also_fails, test_run_service_reports_connect_failure_without_engine_execution, test_run_service_reports_close_failure_after_success. Existing invalid result envelopes retained. |
| J9 | S::test_cleanup_failure_is_check_local_or_stops_native_execution (including independent same-context alias and malformed plan), test_native_failure_isolation_across_database_files, test_mixed_native_failure_preserves_unrelated_database; existing prerequisite regression suites. |
| J10 | A::test_all_nine_checks_use_owned_transaction_and_qualified_queries, test_native_aggregate_service_numeric_outcomes_and_privacy, test_native_aggregate_service_null_and_empty_outcomes, test_native_grouped_service_distinguishes_absence_from_null, test_native_grouped_service_rejects_incompatible_key_types, test_native_grouped_service_high_cardinality_remains_private, test_native_aggregate_service_exact_overflow, test_native_aggregate_service_arbitrary_integer_availability; D::test_run_service_executes_actual_duckdb_key_safety_failures_without_raw_output, test_run_service_executes_actual_duckdb_key_safety_empty_side_cases; existing native numeric, key and row-count suites. |
| J11 | S::test_row_count_refuses_view_scope, test_outside_project_row_count_refuses_without_open, test_project_run_never_borrows_or_closes_supplied_connection; N::test_actual_attached_catalog_is_not_local_base_table, test_memory_and_nonlocal_catalog_are_not_local_binding; A::test_large_native_database_does_not_cap_row_count; existing adapter/renderer/helper and package-export tests. New architecture test: tests/check_engine/test_execution_boundaries.py::test_project_binding_runner_does_not_depend_on_check_family. |
| J12 | S::test_native_failure_isolation_across_database_files, test_primary_outcome_retained_on_cleanup_failure; A::test_native_aggregate_cli_privacy_and_artifact_immutability, test_aggregate_factory_diagnostics_do_not_publish_private_data, test_aggregate_lifecycle_preserves_distinct_connection_failures; D::test_run_service_does_not_mutate_stale_outputs_during_actual_key_safety, test_run_service_does_not_mutate_stale_outputs_during_executable_row_count. Existing redaction tests retained. |

## Gate disposition at exit review

Dispositions below are scoped to this implementation; exact-head verification
and maintainer exit approval are complete. They do not close
cross-cutting gates globally.

| Gate | Local disposition and carryover |
| --- | --- |
| 4Q | J2/J4/J5/J11: approved temporary local base-table scope; S1-S5 local restoration remains mandatory at M10.8, remote S5/S6 at M13.5, S7 at M18, S8 at M29. No permanent restriction. |
| 4I | J1/J5/J6/J7/J10: same-context only, actual owned binding, no implicit movement, no writable or unbound fallback. Other placements remain gated. |
| 4L | J2/J3/J6/J7/J8/J12: A4/A7/A8/A13 binding portions; R5 actual scope, R6 prerequisite cleanup only, R8 safe in-memory diagnostics only, R10 pinned semantic/boundary evidence only. Legacy footprint is not workload evidence or resource enforcement. Remaining A1-A13/R1-R10, measured useful defaults and native controls belong to M8.1.2; remaining B8-B10 to M8.2 unless required earlier. |
| 4A / 4J | J1/J5/J12: preserve profile loading, capability setup, actual factory identity and redaction; no new profile format or secret transport. |
| 4B / 4C | J1/J5/J6/J10/J11: private adapter-neutral lease and shared execution-support seam; public adapter API/version, typed operations, compile SQL and low-level prepared helpers unchanged. |
| 1A / 5 | J1/J8/J9: actual dependency precedence and approved L1 cleanup prerequisite (B9) only. Full lifecycle, timing, deadlines, cancellation and aggregation work remains M8.2; publication M8.3. |
| 3F2 / 6 | J8/J9/J12: fixed safe diagnostic categories, primary/cleanup preservation, no raw source/target/native error or generated output. Later privacy/publication obligations remain. |
| 3A / 4O | J7/J10: strict existing SUM/numeric and grouped semantics retained, no expanded numeric/type capability. |
| 4P | J4/J6/J7/J10/J12: T7 binding, T8 existing typed boundary, T9 safe existing outcomes, T10 pinned local proof for present scope. Mandatory lossless cross-type retrofit remains M9.5. |
| 8C | J4/J7/J10/J11: native semantic and four-version compatibility for the existing local path; grouped SQL optimization is separate corrective work, resource calibration M8.1.2 and shared conformance M29 remain pending. |
| 5E | Not applicable to new writer behavior: no writer or generated artifact contract added; immutability regression evidence retained. M8.3/M9 obligations unchanged. |

Capture decisions: new stable rows `duckdb-owned-project-binding` and
`project-binding-check-local-cleanup` cover the current Core regression
scope. Existing future adapter-testkit, privacy, publication, CLI and
parser/compiler carryovers retain their owning milestones and explicit
deferred status; do not mark them satisfied by Core-only evidence. The
branch-wide advisory was reviewed through equivalent exact-head routing (45 paths, 88 routes, 46 rows, six gates, no pending or missing routed decisions); local command was not executed. No successor implementation or merge without approval.
