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
| Typed check plan schema | Draft typed plans are produced in compiled checks artifacts. | `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`, `docs/compatibility/typed-check-plan.md` | Add `TYPED_CHECK_PLAN_VERSION` only if typed plans get an independent version. |
| Adapter API | Planned; not implemented or stable yet. | `docs/architecture/adapter-interface.md`, `docs/implementation/adapter-interface-spec.md`, `docs/compatibility/adapter-api.md` | Add `ADAPTER_API_VERSION` when the adapter API exists in code. |
| Capability catalog | Draft catalog documented and represented by compiler enums; no production adapter declarations yet. | `docs/compatibility/capability-catalog.md`, `docs/framework/adapters.md` | `AdapterCapability` enum |
| Run result schema | Planned; not implemented yet. | `docs/implementation/result-model.md`, `docs/framework/evidence.md` | Add `RUN_RESULT_VERSION` when run result artifacts are implemented. |
| Evidence and report schema | Planned; not implemented yet. | `docs/framework/evidence.md`, `docs/user-guide/evidence.md`, `docs/implementation/evidence-writers.md` | Add version constants when evidence artifacts have stable machine-readable formats. |
| Failure detail schema | Planned; not implemented yet. | `docs/architecture/artifact-model.md`, `docs/implementation/result-model.md` | Add a version constant only if failure details become machine-readable artifacts. |
| State, watermark, and sample-key formats | Planned; not implemented yet. | `docs/framework/state-and-watermarks.md`, `docs/implementation/sampling-engine.md` | Add version constants when state artifacts are implemented. |
| Package resource schema | Planned; namespace and precedence design locked, not implemented yet. | `docs/decisions/adr-0017-project-resource-loading-and-precedence.md`, `docs/framework/packages.md`, `docs/framework/hub.md`, `docs/compatibility/resource-loading.md` | Add package schema/version constants when package loading is implemented. |
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
