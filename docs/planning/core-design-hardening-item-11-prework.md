# Core Design Hardening Item 11 Prework

## Purpose

This is the prework artifact for final-order item 11: decompose the DuckDB SQL
renderer monolith.

Item 11 is high-risk because it touches SQL rendering, adapter package layout,
typed-plan rendering semantics, generated SQL artifacts, adapter capabilities,
diagnostics, current compile/run behavior, and future adapter test-kit
compatibility. This artifact locks a narrow behavior-preserving implementation
boundary before coding. It does not implement renderer decomposition.

Split Decision: Already Split / Follow Existing Split.

The broader hardening branch already split this work away from render-vs-runtime
capability semantics, runtime renderer wiring, check-execution decomposition,
compile-service decomposition, external adapter discovery, adapter package
extraction, public export-barrel policy, and `BaseAdapter` metadata-interface
work. Item 11 should remain a DuckDB renderer-internal decomposition.

## Scope

Item 11 prework covers:

- the current `DuckDbSqlRenderer` class and its private helper functions,
- current DuckDB SQL rendering for row-count, grain-key safety, aggregate, and
  grouped aggregate typed operations,
- current `RenderedSql` step names, operation types, required capabilities, SQL
  bytes, and renderer error behavior,
- module ownership seams inside `recon_core.adapters.duckdb`,
- import compatibility for the current in-core DuckDB renderer,
- affected tests, diagnostics, compatibility, privacy, and documentation,
- implementation-readiness criteria for the next coding pass.

The selected design is conservative: split DuckDB renderer responsibilities into
private DuckDB renderer modules while preserving the public `SqlRenderer`
boundary, package-level `DuckDbSqlRenderer` import, generated SQL output, and
current compile/run behavior.

## Non-Goals

Item 11 prework and implementation must not implement:

- external adapter package discovery,
- Python entry-point loading,
- renderer registries for third-party packages,
- adapter API version changes,
- capability name changes or support-state changes,
- new typed operations,
- new aggregate execution behavior,
- query endpoint rendering or execution,
- cross-adapter rendering,
- cross-connection rendering,
- materialization or staging,
- generated artifact path, status, or schema changes,
- result, evidence, report, failure-detail, state, or sink output,
- runtime scan-safety changes,
- `RunService` renderer wiring changes,
- `CompileService` decomposition,
- package export-barrel policy changes,
- `BaseAdapter` metadata-method splitting,
- public docs research attribution.

## Current Audit Findings

Current code has strong behavior coverage but concentrated ownership:

- `src/recon_core/adapters/duckdb/adapter.py` contains the DuckDB adapter
  lifecycle class, factory, dependency checks, lifecycle diagnostics,
  `DuckDbSqlRenderer`, operation rendering, type-check SQL helpers, aggregate
  helpers, operation-payload validation helpers, and formatting utilities.
- `DuckDbSqlRenderer` currently owns dispatch, `render_plan()`, identifier and
  relation rendering, row-count rendering, key-safety rendering, aggregate
  rendering, grouped aggregate rendering, and type-check SQL generation.
- `tests/adapters/test_duckdb_sql_renderer.py` already covers exact SQL strings,
  rendered operation types, rendered step names, required capabilities,
  malformed typed-plan payload blockers, and DuckDB semantic execution cases
  where the optional DuckDB dependency is available.
- Public compatibility docs already treat renderer output, step-level
  capabilities, artifact publication, renderer metadata, and SQL comparison
  semantics as compatibility surfaces.
- Current package import shape exposes `DuckDbSqlRenderer` from
  `recon_core.adapters.duckdb`.
- Some internal tests and code import the package facade. No current repository
  code directly imports `DuckDbSqlRenderer` from
  `recon_core.adapters.duckdb.adapter`, but preserving a direct module alias is
  safer during a behavior-preserving refactor.

Current behavior to preserve:

- `recon compile --render-sql` emits identical SQL artifacts for all current
  DuckDB-rendered checks.
