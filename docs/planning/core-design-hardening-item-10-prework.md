# Core Design Hardening Item 10 Prework

## Purpose

This is the prework artifact for final-order item 10: remove hard-coded DuckDB
SQL renderer defaults from check execution.

Item 10 is high-risk because it touches SQL rendering, check execution, adapter
execution, diagnostics, current `recon run` behavior, and future adapter
compatibility. This artifact locks the implementation boundary before coding.
It does not implement runtime behavior.

Split Decision: Already Split / Follow Existing Split.

The broader hardening branch already split this work away from capability and
runtime-safety semantics, DuckDB renderer decomposition, external adapter
package registration, aggregate runtime execution, and `BaseAdapter` metadata
responsibility splitting. Item 10 should remain a focused renderer-binding
cleanup.

## Scope

Item 10 prework covers:

- current row-count execution renderer fallback behavior,
- current grain-key safety execution renderer fallback behavior,
- runtime execution-context renderer wiring,
- current DuckDB `recon run` behavior preservation,
- direct check-engine helper behavior when no renderer is supplied,
- affected tests, diagnostics, compatibility, privacy, and documentation,
- implementation-readiness criteria for the next coding pass.

The selected design is conservative: keep the current in-core DuckDB renderer
available for current DuckDB runtime execution, but register or inject it
through runtime setup and execution context instead of creating it inside
low-level check execution helpers.

Runtime setup must preserve the existing connector-neutral `RunService`
boundary. `RunService` may receive renderer wiring from a neutral default
renderer helper, a renderer registry, or injected execution-context
construction, but it must not directly import `DuckDbSqlRenderer` or any
`recon_core.adapters.duckdb.*` module.

## Non-Goals

Item 10 prework and implementation must not implement:

- external adapter package discovery,
- Python entry-point loading,
- renderer registries for third-party packages,
- adapter API version changes,
- capability name changes,
- SQL renderer decomposition,
- aggregate runtime execution,
- query endpoint execution,
- cross-adapter execution,
- cross-connection bridging,
- materialization or staging,
- hidden Python fallback,
- production scan-budget settings,
- run-result, evidence, report, failure-detail, state, or sink output,
- `BaseAdapter` metadata-method splitting.

## Current Audit Findings

Current code has the needed execution-context shape but still has hidden DuckDB
fallbacks in the execution helpers:

- `CheckExecutionContext` already has `renderers_by_adapter_type`.
- `CheckEngine` asks `_renderer_for_adapter()` for a renderer by adapter
  `adapter_type` and passes the result into row-count or key-safety helpers.
- `RunService` currently creates `CheckExecutionContext` with adapters,
  connections, and scan-budget decisions, but does not populate
  `renderers_by_adapter_type`.
- `check_engine/execution.py` imports `DuckDbSqlRenderer` and instantiates it
  when `execute_row_count_check()` receives no renderer.
- `check_engine/key_safety.py` imports `DuckDbSqlRenderer` and instantiates it
  when `execute_key_safety_check()` receives no renderer.
- Existing direct helper tests call row-count and key-safety execution helpers
  without explicit renderers, so those tests currently depend on the hidden
  fallback.
- Existing engine tests cover incompatible or absent renderer behavior for a
  non-DuckDB adapter, but they do not prove a DuckDB adapter with no renderer
  fails instead of defaulting.

Current behavior to preserve:

- `recon run` works for current same-context DuckDB relation-backed row-count
  execution.
- `recon run` works for current same-context DuckDB relation-backed grain-key
  safety execution when the bounded local/dev scan guard allows execution.
- Current row-count and key-safety execution stay relation-backed only.
- Current unsupported placement, materialization, query endpoint, malformed
  relation, scan-safety, capability, adapter setup, adapter lifecycle, renderer
  failure, empty renderer output, result parsing, and privacy diagnostics remain
  structured.

## Renderer Binding Decision

Check execution helpers should not own dialect default selection.

Renderer ownership for current runtime execution should be:

| Layer | Allowed responsibility | Forbidden responsibility |
| --- | --- | --- |
| `RunService` runtime setup | Build the execution context for current runtime candidates using renderer wiring supplied by neutral helpers or injection. | Rendering SQL directly, choosing renderer behavior inside check-family logic, importing `recon_core.adapters.duckdb.*`, or importing future connector packages. |
| `CheckExecutionContext` | Carry adapters, connections, scan decisions, and renderer instances keyed by adapter type. | Creating renderer defaults lazily. |
| `CheckEngine` | Resolve the renderer from execution context for the resolved adapter type before calling check-family helpers. | Falling through to dialect-specific defaults when the renderer map is missing. |
| Row-count execution helper | Validate row-count plan shape, endpoints, context, renderer compatibility, render query, execute adapter query, and parse result. | Importing or instantiating `DuckDbSqlRenderer`. |
| Key-safety execution helper | Validate key-safety plan shape, identity, endpoints, context, scan decision, renderer compatibility, render query, execute adapter query, and parse result. | Importing or instantiating `DuckDbSqlRenderer`. |

The current in-core DuckDB default remains allowed only at the runtime setup
boundary for the current in-core DuckDB development adapter, and must be exposed
to `RunService` through connector-neutral construction. Future external adapters
must still be gated by package registration or explicit injected registries;
item 10 must not invent that mechanism.

## Expected Behavior

For current CLI behavior:

- `recon run` must keep executing current supported DuckDB row-count checks.
- `recon run` must keep executing current bounded local/dev DuckDB key-safety
  checks.
- Unsupported, blocked, or unsafe checks must keep returning non-execution or
  structured error outcomes as they do now.

For direct check-engine/helper behavior:

- A row-count or key-safety helper that reaches SQL rendering without an
  explicit renderer must not create `DuckDbSqlRenderer()`.
- Missing renderer must produce a structured diagnostic before adapter query
  execution.
- Mismatched renderer `adapter_type` must still block before rendering.
- Malformed or exception-raising renderer metadata must stay sanitized.
- Renderer exceptions and empty renderer output must still be structured and
  must not query the adapter.

The preferred diagnostic for a missing renderer is
`RC_ADAPTER_RENDERER_METADATA_INVALID`, matching the existing renderer metadata
diagnostic family. If implementation discovers this code is too broad for the
runtime execution path, add a new runtime renderer diagnostic only with a
compatibility-doc update in the same pass.

## Acceptance And Conformance Matrix

| Case | Expected behavior | Required implementation coverage |
| --- | --- | --- |
| Row-count helper receives no renderer | Structured renderer diagnostic; no adapter query; no DuckDB renderer default. | Add a row-count helper test. |
| Key-safety helper receives no renderer | Structured renderer diagnostic; no adapter query; no DuckDB renderer default. | Add a key-safety helper test. |
| Engine receives DuckDB adapter without renderer map entry | Structured renderer diagnostic or not-executable result; no adapter query; no hidden DuckDB fallback. | Add an engine-level DuckDB missing-renderer test. |
| Engine receives explicit DuckDB renderer | Row-count and key-safety execution still succeed when other execution gates allow them. | Update or add engine tests using `renderers_by_adapter_type`. |
| Run service builds current DuckDB runtime context | Current supported DuckDB `recon run` row-count and key-safety flows still execute. | Preserve existing run-service tests and add a focused context/wiring assertion if needed. |
| Non-DuckDB adapter without renderer | Remains blocked without a DuckDB fallback. | Preserve existing incompatible-renderer tests. |
| Mismatched renderer `adapter_type` | Blocks before `render_plan()` or `render_operation()`. | Preserve existing renderer mismatch tests; add helper coverage if impacted. |
| Renderer raises while rendering | Structured renderer failure; no raw SQL, raw database error, credentials, or profile values in diagnostics. | Preserve existing renderer-failure and privacy tests. |
| Empty renderer output | Structured empty-renderer diagnostic; no adapter query. | Preserve existing empty-output tests. |
| Runtime setup and scan safety | Renderer wiring must not weaken scan-safety, capability, adapter setup, same-context, or query-endpoint blockers. | Preserve run-service, scan-budget, and capability suites. |

## Workflow Scenarios

Scenario: row-count execution receives no renderer.

- Given a valid relation-backed row-count check and prepared adapter,
- when the row-count helper is called without an explicit renderer,
- then it returns a structured renderer diagnostic and does not query the
  adapter.

Scenario: key-safety execution receives no renderer.

- Given a valid relation-backed key-safety check, prepared adapter, and allowed
  scan decision,
- when the key-safety helper is called without an explicit renderer,
- then it returns a structured renderer diagnostic and does not query the
  adapter.

Scenario: runtime setup provides the current DuckDB renderer.

