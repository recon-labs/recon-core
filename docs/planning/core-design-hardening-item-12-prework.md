# Core Design Hardening Item 12 Prework

## Purpose

This is the prework artifact for final-order item 12: decompose vertical
check-execution modules.

Item 12 is high-risk because it touches check execution, typed-plan dispatch,
adapter execution, SQL rendering handoff, scan-safety consumption, prerequisite
blocking, runtime diagnostics, source/target privacy, current `recon run`
behavior, and future adapter test-kit compatibility. This artifact locks the
responsibility map before coding. It does not implement runtime behavior.

Split Decision: Already Split / Follow Existing Split.

The broader hardening branch already split this work away from capability
semantics, runtime renderer binding, DuckDB renderer decomposition, compile
service decomposition, profile-loader decomposition, public export-barrel
policy, and adapter metadata-interface splitting. Item 12 should remain a
behavior-preserving check-engine decomposition.

## Scope

Item 12 prework covers:

- current `CheckEngine` orchestration for loaded compiled-check artifacts,
- prerequisite and blocker result handling,
- row-count runtime execution helpers,
- grain-key safety runtime execution helpers,
- shared execution support for relation parsing, renderer binding, adapter
  diagnostics, and result creation,
- current scan-budget decision consumption by key-safety execution,
- current `RunService` to `CheckExecutionContext` handoff,
- module ownership, source-map, regression-capture routing, tests, privacy,
  compatibility, and implementation-readiness criteria.

The selected design is conservative: split private responsibilities without
changing public YAML, CLI output, generated artifacts, typed-plan payloads,
adapter API, capability names, result schemas, diagnostic codes, or current
same-context DuckDB execution behavior.

## Non-Goals

Item 12 prework and implementation must not implement:

- new check types,
- aggregate runtime execution,
- row-level value execution,
- query endpoint execution,
- cross-adapter execution,
- cross-context bridging,
- materialization or staging,
- hidden Python fallback,
- production scan-budget settings,
- generated run results,
- evidence, reports, failure details, result tables, state, or sinks,
- adapter capability name or support-state changes,
- adapter package discovery or entry points,
- DuckDB SQL renderer decomposition,
- `RunService` broad decomposition,
- `CompileService` decomposition,
- public Python export policy changes.

## Current Audit Findings

Current code has the needed behavior coverage but concentrated ownership:

- `check_engine/engine.py` owns run assembly, check indexing, prerequisite
  recursion, blocker result creation, rendering-status blockers, runtime
  execution selection for row count and key safety, renderer lookup, and default
  missing scan-budget construction.
- `check_engine/execution.py` owns row-count plan-shape validation, endpoint
  checks, relation parsing, same-context checks, renderer validation, rendering,
  adapter query execution, result parsing, and pass/fail result creation.
- `check_engine/key_safety.py` owns key-safety operation catalog, shape
  validation, identity validation, endpoint checks, relation parsing,
  same-context checks, scan-budget consumption, renderer validation, rendering,
  adapter query execution, result parsing, failure diagnostics, and pass/fail
  result creation.
- `check_engine/execution_support.py` already contains shared runtime support
  for result factories, relation parsing, safe attribute reads, adapter query
  diagnostic sanitization, and sensitive-token suppression.
- `check_engine/scan_budget.py` is already a focused safety-policy module and
  should stay separate.
- `services/run.py` still owns runtime dependency preparation, profile loading,
  runtime safety-check registry use, scan-budget decision construction, adapter
  setup, adapter lifecycle, and `CheckExecutionContext` construction.
- Regression-capture routing currently exact-routes `scan_budget.py` to
  `scan_safety`, exact-routes `services/run.py` to adapter runtime and scan
  safety, and prefix-routes `check_engine/` to check-engine, execution-result,
  prerequisite-blocking, and typed-plan surfaces.

Current behavior to preserve:

- `recon run` executes only current same-context DuckDB relation-backed
  row-count checks and bounded local/dev grain-key safety checks.
- Unsupported, unsafe, malformed, or future-phase checks remain blocked,
  errored, or `not_executable` with current reason-code precedence.
