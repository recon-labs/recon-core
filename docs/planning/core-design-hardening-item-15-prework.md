# Core Design Hardening Item 15 Prework

## Purpose

This is the prework artifact for final-order item 15: decompose adapter
diagnostic redaction internals.

Item 15 is high-risk because it touches profile-backed adapter diagnostics,
diagnostic-code suppression, rendered profile value privacy, runtime adapter
setup diagnostics, compile-time render-SQL diagnostics, compiled-check blocked
metadata, public terminal output, adapter compatibility, and future shared
adapter test-kit behavior. This artifact locks the responsibility map before
coding. It does not implement runtime behavior.

Split Decision: Already Split / Follow Existing Split.

The broader hardening branch already split this work away from adapter
capability semantics, runtime renderer wiring, DuckDB renderer decomposition,
check-engine decomposition, compile-service decomposition, profile-loader
decomposition, public export-barrel policy, and `BaseAdapter` metadata-interface
work. Item 15 should remain a behavior-preserving decomposition inside the
adapter diagnostic redaction boundary.

## Scope

Item 15 prework covers:

- profile-backed adapter diagnostic redaction for current adapter-aware compile,
- profile-backed adapter diagnostic redaction for current runtime adapter setup
  and adapter lifecycle paths,
- diagnostic code suppression with
  `RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED`,
- unsafe rendered profile key and value token collection,
- DSN fragment and parsed component token extraction,
- case-variant and simple transformed rendered-value matching,
- short numeric rendered scalar matching in diagnostic text, resource metadata,
  `line`, `column`, diagnostic codes, and `rendering.adapter_type`,
- safe public diagnostic-code preservation,
- compile-specific redaction of `RenderedCheckSql.diagnostics` and
  `rendering.adapter_type`,
- context-specific generic replacement messages for compile and runtime paths,
- tests, regression-capture routing, compatibility, privacy, and
  implementation-readiness criteria.

The selected design is conservative: split private redaction responsibilities
without changing public YAML shape, profile rendering behavior, adapter API
shape, diagnostic codes, diagnostic messages, diagnostic resource metadata,
compiled artifact schemas, rendering metadata semantics, CLI output, runtime
execution behavior, or public Python exports.

## Non-Goals

Item 15 prework and implementation must not implement:

- new secret-classification config,
- user-configurable redaction policies,
- broad diagnostic redaction redesign,
- profile schema versioning,
- debug/profile commands,
- secure debug artifacts,
- native database error disclosure,
- rendered SQL disclosure,
- run results, evidence, reports, failure details, result sinks, or logs,
- new adapter API version or adapter API shape,
- adapter package discovery or entry points,
- renderer registry changes,
- query endpoint execution,
- broad runtime execution expansion,
- new diagnostic codes except for tests that intentionally assert existing
  behavior,
- public Python export narrowing,
- adapter test-kit extraction.

## Current Audit Findings

Current behavior is covered, but ownership is duplicated and dense:

- `src/recon_core/adapters/diagnostic_redaction.py` owns runtime-facing
  profile-backed adapter diagnostic redaction. It collects rendered profile
  string tokens, diagnostic-code tokens, numeric field tokens, DSN components,
  and suppresses unsafe diagnostics for adapter registry, runtime setup, run
  service, and check-engine execution-support paths.
- `src/recon_core/services/_compile_diagnostic_privacy.py` duplicates much of
  that token collection and matching logic for compile/render-SQL paths. It
  additionally owns compile-specific `RenderedCheckSql` sanitization and
  `rendering.adapter_type` redaction.
- `src/recon_core/services/_compile_adapter_setup.py` computes compile
  connection token sets once per connection and passes them through adapter
  setup redaction calls.
- `src/recon_core/services/_compile_render_sql.py` recomputes token sets for
  prepared source and target adapters, sanitizes metadata diagnostics, renderer
  diagnostics, unsupported-renderer diagnostics, render results, and
  `rendering.adapter_type`.
