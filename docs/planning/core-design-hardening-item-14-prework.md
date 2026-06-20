# Core Design Hardening Item 14 Prework

## Purpose

This is the prework artifact for final-order item 14: decompose profile loader
vertical responsibilities.

Item 14 is high-risk because it touches profile files, environment-variable
rendering, selected target resolution, referenced connection filtering,
connection `type` routing, diagnostics, secret handling, public terminal output,
adapter-aware compile, current runtime execution, and future adapter test-kit
compatibility. This artifact locks the responsibility map before coding. It
does not implement runtime behavior.

Split Decision: Already Split / Follow Existing Split.

The broader hardening branch already split this work away from profile
connection-reference derivation, compile-service decomposition, run-service
decomposition, adapter diagnostic redaction decomposition, external adapter
discovery, public export-barrel policy, and `BaseAdapter` metadata-interface
work. Item 14 should remain a behavior-preserving decomposition inside the
profile-loading boundary.

## Scope

Item 14 prework covers:

- current `connections/profiles.yml` file loading for adapter-aware workflows,
- safe YAML loading and profile YAML diagnostics,
- selected project profile and selected target resolution,
- selected target `connections` schema checks,
- referenced-connection filtering,
- literal non-empty connection `type` enforcement,
- supported `env_var('NAME')` and `env_var('NAME', 'default')` rendering for
  referenced non-routing fields,
- unsupported template and unsupported env-var expression rejection,
- public `recon_core.profiles` import compatibility,
- current compile-service and run-service profile-loading callers,
- tests, regression-capture routing, compatibility, privacy, and
  implementation-readiness criteria.

The selected design is conservative: split private profile-loading
responsibilities without changing public YAML shape, accepted env-var syntax,
diagnostic codes, diagnostic messages, profile-selection semantics,
referenced-connection filtering, rendered config shape, adapter routing, CLI
output, generated artifacts, adapter APIs, or public exports.

## Non-Goals

Item 14 prework and implementation must not implement:

- a new profile schema version,
- project-level `--profile` or `--target` CLI overrides,
- new profile file search locations,
- `.env` loading,
- secret-manager integrations,
- broad Jinja rendering,
- filters, macros, type-casting, or arbitrary template execution,
- rendering for connection `type`,
- adapter discovery or entry points,
- adapter setup, adapter metadata validation, adapter capability validation, or
  renderer selection,
- adapter diagnostic redaction redesign,
- debug/profile commands,
- external adapter test-kit extraction,
- run results, evidence, reports, failure details, state, or sinks,
- public Python export narrowing.

## Current Audit Findings

Current code has the needed behavior coverage but concentrated ownership:

- `src/recon_core/profiles/loader.py` owns file path selection, file I/O, YAML
  parsing, safe YAML diagnostics, top-level `profiles` mapping checks, selected
  profile lookup, target lookup, connection-map validation, referenced
  connection filtering, literal `type` validation, recursive config rendering,
  supported env-var replacement, unsupported-template rejection, diagnostic
  construction, and compatibility wrappers.
- `src/recon_core/profiles/connection_references.py` already owns structural
  contract-to-connection-name derivation. Item 14 should not move this back into
  the loader or change its public wrappers.
- `src/recon_core/profiles/models.py` already owns the rendered profile models:
  `ConnectionConfig`, `SelectedProfile`, and `ProfileLoadResult`.
- `CompileService` and `RunService` call
  `load_selected_profile_for_connection_names()` after they have independently
  decided which contracts or compiled contracts need profiles.
- Plain compile remains profile-free; profile loading is currently invoked by
  adapter-aware compile and current relation-backed runtime execution only.
- Existing profile tests cover selected target loading, referenced-only
  rendering, missing env vars, env-var defaults, bare env-var rendering,
  templated `type` rejection, unsupported template fragments, unsupported
  env-var defaults, invalid YAML sanitization, duplicate-key sanitization, and
  structural connection-reference boundaries.
- Regression-capture routing exact-routes `profiles/loader.py` and
  `profiles/connection_references.py` to `diagnostics`, `profile_secrets`, and
  `redaction`, but any new profile helper files must be exact-routed during
  implementation.

Current behavior to preserve:

- Missing `profile` in `recon_project.yml` returns
  `RC_CONFIG_PROFILE_NOT_SELECTED`.