- Key-safety malformed relation diagnostics outrank missing or blocked
  scan-budget decisions.
- Key-safety typed-plan shape blockers outrank missing scan-budget decisions.
- Prerequisite failures, errors, blocked results, and not-executable results
  block dependent checks without producing misleading comparison evidence.
- Scan-budget classification remains separate from adapter capabilities and
  check execution helpers.
- Current runtime diagnostics stay sanitized and no raw query text, database
  error text, rendered profile value, row value, key value, or failure detail is
  emitted.

## Decomposition Decision

Check execution should be decomposed around responsibility boundaries, not
around the current vertical call stack.

Recommended implementation shape:

| Module or component | Allowed responsibility | Forbidden responsibility |
| --- | --- | --- |
| `check_engine/models.py` | Pure in-memory result/status models and validation invariants. | Adapter access, typed-plan dispatch, SQL rendering, scan policy, filesystem output. |
| `check_engine/dispatch.py` | Non-executing classification for compiled checks and known later-phase blockers. | Adapter setup, runtime profile loading, scan-budget decisions, SQL rendering, execution. |
| `check_engine/engine.py` | Run assembly, artifact diagnostics aggregation, result caching, dependency-aware orchestration, and calls into private prerequisite/runtime-execution helpers. | Per-family plan-shape details, scan-budget classification, renderer compatibility logic, adapter query execution. |
| New prerequisite helper module, or equivalent | Prerequisite recursion support, blocker precedence, `blocked_by` de-duplication, and prerequisite diagnostics. | Adapter/runtime execution, plan-shape validation, SQL rendering, scan policy. |
| New runtime execution router, or equivalent | Decide whether a dispatch result may be replaced by a supported runtime execution result and delegate to the correct check-family executor. | Creating adapter defaults, opening adapters, computing scan-safety decisions, broad service orchestration. |
| `check_engine/execution.py` | Row-count family behavior: supported row-count shape, row-count endpoint/context validation, rendering handoff, adapter query execution, result parsing, pass/fail/error result creation. | Key-safety behavior, scan-budget policy, adapter setup, renderer default creation, public artifact writing. |
| `check_engine/key_safety.py` | Key-safety family behavior: operation catalog, identity validation, supported key-safety shape, scan-decision consumption, rendering handoff, adapter query execution, result parsing, pass/fail/error result creation. | Row-count behavior, scan-budget classification, adapter setup, renderer default creation, raw key export. |
| `check_engine/execution_support.py` or focused shared helpers | Shared relation parsing, same-context checks, renderer compatibility checks, safe adapter diagnostic handling, common not-executable/error result factories. | Owning a complete check family, importing concrete adapter packages, choosing scan policy, opening adapters. |
| `check_engine/scan_budget.py` | Core scan-budget policy from already prepared scan context to allow/block decision. | Adapter metadata inspection, SQL rendering, adapter lifecycle, check-family result parsing. |
| `services/run.py` | Runtime dependency preparation: compiled contract join, profile loading, runtime safety-check registry use, scan-budget decision construction, adapter setup/open/close, execution context creation. | Per-check execution result creation, SQL rendering, prerequisite blocking, concrete check-family internals. |

Exact private module names may change during implementation if the final split
better matches the code. The invariant is the ownership boundary. Public
package exports must remain compatible unless the work stops for explicit
export-policy approval.

## Expected Behavior

For current CLI behavior:

- `recon run` must keep executing current supported DuckDB row-count checks.
- `recon run` must keep executing current supported bounded local/dev DuckDB
  key-safety checks.
- Unsupported future-phase checks must keep returning the same statuses, reason
  codes, messages, diagnostics, and aggregate outcomes.
- No generated run-result, evidence, report, failure-detail, state, or sink
  output may appear.

For direct check-engine/helper behavior:

- Row-count and key-safety helper tests should pass without changing expected
  outcomes.
- Missing, mismatched, malformed, or raising renderer metadata must still block
  before rendering and before adapter queries.
- Renderer failures and empty renderer output must still produce structured
  errors and must not query the adapter.
- Adapter query failures and malformed query results must stay sanitized and
  must not leak raw source/target data or database text.