- `src/recon_core/adapters/runtime_setup.py`,
  `src/recon_core/adapters/registry.py`,
  `src/recon_core/services/run.py`, and
  `src/recon_core/check_engine/execution_support.py` use
  `recon_core.adapters.diagnostic_redaction` for runtime/profile-backed adapter
  diagnostic sanitization.
- Existing compile coverage is concentrated in
  `tests/services/test_compile_service.py`; it covers adapter factory
  exceptions, adapter API diagnostics, metadata diagnostics, capability
  declaration failures, render-phase diagnostics, diagnostic-code suppression,
  safe-code preservation, DSN fragments, non-string rendered values, numeric
  `line`/`column`, short numeric text/resource metadata,
  `rendering.adapter_type`, and integer-equivalent numeric variants.
- Existing runtime/setup coverage lives in
  `tests/adapters/test_runtime_setup.py`, `tests/adapters/test_registry.py`,
  `tests/services/test_run_service.py`, `tests/cli/test_main.py`, and
  `tests/check_engine` execution-support paths.
- Regression-capture metadata exact-routes
  `src/recon_core/services/_compile_diagnostic_privacy.py` to
  `adapter_diagnostics`, `diagnostics`, `profile_secrets`, and `redaction`.
  `src/recon_core/adapters/diagnostic_redaction.py` is currently covered only
  by broader adapter prefixes, so item 15 implementation must add exact routing
  for that file and any new redaction helpers.

Current behavior to preserve:

- Unsafe adapter diagnostic text or metadata is replaced with a generic safe
  diagnostic that preserves severity and actionable context.
- If the unsafe content is in the diagnostic code, the code is replaced with
  `RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED`.
- Safe adapter diagnostic codes remain unchanged even if they contain incidental
  non-secret words.
- Rendered profile values, unsafe keys, credentials, tokens, DSN fragments,
  parsed DSN username/password/host/path/query components, case variants,
  simple transformed values, numeric scalar values, and equivalent integer-like
  numeric representations do not appear in public diagnostics, blocked
  compiled-check metadata, or `rendering.adapter_type`.
- `line` and `column` are cleared when they match rendered numeric profile
  values.
- Compile-specific suppression message wording remains unchanged.
- Runtime-specific suppression message wording remains unchanged.
- `rendering.adapter_type` falls back to the literal profile connection `type`
  only when adapter metadata leaks rendered profile config; invalid or empty
  adapter type metadata still sanitizes to absent metadata as currently tested.
- Adapter setup failures still block rendering, write no compiled SQL, preserve
  distinct source/target diagnostics, de-duplicate repeated same-connection
  diagnostics, and preserve independent render diagnostics from otherwise
  resolvable contracts.
- Current row-count and bounded local/dev grain-key safety runtime diagnostics
  remain sanitized and do not broaden adapter execution.

## Decomposition Decision

Adapter diagnostic redaction decomposition should split reusable token
collection, diagnostic matching, and replacement construction while preserving
context-specific compile and runtime wrapper behavior.

Recommended implementation shape:

| Module or component | Allowed responsibility | Forbidden responsibility |
| --- | --- | --- |
| `adapters/diagnostic_redaction.py` | Stable adapter-facing redaction wrapper, `ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED`, runtime/profile-backed diagnostic sanitization entry point, and delegation to private helpers. | Compile artifact metadata, `RenderedCheckSql`, service-result messages, broad export policy changes. |
| New private token helper, or equivalent | Collect rendered profile text tokens, diagnostic-code boundary/embedded tokens, numeric field tokens, DSN components, percent-decoded values, and secret-like config-key classification. | Constructing public diagnostics, importing services, rendering SQL, adapter setup orchestration. |
| New private matching helper, or equivalent | Decide whether diagnostic code, text fields, resource metadata, numeric `line`/`column`, or `rendering.adapter_type` mention unsafe rendered profile tokens. | Mutating diagnostics, service-specific messages, adapter registry behavior. |
| New private sanitizer/core helper, or equivalent | Build a sanitized diagnostic from a source diagnostic, token context, connection identity, and caller-provided safe message policy. | Choosing compile/run exit categories, writing artifacts, loading profiles, adapter resolution. |
| `services/_compile_diagnostic_privacy.py` | Compile-specific wrapper around shared redaction internals, token-context reuse for compile paths, `RenderedCheckSql` replacement, and `rendering.adapter_type` redaction. | Duplicated low-level token matching after extraction, runtime adapter setup policy, artifact publication. |
| `services/_compile_adapter_setup.py` | Adapter resolution, API validation, metadata matching, and connection-scoped setup diagnostics for render-SQL. | Low-level redaction token matching, rendered SQL, artifact publication. |
| `services/_compile_render_sql.py` | Current in-memory render-SQL orchestration and compile-specific redaction calls for render diagnostics and rendering metadata. | Low-level token extraction internals, broad renderer registry changes, profile-loader behavior. |
| `adapters/runtime_setup.py` and `adapters/registry.py` | Adapter factory/runtime setup validation and runtime capability diagnostics, using the adapter-facing redaction wrapper. | Compile-specific redaction messages, `RenderedCheckSql`, generated artifact behavior. |
| `services/run.py` and `check_engine/execution_support.py` | Runtime/lifecycle/query diagnostic fallback and source-target privacy checks, using the adapter-facing redaction wrapper where profile-backed adapter diagnostics are involved. | Compile-service redaction helper imports, profile rendering internals, broad execution expansion. |

Exact private module names may change during implementation if the final split
better matches the code. The invariant is ownership separation and shared
low-level redaction logic, not filename spelling. Public `recon_core.adapters`
exports must remain compatible unless implementation stops for explicit
public API/export-policy approval.

## Expected Behavior

For compile-time adapter diagnostics:

- Adapter factory diagnostics, adapter metadata diagnostics, adapter API
  compatibility diagnostics, capability diagnostics, unsupported-renderer
  diagnostics, and render-phase diagnostics keep current public codes,
  messages, resource metadata, blocked compiled-check metadata, and CLI output.
- Unsafe profile-backed diagnostic fields are suppressed exactly as today.
- Safe adapter diagnostic codes remain preserved.
- Unsafe diagnostic codes are replaced with
  `RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED`.
- Failed adapter setup still writes blocked compiled-check metadata and no SQL
  files.
- Render diagnostics still suppress all compiled SQL for that invocation when
  current rules require it.

For runtime adapter diagnostics:

- Adapter registry, runtime setup, run-service lifecycle, and check-engine
  execution-support diagnostics keep current sanitization behavior.
- Runtime fallback diagnostics keep current safe exception-type-only hints where
  applicable.
- Adapter lifecycle close failures do not hide primary execution failures.
- No raw database errors, rendered SQL, query text, credentials, DSN fragments,
  rendered profile values, or relation data leak through diagnostics.

For public contracts and compatibility:

- No adapter API version or public adapter interface changes.
- No compiled artifact schema, rendering metadata shape, CLI output, result
  model, evidence, or report behavior changes.
- No public package export narrowing.
- Adapter/Profile Diagnostic Conformance Gate remains the source of truth for
  future adapter test-kit and external adapter compatibility.

## Acceptance And Conformance Matrix