- Missing `connections/profiles.yml` returns
  `RC_CONFIG_PROFILE_FILE_NOT_FOUND`.
- Invalid profile YAML returns `RC_CONFIG_INVALID_PROFILE_YAML` with safe
  summary text and safe line/column metadata when available.
- Invalid profile structure returns `RC_CONFIG_INVALID_PROFILE_CONFIG`.
- Missing selected profile, target, or referenced connection returns the
  existing profile diagnostic codes and safe resource metadata.
- Only selected target connections referenced by selected contracts or compiled
  runtime candidates are rendered.
- Missing env vars in unselected targets or unreferenced connections do not fail
  contract-specific compile or run invocations.
- `env_var('NAME')`, `env_var('NAME', 'default')`, and the current bare full
  string forms render only for referenced non-routing fields.
- Unsupported template fragments and unsupported env-var expressions in
  referenced fields fail before adapter resolution and do not leak raw template
  text.
- Connection `type` must remain a literal non-empty adapter type; templated or
  env-var-derived `type` values fail before adapter resolution.
- Rendered connection config is not written into public diagnostics, terminal
  output, generated artifacts, tests, or companion notes.

## Decomposition Decision

Profile-loader decomposition should separate file/YAML loading, selected
profile resolution, referenced connection rendering, env-var expression
handling, and diagnostic construction without changing behavior.

Recommended implementation shape:

| Module or component | Allowed responsibility | Forbidden responsibility |
| --- | --- | --- |
| `profiles/loader.py` | Public profile-loading functions, compatibility wrappers, top-level orchestration, and delegation to private helpers. | Raw YAML parser details, recursive env rendering internals, adapter setup, diagnostic redaction policy, service-specific behavior. |
| Existing `profiles/models.py` | Rendered profile result models and simple model invariants. | File I/O, env access, adapter setup, service orchestration. |
| Existing `profiles/connection_references.py` | Structural extraction of source/target connection names from authored or loaded contract-like objects. | Profile file loading, rendering, diagnostics, public export policy changes. |
| New file/YAML helper, or equivalent | Resolve current profile file path, read text, parse with unique-key YAML loader, and return safe YAML-load diagnostics. | Selected profile semantics, env rendering, adapter setup, raw YAML exception text in diagnostics. |
| New selection/schema helper, or equivalent | Validate top-level profile shape, selected profile, selected target, target connections mapping, and missing referenced connections. | Env-var rendering internals, adapter resolution, service-result messages, new profile search paths. |
| New env/rendering helper, or equivalent | Render supported env-var forms in referenced non-routing connection values, reject unsupported template syntax, recurse through mappings/lists, and collect safe diagnostics. | Rendering connection `type`, broad template execution, secret-manager lookup, `.env` loading, adapter redaction policy. |
| New profile diagnostic helper, or equivalent | Construct current `RC_CONFIG_*` diagnostics with safe messages, path, resource fields, line/column, and hints. | Adapter `RC_ADAPTER_*` diagnostics, broad diagnostic/redaction redesign, raw parser/template/credential text. |
| `CompileService` and `RunService` | Decide when profile loading is needed and pass explicit referenced connection names. | Profile file parsing, env rendering, unsupported template policy. |
| Adapter setup/redaction helpers | Use already rendered `ConnectionConfig` objects and sanitize adapter-backed diagnostics. | Profile selection, profile YAML parsing, env-var rendering semantics. |

Exact private module names may change during implementation if the final split
better matches the code. The invariant is ownership separation, not filename
spelling. Public `recon_core.profiles` imports must remain compatible unless
implementation stops for explicit public API/export-policy approval.

## Expected Behavior

For profile loading:

- `load_selected_profile()` and `load_selected_profile_for_connection_names()`
  keep their current signatures and return types.
- Profile file path remains `connections/profiles.yml` under the project root.
- The selected profile still comes from `recon_project.yml`.
- The selected profile's `target` still selects one target under `outputs`.
- Only referenced named connections in the selected target are rendered.
- Empty or malformed selected profile, target, outputs, connections, connection
  `type`, or connection payloads produce the same diagnostics as today.

For env rendering and templates:

- Current quoted `{{ env_var('NAME') }}` and
  `{{ env_var('NAME', 'default') }}` forms keep working.
- Current bare whole-string `env_var('NAME')` and
  `env_var('NAME', 'default')` forms keep working.
