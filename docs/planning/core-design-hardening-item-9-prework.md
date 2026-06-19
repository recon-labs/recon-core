# Core Design Hardening Item 9 Prework

## Purpose

This is the prework artifact for final-order item 9: split render-vs-runtime
adapter capability semantics from runtime safety-check semantics.

Item 9 is high-risk because it touches adapter capabilities, adapter API
validation, SQL rendering, check execution, runtime scan safety, public
compatibility docs, future adapter packages, and future shared adapter test-kit
claims. This artifact locks the design boundary before implementation. It does
not implement runtime behavior.

Split Decision: Already Split / Follow Existing Split.

The broader hardening branch already split this work away from row-count
execution, grain-key safety execution, renderer-default cleanup, DuckDB renderer
decomposition, and BaseAdapter metadata-interface work. Item 9 should remain a
focused semantic alignment step. Later implementation must follow the staged
plan in this document instead of folding item 10 or item 16 into item 9.

## Scope

Item 9 prework covers:

- current adapter capability names and support-state semantics,
- render-phase use of compiled plan `required_capabilities`,
- rendered SQL step-level `required_capabilities`,
- runtime adapter setup capability validation,
- runtime safety-check and scan-safety boundaries,
- registry wiring for built-in and future adapter packages,
- separate-repo connector expectations,
- public contract, compatibility, privacy, and test impact,
- implementation-readiness criteria for the next coding pass.

The selected design is conservative: keep current capability names stable for
now, clarify their surface-specific meaning, and keep runtime safety checks as a
separate permission boundary rather than a capability namespace.

## Non-Goals

Item 9 prework must not implement:

- runtime code changes,
- adapter API version changes,
- capability enum renames,
- public YAML schema changes,
- CLI behavior changes,
- new generated artifacts,
- run-result, evidence, report, failure-detail, state, or sink output,
- aggregate runtime execution,
- query endpoint execution,
- cross-adapter execution,
- cross-connection bridging,
- materialization or staging,
- hidden Python fallback,
- adapter-managed placement selection,
- production scan-budget settings,
- shared adapter test-kit publication,
- external adapter package compatibility claims,
- BaseAdapter metadata-method splitting.

## Current Audit Findings

Current code already has the main ingredients for the intended boundary:

- `AdapterCapabilities` stores support states and treats undeclared support as
  `unknown`.
- `validate_required_capabilities()` blocks anything except `full`; future
  `versioned` support still needs an explicit version resolver before it can
  satisfy a requirement.
- `render_check_sql()` validates adapter metadata, adapter API version, renderer
  `adapter_type`, compiled-plan capabilities, renderer output shape, and
  rendered step capabilities before SQL can be published.
- `prepare_runtime_adapter()` validates factory resolution, adapter metadata,
  adapter/profile type match, adapter API version, capability declaration shape,
  and runtime-required capabilities before adapter lifecycle begins.
- `RuntimeSafetyCheckRequest`, `RuntimeScanSafetyStatus`, and
  `RuntimeSafetyCheckRegistry` provide a neutral private boundary for runtime
  safety checks.
- `RunService` asks the runtime safety-check registry for scan-safety status,
  then Core's scan-budget classifier decides whether key-safety execution is
  allowed or not executable.
- DuckDB scan safety mechanics live under the DuckDB adapter package area, not
  in check execution.

Current design debt to preserve as later scoped work:

- Row-count and key-safety execution helpers still default to
  `DuckDbSqlRenderer()` when a renderer is missing. Item 10 owns that cleanup.
- DuckDB declares aggregate rendering capabilities, while aggregate runtime
  execution remains a separate future phase. This is safe only if capabilities
  are documented and tested as mechanics that do not independently enable a
  runtime surface.
- The default runtime safety-check registry currently registers the in-core
  DuckDB scan safety check. Future separate-repo connectors must register
  through adapter package registration or explicit registry injection, not
  through connector imports in `RunService`.

## Capability Boundary Decision

Adapter capability support answers one narrow question: does the adapter declare
the named mechanic with a support state that Core can validate?

It does not answer these questions by itself:

- whether a typed check is currently executable,
- where a comparison is allowed to execute,
- whether data may move between systems,
- whether a scan is safe,
- whether results or evidence may be published,
- whether failure details may be exported.

Surface-specific requirements apply the capability mechanic:

| Surface | Requirement source | Decision owner | Behavior |
| --- | --- | --- | --- |
| Typed plan | `plan.required_capabilities` | Compiler and compatibility docs | Records mechanics required by the operation sequence. |
| SQL rendering | plan requirements plus rendered-step requirements | Adapter rendering orchestration | Blocks SQL publication when capability support is missing, malformed, or inadequate. |
| Runtime operation execution | runtime requirement builder for the supported execution phase | Run service and check engine | Blocks adapter setup or execution when required mechanics are unavailable. |
| Runtime safety | runtime safety-check registry and scan-budget classifier | Core runtime safety policy | Allows or blocks scan-heavy execution independently from operation capabilities. |
| Placement/materialization/sinks | future gated capability families | Core placement and output phases | Not implemented; must remain explicit blockers until owned. |

