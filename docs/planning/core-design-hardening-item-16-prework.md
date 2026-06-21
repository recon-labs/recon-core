# Core Design Hardening Item 16 Prework

## Purpose

This is the prework artifact for final-order item 16: split `BaseAdapter`
metadata responsibilities.

Item 16 is high-risk because it touches the adapter API boundary, adapter API
version expectations, future adapter package compatibility, capability meaning,
metadata access, current DuckDB adapter behavior, test helpers, public docs, and
future shared adapter-test-kit conformance. This artifact locks the
responsibility map before coding. It does not implement runtime behavior.

Split Decision: Already Split / Follow Existing Split.

The broader hardening branch already split this work away from runtime
capability semantics, renderer binding, DuckDB renderer decomposition,
check-engine decomposition, compile-service decomposition, profile-loader
decomposition, adapter diagnostic redaction decomposition, public export-barrel
policy, and monolithic service-test cleanup. Item 16 should remain an
adapter-interface-segregation change only.

## Scope

Item 16 prework covers:

- current `BaseAdapter` abstract method requirements,
- relation metadata methods:
  - `relation_exists`,
  - `get_columns`,
- current adapter identity metadata:
  - `adapter_type`,
  - `adapter_version`,
  - `supported_adapter_api_version`,
- current connection lifecycle and query execution methods:
  - `connect`,
  - `close`,
  - `execute`,
- current capability declaration:
  - `capabilities`,
- current DuckDB adapter behavior where relation metadata methods raise
  `NotImplementedError`,
- current adapter registry, compile setup, runtime setup, and service tests that
  stub relation metadata methods only because `BaseAdapter` requires them,
- adapter API version and compatibility impact,
- public docs, compatibility docs, ADR impact, tests, regression-capture routing,
  local-success blindness checks, and Definition of Done.

The selected design is conservative: separate relation metadata access from the
minimum adapter lifecycle/execution/capability interface without adding metadata
execution behavior, broad discovery, new capability names, external adapter
discovery, adapter packages, shared adapter test-kit extraction, or public
export-barrel cleanup.

## Non-Goals

Item 16 prework and implementation must not implement:

- metadata-backed validation,
- all-column expansion,
- schema policy checks,
- physical column/type validation,
- query endpoint execution,
- broader relation discovery,
- debug/profile/connection metadata commands,
- production adapter packages,
- shared adapter-test-kit extraction,
- adapter package entry points,
- new external adapter discovery,
- new adapter capability names unless implementation finds a blocking
  compatibility gap and stops for separate approval,
- SQL renderer changes,
- runtime execution expansion,
- aggregate execution,
- scan-safety changes,
- result, evidence, report, failure-detail, state, or sink behavior,
- public export-barrel narrowing.

## Current Audit Findings

Current code and docs intentionally created a first adapter boundary, but the
relation metadata requirements are now too broad for the current implementation
phase:

- `src/recon_core/adapters/base.py` requires every `BaseAdapter` implementation
  to implement `relation_exists` and `get_columns`.
- `src/recon_core/adapters/duckdb/adapter.py` implements those methods only by
  raising `NotImplementedError` because metadata access is later-phase work.
- Current runtime setup in `src/recon_core/adapters/runtime_setup.py` validates
  adapter resolution, `adapter_type`, adapter API version, and capabilities
  without using relation metadata methods.
- Current adapter registry logic in `src/recon_core/adapters/registry.py` only
  needs the instance to be a `BaseAdapter` plus safe adapter identity metadata.
- Current compile and run paths use adapter lifecycle, query execution,
  capability validation, renderer binding, and runtime scan guards. They do not
  use `relation_exists` or `get_columns` as `BaseAdapter` requirements.
- Many test fakes in `tests/adapters/`, `tests/services/test_compile_service.py`,
  and run-service tests stub `relation_exists` and `get_columns` only because
  the base class currently forces those abstract methods.
- Public docs currently say `BaseAdapter` owns metadata access:
  - `docs/architecture/adapter-interface.md`,
  - `docs/implementation/adapter-interface-spec.md`,
  - `docs/framework/adapters.md`,
  - `docs/compatibility/adapter-api.md`,
  - `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`.