| Case | Expected behavior | Required implementation coverage |
| --- | --- | --- |
| Public adapter redaction imports | Existing `ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED` import behavior remains compatible. | Existing imports plus focused import compatibility check if needed. |
| Compile wrapper behavior | `services/_compile_diagnostic_privacy.py` preserves compile-specific messages and `RenderedCheckSql`/`rendering.adapter_type` sanitization. | Existing compile-service redaction tests; add focused helper tests if split changes token context. |
| Runtime wrapper behavior | `adapters/diagnostic_redaction.py` preserves runtime-specific suppression messages for registry/runtime setup/run paths. | Existing runtime setup, registry, run-service, and CLI tests. |
| Factory exceptions | Raw exception text and rendered profile values stay suppressed while safe exception type context remains where currently expected. | Existing compile-service, registry, runtime setup, and run-service tests. |
| Adapter-provided diagnostics | Unsafe message, hint, path, resource type, resource name, line, column, and future structured fields are suppressed. | Existing compile-service/runtime tests plus focused helper tests if new helpers own field matching. |
| Diagnostic-code redaction | Unsafe config keys and rendered values in delimiter-separated or separatorless diagnostic codes are suppressed. | Existing compile-service tests for `RC_PASSWORD_LEAK`, `RCPASSWORDLEAK`, rendered-value embeddings, and numeric embeddings. |
| Safe-code preservation | Safe public adapter codes with incidental non-secret words are preserved. | Existing compile-service/runtime setup tests. |
| DSN parsing | Username, password, host, path, query values, percent-decoded values, and split fragments remain unsafe when derived from rendered profile config. | Existing compile-service tests; add focused token tests if token helper is extracted. |
| Numeric field matching | Numeric rendered scalars and integer-equivalent formats match diagnostic codes, text, resource metadata, line, column, and `rendering.adapter_type`. | Existing compile-service tests for `12`, `12.0`, `+12`, and `1.2e1`; add helper tests if split changes numeric parsing. |
| Adapter type metadata redaction | Unsafe `rendering.adapter_type` is replaced with literal profile `type`; invalid/empty metadata remains absent. | Existing compile-service tests. |
| Setup diagnostic grouping | Same-connection diagnostics remain de-duplicated; distinct source/target diagnostics remain visible. | Existing compile-service tests. |
| Independent setup and render diagnostics | Setup diagnostics do not mask render diagnostics from otherwise resolvable contracts. | Existing compile-service tests. |
| Artifact safety | Adapter setup/render diagnostics still write no compiled SQL when current rules block publication. | Existing compile-service generated-artifact tests. |
| Runtime execution privacy | Current row-count and bounded local/dev grain-key safety runtime diagnostics remain sanitized. | Existing run-service and CLI tests. |
| Boundary imports | Adapter redaction internals do not import services, compiled artifacts, render-SQL orchestration, or concrete adapters. Compile privacy wrappers do not leak into compiler/check-engine modules. | Existing boundary tests plus new focused boundary tests if private helpers are created. |
| Regression routing | Existing and new redaction helper files are exact-routed to diagnostic/privacy surfaces. | Update `index.yml` and script tests during implementation. |

## Workflow Scenarios

Scenario: adapter setup diagnostic contains rendered profile secrets.

- Given a selected profile connection renders a password, token, DSN, or short
  numeric scalar,
- when adapter setup returns a diagnostic containing that value in any public
  diagnostic field,
- then the public diagnostic uses safe generic adapter context, suppresses the
  unsafe field value, preserves severity, and preserves the original diagnostic
  code only when the code is safe.

Scenario: adapter diagnostic code embeds unsafe profile data.

- Given an adapter diagnostic code contains a rendered profile key or value in
  delimiter-separated or separatorless form,
- when compile or runtime sanitizes the diagnostic,
- then the public code is `RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED` and no
  compiled artifact or terminal output contains the unsafe token.

Scenario: renderer metadata leaks profile config.

- Given render-SQL returns `rendering.adapter_type` that includes a rendered
  profile value or equivalent numeric token,
- when compile writes blocked or failed rendering metadata,
- then `rendering.adapter_type` falls back to the literal profile connection
  `type` or is omitted according to current behavior.

Scenario: runtime lifecycle diagnostics stay safe.

- Given runtime adapter connect, execute, or close raises a diagnostic-bearing
  exception whose text includes rendered profile config or database payloads,
- when `recon run` reports diagnostics,
- then public diagnostics remain sanitized and no raw adapter/database payload
  appears in terminal output.

Scenario: helper extraction does not create a compile/runtime dependency leak.

- Given redaction internals are split into private helpers,
- when adapter registry, runtime setup, run service, check engine, and compile
  render-SQL paths import redaction code,
- then adapter-layer helpers do not import compile services, artifact writers,
  concrete DuckDB modules, or renderer orchestration.

## Source Map

Implementation is expected to inspect or edit:

- `src/recon_core/adapters/diagnostic_redaction.py`
- new private modules under `src/recon_core/adapters/`, if used
- `src/recon_core/services/_compile_diagnostic_privacy.py`
- `src/recon_core/services/_compile_adapter_setup.py`
- `src/recon_core/services/_compile_render_sql.py`
- `src/recon_core/adapters/runtime_setup.py`
- `src/recon_core/adapters/registry.py`
- `src/recon_core/services/run.py`
- `src/recon_core/check_engine/execution_support.py`
- `tests/services/test_compile_service.py`
- `tests/adapters/test_runtime_setup.py`
- `tests/adapters/test_registry.py`
- `tests/services/test_run_service.py`
- `tests/cli/test_main.py`
- `tests/services/test_compile_service_boundaries.py`
- `tests/scripts/test_check_regression_capture_decisions.py`
- `docs/compatibility/regression-capture/index.yml`

Implementation may inspect, but should avoid changing unless needed:

- `src/recon_core/adapters/__init__.py`
- `src/recon_core/adapters/base.py`
- `src/recon_core/adapters/capabilities.py`
- `src/recon_core/adapters/rendering.py`
- `src/recon_core/adapters/rendered_sql_validation.py`
- `src/recon_core/profiles/loader.py`
- `src/recon_core/profiles/_rendering.py`
- `docs/compatibility/adapter-api.md`
- `docs/compatibility/compatibility-matrix.md`
- `docs/implementation/errors-and-diagnostics.md`
- `docs/compatibility/public-contract-inventory.md`
- `docs/compatibility/change-checklist.md`
- `docs/compatibility/regression-capture/diagnostics-privacy.yml`

Implementation should not edit adapter API shape, adapter registry semantics,
profile rendering behavior, compile artifact schemas, CLI output wording,
runtime execution behavior, public exports, or compatibility docs unless source
inspection proves a tiny alignment change is required. Broad changes to those
areas are different final-order items or future gated surfaces.

## Responsibility Map

| Component | Allowed responsibilities | Forbidden responsibilities | Refactor trigger | Tests protecting boundary |
| --- | --- | --- | --- | --- |
| `adapters/diagnostic_redaction.py` | Stable adapter-facing redaction wrapper and current public constant. | Compile-only `RenderedCheckSql`, service messages, generated artifact metadata. | If the module remains a 500-line vertical mix after implementation, split private helpers. | Runtime setup, registry, run-service, CLI privacy tests. |
| Token collection helper | Rendered config key/value, DSN, decoded fragment, code-token, and numeric-token extraction. | Constructing public diagnostics or importing services. | If compile and runtime wrappers keep separate duplicate token logic, finish the extraction. | Focused token tests plus existing compile/runtime redaction tests. |
| Matching helper | Field, code, numeric, boundary, and substring matching. | Changing token collection policy or replacement messages. | If matching knows about compile artifacts or runtime results, split again. | Focused matching tests plus existing field/code tests. |
| Sanitizer/core helper | Decide whether a diagnostic must be sanitized and construct safe replacement from caller policy. | Exit categories, artifact publication, adapter resolution. | If callers pass raw profile data instead of a token context, review API shape. | Existing sanitizer behavior tests. |
| `services/_compile_diagnostic_privacy.py` | Compile-specific wrappers, token-context reuse, render-result and `rendering.adapter_type` redaction. | Duplicated low-level token parsing/matching after extraction, runtime setup policy. | If compile wrapper imports runtime services or artifact writers, stop and fix boundary. | Compile-service redaction tests and boundary tests. |
| `services/_compile_adapter_setup.py` | Adapter setup and connection-scoped setup diagnostics. | Low-level redaction internals. | If setup starts parsing DSNs or matching tokens directly, move that to redaction helpers. | Compile adapter setup and service tests. |
| `services/_compile_render_sql.py` | Render orchestration and compile-specific redaction calls. | Low-level token matching or broad renderer discovery. | If render orchestration owns redaction matching, split back into privacy helper. | Render-SQL compile tests. |
| Runtime setup/registry/run/check-engine callers | Use adapter-facing redaction wrapper for profile-backed adapter diagnostics. | Compile privacy helper imports. | If runtime imports `services._compile_diagnostic_privacy`, stop and fix boundary. | Runtime setup, registry, run-service, and check-engine boundary tests. |
| Regression-capture metadata | Exact-route redaction source/test files to diagnostic/privacy surfaces. | Relying on broad adapter prefixes for redaction-owned helpers. | Any new redaction helper or dedicated test file requires route review. | Regression-capture decision script tests. |