- Scan-budget decisions must still block key-safety execution before renderer
  work and adapter queries.

For module boundaries:

- No `DuckDbSqlRenderer` or `recon_core.adapters.duckdb` import may enter
  check-engine source or `services/run.py`.
- `scan_budget.py` must not import adapters, renderers, compiled artifacts, or
  service objects.
- Check-family modules may consume prepared adapters/renderers but must not
  prepare profiles, adapter registries, runtime safety-check registries, or
  generated outputs.

## Acceptance And Conformance Matrix

| Case | Expected behavior | Required implementation coverage |
| --- | --- | --- |
| Run assembly | Same run ID/project/time/status aggregation behavior; artifact diagnostics are preserved. | Existing engine and service tests. |
| Prerequisite failed/error/blocked/not-executable | Dependent check is `blocked`, keeps correct dominant reason and `blocked_by`. | Existing prerequisite tests plus any moved-helper tests. |
| Missing or cyclic prerequisite | Missing prerequisite blocks; recursion errors sanitize to internal error. | Existing engine tests. |
| Rendering status blocked/failed | Supported row-count/key-safety shapes error before adapter query; unsupported shapes keep shape blockers. | Existing engine and run-service rendering-status tests. |
| Row-count supported plan | Current same-context DuckDB relation-backed row-count execution passes/fails/errors exactly as before. | Existing row-count helper, engine, and run-service tests. |
| Row-count blockers | Unsupported type, unsupported shape, reserved placement/materialization, query endpoint, malformed relation, cross-context, missing/mismatched renderer, renderer failure, empty SQL, adapter query failure, and malformed result stay ordered and sanitized. | Existing row-count tests; add focused moved-boundary tests if coverage becomes indirect. |
| Key-safety supported plan | Current null, duplicate, missing, and extra key-safety checks pass/fail/errors exactly as before. | Existing key-safety helper, engine, and run-service tests. |
| Key-safety blockers | Unsupported shape, identity mismatch, query endpoint, malformed relation, connection context, scan budget, renderer, adapter query, and malformed result stay ordered and sanitized. | Existing key-safety tests and regression-capture rows. |
| Shape before scan budget | Key-safety typed-plan shape blocker outranks absent scan-budget decisions. | Existing regression-capture tests must remain mapped. |
| Malformed relation before scan budget | Malformed compiled relation diagnostics outrank scan-budget blockers. | Existing regression-capture tests must remain mapped. |
| Scan-budget isolation | Scan-budget policy remains separately owned and is consumed only as a decision by key-safety execution. | Existing scan-budget tests and import guards; no helper merge into execution. |
| Capability and adapter setup | Runtime capability checks still happen before adapter open/connect. | Existing run-service capability-preflight tests. |
| Source/target privacy | Diagnostics and results do not expose raw rows, keys, query text, database errors, rendered profile values, or failure details. | Existing privacy tests plus focused tests if helper movement changes diagnostics. |
| Public contracts | YAML, compiled artifacts, typed-plan payloads, diagnostic codes, CLI output, result dicts, and adapter API remain unchanged. | Existing full test suite and diff review; no expected-output churn. |
| Regression routing | Any new or moved file that owns check-engine, execution-result, typed-plan, prerequisite, adapter-runtime, SQL-rendering, scan-safety, diagnostics, or privacy behavior is exact-routed. | Update `index.yml` and script tests in the implementation if ownership changes. |

## Workflow Scenarios

Scenario: prerequisite blocking remains independent of execution.

- Given a dependent check references a key-safety prerequisite,
- when the prerequisite fails, errors, is blocked, or is not executable,
- then the dependent check is blocked with the same reason precedence and no
  adapter query runs for the dependent check.

Scenario: key-safety shape errors outrank scan policy.

- Given a key-safety compiled check has an unsupported typed-plan shape,
- when no scan-budget decision exists for that check,
- then the typed-plan shape blocker is reported instead of a missing scan-policy
  blocker.

Scenario: malformed relation errors outrank scan policy.

- Given a key-safety compiled contract contains a malformed relation endpoint,
- when scan-budget decisions are absent or blocking,
- then the malformed relation diagnostic is reported before scan-policy
  blockers and no profile, renderer, or adapter query work occurs.