- Compatibility docs classify adapter method changes as adapter API
  compatibility-impacting. A method removal, rename, payload change, return
  model change, or error-semantics change cannot be treated as a silent internal
  refactor.
- `ADAPTER_API_VERSION = "1"` exists, but public docs also state no stable
  external adapter API release or shared adapter test kit exists yet.
- Regression-capture routing already maps `src/recon_core/adapters/` and
  `tests/adapters/` to `adapter_api` and `adapter_capabilities`. If item 16 adds
  a new metadata-interface module or focused test file, it should be exact-routed
  instead of relying only on broad prefixes.

Prior design context:

- ADR 0020 locked the first boundary as `BaseAdapter` plus `SqlRenderer`.
- That decision was correct for the first local/dev adapter and render-SQL
  milestone, but current implementation pressure shows relation metadata access
  should be a narrower interface so adapters are not forced to claim methods
  they cannot support.
- Mature adapter ecosystems commonly separate mandatory lifecycle/identity from
  optional capability-specific behavior. Recon should adapt that pattern in
  Recon-native terms: Core owns semantics and required-capability checks; adapter
  subinterfaces expose mechanics only when those mechanics are implemented and
  tested.

## Interface Segregation Decision

Selected item 16 direction:

- Keep `BaseAdapter` as the minimum adapter identity, lifecycle, query execution,
  and capability declaration boundary.
- Move relation metadata access into a separate relation-metadata interface,
  with the exact public name decided during implementation. Preferred name:
  `RelationMetadataAdapter`.
- The relation-metadata interface owns:
  - `relation_exists(relation: Relation) -> bool`,
  - `get_columns(relation: Relation) -> tuple[ColumnMetadata, ...]`.
- Do not model metadata support through method presence, `hasattr`, or broad
  `BaseAdapter` type checks.
- Any future caller that needs relation metadata must require both:
  - a metadata-capable adapter interface, and
  - the appropriate adapter capability state, such as current
    `metadata_columns` for column metadata.
- Do not add a new metadata capability name during item 16 unless implementation
  discovers that existing capability names cannot express the required blocker.
  If that happens, stop for compatibility approval instead of widening item 16.
- Keep current DuckDB metadata capability declarations as
  `not_implemented`. DuckDB should not appear metadata-capable just because it
  can render and execute current relation-backed checks.
- Keep current runtime execution, compile/render-SQL, and scan-safety behavior
  unchanged.

Compatibility-shim choice:

- Implementation should avoid breaking existing pre-alpha imports or casual
  method lookups if it can do so without making metadata support ambiguous.
- A nominal metadata subinterface is preferred over a structural `Protocol` if a
  temporary compatibility shim remains on `BaseAdapter`, because structural
  method checks would otherwise make every base adapter appear metadata-capable.
- If implementation removes `relation_exists` and `get_columns` from
  `BaseAdapter` entirely, it must treat that as a public adapter API shape
  change and update compatibility docs, ADR context, tests, and changelog
  assessment accordingly.

## Adapter API Version Impact

Item 16 changes adapter API requiredness, but it should not automatically bump
`ADAPTER_API_VERSION` if the implementation chooses a compatibility-preserving
path:

- Existing adapters that already implement `relation_exists` and `get_columns`
  should remain valid.
- New minimal adapters should be able to implement the current base boundary
  without metadata methods.
- Core must not call relation metadata methods on a plain `BaseAdapter`.
- Core must not infer relation metadata support from capability support alone.
- Core must not infer relation metadata support from method presence alone if
  compatibility shims remain.

An adapter API version bump is required only if implementation makes a breaking
adapter contract change that cannot be represented as a compatibility relaxation
or documented pre-alpha interface tightening. Examples:

- removing public methods without compatibility shims,
- changing relation metadata method payloads or return types,
- changing adapter API compatibility diagnostics,
- changing registry resolution behavior,
- changing capability semantics,
- making current DuckDB claim metadata support.

Even without an API version bump, item 16 implementation is compatibility
impacting and must update public adapter-interface docs and ADR context.

## Expected Behavior