- Missing env vars without defaults in referenced fields still produce
  `RC_CONFIG_PROFILE_ENV_VAR_MISSING`.
- Defaults for unreferenced connections remain unrendered and do not leak in
  missing-env diagnostics.
- Unsupported Jinja fragments, unsupported env-var expressions, embedded env-var
  defaults, and templated `type` values still fail before adapter resolution.

For callers and public output:

- Plain `recon compile` still does not load profiles.
- `recon compile --render-sql` and current `recon run` still load profiles only
  after their existing compile/runtime preconditions decide profile loading is
  required.
- Profile diagnostics keep the same codes, messages, resource metadata, hints,
  exit categories through service callers, and CLI output.
- Generated artifacts, compiled SQL, in-memory run results, and terminal output
  do not gain rendered profile payloads.

## Acceptance And Conformance Matrix

| Case | Expected behavior | Required implementation coverage |
| --- | --- | --- |
| Public profile imports | Existing `recon_core.profiles` imports continue to work. | Import compatibility tests or existing import usage. |
| Missing project profile | `RC_CONFIG_PROFILE_NOT_SELECTED` with current message and hint. | Existing profile-loader tests. |
| Missing profiles file | `RC_CONFIG_PROFILE_FILE_NOT_FOUND` with current display path. | Existing compile-service tests; add profile-loader coverage if needed. |
| Invalid YAML | `RC_CONFIG_INVALID_PROFILE_YAML` safe summary, no raw parser text or secrets. | Existing regression-capture profile YAML tests. |
| Duplicate/unhashable YAML keys | Safe invalid YAML diagnostic with no authored key or secret leak. | Existing regression-capture profile YAML tests. |
| Missing selected profile | `RC_CONFIG_PROFILE_NOT_FOUND` and selected profile resource name. | Existing profile-loader tests. |
| Missing selected target | `RC_CONFIG_PROFILE_TARGET_NOT_FOUND` and profile resource name. | Existing profile-loader tests. |
| Invalid profile structure | `RC_CONFIG_INVALID_PROFILE_CONFIG` with current safe messages. | Existing or added profile-loader tests. |
| Missing referenced connection | `RC_CONFIG_PROFILE_CONNECTION_NOT_FOUND` for only the missing referenced connection. | Existing profile-loader tests. |
| Referenced-only rendering | Referenced connections render; unreferenced selected-target connections are ignored. | Existing profile-loader, compile-service, and run-service tests. |
| Unselected target ignored | Missing env vars in unselected targets do not fail. | Existing profile-loader tests. |
| Env-var default | Referenced defaults render when env is missing and do not leak through unrelated diagnostics. | Existing profile-loader tests. |
| Bare env-var form | Current whole-string bare env-var form renders. | Existing profile-loader tests. |
| Missing env var | `RC_CONFIG_PROFILE_ENV_VAR_MISSING` names only the missing referenced env var. | Existing profile-loader and service tests. |
| Unsupported template expression | Fails with `RC_CONFIG_INVALID_PROFILE_CONFIG` and no raw template text. | Existing profile-loader tests. |
| Unsupported env-var default | Fails safely and does not leak embedded default/template content. | Existing profile-loader tests. |
| Literal type routing | Non-empty literal `type` succeeds; templated or env-var `type` fails before adapter resolution. | Existing profile-loader and compile-service tests. |
| Recursive render shape | Nested mappings and lists still render only supported strings and preserve scalar values. | Existing tests plus focused helper tests if extraction changes recursion. |
| Compile profile timing | Plain compile stays profile-free; render-SQL profile failures keep current service result. | Existing compile-service tests. |
| Run profile timing | Current run profile loading stays gated by relation-backed runtime candidates and prerequisite blockers. | Existing run-service tests. |
| Regression routing | Any new profile helper owning profile diagnostics/secrets/redaction is exact-routed. | Update `index.yml` and script tests during implementation. |

## Workflow Scenarios

Scenario: adapter-aware compile renders only selected referenced connections.

- Given a selected profile target with referenced and unreferenced connections,
- when `recon compile --render-sql` loads the profile,
- then only the referenced connection payloads are rendered and unreferenced
  env vars do not fail the invocation.

Scenario: unsupported template syntax fails before adapter setup.