Scenario: runtime execution still requires explicit prepared dependencies.

- Given supported row-count or key-safety compiled artifacts,
- when no matching prepared adapter or renderer is present,
- then the check remains blocked, errored, or not executable according to the
  current rules and Core does not create hidden defaults.

Scenario: current DuckDB runtime behavior remains intact.

- Given current same-context relation-backed DuckDB compiled artifacts and a
  profile that passes the current gates,
- when `recon run` executes after decomposition,
- then row-count and bounded local/dev key-safety checks produce the same
  in-memory outcomes and diagnostics as before.

## Source Map

Implementation is expected to inspect or edit:

- `src/recon_core/check_engine/engine.py`
- `src/recon_core/check_engine/execution.py`
- `src/recon_core/check_engine/key_safety.py`
- `src/recon_core/check_engine/execution_support.py`
- `src/recon_core/check_engine/__init__.py`
- new private modules under `src/recon_core/check_engine/`
- `tests/check_engine/test_engine.py`
- `tests/check_engine/test_row_count_execution.py`
- `tests/check_engine/test_key_safety_execution.py`
- `tests/check_engine/test_execution_boundaries.py`
- `tests/services/test_run_service.py`
- `docs/compatibility/regression-capture/index.yml`
- `tests/scripts/test_check_regression_capture_decisions.py`

Implementation may inspect, but should avoid changing unless needed:

- `src/recon_core/services/run.py`
- `src/recon_core/check_engine/scan_budget.py`
- `src/recon_core/adapters/rendering.py`
- `src/recon_core/adapters/runtime_setup.py`
- `src/recon_core/adapters/runtime_safety.py`
- `docs/architecture/check-engine.md`
- `docs/implementation/check-engine.md`
- `docs/compatibility/public-contract-inventory.md`
- `docs/compatibility/typed-check-plan.md`
- `docs/compatibility/capability-catalog.md`
- `docs/implementation/testing-plan.md`

Implementation should not edit `RunService` unless source inspection proves a
small compatibility import or test seam is necessary. Broad run-service
decomposition is not item 12.

## Responsibility Map

| Component | Allowed responsibilities | Forbidden responsibilities | Refactor trigger | Tests protecting boundary |
| --- | --- | --- | --- | --- |
| `CheckEngine` | Coordinate artifacts, cache results, delegate prerequisites and runtime execution. | Owning family-specific plan shapes, scan classification, renderer validation, adapter queries. | If `engine.py` still grows with new check-family branches after extraction, stop and add a router/helper boundary. | Engine run assembly, prerequisite, rendering-status, no-output tests. |
| Prerequisite helper | Compute prerequisite blocker results and reason precedence. | Dispatch classification, adapter execution, scan policy, SQL rendering. | If it needs adapters, renderers, or contract endpoints, the split is wrong. | Prerequisite fail/error/blocked/not-executable/missing tests. |
| Runtime execution router | Decide whether dispatch results may be replaced by current supported execution and delegate by family. | Adapter setup, profile loading, scan-safety inspection, result parsing, SQL text construction. | If it duplicates row-count or key-safety validation logic, push logic back to family modules. | Mixed row-count/key-safety engine tests and hard-blocker precedence tests. |
| Row-count family module | Row-count validation, rendering handoff, adapter query, result parsing, pass/fail/error outcomes. | Key-safety semantics, scan policy, adapter setup, public artifact writing. | If relation/context/renderer helpers duplicate key-safety code, extract a shared helper. | Row-count helper tests, engine row-count tests, run-service row-count tests. |
| Key-safety family module | Key-safety validation, identity checks, scan-decision consumption, rendering handoff, adapter query, result parsing, failure diagnostics. | Row-count semantics, scan classification, adapter setup, raw key/failure-detail output. | If scan-budget classification moves here, revert and preserve `scan_budget.py` ownership. | Key-safety helper tests, regression-capture rows, run-service key-safety tests. |
| Shared execution support | Small reusable utilities for safe attributes, relation parsing, same-context checks, renderer/adapter diagnostics, and standard result factories. | Full check-family execution, concrete adapter imports, registry setup, scan policy. | If the helper becomes a vertical executor or imports `services/run.py`, split it again. | Import-boundary tests, row-count/key-safety behavior tests. |
| `scan_budget.py` | Map scan context to allow/block decision. | Adapter metadata inspection, renderer binding, result construction outside scan diagnostics. | Any adapter import or compiled artifact import is a blocker. | Scan-budget tests and routing guard. |
| Regression-capture metadata | Exact-route newly owned files to the surfaces they govern. | Relying only on generic prefixes after ownership moves. | Any new/moved check-engine file owning a routed surface requires `index.yml` and script-test review. | Regression-capture decision script tests and `--base-ref origin/main`. |