For current runtime and compile behavior:

- `recon compile --render-sql` behavior remains unchanged.
- `recon run` behavior remains unchanged for the current row-count and bounded
  local/dev grain-key safety scope.
- Adapter registry, compile setup, runtime setup, and renderer binding continue
  validating adapter type, adapter API version, and capabilities before
  rendering or execution.
- Current DuckDB relation-backed render and execution capabilities remain
  unchanged.
- Current DuckDB relation metadata remains not implemented.
- Current scan-safety guards remain independent from adapter relation metadata
  methods.

For adapter implementers:

- Minimal adapters are no longer forced to implement relation metadata methods
  when they do not support metadata.
- Metadata-capable adapters implement the metadata subinterface and declare the
  relevant metadata capabilities.
- Existing adapter classes that already implement relation metadata methods
  continue to work.
- Unsupported, unknown, not-implemented, malformed, or incompatible capability
  states remain blockers.

For public output and artifacts:

- No diagnostic code/message behavior changes.
- No CLI command, option, exit-code, or terminal output changes.
- No generated artifact schema, path, version, or rendering metadata changes.
- No result, evidence, report, state, or sink output changes.
- No profile rendering, secret handling, or diagnostic redaction changes.

## Acceptance And Conformance Matrix

| Case | Expected behavior | Required implementation coverage |
| --- | --- | --- |
| Minimal adapter implementer | A `BaseAdapter` subclass can satisfy the base abstract interface without `relation_exists` or `get_columns`. | New adapter-interface unit test. |
| Metadata-capable adapter | A metadata-capable adapter has a clear nominal interface for `relation_exists` and `get_columns`. | New relation-metadata interface test. |
| No false metadata support | Plain `BaseAdapter` instances do not satisfy the metadata-capable check used by future callers. | Unit test proving the chosen check does not treat minimal adapters as metadata-capable. |
| Existing metadata methods | Existing adapters that implement metadata methods remain valid. | Compatibility unit test or existing fake adapter coverage. |
| DuckDB current behavior | DuckDB keeps current render/execution capabilities and continues to declare metadata columns as `not_implemented`. | Existing DuckDB adapter tests plus focused assertion if needed. |
| Registry behavior | Adapter registry resolution still requires a `BaseAdapter`, validates malformed factory results, and keeps current diagnostics. | Existing `tests/adapters/test_registry.py`. |
| Runtime setup behavior | Runtime setup still validates adapter type, API version, and capabilities before connect and does not ask for relation metadata. | Existing `tests/adapters/test_runtime_setup.py` and run-service tests. |
| Compile setup behavior | Render-SQL adapter setup still validates adapter type, API version, capabilities, and renderer binding without relation metadata. | Existing compile-service tests. |
| Capability blockers | Metadata capability support states do not imply metadata-call permission without the metadata interface. | New focused test if helper/check is introduced. |
| No capability broadening | Item 16 does not add or reinterpret capability names unless it stops for separate compatibility approval. | Diff review plus capability tests. |
| Adapter API version | `ADAPTER_API_VERSION` remains stable unless implementation intentionally chooses a breaking API change. | Unit test/doc review if version remains unchanged; compatibility/changelog review if it changes. |
| Public docs | Architecture, framework, implementation, compatibility, and ADR context agree on the split. | Docs review and public research-attribution grep. |
| Regression routing | Any new adapter metadata-interface files and tests are exact-routed to `adapter_api` and `adapter_capabilities`. | Update `index.yml` and script tests during implementation if new files are added. |

## Workflow Scenarios

Scenario: minimal adapter is not forced to implement metadata.

- Given an adapter that can resolve, declare capabilities, connect, execute, and
  close,
- when it subclasses the base adapter interface,
- then it does not need `relation_exists` or `get_columns` unless it claims the
  relation-metadata interface.

Scenario: metadata support is explicit.

- Given a future metadata-backed validation path needs column metadata,
- when it receives a resolved adapter,
- then it checks for the relation-metadata interface and the required metadata
  capability before calling `get_columns`.

Scenario: current DuckDB does not become metadata-capable accidentally.

