# Public Contract Inventory

## Purpose

This inventory lists the Recon surfaces that users, adapters, packages,
integrations, generated-artifact readers, CI workflows, or future repositories
may depend on.

Treat these surfaces as public contract surfaces even before 1.0. Pre-alpha
surfaces can still change, but changes must be deliberate, documented, and
reviewed for compatibility impact.

## Current inventory

| Public contract surface | Current status | Primary docs | Code version constant |
| --- | --- | --- | --- |
| Contract YAML schema | Parser scope implemented; not frozen before 1.0. | `docs/framework/equivalence-contracts.md`, `docs/user-guide/equivalence-contracts.md` | Not centralized yet. |
| Manifest artifact schema | Implemented for `recon parse`. | `docs/implementation/parser-and-manifest.md`, `docs/compatibility/artifact-versions.md` | `MANIFEST_ARTIFACT_VERSION = 1` |
| Compiled artifact schema | Implemented for compiled contract and compiled checks YAML. | `docs/decisions/adr-0015-compiled-artifact-schema-and-versioning.md`, `docs/implementation/compiled-artifacts.md` | `COMPILED_ARTIFACT_VERSION = 1` |
| Diagnostic codes and validation timing | Implemented for current parse/compile scope; Milestone 5 timing and code ownership locked. | `docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`, `docs/implementation/errors-and-diagnostics.md`, `docs/architecture/diagnostics-and-errors.md` | No separate version constant. |
| Project resource loading and reference resolution | Contract-only loading implemented; non-contract loading/precedence design locked, not implemented. | `docs/decisions/adr-0017-project-resource-loading-and-precedence.md`, `docs/compatibility/resource-loading.md`, `docs/architecture/project-loading-and-config.md` | No separate version constant. |
| Check-pack invocation config | Current compiler supports strings and `{name}` mappings only; future `config` and `on_empty` shape locked, not implemented. | `docs/decisions/adr-0018-check-pack-invocation-config.md`, `docs/compatibility/check-pack-invocation.md`, `docs/framework/check-packs.md` | Covered by contract YAML and compiled artifact versions when implemented. |
| Column and value comparison surface | Raw authored columns are preserved; typed column validation, value checks, and all-column expansion design locked, not implemented. | `docs/decisions/adr-0019-column-and-value-comparison-surface.md`, `docs/compatibility/column-value-comparison.md`, `docs/framework/equivalence-contracts.md` | Covered by contract YAML, compiled artifact, and typed check-plan versions when implemented. |
| Tolerance, null, and normalization policy | High-level authored fields exist; MVP policy surface locked, full resolver and execution not implemented. | `docs/decisions/adr-0009-tolerance-normalization-and-null-equivalence.md`, `docs/compatibility/tolerance-null-normalization.md`, `docs/framework/tolerance-policies.md` | Covered by contract YAML, compiled artifact, typed check-plan, run result, and evidence versions when implemented. |
| Endpoint resources and query execution | Inline endpoint shape exists; endpoint resources, endpoint refs, and executable query endpoints are planned and gated. | `docs/framework/equivalence-contracts.md`, `docs/architecture/project-loading-and-config.md`, `docs/implementation/mvp-build-order.md` | Covered by contract YAML, adapter API, compiled artifact, run result, and evidence versions when implemented. |
| Selector and subset execution | Planned; `selectors.yml`, `--select`, `--exclude`, partial compile, and partial run semantics are not locked yet. | `docs/framework/project-structure.md`, `docs/user-guide/cli.md`, `docs/implementation/cli-services.md`, `docs/implementation/mvp-build-order.md` | Covered by CLI behavior, manifest, compiled artifact, and run result versions when implemented. |
| Sampling execution and stateful policies | Authored sampling fields exist at a high level; deterministic execution, anchor-side semantics, persisted samples, and previous-failure sampling are gated. | `docs/framework/sampling-policies.md`, `docs/framework/state-and-watermarks.md`, `docs/implementation/sampling-engine.md`, `docs/implementation/mvp-build-order.md` | Covered by contract YAML, typed check-plan, run result, evidence, and state versions when implemented. |
| CDC policy and delete semantics | High-level CDC docs and key semantics exist; first CDC execution and asymmetric delete representation are gated. | `docs/decisions/adr-0011-cdc-policy-and-delete-modes.md`, `docs/decisions/adr-0014-key-semantics-and-check-dependencies.md`, `docs/implementation/cdc-policy-engine.md`, `docs/implementation/mvp-build-order.md` | Covered by contract YAML, compiled artifact, run result, evidence, and state versions when implemented. |
| Semi-structured comparison | Draft adapter capabilities mention JSON/semi-structured support; public syntax and execution semantics are not implemented. | `docs/compatibility/capability-catalog.md`, `docs/implementation/mvp-build-order.md` | Covered by contract YAML, typed check-plan, adapter API, run result, and evidence versions when implemented. |
| Typed check plan schema | Draft typed plans are produced in compiled checks artifacts. | `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`, `docs/compatibility/typed-check-plan.md` | Add `TYPED_CHECK_PLAN_VERSION` only if typed plans get an independent version. |
| Adapter API | Planned; not implemented or stable yet. | `docs/architecture/adapter-interface.md`, `docs/implementation/adapter-interface-spec.md`, `docs/compatibility/adapter-api.md` | Add `ADAPTER_API_VERSION` when the adapter API exists in code. |
| Capability catalog | Draft catalog documented and represented by compiler enums; no production adapter declarations yet. | `docs/compatibility/capability-catalog.md`, `docs/framework/adapters.md` | `AdapterCapability` enum |
| Adapter test kit | Planned; no shared adapter compliance test kit exists yet. | `docs/compatibility/adapter-api.md`, `docs/compatibility/capability-catalog.md`, `docs/compatibility/compatibility-matrix.md`, `docs/implementation/mvp-build-order.md` | Add test-kit compatibility/version docs when the test kit exists. |
| CLI command and option behavior | MVP commands are pre-alpha; future commands/options are gated before automation can rely on them. | `docs/user-guide/cli.md`, `docs/architecture/cli-architecture.md`, `docs/implementation/cli-services.md`, `docs/implementation/mvp-build-order.md` | No separate version constant. |
| Run result schema | Planned; not implemented yet. | `docs/implementation/result-model.md`, `docs/framework/evidence.md` | Add `RUN_RESULT_VERSION` when run result artifacts are implemented. |
| Evidence and report schema | Planned; not implemented yet. | `docs/framework/evidence.md`, `docs/user-guide/evidence.md`, `docs/implementation/evidence-writers.md` | Add version constants when evidence artifacts have stable machine-readable formats. |
| Failure detail schema | Planned; not implemented yet. | `docs/architecture/artifact-model.md`, `docs/implementation/result-model.md` | Add a version constant only if failure details become machine-readable artifacts. |
| State, watermark, and sample-key formats | Planned; not implemented yet. | `docs/framework/state-and-watermarks.md`, `docs/implementation/sampling-engine.md` | Add version constants when state artifacts are implemented. |
| Package resource schema | Planned; namespace and precedence design locked, not implemented yet. | `docs/decisions/adr-0017-project-resource-loading-and-precedence.md`, `docs/framework/packages.md`, `docs/framework/hub.md`, `docs/compatibility/resource-loading.md` | Add package schema/version constants when package loading is implemented. |
| Hub and integration metadata | Planned; Hub, GitHub Actions, orchestrator integrations, data catalog integrations, and issue integrations have no stable metadata contract yet. | `docs/framework/hub.md`, `docs/planning/ecosystem-roadmap.md`, `docs/planning/roadmap.md`, `docs/implementation/mvp-build-order.md` | Add metadata/schema versioning when Hub or integration manifests exist. |
| Diagnostic source locations | Path-level diagnostics exist; line, column, span, and range output is planned and gated. | `docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`, `docs/implementation/errors-and-diagnostics.md`, `docs/implementation/mvp-build-order.md` | Covered by artifact schemas that carry diagnostics when implemented. |
| Cross-repo compatibility matrix | Documented as current/future matrix. | `docs/compatibility/compatibility-matrix.md` | Not a code constant. |