## Affected Docs

This prework adds this planning artifact.

Future implementation is expected to be behavior-preserving and should not need
durable public architecture or compatibility wording changes if:

- public behavior and generated outputs stay unchanged,
- no diagnostic code, message, status, reason code, result dict, artifact
  schema, adapter API, capability meaning, or CLI output changes,
- package-level imports remain compatible,
- regression-capture routing is updated for any new or moved files.

If implementation changes one of those surfaces, stop and update the relevant
compatibility docs, implementation docs, ADRs, and changelog decision before
claiming completion.

No changelog entry is required for this prework because it changes planning
only.

## Compatibility, Security, And Privacy Impact

Compatibility impact:

- Current `recon run` behavior must remain compatible for current supported
  DuckDB row-count and bounded local/dev key-safety execution.
- Current compiled artifact schemas, typed-plan payloads, rendering metadata,
  adapter capabilities, adapter API version, result object dictionary shape,
  diagnostic codes, and CLI output must not change.
- Internal helper import paths may move only if public package exports remain
  compatible through re-exports or aliases.
- Future adapter and test-kit compatibility improves because check-engine
  ownership becomes easier to route and audit.

Security and privacy impact:

- Decomposition must not expose raw source/target rows, keys, relation data,
  query text, database errors, rendered profile values, credentials, DSN
  fragments, or raw failure details in diagnostics, logs, terminal output,
  artifacts, tests, or companion notes.
- No generated outputs, local profiles, evidence, result artifacts, reports, or
  state files should be created or committed by this refactor.

## Required Tests For Future Implementation

Before item 12 implementation claims completion, run at minimum:

```bash
python3 -m pytest tests/check_engine/test_execution_boundaries.py -q
python3 -m pytest tests/check_engine/test_engine.py tests/check_engine/test_row_count_execution.py tests/check_engine/test_key_safety_execution.py -q
python3 -m pytest tests/services/test_run_service.py -q
python3 -m pytest tests/scripts/test_check_regression_capture_decisions.py tests/scripts/test_check_regression_capture.py -q
python3 scripts/check_regression_capture.py
python3 scripts/check_regression_capture_decisions.py --base-ref origin/main
python3 -m pytest -q
python3 -m ruff check .
python3 -m mypy src
python3 -m compileall -q src tests
git diff --check
git -C /Users/musa-atlihan/Documents/work/reconlabs/recon-core-agents diff --check
```

Also run import and routing guards after implementation:

- no `DuckDbSqlRenderer` or `recon_core.adapters.duckdb` import in
  `src/recon_core/check_engine/` or `src/recon_core/services/run.py`,
- no adapter, renderer, compiled artifact, or service import in
  `check_engine/scan_budget.py`,
- no key-safety module import from row-count execution module,
- no new public export removed from `recon_core.check_engine.__all__`,
- new check-engine files exact-route to their owned regression-capture
  surfaces when they own more than the generic check-engine prefix.

## Local-Success Blindness Second Pass

A passing local DuckDB run is insufficient if the implementation still:

- leaves `engine.py` owning a full vertical row-count or key-safety execution
  path,
- moves scan-budget policy into row-count, key-safety, or shared execution
  helpers,
- creates or moves check-engine files without updating regression-capture
  routing,
- changes blocker precedence while preserving only happy-path execution,
- changes result dictionaries, CLI output, diagnostics, or generated artifacts
  unintentionally,