- `recon run` keeps executing current same-context DuckDB relation-backed
  row-count checks and bounded local/dev grain-key safety checks.
- `DuckDbSqlRenderer.render_operation()` and `render_plan()` keep returning the
  same `RenderedSql` operation types, step names, required capabilities, and SQL
  strings.
- Key-diff SQL continues comparing distinct non-null key sets and guarding key
  equality with `typeof(...)` plus null-safe equality.
- Duplicate-key SQL continues excluding null-containing grain-key tuples.
- Aggregate and grouped aggregate SQL continue using the current input/result
  type-check statements and keep current unsafe-type rejection behavior.
- Renderer output validation remains Core-owned outside the renderer.

## Decomposition Decision

The DuckDB adapter package should separate lifecycle/factory responsibilities
from renderer responsibilities without changing public behavior.

Recommended implementation shape:

| Module | Allowed responsibility | Forbidden responsibility |
| --- | --- | --- |
| `adapters/duckdb/adapter.py` | DuckDB `BaseAdapter`, factory, dependency check, lifecycle errors, lifecycle diagnostics, compatibility re-export of `DuckDbSqlRenderer` if needed. | Typed operation SQL rendering, renderer dispatch, aggregate/key SQL helpers, runtime scan-safety mechanics. |
| `adapters/duckdb/renderer.py` | Public `DuckDbSqlRenderer` class, `SqlRenderer` protocol implementation, render dispatch, `render_plan()` step naming orchestration, public `quote_identifier()` and `render_relation()`. | Adapter lifecycle, dependency checks, profile handling, runtime safety, artifact writing, capability validation beyond returned `RenderedSql.required_capabilities`. |
| `adapters/duckdb/renderer_operations.py` or equivalent private module | DuckDB SQL builders for row-count, key-safety, aggregate, grouped aggregate, and compare operations. | Public adapter API exports, lifecycle behavior, Core artifact publication. |
| `adapters/duckdb/renderer_sql.py` or equivalent private module | Identifier/relation-aware SQL fragments, type-check statement builders, aggregate input/result type predicates, string literal escaping, operation payload helper functions. | Adapter lifecycle, check execution, run-service scan policy, generated artifact writing. |
| `adapters/duckdb/__init__.py` | Preserve package-level imports for `DuckDbAdapter`, `DuckDbAdapterFactory`, `DuckDbSqlRenderer`, diagnostics, and lifecycle errors. | Expanding the public facade or adding new connector/package registration behavior. |

Exact private module names may change during implementation if the final split
better matches the code. The invariant is the responsibility separation, not the
filename spelling.

## Expected Behavior

For renderer API behavior:

- `from recon_core.adapters.duckdb import DuckDbSqlRenderer` continues to work.
- `DuckDbSqlRenderer.adapter_type` remains `"duckdb"`.
- `render_operation()` keeps accepting current typed operation dictionaries and
  raising structured Python errors for malformed unsupported operation payloads
  as it does today.
- `render_plan()` keeps assigning the same step names and handling
  `compare_aggregates` and `compare_grouped_aggregates` with plan context.
- `quote_identifier()` and `render_relation()` keep their current escaping and
  dotted relation rendering behavior.

For generated SQL behavior:

- Every existing renderer unit test comparing exact SQL must keep passing
  without expected-string edits unless the implementation discovers a real
  pre-existing bug and the user approves a behavior change.
- Current semantic DuckDB tests must keep passing when the optional DuckDB test
  dependency is installed or required by environment.
- `RenderedSql.required_capabilities` values must not change.
- `RenderedSql.step_name` values must not change.

For compile/run behavior:

- `recon compile --render-sql` must keep generated SQL paths, compiled-check
  rendering status, and `rendering.adapter_type` behavior unchanged.
- Current `recon run` DuckDB row-count/key-safety behavior must remain unchanged.
- Runtime renderer wiring from item 10 must not move or broaden.

## Acceptance And Conformance Matrix