- Given the current in-core DuckDB local/dev adapter,
- when item 16 splits metadata responsibilities,
- then DuckDB keeps current rendering and execution behavior but does not claim
  metadata access support.

## Source And Responsibility Map

| Module or component | Allowed responsibility | Forbidden responsibility | Boundary trigger | Boundary-protecting tests |
| --- | --- | --- | --- | --- |
| `adapters/base.py` | Minimum adapter identity, lifecycle, query execution, capability declaration, and relation-metadata subinterface definition if implementation places it here. | Runtime orchestration, registry resolution, renderer selection, metadata-backed validation, scan safety, result/evidence behavior. | If `BaseAdapter` still forces metadata methods, item 16 is incomplete. If metadata support is inferred from method presence alone, stop and fix. | New adapter-interface unit tests. |
| New metadata-interface helper/module, if used | Relation metadata interface and optional helper for checking metadata-capable adapters. | Capability semantics, adapter registry behavior, metadata-backed validation, public export cleanup. | If it imports services, DuckDB concrete adapter code, compiler/check-engine modules, or profile loading, stop and fix. | New helper tests and import-boundary checks. |
| `adapters/duckdb/adapter.py` | Current DuckDB lifecycle, query execution, capability declarations, and optional dependency behavior. | Claiming metadata support, metadata-backed validation, scan-safety classification. | If DuckDB metadata methods remain as required stubs only to satisfy `BaseAdapter`, remove or convert according to the final interface decision. | Existing DuckDB adapter tests plus metadata-capability assertion. |
| `adapters/registry.py` | Factory resolution, adapter type metadata validation, API compatibility diagnostics, sanitized factory diagnostics. | Relation metadata probing, metadata capability interpretation, renderer binding. | If registry starts calling relation metadata methods, stop and move that to future metadata validation work. | Existing registry tests. |
| `adapters/runtime_setup.py` | Runtime adapter setup validation: type, API version, capabilities, required-capability blockers. | Relation metadata probing, scan-budget policy, compile-specific setup. | If runtime setup requires metadata methods for current row-count/key-safety execution, stop and reassess scope. | Existing runtime setup and run-service tests. |
| `services/_compile_adapter_setup.py` and render-SQL callers | Compile adapter setup, adapter type/API/capability validation, renderer binding prerequisites. | Relation metadata probing, BaseAdapter metadata split policy. | If render-SQL starts requiring relation metadata, stop and document a separate compatibility change. | Existing compile-service tests. |
| Public adapter docs | State the new base-vs-metadata interface boundary and compatibility impact. | Named mature-project research attribution, unrelated adapter package policy, item 17 export-barrel cleanup. | If docs still say `BaseAdapter` owns relation metadata as a required base method, implementation is incomplete. | Docs review and grep. |
| Regression-capture metadata | Route new adapter-interface files/tests to adapter API/capability surfaces. | Behavior regression rows for planning-only work. | If new files are not exact-routed, fix before review. | Regression-capture validator and decision advisory. |

## Public Contract And Docs Impact

Item 16 implementation affects the adapter API public contract surface.

Required docs/ADR work if implementation proceeds:

- Add a new ADR or update ADR context without rewriting history. Because ADR
  0020 said `BaseAdapter` owns metadata access, a new ADR that supersedes only
  the relation metadata part is preferred if the implementation changes public
  interface shape.
- Update `docs/architecture/adapter-interface.md`.
- Update `docs/implementation/adapter-interface-spec.md`.
- Update `docs/framework/adapters.md`.
- Update `docs/compatibility/adapter-api.md`.
- Update `docs/compatibility/compatibility-matrix.md`.
- Update `docs/compatibility/public-contract-inventory.md` if the adapter API
  status or version-impact wording changes.
- Update `docs/compatibility/capability-catalog.md` only if implementation
  changes metadata capability wording. Do not add capability names silently.
- Review `docs/implementation/testing-plan.md` for adapter API and future
  adapter-test-kit wording.

Changelog guidance:

- Prework is docs/planning only, so no changelog entry is required for this
  artifact.
