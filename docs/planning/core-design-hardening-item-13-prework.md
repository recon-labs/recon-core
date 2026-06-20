# Core Design Hardening Item 13 Prework

## Purpose

This is the prework artifact for final-order item 13: decompose
`CompileService`.

Item 13 is high-risk because it touches compile orchestration, generated
artifact cleanup and publication, adapter-aware SQL rendering, profile-backed
adapter setup, diagnostic redaction, terminal messages, exit categories,
compiled artifact metadata, compiled SQL output, and future adapter test-kit
compatibility. This artifact locks the responsibility map before coding. It
does not implement runtime behavior.

Split Decision: Already Split / Follow Existing Split.

The broader hardening branch already split this work away from runtime
capability semantics, runtime renderer wiring, DuckDB renderer decomposition,
check-engine decomposition, profile-loader decomposition, adapter diagnostic
redaction decomposition, external adapter discovery, public export-barrel
policy, and `BaseAdapter` metadata-interface work. Item 13 should remain a
behavior-preserving compile-service decomposition.

## Scope

Item 13 prework covers:

- current `CompileService` command orchestration,
- project-context loading, parsed-project loading, and compiler invocation as
  used by `recon compile`,
- compiled YAML artifact cleanup, write, and rollback behavior,
- compiled SQL artifact publication and in-memory rendering metadata updates,
- adapter-aware `recon compile --render-sql` orchestration,
- selected-profile loading and referenced-connection filtering for render-SQL,
- adapter registry resolution, adapter API validation, adapter metadata
  validation, capability validation handoff, and current renderer selection,
- compile/render diagnostic ordering, de-duplication, and privacy redaction,
- current CLI messages, exit categories, generated artifact paths, tests,
  regression-capture routing, compatibility, and implementation-readiness
  criteria.

The selected design is conservative: split private compile-service
responsibilities without changing public YAML, CLI output, generated artifact
schemas, generated artifact paths, typed-plan payloads, adapter API, capability
names, rendering statuses, diagnostic codes, diagnostic messages, profile
selection behavior, or current DuckDB render-SQL behavior.

## Non-Goals

Item 13 prework and implementation must not implement:

- selector support or partial compile,
- artifact freshness or cache optimization,
- automatic parse/compile from `recon run`,
- reading `target/manifest.json` as compile's source of truth,
- new compiled artifact fields, versions, paths, or schemas,
- new rendering statuses or status meanings,
- new SQL renderer behavior or SQL text changes,
- external adapter package discovery,
- Python entry-point loading,
- third-party renderer registries,
- adapter API version changes,
- capability name or support-state changes,
- query endpoint rendering or execution,
- cross-adapter rendering,
- cross-connection or attached-database rendering,
- materialization, staging, or hidden Python fallback,
- aggregate runtime execution,
- result, evidence, report, failure-detail, state, cache, or sink output,
- broad profile-loader decomposition,
- broad adapter diagnostic redaction redesign,
- public Python export policy changes.

## Current Audit Findings

Current code has strong behavior coverage but concentrated ownership:

- `src/recon_core/services/compile.py` is about 1,500 lines and owns the full
  `recon compile` flow.
- `CompileService.execute()` loads project context, clears existing compiled
  artifacts, loads parsed resources, invokes `compile_project()`, decides
  fatal versus partial compile outcomes, handles render-SQL branching, writes
  compiled YAML and SQL artifacts, rolls back failed writes, and assembles
  command messages.
- The same module owns compiled YAML publication, compiled SQL publication,
  rendering metadata mutation, invocation-wide SQL suppression diagnostics,
  compile-diagnostic render blockers, artifact cleanup, artifact write error
  diagnostics, adapter/profile setup, adapter metadata validation, renderer
  selection, same-context render-SQL enforcement, render invocation,
  diagnostic de-duplication, profile-backed diagnostic redaction, unsafe
  diagnostic-code suppression, connection-config token extraction, numeric
  token matching, and display-path formatting.
- `CompileService` currently imports the in-core DuckDB renderer directly for
  current DuckDB render-SQL support.