- broadens into `RunService`, `CompileService`, public export policy, adapter
  registry, entry-point discovery, aggregate execution, query endpoint
  execution, evidence, results, or failure details,
- uses concrete DuckDB imports in check-engine runtime code,
- hides non-DuckDB or missing-renderer failures behind passing same-context
  DuckDB tests.

## Regression Capture Review

Applicable regression-capture routing before implementation:

- `src/recon_core/check_engine/scan_budget.py` exact-routes to `scan_safety`.
- `src/recon_core/services/run.py` exact-routes to `adapter_runtime` and
  `scan_safety`.
- `src/recon_core/check_engine/` prefix-routes to `check_engine`,
  `execution_result`, `prerequisite_blocking`, and `typed_check_plan`.
- `tests/check_engine/` prefix-routes to the same check-engine surfaces.

Applicable current capture rows include:

- `key-safety-shape-blocker-precedence`,
- `key-safety-invalid-relation-diagnostic-precedence`,
- `key-safety-prerequisites-block-dependent-checks`,
- `key-safety-empty-grain-keys-shape-blocker`,
- adapter runtime scan-safety rows in `adapter-runtime.yml`,
- `key-safety-adapter-capability-preflight`,
- runtime adapter diagnostic rows that must stay unaffected by check-engine
  module movement.

Implementation must apply the routing ownership principle:

- identify the old route before moving code,
- exact-route any new module that owns prerequisite blocking, execution result,
  typed-plan, adapter-runtime, SQL-rendering, scan-safety, diagnostics, or
  privacy behavior,
- add or update `tests/scripts/test_check_regression_capture_decisions.py`,
- update existing capture metadata only if a current row's test references or
  ownership changes,
- run both regression-capture scripts.

No new regression-capture row is required for this prework because it changes
planning only and does not fix a behavior bug. Future implementation should add
or update a row only if it fixes a reusable behavior bug or discovers a missed
conformance requirement. Otherwise record:

```text
regression_capture_decision: not-required
```

## Implementation Plan

Recommended implementation order:

1. Add or preserve boundary tests before moving code: import guards, public
   `__all__` compatibility, prerequisite behavior, row-count behavior,
   key-safety behavior, and regression-capture routing tests if new paths are
   planned.
2. Extract prerequisite blocker support from `engine.py` without changing
   reason precedence, messages, diagnostics, or `blocked_by` ordering.
3. Extract runtime execution routing from `engine.py` so the engine delegates
   row-count and key-safety replacement of dispatch results through one private
   boundary.
4. Deduplicate shared row-count/key-safety relation, connection-context,
   renderer, and reserved-metadata helper logic only where tests prove identical
   behavior. Keep family-specific messages where they are currently distinct.
5. Keep `scan_budget.py` as the only scan-decision policy module and keep
   `services/run.py` as the runtime-dependency preparation boundary.
6. Update regression-capture routing and routing tests for any new or moved
   files that own governed surfaces.
7. Run focused tests after each extraction, then run full validation and the
   local-success blindness second pass.

Implementation should stop for user approval if it requires any public behavior
change, generated artifact change, diagnostic-code change, adapter API change,
capability change, public export narrowing, broad service decomposition, or new
execution capability.

## Definition Of Done

Item 12 implementation is complete only when:

- `engine.py` no longer owns family-specific row-count/key-safety execution
  details beyond orchestration and delegation.
- Prerequisite/blocker responsibility has a clear private owner and preserves
  existing behavior.
- Row-count and key-safety family modules remain behavior-compatible and have
  no cross-family private imports.
- Shared helpers are small and do not become a new vertical executor.
- `scan_budget.py` remains independently owned and isolated.
- `RunService` remains the runtime dependency preparation boundary and is not
  broadly decomposed.
- Regression-capture routing covers every new or moved governed file.
- Current row-count, key-safety, engine, run-service, and regression-capture
  tests pass.
- Full validation passes.
- No non-goal scope is introduced.
- Companion brain dump records validation, remaining risks, split decision,
  changelog decision, local-success blindness result, and
  regression-capture decision.

Split Decision: Already Split / Follow Existing Split.

Changelog Decision: Not Required for prework.

`regression_capture_decision: not-required`