| Case | Expected behavior | Required implementation coverage |
| --- | --- | --- |
| Package import compatibility | Package-level `DuckDbSqlRenderer` import still works. | Preserve or add an import compatibility test. |
| Direct module compatibility | Existing direct module path remains available or intentionally documented as internal. | Prefer preserving an alias from `adapters/duckdb/adapter.py`; add a focused test if the implementation moves the class. |
| Row-count rendering | Same SQL, operation type, and required capabilities. | Existing renderer tests must pass unchanged. |
| Key-diff rendering | Same non-null distinct key-set SQL, type guard, direction handling, operation type, and capabilities. | Existing exact SQL and semantic tests must pass unchanged. |
| Null-key rendering | Same SQL and capabilities. | Existing renderer tests must pass unchanged. |
| Duplicate-key rendering | Same non-null tuple filtering and capabilities. | Existing exact SQL and regression-capture semantic test must pass unchanged. |
| Aggregate rendering | Same type-check statements, native aggregate expression, unsupported input behavior, operation types, and capabilities. | Existing exact SQL and semantic tests must pass unchanged. |
| Grouped aggregate rendering | Same group-key type checks, separate source/target key output columns, aggregate type checks, operation types, and capabilities. | Existing exact SQL and semantic tests must pass unchanged. |
| Plan context operations | `compare_aggregates` and `compare_grouped_aggregates` still require `render_plan()` context and still reject direct `render_operation()` calls. | Preserve existing tests or add a focused rejection test if coverage is missing. |
| Renderer output validation | Empty/malformed `RenderedSql` remains rejected by Core orchestration and writer boundaries. | Existing `tests/adapters/test_rendering.py`, writer, and compile-service tests must pass. |
| Capability enforcement | Rendered-step `required_capabilities` remain enforced before SQL publication. | Existing capability enforcement tests must pass. |
| Compile SQL artifacts | `recon compile --render-sql` output shape and paths do not change. | Existing compile-service tests plus regression-capture scripts. |
| Runtime execution | Current DuckDB row-count and bounded local/dev key-safety execution do not change. | Existing run-service tests must pass. |
| Import boundary | Decomposition must not introduce `duckdb` optional dependency import at module import time. | Existing adapter dependency tests plus an import guard if implementation adds new modules. |

## Workflow Scenarios

Scenario: SQL rendering is decomposed without SQL drift.

- Given a current DuckDB-rendered row-count, key-safety, aggregate, or grouped
  aggregate typed plan,
- when `DuckDbSqlRenderer.render_plan()` renders after decomposition,
- then each `RenderedSql` step has the same `step_name`, `operation_type`,
  `required_capabilities`, and SQL text as before.

Scenario: package imports remain stable.

- Given existing code imports `DuckDbSqlRenderer` from
  `recon_core.adapters.duckdb`,
- when the renderer implementation moves into a dedicated module,
- then the package import still resolves to the same renderer class.

Scenario: renderer decomposition does not load optional DuckDB on import.

- Given a project imports the DuckDB renderer for SQL artifact generation,
- when the optional runtime DuckDB dependency is absent,
- then importing the renderer still succeeds and only adapter connection
  lifecycle checks require the optional database package.

Scenario: runtime behavior remains unchanged.

- Given current compiled DuckDB row-count or bounded local/dev key-safety
  artifacts,
- when `recon run` executes after renderer decomposition,
- then runtime behavior, blockers, diagnostics, and source/target privacy remain
  unchanged.

## Source Map

Implementation is expected to inspect or edit:

- `src/recon_core/adapters/duckdb/adapter.py`
- `src/recon_core/adapters/duckdb/__init__.py`
- new private modules under `src/recon_core/adapters/duckdb/`
- `tests/adapters/test_duckdb_sql_renderer.py`
- `tests/adapters/test_duckdb_adapter.py`
- `tests/adapters/test_rendering.py`
- `tests/services/test_compile_service.py`
- `tests/services/test_run_service.py`

Implementation may inspect, but should avoid changing unless needed:

- `src/recon_core/services/compile.py`
- `src/recon_core/adapters/rendering.py`
- `src/recon_core/adapters/default_renderers.py`
- `src/recon_core/adapters/default_registry.py`
- `src/recon_core/check_engine/`
- `docs/compatibility/adapter-api.md`
- `docs/compatibility/compatibility-matrix.md`
- `docs/implementation/adapter-interface-spec.md`
- `docs/implementation/testing-plan.md`
- `docs/compatibility/regression-capture/`

## Responsibility Map

| Component | Allowed responsibilities | Forbidden responsibilities | Refactor trigger |
| --- | --- | --- | --- |
| `DuckDbAdapter` and factory | Adapter lifecycle, dependency detection, query execution, capability declaration, lifecycle diagnostics. | SQL rendering, scan-safety policy, typed operation semantics. | If renderer imports lifecycle-only dependencies, move the dependency back out. |
| `DuckDbSqlRenderer` | Public renderer protocol, dispatch, plan context, relation and identifier rendering. | Adapter lifecycle, runtime execution, compile service orchestration, artifact writing. | If the class still contains most operation SQL builders after decomposition, split further inside item 11 scope. |
| Operation renderer helpers | Build SQL for current typed operations and comparisons. | Returning malformed `RenderedSql`, validating adapter capabilities, writing artifacts. | If helpers need Core compiler/check-engine objects instead of typed operation dictionaries and `Relation`, stop and re-check boundaries. |
| SQL fragment/type-check helpers | Build reusable DuckDB-specific SQL fragments and type-check predicates. | Source/target data inspection, executing SQL, changing comparison semantics. | If a helper changes SQL text, require explicit expected-output test review before proceeding. |
| Tests | Prove import stability, exact SQL preservation, semantic preservation, and boundary hygiene. | Replacing exact SQL/semantic coverage with only import or smoke tests. | If expected SQL updates are needed, treat that as a behavior change and stop for approval unless fixing an approved bug. |

## Affected Docs

This prework adds this planning artifact.

Future implementation is expected to be behavior-preserving and should not need
public docs changes if:

- package-level imports remain compatible,
- generated SQL text and compiled artifact paths do not change,
- renderer output semantics do not change,
- capability requirements do not change,
- compile/run behavior does not change.

If implementation changes any of those surfaces, stop and update the relevant
compatibility docs, implementation docs, and changelog decision before claiming
completion.

No changelog entry is required for this prework because it changes planning
only.

## Compatibility, Security, And Privacy Impact

Compatibility impact:

- Current SQL renderer behavior is a compatibility surface for generated SQL
  artifacts and future adapter test-kit claims.
- Current package-level import compatibility must be preserved.
- Compiled artifact schema, rendered SQL paths, rendering status meanings,
  `rendering.adapter_type`, and `RenderedSql.required_capabilities` must not
  change.
- Future adapter/test-kit compatibility improves because renderer internals will
  be easier to port without changing Core's typed-plan boundary.

Security and privacy impact:

- Renderer decomposition must not expose raw SQL, raw database errors, profile
  values, credentials, DSN fragments, source/target row values, or low-level
  exception text in public diagnostics.
- No generated outputs, local profiles, evidence, result artifacts, reports, or
  state files should be created or committed by this refactor.

## Required Tests For Future Implementation

Before item 11 implementation claims completion, run at minimum:

```bash
python3 -m pytest tests/adapters/test_duckdb_sql_renderer.py -q
python3 -m pytest tests/adapters/test_duckdb_adapter.py tests/adapters/test_rendering.py -q
python3 -m pytest tests/services/test_compile_service.py tests/services/test_run_service.py -q
python3 scripts/check_regression_capture_decisions.py --base-ref origin/main
python3 scripts/check_regression_capture.py
python3 -m pytest -q
python3 -m ruff check .
python3 -m mypy src
python3 -m compileall -q src tests
git diff --check
git -C /Users/musa-atlihan/Documents/work/reconlabs/recon-core-agents diff --check
```