- The plain compile path correctly avoids profile loading and adapter setup.
- The render-SQL path correctly loads only referenced profile connections after
  compile validation succeeds, except when compile diagnostics with compiled
  contracts intentionally write blocked rendering metadata without invoking
  profiles or adapters.
- Existing tests in `tests/services/test_compile_service.py` cover success,
  compile validation, no contracts, stale artifact cleanup, symlink/path
  safety, partial-write cleanup, render-SQL success, adapter setup failures,
  render failures, invocation-wide SQL suppression, capability enforcement,
  compile-diagnostic render blockers, profile-backed diagnostic redaction, and
  output privacy.
- Regression-capture routing currently covers `artifacts/`, `cli/`, adapter
  and renderer modules, and compiler model surfaces, but it does not exact-route
  `src/recon_core/services/compile.py` or any future compile-service split
  modules.

Current behavior to preserve:

- Plain `recon compile` does not require profiles.
- Compile parse failures and fatal compile validation failures write no
  compiled artifacts and remove stale compiled outputs.
- Partial compile validation with compiled contracts writes compiled YAML
  artifacts and returns validation diagnostics.
- `recon compile --render-sql` blocks adapter rendering when compile validation
  already produced diagnostics, writes compiled YAML with blocked rendering
  metadata, and does not invoke profile loading, adapter resolution, renderer
  selection, or SQL writing.
- Adapter/profile setup diagnostics mark affected checks blocked, write no SQL
  files, preserve distinct source/target diagnostics, preserve independent
  render diagnostics from otherwise resolvable contracts, and keep service
  diagnostics de-duplicated.
- Any render diagnostic suppresses all compiled SQL files for that render-SQL
  invocation and marks otherwise renderable checks blocked with
  `RC_ADAPTER_RENDERING_OUTPUT_SUPPRESSED`.
- Renderer failures, empty renderer output, malformed renderer output,
  unsupported rendered-step capabilities, mixed adapter types, distinct
  connection contexts, query endpoints, and profile-backed diagnostic leaks
  remain structured, safe, and artifact-visible.
- Artifact cleanup and rollback prevent stale, partial, orphaned, symlinked, or
  misleading generated outputs.

## Decomposition Decision

Compile-service decomposition should separate command orchestration, artifact
publication, render-SQL orchestration, adapter/profile preparation, rendering
metadata, and diagnostic redaction without changing behavior.

Recommended implementation shape:

| Module or component | Allowed responsibility | Forbidden responsibility |
| --- | --- | --- |
| `services/compile.py` | Public `CompileService` dataclass, top-level command flow, dependency injection surface, service-result assembly, and delegation to private compile helpers. | Artifact cleanup internals, SQL writer batching, adapter/profile diagnostic tokenization, per-check rendering metadata mutation, concrete renderer defaults in orchestration code. |
| New artifact publication helper, or equivalent | Clear compiled YAML and SQL outputs safely, write compiled contract/check artifacts, write compiled SQL artifacts, discard partial outputs, convert artifact write failures into current diagnostics. | Compiler validation, profile loading, adapter setup, renderer selection, diagnostic redaction policy, CLI option parsing. |
| New render-SQL orchestration helper, or equivalent | Coordinate current render-SQL flow for already compiled contracts: use prepared adapters, render checks, collect render results, apply rendering metadata, and request SQL publication. | Project parsing, compiler validation, artifact cleanup policy outside render output, profile loader internals, new renderer discovery. |
| New adapter/profile preparation helper, or equivalent | Load selected profile for referenced connection names, resolve adapters from the supplied or default registry, validate adapter metadata and API compatibility, preserve literal profile type matching, and return prepared adapters plus setup diagnostics. | Rendering SQL, writing artifacts, changing profile-loader behavior, broad profile-loader decomposition. |
| Rendering metadata helper, or equivalent | Apply rendered, blocked, and failed `Rendering` metadata to compiled checks; produce existing output-suppressed and compile-diagnostic-blocked diagnostics. | Adapter resolution, SQL writing, compiler validation, diagnostic redaction token extraction. |
| Profile-backed diagnostic privacy helper, or equivalent | Preserve current compile render-SQL redaction/token behavior for adapter setup and render diagnostics. | Broad redaction redesign, changing unsafe-token policy, changing diagnostic codes/messages, sharing as a public adapter API. |
| Existing artifact writers | Keep owning concrete YAML and SQL file writes, path validation, and writer-level preflight behavior. | Compile command orchestration, profile loading, adapter resolution. |
| Existing compiler | Keep owning compiled contracts, checks, typed plans, and compile diagnostics. | Generated artifact cleanup, profile loading, adapter setup, SQL artifact writing. |
| Existing profile loader | Keep owning selected target/profile rendering, referenced connection filtering, env-var behavior, unsupported-template rejection, and profile diagnostics. | Compile artifact writing, render metadata, adapter SQL rendering. |