- Given a referenced connection payload contains unsupported template fragments,
- when profile loading runs,
- then profile loading returns `RC_CONFIG_INVALID_PROFILE_CONFIG`, adapter
  factories are not invoked, and raw template text is not emitted.

Scenario: adapter type remains routing metadata.

- Given a connection `type` value uses `env_var(...)` or template markers,
- when profile loading runs,
- then profile loading fails before adapter resolution and no rendered
  environment value appears as adapter identity.

Scenario: profile YAML diagnostics stay sanitized after helper extraction.

- Given profile YAML contains duplicate keys or parser errors near secret-like
  values,
- when profile loading fails,
- then the diagnostic keeps the current safe code/message/path/line/column
  behavior without raw parser text.

Scenario: run profile loading remains gated by runtime preconditions.

- Given a compiled project contains unsupported future-phase checks or blockers
  that do not require profile-backed execution,
- when `recon run` prepares dependencies,
- then profile loading is not broadened by the profile-loader decomposition.

## Source Map

Implementation is expected to inspect or edit:

- `src/recon_core/profiles/loader.py`
- `src/recon_core/profiles/models.py`
- `src/recon_core/profiles/connection_references.py`
- new private modules under `src/recon_core/profiles/`
- `src/recon_core/profiles/__init__.py`
- `tests/profiles/test_loader.py`
- `tests/profiles/test_connection_references.py`
- `tests/scripts/test_check_regression_capture_decisions.py`
- `docs/compatibility/regression-capture/index.yml`

Implementation may inspect, but should avoid changing unless needed:

- `src/recon_core/services/compile.py`
- `src/recon_core/services/run.py`
- `src/recon_core/services/_compile_adapter_setup.py`
- `src/recon_core/services/_compile_diagnostic_privacy.py`
- `src/recon_core/services/_compile_render_sql.py`
- `src/recon_core/adapters/diagnostic_redaction.py`
- `docs/architecture/project-loading-and-config.md`
- `docs/architecture/adapter-interface.md`
- `docs/implementation/config-models.md`
- `docs/implementation/errors-and-diagnostics.md`
- `docs/implementation/testing-plan.md`
- `docs/compatibility/public-contract-inventory.md`
- `docs/compatibility/change-checklist.md`
- `docs/compatibility/regression-capture/diagnostics-privacy.yml`

Implementation should not edit adapter APIs, adapter registries, renderer
selection, compile artifact behavior, run execution behavior, diagnostic
redaction policy, public package export policy, or compatibility docs unless
source inspection proves a tiny compatibility seam is necessary. Broad changes
to those areas are different final-order items.

## Responsibility Map

| Component | Allowed responsibilities | Forbidden responsibilities | Refactor trigger | Tests protecting boundary |
| --- | --- | --- | --- | --- |
| `profiles/loader.py` | Public orchestration and compatibility wrappers. | Full vertical file/schema/env/diagnostic ownership after extraction. | If loader still contains most parsing, rendering, and diagnostics logic after extraction, split another private helper. | Profile-loader tests and import compatibility. |
| File/YAML helper | Current profile path, read, unique-key YAML parse, safe YAML diagnostics. | Selected target semantics, env rendering, raw parser exception text. | If it needs referenced connection names, the boundary is wrong. | Invalid YAML, duplicate key, unhashable key tests. |
| Selection/schema helper | Selected profile/target/connections checks and missing referenced connection diagnostics. | Env-var replacement, adapter setup, service-result assembly. | If it reads `os.environ` or imports adapters/services, split again. | Missing profile/target/connection tests. |
| Env/rendering helper | Supported env-var rendering, unsupported template rejection, recursive value rendering for referenced payloads. | Rendering `type`, broad template engine use, `.env` loading, secret-manager lookup. | If it accepts arbitrary Jinja or filters, stop for design alignment. | Env-var, default, unsupported template, templated type tests. |
| Diagnostic helper | Current safe `RC_CONFIG_*` profile diagnostics. | Adapter diagnostic redaction policy or `RC_ADAPTER_*` ownership. | If messages/codes change, stop for public-contract review. | Diagnostic code/message tests and CLI/service tests. |
| Connection-reference helper | Structural connection-name derivation. | Profile loading, YAML parsing, env rendering. | If profile loader imports parser/artifact concrete shapes, fix boundary. | Existing connection-reference boundary test. |
| Compile/run services | Decide whether and when to call profile loading with explicit names. | Profile internals, env rendering, template policy. | If profile decomposition broadens caller behavior, stop and review item scope. | Compile-service and run-service tests. |
| Regression-capture metadata | Exact-route every moved/new governed profile helper. | Relying on old monolith route after ownership moves. | Any new helper under `profiles/` that owns diagnostics, profile secrets, redaction, or public routing behavior requires route review. | Regression-capture decision script tests. |