## Affected Docs

This prework adds this planning artifact.

Existing durable docs already define the behavior item 15 must preserve:

- `docs/compatibility/adapter-api.md`:
  Adapter/Profile Rendering Conformance Matrix and Adapter/Profile Diagnostic
  Conformance Gate.
- `docs/compatibility/compatibility-matrix.md`:
  Profile and secret handling; Adapter/Profile Diagnostic Conformance Gate.
- `docs/implementation/errors-and-diagnostics.md`:
  adapter/profile diagnostic redaction behavior and low-level exception
  sanitization.
- `docs/compatibility/public-contract-inventory.md`:
  profile and secret handling; low-level exception diagnostic sanitization.

Future implementation is expected to be behavior-preserving and should not need
additional durable public architecture, compatibility, ADR, or changelog wording
changes if:

- diagnostic codes, messages, resource metadata, hints, line/column behavior,
  and `rendering.adapter_type` behavior stay unchanged,
- profile rendering and literal adapter `type` behavior stay unchanged,
- adapter API shape and public exports stay unchanged,
- compile/run diagnostic timing and artifact publication behavior stay
  unchanged.

If implementation changes any public diagnostic behavior, adapter API behavior,
artifact shape, CLI output, or redaction policy, stop for explicit
public-contract review before continuing.

## Public Contract, Compatibility, Security, And Privacy Impact

This prework is planning-only and changes no runtime behavior.

Future item 15 implementation is intended to be behavior-preserving but touches
public-risk diagnostic/privacy surfaces. It must preserve:

- Adapter/Profile Diagnostic Conformance Gate behavior,
- profile and secret handling compatibility expectations,
- low-level exception sanitization rules,
- current CLI and compiled artifact diagnostic output,
- source/target and profile privacy defaults.

Security/privacy impact is high if behavior changes. Implementation must not
emit rendered profile values, credentials, tokens, DSN fragments, raw adapter
exception text, raw database error text, source/target query text, row values,
or relation data into diagnostics, artifacts, terminal output, logs, or tests.

Changelog Decision: Not Required for this prework.

Changelog rationale:

- Planning artifact only.
- No user-visible behavior, public contract semantics, compatibility promise,
  generated artifact behavior, CLI output, support range, or default behavior
  changed.

## Regression-Capture Decision

`regression_capture_decision: not-required`

Rationale:

- This is planning-only prework.
- No behavior bug was fixed and no runtime/test behavior changed.
- Existing regression-capture rows for diagnostic privacy remain unchanged.

Implementation must re-check regression-capture routing before review or
commit:

- exact-route `src/recon_core/adapters/diagnostic_redaction.py` to
  `adapter_diagnostics`, `diagnostics`, `profile_secrets`, and `redaction`,
  unless another exact route already covers those surfaces by then;
- exact-route every new private adapter redaction helper to the same surfaces;
- exact-route any new dedicated redaction helper test file to the same surfaces
  and any additional adapter/runtime surfaces it actually owns;
- update `tests/scripts/test_check_regression_capture_decisions.py` fixtures and
  mapping assertions with every new exact route;
- add or update a capture row if implementation fixes a real privacy leak,
  missed conformance case, or recurring bug class.

## Implementation Plan

1. Add focused tests before refactoring.
   - Prefer focused adapter redaction helper tests for token collection,
     diagnostic-code matching, DSN component extraction, numeric matching, safe
     code preservation, and replacement-diagnostic construction if private
     helpers are introduced.
   - Add boundary tests proving adapter redaction internals do not import
     services, compiled artifacts, render-SQL orchestration, concrete DuckDB
     modules, or artifact writers.
   - Keep existing compile-service/runtime tests as conformance coverage rather
     than moving all cases at once.