- Given current DuckDB relation-backed compiled artifacts and profile,
- when `recon run` prepares execution dependencies,
- then the execution context includes the DuckDB renderer under adapter type
  `duckdb`, and supported checks execute as before.

Scenario: future adapter has no renderer registration.

- Given a future adapter type has an adapter but no renderer entry,
- when current check execution reaches renderer resolution,
- then Core does not fall back to DuckDB and does not produce misleading
  execution evidence.

## Source Map

Implementation is expected to inspect or edit:

- `src/recon_core/check_engine/execution.py`
- `src/recon_core/check_engine/key_safety.py`
- `src/recon_core/check_engine/engine.py`
- `src/recon_core/services/run.py`
- `tests/check_engine/test_row_count_execution.py`
- `tests/check_engine/test_key_safety_execution.py`
- `tests/check_engine/test_engine.py`
- `tests/services/test_run_service.py`

Implementation may inspect, but should avoid changing unless needed:

- `src/recon_core/adapters/rendering.py`
- `src/recon_core/adapters/duckdb/__init__.py`
- `src/recon_core/adapters/duckdb/adapter.py`
- `docs/compatibility/adapter-api.md`
- `docs/compatibility/compatibility-matrix.md`
- `docs/compatibility/public-contract-inventory.md`
- `docs/implementation/adapter-interface-spec.md`
- `docs/implementation/testing-plan.md`
- `docs/compatibility/regression-capture/`

## Responsibility Map

| Component | Allowed responsibilities | Forbidden responsibilities | Refactor trigger |
| --- | --- | --- | --- |
| `services/run.py` | Build runtime dependencies for current supported execution from neutral renderer wiring. | Per-check SQL rendering, direct `recon_core.adapters.duckdb.*` imports, future connector imports, hidden adapter-specific behavior outside neutral construction. | If renderer wiring needs multiple adapter-specific branches, stop and propose registry prework. |
| `check_engine/engine.py` | Resolve adapter-type renderer from `CheckExecutionContext`, preserve blocker precedence, call helpers with explicit dependencies. | Creating renderer instances or importing adapter-specific renderers. | If renderer-missing handling duplicates helper diagnostics materially, extract a small shared helper. |
| `check_engine/execution.py` | Row-count validation, explicit renderer validation, query rendering, adapter execution, result parsing. | DuckDB renderer construction or adapter registry lookup. | If row-count and key-safety renderer validation diverge, extract shared private validation. |
| `check_engine/key_safety.py` | Key-safety validation, explicit renderer validation, scan-decision use, query rendering, adapter execution, result parsing. | DuckDB renderer construction, scan-safety ownership, adapter registry lookup. | If scan safety is affected, stop and re-check item 9 boundaries. |
| Tests | Prove explicit renderer wiring and no hidden fallback. | Replacing behavior coverage with only import checks. | If test setup becomes broad, extract helper fixtures after implementation. |

## Affected Docs

This prework adds this planning artifact.

Future implementation may need targeted updates to:

- `docs/compatibility/adapter-api.md` if a new renderer-missing diagnostic code
  or compatibility wording is introduced,
- `docs/compatibility/compatibility-matrix.md` if execution renderer binding is
  promoted as a durable compatibility row,
- `docs/implementation/adapter-interface-spec.md` if runtime execution helper
  renderer requirements need durable wording,
- `docs/implementation/testing-plan.md` if test-plan wording must mention
  runtime missing-renderer coverage.

No changelog entry is required for this prework because it changes planning
only.

For the future implementation, a changelog entry is not expected if current CLI
behavior and generated outputs remain unchanged. Re-check this if direct
package helper behavior is treated as a public Python API change.

## Compatibility, Security, And Privacy Impact

Compatibility impact:

- Current `recon run` DuckDB behavior must remain compatible.
- Current compiled artifact schemas, YAML syntax, generated SQL artifact
  formats, adapter capability names, and adapter API version must not change.
- Direct helper behavior may change from implicit DuckDB fallback to explicit
  renderer requirement. This is pre-alpha check-engine surface behavior and
  should be covered by tests and, if needed, compatibility wording.
- Future adapter and test-kit compatibility improves because no runtime helper
  silently assumes DuckDB when another adapter type is in play.

Security and privacy impact:

- Missing renderer handling must not emit rendered profile values, credentials,
  raw SQL, raw database errors, source/target relation names, key values, row
  values, or failure details.