## Affected Docs

This prework adds this planning artifact.

This prework also aligns
`docs/architecture/project-loading-and-config.md` with current implementation:
profiles are loaded for `recon compile --render-sql` and for relation-backed
`recon run` execution paths that require runtime adapter connections. Future
item 14 implementation must preserve that compile/run profile-loading scope
unless it stops for a separate public-contract review.

Future implementation is expected to be behavior-preserving and should not need
additional durable public architecture, compatibility, ADR, or changelog wording
changes if:

- accepted profile YAML shape and env-var syntax stay unchanged,
- profile selection and selected-target behavior stay unchanged,
- referenced-connection filtering stays unchanged,
- compile and run profile-loading scope stays unchanged,
- diagnostic codes, messages, resource metadata, hints, and exit categories
  stay unchanged,
- profile values and credentials stay absent from public outputs,
- package-level imports remain compatible,
- regression-capture routing is updated for any new or moved profile helper
  files.

If implementation changes one of those surfaces, stop and update the relevant
compatibility docs, implementation docs, ADRs, and changelog decision before
claiming completion.

No changelog entry is required for this prework because it changes planning
only.

## Compatibility, Security, And Privacy Impact

Compatibility impact:

- Profile and secret handling is a public compatibility surface.
- Current profile file path, selected-profile semantics, target semantics,
  referenced connection filtering, env-var forms, literal `type` rule,
  diagnostic codes/messages, service messages, CLI output, and public imports
  must not change.
- Future adapter/test-kit compatibility improves because profile ownership
  becomes easier to route and audit.

Security and privacy impact:

- Decomposition must not expose rendered profile values, credentials, DSN
  fragments, raw YAML parser text, raw template text, adapter exceptions,
  database errors, source/target query text, relation data, row values, raw
  failure details, or unsafe diagnostic codes in diagnostics, terminal output,
  generated artifacts, tests, or companion notes.
- No generated outputs, local profiles, evidence, result artifacts, reports, or
  state files should be created or committed by this refactor.

## Required Tests For Future Implementation

Before item 14 implementation claims completion, run at minimum:

```bash
python3 -m pytest tests/profiles/test_loader.py tests/profiles/test_connection_references.py -q
python3 -m pytest tests/services/test_compile_service.py tests/services/test_run_service.py -q
python3 -m pytest tests/cli/test_main.py -q
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

- no `recon_core.adapters`, `recon_core.services`, or DuckDB imports in new
  profile file/YAML, selection, rendering, or diagnostic helpers,
- no parser or compiled-artifact concrete shape imports in
  `profiles/loader.py` or new profile helpers,
- no broad template engine or unsafe `eval`/Jinja execution,
- no code path that renders unreferenced connections for compile or run,
- no code path that renders or accepts templated connection `type`,
- no raw YAML/template/profile value text in public diagnostics,
- every new profile helper exact-routes through regression-capture metadata
  when it owns diagnostics, profile secrets, redaction, or compatibility
  behavior.

## Local-Success Blindness Second Pass

A passing local DuckDB `recon compile --render-sql` or `recon run` is
insufficient if the implementation still:

- leaves `profiles/loader.py` owning the full file/schema/env/diagnostic
  vertical path,
- renders unreferenced or unselected connection payloads,
- renders or accepts connection `type` from env vars or template fragments,
- broadens supported template syntax beyond the locked env-var subset,
- changes profile diagnostic codes, messages, resource fields, hints, line,
  column, service messages, or CLI output unexpectedly,
- hides invalid profile YAML or unsupported template syntax behind adapter
  setup or render failures,
- leaks env-var defaults, rendered values, credential keys, DSN fragments, or
  raw parser/template text through diagnostics, artifacts, terminal output, or
  tests,
- pulls adapter setup, renderer selection, diagnostic-redaction policy, compile
  orchestration, or run execution into profile helper modules,
- moves/splits profile files without updating regression-capture routing and
  routing tests,
- broadens into debug/profile commands, secret-manager support, `.env` loading,
  adapter diagnostic redaction redesign, public export policy, or external
  adapter discovery.

## Regression Capture Review

Applicable regression-capture routing before implementation:

- `src/recon_core/profiles/loader.py` exact-routes to `diagnostics`,
  `profile_secrets`, and `redaction`.
- `src/recon_core/profiles/connection_references.py` exact-routes to
  `diagnostics`, `profile_secrets`, and `redaction`.
- `tests/profiles/test_connection_references.py` exact-routes to the same
  profile surfaces.
- `src/recon_core/_yaml.py` exact-routes to profile, diagnostics, redaction,
  artifact, parser, and source-target privacy surfaces.
- `src/recon_core/services/compile.py` and `src/recon_core/services/run.py`
  already exact-route the service-owned profile-consuming surfaces.

Capture rows already relevant to item 14:

- `yaml-diagnostic-redaction`
- `yaml-profile-and-source-privacy`
- `regression-capture-decision-advisory-metadata-routing`

Current gap to close during implementation:

- any new profile helper file must be exact-routed to the surfaces it owns.
  Do not rely on the old `profiles/loader.py` monolith route after extraction.

Likely route decisions during implementation:

- file/YAML helper: `diagnostics`, `profile_secrets`, `redaction`,
- selection/schema helper: `diagnostics`, `profile_secrets`, `redaction`,
- env/rendering helper: `diagnostics`, `profile_secrets`, `redaction`,
- diagnostic helper: `diagnostics`, `profile_secrets`, `redaction`,
- remaining `profiles/loader.py`: same surfaces while it remains the public
  profile-loading orchestration boundary.

Implementation must apply the routing ownership principle:

- identify the old effective route before moving code,
- exact-route any new module that owns profile diagnostics, profile secrets,
  redaction, env-var rendering, unsupported-template behavior, or profile
  compatibility behavior,
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

1. Add or preserve focused boundary tests before moving code: public import
   compatibility, no parser/artifact concrete shape imports, no adapter/service
   imports in profile helpers, referenced-only rendering, literal `type`
   rejection, unsupported-template rejection, and safe YAML diagnostics.
2. Extract safe profile file/YAML loading into a private helper without changing
   path, YAML loader, duplicate-key behavior, line/column handling, or
   diagnostic text.
3. Extract selected profile, target, outputs, connections, and missing
   referenced-connection checks into a private schema/selection helper.
4. Extract env-var rendering and unsupported-template detection into a private
   rendering helper while preserving the current regex-supported subset.
5. Extract profile diagnostic construction if it reduces duplication and does
   not change codes/messages/resource metadata.
6. Keep `loader.py` as the public orchestration boundary and maintain existing
   `recon_core.profiles` exports.
7. Update regression-capture routing and routing tests for every new or moved
   governed file.
8. Run focused profile tests after each extraction, then service/CLI
   profile-consuming tests, full validation, and the local-success blindness
   second pass.

Implementation should stop for user approval if it requires any public profile
syntax change, diagnostic code or message change, profile file location change,
environment-rendering behavior change, connection `type` behavior change,
profile export narrowing, adapter setup behavior change, redaction-policy
change, debug/profile command behavior, external adapter discovery, generated
artifact change, CLI output change, or result/evidence output.

## Definition Of Done

Item 14 implementation is complete only when:

- profile file/YAML loading, selected profile/target schema checks, referenced
  connection rendering, env-var/template handling, and diagnostic construction
  have clear private owners,
- `profiles/loader.py` remains the public profile-loading orchestration
  boundary and no longer owns the full vertical path,
- `connection_references.py` remains the structural connection-reference owner,
- current profile selection, referenced-connection filtering, literal `type`,
  env rendering, unsupported-template rejection, diagnostics, privacy, compile
  behavior, run behavior, and public imports are unchanged,
- no non-goal scope is introduced,
- regression-capture routing covers every new or moved governed file,
- current profile, compile-service, run-service, CLI, regression-capture, and
  full validation pass,
- companion brain dump records validation, remaining risks, split decision,
  changelog decision, local-success blindness result, and regression-capture
  decision.

Split Decision: Already Split / Follow Existing Split.

Changelog Decision: Not Required for prework.

`regression_capture_decision: not-required`