Exact private module names may change during implementation if the final split
better matches the code. The invariant is ownership separation, not filename
spelling. Public `recon_core.services.CompileService` import compatibility must
remain intact.

The current in-core DuckDB render-SQL default may remain only as a private
compile rendering detail for the current in-core DuckDB adapter. Item 13 must
not introduce external adapter discovery or a third-party renderer registry. If
implementation moves renderer selection, prefer isolating the current DuckDB
import away from the `CompileService` orchestration module while keeping current
behavior unchanged.

## Expected Behavior

For current CLI behavior:

- `recon compile` success message, validation messages, runtime-error messages,
  diagnostic rendering, and exit categories remain unchanged.
- `recon compile --render-sql` success, setup-failure, render-failure,
  compile-diagnostic, and artifact-write messages remain unchanged.
- CLI command handlers stay thin and do not gain compile/render/artifact logic.

For generated artifacts:

- `target/compiled_contracts/`, `target/compiled_checks/`, and
  `target/compiled_sql/` paths remain unchanged.
- Compiled artifact schemas, field order expectations from existing writer
  tests, rendering statuses, `rendering.sql_paths`, and
  `rendering.adapter_type` behavior remain unchanged.
- Stale compiled YAML and SQL outputs are still cleared after project
  configuration succeeds and before parse/compile continues.
- Failed parse or fatal compile validation leaves no stale compiled artifacts.
- Failed artifact writes leave no misleading partial compiled YAML or orphaned
  compiled SQL output.
- Successful rendered checks still produce at least one SQL file each, and any
  malformed or empty rendered SQL output fails before artifact publication.

For render-SQL behavior:

- Plain compile still does not load profiles or resolve adapters.
- Compile validation diagnostics still take precedence over profile and adapter
  configuration for render-SQL.
- Adapter setup diagnostics still produce blocked compiled-check rendering
  metadata and no SQL files.
- Mixed adapter types and distinct connection contexts still block rendering.
- Query endpoints still block relation-only rendering without SQL artifacts.
- Current DuckDB rendered SQL text, step names, operation types, required
  capabilities, and output paths remain byte-for-byte compatible with existing
  tests.
- Capability enforcement for rendered steps still happens before compiled SQL
  publication.

For privacy and diagnostics:

- Profile-backed adapter diagnostics remain sanitized across code, message,
  hint, path, resource type, resource name, line, column, and
  `rendering.adapter_type`.
- Adapter setup diagnostics and independent render diagnostics from otherwise
  resolvable contracts both remain visible.
- Raw adapter exceptions, database errors, rendered profile values, DSN
  fragments, credentials, source/target query text, relation data, row values,
  and raw failure details do not enter service diagnostics, terminal output,
  generated artifacts, tests, or companion notes.

## Acceptance And Conformance Matrix