Support-state semantics remain unchanged:

- `unknown`, `unsupported`, `not_implemented`, malformed, and incompatible
  states are blockers.
- `full` satisfies a requirement.
- `versioned` does not satisfy a requirement until a version resolver validates
  the adapter, engine, or database version for that exact capability.

## Runtime Safety-Check Decision

Runtime safety checks are permission checks, not check execution and not adapter
operation capabilities.

The runtime safety-check boundary should keep these properties:

- neutral request and result shapes,
- no dependency on compiled artifact classes,
- no dependency on check result models,
- no raw database error text in diagnostics,
- no raw source/target row, key, or value movement into Core,
- fail-closed behavior when a safety check is missing, unsupported, malformed,
  or cannot inspect metadata safely,
- Core-owned mapping from safety status to `ScanBudgetDecision`,
- no direct connector-specific imports in `RunService`.

For current key-safety execution, the scan safety check only classifies whether
the relation-backed DuckDB context is internal bounded local/dev. The
scan-budget classifier still owns the final allowed or not-executable decision.

## Separate-Repo Connector Model

Future adapter packages should provide adapter factories, SQL renderers,
capability declarations, and optional runtime safety checks through installed
package registration or explicit registry injection.

Core may keep an in-core default for the current DuckDB development adapter
until the adapter API and shared adapter test kit are stable. Core runtime
orchestration must not grow per-connector imports as new adapters appear.

Adapter packages cannot claim execution, placement, scan-safety, staging,
result-sink, or evidence compatibility until the relevant capability semantics,
runtime safety checks, docs, and shared conformance rows exist.

## Acceptance And Conformance Matrix

| Case | Expected behavior | Required test coverage before implementation claims completion |
| --- | --- | --- |
| Unsupported plan capability | Rendering and runtime setup block with structured capability diagnostics. | Existing render/runtime capability tests plus any changed requirement-builder tests. |
| Rendered step adds an unsupported capability | SQL artifacts are not published. | Existing rendered-step capability tests must keep covering unsupported, `unknown`, `not_implemented`, malformed, and extra declarations. |
| Adapter has `full` operation capability but execution phase is absent | Check remains `not_executable`; capability does not create runtime support. | Add or preserve tests proving aggregate checks do not execute merely because aggregate mechanics are declared. |
| Key-safety operation capabilities are present but scan safety is not allowed | Check is `not_executable`, not a data failure. | Existing scan-budget tests plus any changed safety-registry tests. |
| Runtime safety check missing for a scan-heavy adapter context | Core fails closed through unknown or unsupported scan-budget status. | Add registry tests before external adapter support. |
| Adapter API version mismatch | Rendering/runtime setup blocks before capabilities, lifecycle, rendering, or execution. | Existing adapter API tests must remain mapped. |
| Factory returns malformed result or malformed diagnostics | Adapter resolution fails before rendering or execution. | Existing registry tests must remain mapped. |
| Explicit renderer `adapter_type` mismatch | Rendering blocks before `render_plan()`. | Existing renderer binding tests must remain mapped. |
| Execution helper receives no renderer | Item 10 must make this explicit; item 9 must not rely on DuckDB defaults as long-term design. | Item 10 tests. |
| Future connector provides runtime safety check | Registered safety check is discovered without `RunService` importing the connector package. | Future adapter package or registry tests. |
| Placement or materialization metadata appears before owning phase | Check is blocked or `not_executable`; no fallback placement is inferred. | Existing placement/materialization blocker tests plus future execution-surface tests. |

## Workflow Scenarios

Scenario: rendered SQL step requires an extra mechanic.

- Given an adapter supports the compiled plan requirements,
- when the renderer returns a step with an additional unsupported capability,
- then Core blocks SQL publication and writes no partial SQL artifacts.

Scenario: operation capability does not bypass scan safety.

- Given a key-safety operation capability is `full`,
- when the scan safety check cannot prove the current context is allowed,
- then the key-safety check is `not_executable` and no data check runs.

Scenario: aggregate mechanics do not enable aggregate runtime execution.

- Given an adapter can render aggregate mechanics,
- when `recon run` sees aggregate checks before the aggregate execution phase,
- then aggregate checks remain assigned to their later phase and do not run.

Scenario: separate adapter package registration.

- Given a future adapter package is installed,
- when Core builds adapter and runtime safety registries,
- then package registration supplies the adapter-specific entries and
  `RunService` stays adapter-neutral.

## Responsibility Map