- Renderer failures must remain sanitized.
- No new generated artifacts, result files, evidence, reports, state, or sink
  writes are in scope.

## Regression-Capture Review

Before implementation, review:

- `docs/compatibility/regression-capture/index.yml`
- `docs/compatibility/regression-capture/check-engine.yml`
- `docs/compatibility/regression-capture/adapter-runtime.yml`

Expected trigger surfaces are:

- `check_engine`,
- `typed_check_plan`,
- `execution_result`,
- `adapter_runtime`,
- `adapter_api` if diagnostics or renderer validation semantics change.

Add or update a regression-capture row only if implementation fixes a reusable
missed requirement or changes a carryover gate. If implementation only locks the
planned explicit renderer boundary and maps to existing conformance coverage,
record `regression_capture_decision: not-required` in the companion brain dump.

## Required Tests For Future Implementation

Before item 10 implementation claims completion, test coverage must prove:

- row-count helper does not execute or default to DuckDB when renderer is
  missing,
- key-safety helper does not execute or default to DuckDB when renderer is
  missing,
- engine-level DuckDB execution requires a renderer entry in
  `CheckExecutionContext`,
- run-service DuckDB row-count execution still succeeds through explicit
  renderer wiring,
- run-service bounded local/dev DuckDB key-safety execution still succeeds
  through explicit renderer wiring,
- renderer mismatch and malformed renderer metadata still block before
  rendering,
- renderer exceptions and empty renderer output remain structured and sanitized,
- no scan-safety, adapter-capability, same-context, query-endpoint,
  materialization, or placement blocker is weakened,
- `check_engine/execution.py` and `check_engine/key_safety.py` no longer import
  `DuckDbSqlRenderer`.

## Definition Of Done

Item 10 implementation is complete when:

- hidden `DuckDbSqlRenderer()` construction is removed from row-count and
  key-safety execution helpers,
- current DuckDB `recon run` row-count and bounded local/dev key-safety behavior
  still works through explicit runtime renderer wiring,
- missing renderer cases fail closed with structured diagnostics and no adapter
  query,
- renderer mismatch, renderer failure, empty renderer output, capability,
  scan-safety, same-context, and query-endpoint tests still pass,
- no item 11, item 16, external adapter package, entry-point discovery,
  aggregate execution, query endpoint, result/evidence, or materialization work
  is folded into item 10,
- regression-capture decision is recorded,
- companion brain dump is updated,
- validation passes.

## Future Implementation Plan

1. Add failing tests for missing renderer behavior in row-count helper,
   key-safety helper, and engine DuckDB execution context.
2. Update existing direct helper success tests to pass an explicit DuckDB
   renderer, preserving behavior while removing hidden dependency on defaults.
3. Wire the current DuckDB renderer into `RunService`'s `CheckExecutionContext`
   for current built-in DuckDB runtime execution through a neutral helper,
   registry, or injected construction path that keeps `RunService` free of
   direct `recon_core.adapters.duckdb.*` imports.
4. Remove `DuckDbSqlRenderer` imports and fallback construction from
   `check_engine/execution.py` and `check_engine/key_safety.py`.
5. Preserve or add tests proving `recon run` still executes current supported
   DuckDB row-count and bounded local/dev key-safety checks.
6. Run focused check-engine/run-service validation, regression-capture checks,
   full pytest, ruff, mypy, and compileall.

## Phase Exit Review Plan

Implementation phase exit must answer:

- Did any helper still create a DuckDB renderer implicitly?
- Does `RunService` provide current DuckDB renderer wiring explicitly?
- Does `RunService` still avoid direct `recon_core.adapters.duckdb.*` imports?
- Did current DuckDB `recon run` behavior remain unchanged?
- Did missing renderer fail before adapter query execution?
- Did diagnostics remain sanitized?
- Did any non-goal surface change?
- Did regression-capture review produce `row-added` or `not-required`?

## Local-Success Blindness Second Pass

A passing local DuckDB run is insufficient if the implementation still:

- imports `DuckDbSqlRenderer` from check execution helpers,
- creates a DuckDB renderer lazily when `renderer` is missing,
- makes non-DuckDB adapters appear executable through DuckDB SQL,
- weakens scan-safety or capability blockers,
- changes generated artifacts, evidence, result, or CLI output unexpectedly,
- hides missing renderer failures as data check failures,
- broadens item 10 into renderer decomposition or external adapter discovery.