| Case | Expected behavior | Required implementation coverage |
| --- | --- | --- |
| Plain compile success | Same compiled YAML artifacts and success message; no profile loading or SQL directory. | Existing compile-service success tests and CLI compile test. |
| Project/config failure | Same configuration error result; no cleanup based on unknown target path. | Existing service tests. |
| Parse failure | Same validation result; stale compiled YAML/SQL outputs removed after target path is known; no new artifacts. | Existing parse-failure and stale-output tests. |
| Fatal compile validation | Same validation result and no artifacts. | Existing no-contracts, invalid stable ID, duplicate contract, and filename-collision tests. |
| Partial compile validation | Same compiled YAML artifacts and validation summary. | Existing compile-validation tests. |
| Render-SQL compile diagnostics | Compile diagnostics block rendering before profile/adapter work, write blocked rendering metadata, and write no SQL files. | Existing blocked-by-compile-diagnostics tests. |
| Render-SQL profile failure | Same configuration error and diagnostics; no SQL artifacts. | Existing missing/invalid profile tests. |
| Adapter resolution failure | Same blocked compiled-check metadata, de-duplicated setup diagnostics, and no SQL artifacts. | Existing adapter resolution and malformed factory tests. |
| Adapter setup plus render diagnostics | Setup diagnostics do not mask independent render diagnostics from otherwise resolvable contracts. | Existing setup-and-render diagnostics test. |
| Metadata/API mismatch | Same adapter metadata, API compatibility, profile type mismatch, and support-state diagnostics. | Existing render-SQL adapter metadata/API tests. |
| Same-context requirement | Distinct connection contexts still block current render-SQL. | Existing distinct-context test. |
| Query endpoint boundary | Query endpoints remain blocked without SQL artifacts. | Existing query-endpoint render-SQL test. |
| Render success | Same compiled SQL files, `rendering.status`, `sql_paths`, `adapter_type`, and success message. | Existing render-SQL success tests and SQL writer tests. |
| Render failure | Same `blocked` or `failed` metadata, no SQL files, and safe diagnostics. | Existing renderer failure, empty output, malformed output, and output-suppression tests. |
| Capability enforcement | Unsupported rendered-step capabilities block before SQL publication. | Existing rendered-step capability test. |
| Artifact preflight | Unsafe, symlinked, colliding, invalid, empty, or partial output paths fail before misleading publication. | Existing artifact writer and compile-service cleanup tests. |
| Diagnostic privacy | All existing profile-backed redaction cases pass unchanged. | Existing compile-service redaction tests. |
| CLI output | `recon compile` and `recon compile --render-sql` terminal behavior stays unchanged. | Existing CLI tests plus focused service tests. |
| Regression routing | Any new or moved compile helper owning governed surfaces is exact-routed. | Update `index.yml` and script tests during implementation if ownership changes. |

## Workflow Scenarios

Scenario: plain compile stays profile-free.

- Given a project with a selected profile target,
- when `recon compile` runs without `--render-sql`,
- then compile writes compiled YAML artifacts and does not require or inspect
  profiles.

Scenario: compile diagnostics block render-SQL before adapter setup.

- Given compile produces diagnostics but still produces compiled contracts,
- when `recon compile --render-sql` runs,
- then compiled checks show rendering blocked by compile diagnostics, no
  profiles or adapters are invoked, and no SQL files are written.

Scenario: adapter setup failure remains artifact-visible and private.

- Given referenced profile connections resolve to adapter setup diagnostics,
- when render-SQL runs,
- then affected checks are marked blocked, no SQL files are written, setup
  diagnostics are de-duplicated and connection-scoped, and rendered profile
  values do not leak.

Scenario: one render failure suppresses all SQL output for the invocation.

- Given one check renders with diagnostics and another could otherwise render,
- when render-SQL runs,
- then no compiled SQL files are written; the failing check is failed or
  blocked, and the otherwise renderable check is blocked with output-suppressed
  metadata.

Scenario: artifact publication stays all-or-nothing.

- Given SQL rendering succeeds in memory but a later YAML or SQL artifact write
  fails,
- when compile handles the failure,
- then partial generated outputs are removed and downstream automation cannot
  read stale or orphaned artifacts as current evidence.

## Source Map

Implementation is expected to inspect or edit:

- `src/recon_core/services/compile.py`
- new private modules under `src/recon_core/services/`
- `tests/services/test_compile_service.py`
- `tests/cli/test_main.py`
- `docs/compatibility/regression-capture/index.yml`
- `tests/scripts/test_check_regression_capture_decisions.py`

Implementation may inspect, but should avoid changing unless needed:

- `src/recon_core/services/__init__.py`
- `src/recon_core/compiler/compile.py`
- `src/recon_core/compiler/models.py`
- `src/recon_core/artifacts/compiled_contract_writer.py`
- `src/recon_core/artifacts/compiled_check_writer.py`
- `src/recon_core/artifacts/compiled_sql_writer.py`
- `src/recon_core/artifacts/_paths.py`
- `src/recon_core/adapters/rendering.py`
- `src/recon_core/adapters/rendered_sql_validation.py`
- `src/recon_core/adapters/default_registry.py`
- `src/recon_core/adapters/registry.py`
- `src/recon_core/adapters/duckdb/`
- `src/recon_core/profiles/`
- `docs/architecture/parse-compile-run.md`
- `docs/architecture/artifact-model.md`
- `docs/architecture/cli-architecture.md`
- `docs/implementation/cli-services.md`
- `docs/implementation/compiled-artifacts.md`
- `docs/implementation/contract-compiler-and-validation.md`
- `docs/implementation/errors-and-diagnostics.md`
- `docs/implementation/testing-plan.md`
- `docs/compatibility/public-contract-inventory.md`
- `docs/compatibility/change-checklist.md`
- `docs/compatibility/regression-capture/`

Implementation should not edit `RunService`, check-engine modules, profile
loader behavior, DuckDB renderer SQL builders, adapter API docs, or public
exports unless source inspection proves a tiny compatibility seam is necessary.
Broad changes to those areas are different final-order items.

## Responsibility Map

| Component | Allowed responsibilities | Forbidden responsibilities | Refactor trigger | Tests protecting boundary |
| --- | --- | --- | --- | --- |
| `CompileService` | Public service entry point, injected registry option, top-level flow, service-result delegation. | Artifact writer internals, profile diagnostic tokenization, renderer SQL details, concrete adapter-specific defaults in orchestration. | If `execute()` still contains most render-SQL or artifact cleanup logic after extraction, split another private helper. | Compile-service and CLI tests. |
| Compile pipeline helper | Load parsed project through existing parser pipeline and invoke compiler with current context config. | Artifact writes, profile loading, adapter setup, renderer selection. | If it starts interpreting raw YAML or reading manifest freshness, stop and re-check scope. | Parser/compiler service tests and compile validation tests. |
| Artifact publication helper | Safe cleanup, YAML writes, SQL writes, rollback/discard, artifact write diagnostics. | Compiler validation, adapter setup, SQL rendering, profile redaction. | If it needs profile or adapter objects, the boundary is wrong. | Artifact writer tests and compile-service cleanup tests. |
| Render-SQL helper | Coordinate current render-SQL flow after compilation, collect render results, apply rendering metadata, request SQL publication. | Project parsing, compile validation ownership, profile-loader internals, external renderer discovery. | If it changes SQL output or generated metadata shape, stop for public-contract review. | Render-SQL service tests and renderer tests. |
| Adapter/profile preparation helper | Referenced connection selection, selected profile load call, adapter registry resolution, metadata/API validation, setup diagnostics. | SQL rendering, artifact writing, changing profile-loader semantics. | If profile-loading behavior changes, defer to profile-loader item 14. | Profile-backed compile-service tests. |
| Diagnostic privacy helper | Current compile render-SQL adapter diagnostic sanitization and token checks. | Broad redaction redesign, changing redaction policy, public API export. | If new privacy policy is required, defer to item 15 or stop for docs/ADR. | Redaction tests covering every public diagnostic field. |
| Rendering metadata helper | `Rendering` status transitions, blocked/failed/rendered metadata, output suppression and compile-diagnostic blocked diagnostics. | Adapter resolution, writer preflight, compiler validation. | If metadata status meanings change, stop for compatibility docs and changelog. | Compiled-check artifact tests. |
| Regression-capture metadata | Exact-route new compile split modules to owned surfaces. | Relying on old monolith or generic prefixes after ownership moves. | Any new/moved service file owning generated artifacts, rendering, diagnostics, profile secrets, CLI output, adapter setup, or compiler behavior requires route review. | Regression-capture decision script tests and `--base-ref origin/main`. |

## Affected Docs

This prework adds this planning artifact.

Future implementation is expected to be behavior-preserving and should not need
durable public architecture or compatibility wording changes if:

- public behavior and generated outputs stay unchanged,
- no diagnostic code, message, rendering status, artifact field, artifact path,
  adapter API, capability meaning, service message, exit category, or CLI
  output changes,
- package-level imports remain compatible,
- regression-capture routing is updated for any new or moved compile helper
  files.