- Implementation must make an explicit changelog decision. If it changes the
  documented public adapter API shape, a concise `Unreleased` entry may be
  required even though the adapter API is pre-alpha.

Migration guidance:

- No external production adapter package exists today.
- If the implementation preserves compatibility for existing adapters that
  implement relation metadata methods, no user migration guidance should be
  needed beyond updated adapter-author docs.
- If implementation removes public methods from `BaseAdapter` without shims,
  add migration/deprecation guidance for adapter authors and consider an adapter
  API version bump.

## Regression-Capture Review

Matching carryover gate:

- `adapter_testkit_regression_carryover`

Triggered surfaces:

- `adapter_api`,
- `adapter_capabilities`,
- `adapter_runtime` if implementation touches runtime setup,
- `cross_repo_compatibility` through future adapter-package/test-kit impact.

Current applicable rows checked:

- `key-safety-adapter-capability-preflight`
  - remains relevant because capability blockers must still run before adapter
    lifecycle or execution.
- Adapter API and diagnostics rows in `adapter-runtime.yml` and
  `diagnostics-privacy.yml`
  - remain relevant if implementation touches setup diagnostics, adapter
    metadata diagnostics, or capability diagnostics.

Prework decision:

`regression_capture_decision: not-required`

Rationale:

- This artifact is planning-only.
- No runtime behavior, adapter API code, capability names, diagnostics,
  generated artifacts, CLI output, result/evidence behavior, or public
  compatibility promise changed yet.
- Item 16 implementation must re-check routing and add exact routes for any new
  adapter-interface modules/tests before review.

## Local-Success Blindness Second Pass

Passing local DuckDB tests is insufficient if item 16 implementation still:

- leaves `BaseAdapter` forcing relation metadata methods,
- makes DuckDB appear metadata-capable only because a method exists,
- treats `metadata_columns: full` as permission to call metadata without the
  metadata interface,
- treats metadata interface presence as enough without capability validation,
- changes `ADAPTER_API_VERSION` without compatibility docs, tests, and changelog
  assessment,
- changes adapter registry, compile setup, runtime setup, or renderer binding
  behavior while claiming interface-only scope,
- broadens into metadata-backed validation, all-column expansion, schema policy
  execution, query endpoints, debug commands, external adapter discovery,
  adapter package split, or adapter test-kit extraction,
- leaves public docs or ADR text saying relation metadata access is a required
  `BaseAdapter` responsibility,
- forgets regression-capture exact routing for new adapter-interface files.

Required local-success blindness checks after implementation:

- AST/grep guard that current runtime setup, compile setup, registry, run
  service, and renderer paths do not call `relation_exists` or `get_columns`
  for current row-count/key-safety/render-SQL behavior.
- Tests proving a minimal adapter can implement `BaseAdapter` without relation
  metadata methods.
- Tests proving metadata-capable checks use the chosen nominal metadata
  interface, not broad method presence.
- Existing adapter registry, runtime setup, compile-service, run-service,
  DuckDB adapter, and capability tests.
- Regression-capture validation and decision advisory.
- Ruff, mypy, compileall, diff check, and full pytest before review.

## Implementation Plan After Prework Review

1. Add the relation metadata interface and adjust `BaseAdapter` required methods
   according to the selected compatibility path.
2. Update DuckDB and test fake adapters so relation metadata stubs are no longer
   required unless the adapter intentionally implements the metadata interface.
3. Update public adapter docs, compatibility docs, and ADR context.
4. Add focused adapter-interface tests for minimal adapters, metadata-capable
   adapters, no false metadata support, and current DuckDB metadata capability
   status.
5. Update regression-capture exact routing for any new interface/helper/test
   files.
6. Run local-success blindness checks and full validation.

## Definition Of Done

Item 16 prework is complete when:

- this artifact defines scope, non-goals, expected behavior, public contract
  impact, compatibility impact, regression-capture decision, acceptance matrix,
  responsibility map, local-success blindness checks, and implementation plan,
- no runtime/source/test implementation has been performed,
- public research attribution rules are preserved,
- regression-capture validation passes,
- regression-capture decision advisory is checked,
- formatting/diff checks pass,
- the companion brain dump records the prework and next task.