## Version constant policy

Code version constants should exist only for surfaces that code can actually
produce, consume, validate, or reject.

Use this policy:

- keep `MANIFEST_ARTIFACT_VERSION` because `target/manifest.json` is implemented,
- keep `COMPILED_ARTIFACT_VERSION` because compiled artifact writers are
  implemented,
- add `TYPED_CHECK_PLAN_VERSION` only if typed check plans become independently
  versioned from compiled artifact schemas,
- add `ADAPTER_API_VERSION` when the adapter API exists in code,
- add `RUN_RESULT_VERSION` when `target/run_results.json` is implemented,
- avoid placeholder constants that imply a stable API before the surface exists.

## Public contract change rule

A change touches a public contract surface when it changes:

- accepted YAML syntax,
- validation defaults or error behavior users rely on,
- generated artifact fields, paths, IDs, versions, or semantics,
- typed check-plan operation names, payloads, requirements, or rendering states,
- adapter interfaces, capabilities, registry behavior, or version support,
- result, evidence, failure detail, state, or watermark formats,
- package resource schema or package compatibility behavior,
- support ranges for Python, `recon-core`, adapters, packages, or test kits,
- deprecation, migration, or cross-repo compatibility promises.

When a public contract surface changes, use
`docs/compatibility/change-checklist.md`.

If a new public surface appears later, add it to this inventory in the same
change that introduces the surface.

## Related docs

- `docs/compatibility/change-checklist.md`
- `docs/compatibility/artifact-versions.md`
- `docs/compatibility/adapter-api.md`
- `docs/compatibility/typed-check-plan.md`
- `docs/compatibility/capability-catalog.md`
- `docs/compatibility/compatibility-matrix.md`