| Component | Allowed responsibilities | Forbidden responsibilities |
| --- | --- | --- |
| `adapters/capabilities.py` | Support states and required-capability validation. | Placement decisions, scan safety decisions, check execution, result semantics. |
| `adapters/rendering.py` | Render-phase adapter/API/renderer/capability validation and rendered-output validation. | Runtime scan policy, adapter lifecycle, evidence/result publication. |
| `adapters/runtime_setup.py` | Runtime adapter resolution and pre-lifecycle compatibility validation. | Opening connections, choosing execution placement, scan-budget policy. |
| `adapters/runtime_safety.py` | Neutral runtime safety-check protocol and registry. | DuckDB mechanics, compiled artifact parsing, check-result creation. |
| `adapters/duckdb/runtime_scan_guard.py` | DuckDB bounded local/dev scan classification mechanics. | Core scan-budget policy, key-safety result logic, public scan settings. |
| `services/run.py` | Runtime orchestration, profile loading, registry use, adapter setup, check-engine invocation. | Per-connector mechanics, SQL dialect choices, direct safety-check implementation. |
| `check_engine/scan_budget.py` | Core safety policy that maps scan classification to allow/block decisions. | Adapter metadata inspection, SQL rendering, adapter lifecycle. |
| `check_engine/execution.py` and `check_engine/key_safety.py` | Supported check-family execution and result parsing. | Safety-policy ownership, hidden renderer defaults as long-term design, cross-adapter fallback. |

## Affected Docs

This prework adds this planning artifact and clarifies
`docs/compatibility/capability-catalog.md`.

Future implementation may also need updates to:

- `docs/compatibility/adapter-api.md`,
- `docs/compatibility/typed-check-plan.md`,
- `docs/compatibility/compatibility-matrix.md`,
- `docs/architecture/adapter-interface.md`,
- `docs/architecture/check-engine.md`,
- `docs/implementation/adapter-interface-spec.md`,
- `docs/framework/adapters.md`,
- relevant ADRs only if behavior becomes durable beyond existing ADR coverage.

No changelog entry is required for this prework because it changes planning and
compatibility wording only, with no public behavior change.

## Required Tests For Future Implementation

Before item 9 implementation or a dependent item claims completion, test
coverage must prove:

- operation capabilities do not independently enable unsupported runtime check
  families,
- rendered-step capability enforcement still blocks artifact publication,
- runtime adapter setup still validates adapter API before capabilities and
  lifecycle,
- malformed capability declarations remain structured diagnostics,
- missing runtime safety checks fail closed for scan-heavy execution,
- scan safety and operation capability validation are both required for
  key-safety execution,
- registry wiring does not add connector imports to `RunService`,
- no hidden Python, cross-adapter, cross-connection, materialization, or
  placement fallback appears.

Regression-capture review is required for any implementation that changes
adapter capability validation, scan safety, runtime setup, SQL rendering,
artifact publication, or check execution behavior.

## Compatibility, Security, And Privacy Impact

Compatibility impact:

- This prework does not rename capabilities or change runtime behavior.
- Clarifying capability semantics is compatibility-relevant documentation, but
  it is not a breaking code change because no stable external adapter API has
  been released.
- Future behavior changes to capability names, support states, runtime
  requirements, placement, materialization, or safety-check registration remain
  compatibility-impacting.

Security and privacy impact:

- Runtime safety checks must not expose credentials, rendered profile values,
  raw query text, raw database errors, source/target rows, key values, or
  failure details.
- Scan-heavy execution remains fail-closed unless Core's safety policy allows
  it.
- Result/evidence/failure-detail/sink output remains out of scope.

## Definition Of Done

Item 9 prework is complete when:

- current capability and runtime safety code surfaces have been audited,
- the render-vs-runtime capability boundary is documented,
- runtime safety-check semantics are documented,
- separate-repo connector expectations are documented,
- compatibility, docs, changelog, privacy, security, and test impacts are
  recorded,
- Split Decision is recorded,
- the no-aggregate-runtime and no-M7.4 boundary is preserved,
- the companion brain dump is updated,
- doc-only validation passes.

## Future Implementation Plan

1. Centralize any item 9 code changes around semantics and requirement builders
   only; do not rename capability constants unless a separate compatibility
   decision approves it.
2. Add tests proving capability support does not imply execution permission for
   check families whose runtime phase is absent.
3. Add or preserve tests proving scan safety is independent from operation
   capability validation.
4. Keep `RuntimeSafetyCheckRequest` and `RuntimeScanSafetyStatus` neutral. If
   they need fields, extend them with primitive execution-context data rather
   than compiled artifact or check-result objects.
5. Preserve default DuckDB support only through built-in registry construction.
   Future external connectors must use package registration or injected
   registries.
6. Hand off hard-coded renderer default cleanup to item 10 after item 9
   semantics are accepted.

## Local-Success Blindness Second Pass

The local objective is a docs/prework lock, not runtime behavior. A passing
docs edit is insufficient if it accidentally:

- treats operation capabilities as runtime permission,
- weakens rendered-step capability enforcement,
- weakens support-state blockers,
- introduces hidden fallback language,
- expands current execution claims to aggregate or query endpoints,
- names a future connector mechanism as implemented,
- moves mature-project research attribution into public docs.

Second-pass result for this prework: the design keeps capability mechanics,
runtime safety checks, execution placement, and output surfaces separately
owned; it records item 10 and item 16 as later scoped work; and public docs use
Recon-native decisions only.