2. Extract low-level redaction internals.
   - Split token collection, matching, and sanitizer/replacement construction
     into private helpers.
   - Preserve runtime wrapper messages and compile wrapper messages.
   - Preserve compile token-context reuse so render-SQL paths do not repeatedly
     parse the same connection config when current code already avoids that.

3. Rewire compile and runtime callers narrowly.
   - Keep `adapters/diagnostic_redaction.py` as the adapter-facing wrapper.
   - Keep `services/_compile_diagnostic_privacy.py` as the compile-specific
     wrapper for render results and `rendering.adapter_type`.
   - Do not import compile privacy helpers from runtime setup, registry,
     run-service, or check-engine paths.

4. Update regression-capture routing.
   - Add exact routes for existing and new redaction files.
   - Update script tests for the route matrix.

5. Run the local-success blindness second pass before review.
   - Check direct/transitive imports.
   - Check public diagnostics/artifacts/CLI output with focused tests.
   - Check regression-capture advisory with `--base-ref origin/main`.

## Required Validation

Future implementation should run at minimum:

```bash
python3 -m pytest tests/services/test_compile_service.py -q
python3 -m pytest tests/adapters/test_runtime_setup.py tests/adapters/test_registry.py -q
python3 -m pytest tests/services/test_run_service.py tests/cli/test_main.py -q
python3 -m pytest tests/services/test_compile_service_boundaries.py -q
python3 -m pytest tests/scripts/test_check_regression_capture_decisions.py tests/scripts/test_check_regression_capture.py -q
python3 scripts/check_regression_capture.py
python3 scripts/check_regression_capture_decisions.py --base-ref origin/main
python3 -m pytest -q
python3 -m ruff format --check .
python3 -m ruff check .
python3 -m mypy src
python3 -m compileall -q src tests
git diff --check
```

Add narrower focused helper tests to the list if implementation creates new
private redaction helpers.

## Local-Success Blindness Second Pass

Before calling item 15 complete, explicitly check:

- No raw rendered profile key, value, credential, token, DSN fragment, numeric
  scalar, adapter exception text, database error text, rendered SQL, raw SQL,
  source/target query text, row value, or relation data appears in public
  diagnostics, terminal output, compiled artifacts, or tests intended to model
  public output.
- No redaction helper imports `recon_core.services`, compiled artifact writers,
  concrete DuckDB modules, renderer orchestration, or run-service orchestration.
- No runtime setup, registry, run-service, or check-engine path imports
  `recon_core.services._compile_diagnostic_privacy`.
- No compile wrapper duplicates low-level token parsing/matching after the
  private helper extraction is complete.
- Safe adapter diagnostic codes remain preserved.
- Unsafe diagnostic-code tokens remain suppressed.
- Numeric matching still covers `line`, `column`, text, resource metadata,
  diagnostic code, and `rendering.adapter_type`.
- `rendering.adapter_type` sanitization still happens before compiled-check
  metadata is written.
- Adapter setup failures still write no compiled SQL and mark affected checks
  blocked exactly as before.
- Regression-capture routing is exact for every moved or newly created
  diagnostic redaction file.

## Definition Of Done

Item 15 prework is complete when:

- this artifact exists and is current with the code/docs audit,
- scope and non-goals are explicit,
- expected behavior and compatibility impact are explicit,
- acceptance/conformance rows map to existing or planned tests,
- responsibility map identifies allowed and forbidden ownership,
- regression-capture routing requirements are explicit,
- implementation plan and validation commands are explicit,
- companion brain dump records the prework and next task.

Item 15 implementation is complete only when:

- redaction internals are decomposed without behavior drift,
- focused helper/boundary tests and existing conformance tests pass,
- regression-capture routing is updated for every new/moved owned surface,
- full validation passes,
- local-success blindness second pass is recorded,
- companion brain dump records `regression_capture_decision`.
