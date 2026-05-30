# ADR 0015: Compiled Artifact Schema and Versioning

## Context

Recon separates authored contracts from generated compile artifacts. Compiled artifacts show resolved contract meaning and planned checks before later run behavior uses them.

ADR 0003 defines the parse, compile, and run artifact model. ADR 0013 defines typed check plans and adapter SQL rendering. ADR 0014 defines comparison keys separately from CDC keys.

Compiled artifacts are user-facing and automation-facing files, so their shape is a compatibility surface.

## Decision

Recon writes two compiled YAML artifacts for each contract.

The compiled contract artifact records resolved contract meaning.

The compiled checks artifact records executable checks, check origins, requirements, prerequisites, typed plans, rendering metadata, and diagnostics.

Compiled artifacts use top-level header fields for artifact type, artifact version, Recon version, generation time, and invocation ID.

Compiled artifacts use stable IDs for contracts, checks, and plans. Stable ID parts must be validated before they are used in artifact IDs or artifact file names.

Compiled artifact directories must be treated as generated output directories. Recon should avoid stale artifacts and reject unsafe artifact paths.

## Compiled contract artifact

A compiled contract artifact includes project metadata, contract metadata, source and target endpoints, comparison identity, CDC policy when present, authored column declarations, authored metrics, preserved policy fields, and diagnostics.

Policy compatibility rules:

- tolerance policy fields preserve authored references until a resolver exists.
- null policy fields preserve accepted contract-level null policy when present.
- normalization policy fields are reserved for a future accepted and resolved policy surface.
- additive fields may stay in artifact version 1 only when existing field meanings stay stable.
- removing, renaming, or changing existing field meanings requires compatibility review.

CDC compatibility rules:

- current compiled artifacts preserve authored CDC policy when present.
- current compiled artifacts do not resolve grain aliases into concrete CDC key lists.
- resolved CDC identity fields require the CDC execution gate, compatibility review, artifact tests, and result/evidence visibility decisions.

## Compiled checks artifact

Every compiled check includes ID, name, type, origin, identity, requirements, prerequisites, blocking policy, sampling, tolerance when applicable, typed plan, rendering metadata, and diagnostics.

Allowed origin kinds are explicit check, metric, check pack, and framework-required safety check.

Check-pack expansion and framework-generated safety checks must be visible in compiled artifacts.

## Typed check plans

The typed check plan is the execution contract owned by Recon Core. Typed operation payloads are explicit models, not arbitrary dictionaries.

Adapters render typed plans into SQL or equivalent execution requests. Adapter rendering must not define reconciliation semantics.

Key safety checks use side-specific null-key operations for null values in declared identity keys. These checks are separate from schema nullability checks.

## Rendering metadata

Compiled checks must include rendering metadata even when SQL is not generated.

Milestone 4 compiled checks write not_rendered until adapter SQL rendering exists. ADR 0020 defines the Milestone 6 adapter-aware rendering migration target: not_rendered, rendered, blocked, and failed.

Blocked means rendering was intentionally skipped because validation failed. Failed means rendering was attempted but failed because of an adapter or rendering error.

Current pre-Milestone-6 compiler models may still expose earlier draft statuses until the implementation migration updates code, tests, compiled-artifact examples, and compatibility docs together.

See also docs/decisions/adr-0015-rendering-status-amendment.md.

## Built-in check-pack scope

recon_core.basic_equivalence expands to row_count_diff, missing_keys, extra_keys, null_source_keys, null_target_keys, duplicate_source_keys, and duplicate_target_keys.

The pack requires grain keys. It must not silently weaken to only row_count_diff when grain is missing. Empty check-pack expansion is an error.

Aggregate equivalence remains a design target. Recon must not infer aggregate checks from numeric columns until a future decision explicitly enables that behavior and defines artifact visibility. Explicit metrics compile into aggregate checks without needing the aggregate check pack.

## Metric compilation scope

Explicit metrics compile into aggregate checks. Metric compilation must not depend on grain keys.

Ungrouped aggregate metrics use aggregate operations followed by compare aggregates. Grouped aggregate metrics use grouped aggregate operations followed by compare grouped aggregates.

## Diagnostics and implementation pattern

Compiled artifacts embed structured diagnostics. Root-level diagnostics describe contract-level or artifact-level issues. Check-level diagnostics describe a specific compiled check.

ADR 0016 owns current diagnostic timing and code-family behavior.

Compiler implementation should use typed models, stable ID helpers, explicit serialization, thin CLI modules, service orchestration boundaries, and focused artifact writers.

## Versioning and compatibility

Artifact versions start at 1.

Additive fields are allowed within the same artifact version when they do not change existing field meaning.

Renaming fields, removing fields, changing field meaning, or changing required field semantics requires compatibility review, an ADR update, and may require an artifact version bump.

Generated artifacts remain under ignored paths such as target.