If implementation changes one of those surfaces, stop and update the relevant
compatibility docs, implementation docs, ADRs, and changelog decision before
claiming completion.

No changelog entry is required for this prework because it changes planning
only.

## Compatibility, Security, And Privacy Impact

Compatibility impact:

- Current `recon compile` and `recon compile --render-sql` behavior must remain
  compatible.
- Current compiled artifact schemas, compiled SQL paths, rendering metadata,
  typed-plan payloads, adapter API version, capability names, diagnostic codes,
  service messages, exit categories, and CLI output must not change.
- Internal helper import paths may move only if public package exports remain
  compatible.
- Future adapter and test-kit compatibility improves because compile ownership
  becomes easier to route and audit.

Security and privacy impact:

- Decomposition must not expose rendered profile values, credentials, DSN
  fragments, raw adapter exceptions, raw database errors, source/target query
  text, relation data, row values, raw failure details, or unsafe diagnostic
  codes in diagnostics, terminal output, generated artifacts, tests, or
  companion notes.
- No generated outputs, local profiles, evidence, result artifacts, reports, or
  state files should be created or committed by this refactor.

## Required Tests For Future Implementation

Before item 13 implementation claims completion, run at minimum:

```bash
python3 -m pytest tests/services/test_compile_service.py -q
python3 -m pytest tests/cli/test_main.py -q
python3 -m pytest tests/artifacts/test_compiled_artifact_writers.py tests/artifacts/test_compiled_sql_writer.py -q
python3 -m pytest tests/adapters/test_rendering.py tests/adapters/test_duckdb_sql_renderer.py -q
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

Also run local-success blindness guards after implementation:

- no generated artifact schema, path, status, or CLI output expected-string
  churn unless explicitly approved,
- no `DuckDbSqlRenderer` or `recon_core.adapters.duckdb` import in
  `src/recon_core/services/compile.py` if renderer selection moved to a private
  helper,
- no profile loader, adapter registry, or renderer imports in artifact
  publication helpers,
- no artifact writer or filesystem cleanup imports in adapter/profile
  preparation helpers,
- no profile token/redaction helper imports in compiler modules,
- every new compile helper file exact-routes through regression-capture
  metadata when it owns a governed surface.

## Local-Success Blindness Second Pass

A passing local `recon compile --render-sql` run is insufficient if the
implementation still:

- leaves `CompileService.execute()` owning a full vertical artifact,
  render-SQL, adapter setup, and redaction path,
- changes generated artifacts, SQL paths, rendering metadata, service messages,
  diagnostic ordering, or CLI output unexpectedly,
- hides missing profile, adapter setup, metadata, capability, or renderer
  failures behind generic compile failures,
- masks independent render diagnostics when adapter setup diagnostics also
  exist,
- weakens compile-diagnostic precedence over profile and adapter setup,
- changes artifact cleanup, rollback, or stale-output behavior while preserving
  only happy-path SQL generation,
- moves files without updating regression-capture routing and routing tests,
- introduces concrete DuckDB or future adapter imports into the public compile
  orchestration boundary,
- broadens into profile-loader decomposition, redaction policy redesign,
  renderer registry design, external adapter discovery, selector behavior,
  artifact freshness, run results, evidence, or `RunService`.

## Regression Capture Review

Applicable regression-capture routing before implementation:

- `src/recon_core/artifacts/` prefix-routes to `generated_artifacts` and
  `artifact_lifecycle`.
- `tests/artifacts/` prefix-routes to the same artifact surfaces.
- `src/recon_core/cli/` and `tests/cli/` prefix-route to `cli`,
  `terminal_output`, and `exit_codes`.
- `src/recon_core/adapters/duckdb/renderer.py`,
  `renderer_operations.py`, and `renderer_sql.py` exact-route to
  `sql_rendering`.
- `src/recon_core/profiles/loader.py` exact-routes to `diagnostics`,
  `profile_secrets`, and `redaction`.
- `src/recon_core/profiles/connection_references.py` exact-routes to
  `diagnostics`, `profile_secrets`, and `redaction`.
- `src/recon_core/compiler/models.py` exact-routes to `typed_check_plan`.
- `src/recon_core/compiled_artifact_schema.py` exact-routes to
  `artifact_lifecycle`, `generated_artifacts`, and `typed_check_plan`.

Current gap to close during implementation:

- `src/recon_core/services/compile.py` and any new compile-service helper
  modules should be exact-routed to the surfaces they own. Do not assume
  artifact, CLI, adapter, profile, or compiler prefix routes cover behavior
  once service ownership is split.

Likely route decisions during implementation:

- artifact publication helper: `generated_artifacts`, `artifact_lifecycle`,
- render-SQL orchestration helper: `sql_rendering`, `adapter_runtime`,
  `adapter_capabilities`, `generated_artifacts`,
- adapter/profile preparation helper: `adapter_runtime`, `adapter_api`,
  `adapter_capabilities`, `diagnostics`, `profile_secrets`, `redaction`,
- rendering metadata helper: `generated_artifacts`, `artifact_lifecycle`,
  `sql_rendering`, `diagnostics`,
- diagnostic privacy helper: `diagnostics`, `profile_secrets`, `redaction`,
  `adapter_diagnostics`,
- remaining `services/compile.py`: `cli`, `terminal_output`, `exit_codes`,
  plus any surfaces it still directly owns after extraction.

Implementation must apply the routing ownership principle:

- identify the old effective route before moving code,
- exact-route any new module that owns generated artifacts, artifact
  lifecycle, SQL rendering, adapter runtime, adapter API, adapter capabilities,
  diagnostics, profile secrets, redaction, CLI output, exit codes, compiler, or
  typed-plan behavior,
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

1. Add or preserve focused boundary tests before moving code: public
   `CompileService` import compatibility, CLI output stability, no profile
   loading for plain compile, compile-diagnostic render blockers before profile
   work, artifact cleanup/rollback behavior, and new import-boundary guards.
2. Extract compiled artifact cleanup, YAML writing, SQL writing, discard, and
   artifact runtime-error construction behind one private artifact publication
   boundary.
3. Extract rendering metadata helpers for rendered, blocked, failed,
   output-suppressed, and compile-diagnostic-blocked states without changing
   diagnostics or artifact shape.
4. Extract adapter/profile preparation for render-SQL while preserving selected
   profile loading, referenced connection filtering, adapter metadata/API
   validation, literal profile type matching, and diagnostic de-duplication.
5. Extract render-SQL orchestration so it coordinates prepared adapters,
   current renderer selection, `render_check_sql()`, sanitized render results,
   and SQL publication without owning artifact cleanup or profile loading.
6. Move profile-backed diagnostic sanitization only as far as needed to remove
   vertical ownership from `compile.py`; do not redesign redaction policy in
   item 13.
7. Update regression-capture routing and routing tests for every new or moved
   governed file.
8. Run focused tests after each extraction, then run full validation and the
   local-success blindness second pass.

Implementation should stop for user approval if it requires any public
behavior change, generated artifact change, diagnostic-code change, adapter API
change, capability change, public export narrowing, broad profile-loader
decomposition, broad redaction redesign, renderer registry design, external
adapter discovery, selector behavior, artifact freshness behavior, or
run-result/evidence output.

## Definition Of Done

Item 13 implementation is complete only when:

- `CompileService.execute()` is reduced to command-level orchestration and
  delegation.
- Artifact cleanup, YAML publication, SQL publication, and rollback have a
  clear private owner.
- Render-SQL adapter/profile preparation has a clear private owner.
- Rendering metadata mutation has a clear private owner.
- Profile-backed diagnostic sanitization is not interleaved with service
  orchestration.
- Current `recon compile` and `recon compile --render-sql` behavior, messages,
  artifacts, diagnostics, privacy, and exit categories are unchanged.
- No non-goal scope is introduced.
- Regression-capture routing covers every new or moved governed file.
- Current compile-service, CLI, artifact writer, renderer, regression-capture,
  and full validation pass.
- Companion brain dump records validation, remaining risks, split decision,
  changelog decision, local-success blindness result, and regression-capture
  decision.

Split Decision: Already Split / Follow Existing Split.

Changelog Decision: Not Required for prework.

`regression_capture_decision: not-required`
