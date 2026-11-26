# M8.1.1 - Shared Database Binding Prework

Status: proposed detailed prework, not authorization to code. Core baseline
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

L1 (pending maintainer approval): current RunService opens connections
before engine and aborts whole run on connect failure. Recommend new
native open/begin/metadata/guard/query failures are check-local ERROR,
executed=false, dependent checks blocked; unrelated eligible checks may
continue when safe. Existing service-level profile/factory/capability
configuration failures and aggregate capability blocker semantics remain.
Run/CLI overall error precedence preserved. On cleanup failure, never
publish unqualified PASS; proposed ERROR with no result values, retain
primary outcome/diagnostics safely. Do not imply no SQL attempted from
executed=false. If cleanup state uncertain, stop further work for affected
context; unrelated context only when containment is proven, otherwise
abort remaining work. Exact diagnostic and status mapping, including
cleanup and dependency precedence, must be reviewed/approved. Alternative
whole-run abort requires explicit orchestration mechanism, not a redundant
pre-opening connection. Catalog-only safety refusal becomes check-level
not_executable before data query; retain existing safe reason taxonomy.
No coding before L1 and full compatibility/gate review.

## Acceptance matrix and planned test nodes

New tests/adapters/test_duckdb_bound_execution.py and
tests/services/test_run_service_bound_execution.py. Names below are
planned nodes, not claimed existing tests. Each variant requires exact
expected status/reason/diagnostics, zero data SQL where blocked, native
truth and cleanup assertions; expand before RED commit. Four existing
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
| J10 | test_bound_native_semantics: all seven existing check families; pass/fail, empty, null, composite, type mismatch, numeric boundaries | Current supported semantics, bounded transport, strict guards |
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
Assignment-family orphan check complete; detailed variants, gate satisfaction
and final public compatibility inventory pending.

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
gate proof and exit approval. Expand exact variants and test references,
finalize compatibility and L1 before code. Ruff format/lint, mypy, pytest,
pinned native suites, pre-commit and capture routing required. Prior local
waivers for #34/#35 docs do not waive runtime validation. M7.4 correction
blocked until verified M8.1.1 exit. No implementation approval.