Also run an import/AST guard after implementation:

- importing `recon_core.adapters.duckdb.DuckDbSqlRenderer` succeeds,
- importing any new renderer module does not import the optional `duckdb`
  package,
- `RunService` still does not import `DuckDbSqlRenderer` or
  `recon_core.adapters.duckdb`,
- item 10 runtime renderer wiring remains internal.

## Local-Success Blindness Second Pass

A local DuckDB renderer test pass is insufficient if the implementation still:

- changes generated SQL text unintentionally,
- changes `RenderedSql.step_name`, `operation_type`, or
  `required_capabilities`,
- changes compiled SQL artifact paths or rendering status semantics,
- changes key-diff null/type semantics,
- changes duplicate-key null-containing tuple behavior,
- changes aggregate unsafe-type rejection behavior,
- loads the optional `duckdb` runtime package at renderer import time,
- breaks package-level `DuckDbSqlRenderer` imports,
- hides behavior drift behind broad expected-SQL fixture rewrites,
- broadens item 11 into compile-service decomposition, renderer registry work,
  external adapter discovery, adapter package extraction, or public export
  policy changes.

## Regression Capture Review

Applicable regression-capture routing:

- `src/recon_core/adapters/duckdb/adapter.py` maps to `adapter_runtime`,
  `adapter_capabilities`, and the generic adapter API/capability prefix.
- The split DuckDB renderer modules map to `sql_rendering` plus the generic
  adapter API/capability prefix:
  - `src/recon_core/adapters/duckdb/renderer.py`,
  - `src/recon_core/adapters/duckdb/renderer_operations.py`,
  - `src/recon_core/adapters/duckdb/renderer_sql.py`.
- `tests/adapters/test_duckdb_sql_renderer.py` maps to `sql_rendering`.
- The matching carryover gate is `adapter_testkit_regression_carryover`.
- Matching current rows include:
  - `duplicate-key-excludes-null-containing-tuples`,
  - `key-safety-empty-grain-keys-shape-blocker`,
  - adapter runtime and scan-safety rows that must stay unaffected by this
    renderer-only refactor.

No new regression-capture row is required for prework. Future implementation
should add or update a row only if it fixes a reusable renderer bug or discovers
a missed conformance requirement. Otherwise record:

```text
regression_capture_decision: not-required
```

## Implementation Plan

Recommended implementation order:

1. Add import-compatibility and optional-dependency import guard tests if
   current coverage is insufficient.
2. Move renderer SQL helpers into private DuckDB renderer modules without
   changing SQL text.
3. Move `DuckDbSqlRenderer` into a dedicated renderer module, preserving
   package-level imports and a compatibility alias from `adapter.py` if needed.
4. Keep `DuckDbAdapter`, factory, dependency detection, and lifecycle
   diagnostics in `adapter.py`.
5. Run focused renderer tests before touching compile/run tests.
6. Run the local-success blindness second pass and full validation.

Implementation should stop for user approval if any expected SQL text,
generated artifact path, public import, capability requirement, diagnostic code,
runtime behavior, or public docs contract needs to change.

## Definition Of Done

Item 11 implementation is complete only when:

- DuckDB adapter lifecycle/factory responsibilities are separated from renderer
  implementation responsibilities.
- `DuckDbSqlRenderer` package-level import compatibility is preserved.
- Exact SQL renderer tests pass without expected-output churn.
- DuckDB semantic renderer tests pass when the optional dependency is available
  or required by environment.
- Compile-service rendered SQL tests pass.
- Run-service DuckDB row-count and key-safety tests pass.
- Regression-capture validation and advisory checks pass.
- Ruff, mypy, compileall, full pytest, and diff checks pass.
- No non-goal scope is introduced.
- Companion brain dump records the validation, remaining risks, split decision,
  changelog decision, and regression-capture decision.

Split Decision: Already Split / Follow Existing Split.

Changelog Decision: Not Required for prework.

`regression_capture_decision: not-required`
