# Artifact Versions

## Purpose

Generated artifacts are consumed by humans, automation, CI systems, future
orchestration integrations, and future adapter or package tooling.

This document records current artifact version status and the rules for changing
artifact formats.

## Current artifact status

| Artifact | Path | Format | Version status |
| --- | --- | --- | --- |
| Manifest | `target/manifest.json` | JSON | Implemented with `artifact_version: 1`. |
| Compiled contract | `target/compiled_contracts/<contract_name>.yml` | YAML | Implemented with `artifact_version: 1` for the current compiler scope. |
| Compiled checks | `target/compiled_checks/<contract_name>.yml` | YAML | Implemented with `artifact_version: 1` for the current compiler scope. |
| Compiled SQL | `target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql` | SQL | Implemented for `recon compile --render-sql`; referenced from compiled checks artifacts. |
| Run results | `target/run_results.json` | JSON | Planned, not implemented yet. |
| Failure details | `target/failures/` | TBD | Planned, not implemented yet. |
| Evidence reports | `reports/` | HTML or other report formats | Planned, not implemented yet. |
| State | `state/` and `target/sample_keys/` | TBD | Planned, not implemented yet. |

## Compiled artifact lifecycle

`recon compile` writes compiled contract and compiled checks YAML as a current
snapshot. After project configuration loads and `target-path` is known, Recon
removes existing top-level `*.yml` files under `target/compiled_contracts/` and
`target/compiled_checks/` before parsing and compilation continue. This
prevents removed, renamed, or invalid current contracts from leaving stale
compiled artifacts for downstream automation to read.

Compiled artifact cleanup and writes reject compiled artifact paths that are not
directories, symlinked compiled artifact directories, and symlinked
`target-path` ancestry. Adapter-aware compile must reject invalid compiled YAML
artifact paths before publishing compiled SQL, and failed compiled YAML writes
must not leave orphaned SQL artifacts or partial compiled YAML files from the
same invocation. Standalone compiled artifact writers also reject exact
output-file symlinks and path-like artifact names so generated filenames cannot
escape `target/compiled_contracts/` or
`target/compiled_checks/`.

Manifest writes also reject symlinked `target-path` ancestry and exact
`manifest.json` output-file symlinks. Normal manifest regeneration still
overwrites the current manifest file.

Generated-artifact lifecycle cleanup is a compatibility gate for future core
writers. Before adding run results, evidence, failure details, reports, state,
docs output, or selector-scoped generated artifacts, the milestone must define
cleanup and publish ordering so failed writes do not leave stale, partial, or
orphaned outputs that downstream automation could mistake for trustworthy
evidence. Batched writers must also define whether each successful item is
required to produce one or more files; for compiled SQL, empty per-check output
sets are failures and must not create empty artifact directories. This is a
core artifact-writer responsibility; adapters should avoid side effects during
rendering and execution, but core owns generated file lifecycle behavior.

These lifecycle behaviors do not require an artifact version bump by themselves
because artifact paths, schemas, header fields, and field meanings are
unchanged.

## Header convention

Machine-oriented and compiled artifacts should use top-level header fields.

Example:

```json
{
  "artifact_type": "manifest",
  "artifact_version": 1,
  "recon_version": "0.0.0",
  "generated_at": "2026-05-22T12:00:00Z"
}
```

Compiled artifacts also include `invocation_id`. Run artifacts should include
`invocation_id` once run artifact writers exist.

## Artifact version rules

Increment `artifact_version` when a generated artifact changes in a way that can
break automation or readers.

Version-impacting changes include:

- removing a field,
- renaming a field,
- changing field meaning,
- changing a field type,
- changing stable ID formats,
- changing artifact paths expected by tools,
- changing rendering status semantics,
- changing diagnostics structure,
- changing result or evidence outcome semantics.

Additive optional fields may keep the same `artifact_version` when readers can
ignore unknown fields safely and the meaning of existing fields does not change.

Adding non-contract project resource file records to the existing
`target/manifest.json.files` map may keep the current artifact version when the
change is additive and existing file key, field, and checksum meanings do not
change. Adding parsed non-contract resource summaries to `target/manifest.json`
should follow ADR 0017 and `docs/compatibility/resource-loading.md`. Package
resource file keys or namespace-qualified source-file IDs require
compatibility review because they may change manifest reader assumptions.

Adding check-pack invocation summaries to compiled artifacts should follow ADR
0018 and `docs/compatibility/check-pack-invocation.md`. Accepting check-pack
`config`, `on_empty: warn`, or `on_empty: skip` before those summaries exist
would make compiled artifacts incomplete. Changing existing check origin,
stable check IDs, or generated check semantics may require a compiled artifact
version bump.

Adding resolved column metadata to compiled artifacts should follow ADR 0019
and `docs/compatibility/column-value-comparison.md`. Raw wildcard selectors
must not appear in typed check plans. Changing existing `columns` field meaning,
required-column semantics, stable check IDs, or typed operation payloads may
require a compiled artifact version bump.

Adding resolved tolerance, null, or normalization policy fields to compiled
artifacts should follow ADR 0009 and
`docs/compatibility/tolerance-null-normalization.md`. Changing existing
`tolerance` field meaning, policy precedence, null defaults, null sentinel
matching, normalization step ordering, regex payloads, typed operation payloads,
result fields, or evidence semantics may require a compatibility review and
artifact version bump.

Compiled contract policy alignment must preserve existing field meanings. The
current compiled contract artifact emits `policies.tolerance_policy` as the
authored named tolerance policy reference and `policies.nulls` as the accepted
contract-level null policy when present. Adding optional fields such as
`policies.tolerance` or `policies.normalization` may keep
`COMPILED_ARTIFACT_VERSION = 1` only when the change is additive and existing
fields keep their meaning. Removing or renaming `policies.tolerance_policy`, or
changing it from an authored reference into a resolved policy object, requires
compatibility review and likely a compiled artifact version bump.

Current compiled contract artifacts preserve authored CDC policy under
`identity.cdc` and `policies.cdc`; they do not emit resolved CDC identity
fields. Adding fields such as `identity.cdc.declaration` or
`identity.cdc.resolved_keys`, or changing `identity.cdc` from authored policy
into resolved CDC identity, requires compatibility review and likely a compiled
artifact version bump.

Adding compiled SQL artifacts should follow ADR 0020. SQL files are generated
under:

```text
target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql
```

Compiled checks may reference rendered SQL files as an additive change when
existing field meanings do not change. Changing compiled SQL paths, rendering
status meanings, stable check IDs, SQL reference fields, or traceability
requirements is compatibility-impacting and may require a compiled artifact
version bump.

Compiled-check `rendering.sql_paths` stores paths relative to the configured
`target-path`, and `rendering.adapter_type` stores the adapter type when known.
Checks with `rendering.status: rendered` must have one or more SQL paths. Empty
renderer output and exported compiled SQL writer calls with no rendered steps
are failures and must not be represented as successful rendering with empty
`sql_paths` or empty compiled SQL directories. Malformed non-empty renderer
output is also a rendering failure and must not reach compiled SQL artifact
writing, including unsafe path-like renderer step names, invalid later renderer
steps, or duplicate step names including case-insensitive output collisions.
The compiled SQL writer validates the whole SQL batch and preflights output
paths before writing any SQL file or creating compiled SQL directories, so empty
direct writer requests, later empty rendered SQL batch requests, invalid later
renderer steps, unsafe path segments, and duplicate output paths must not leave
partial `target/compiled_sql/` artifacts behind.
For example:

```text
compiled_sql/customer_revenue/check.ecommerce_recon.customer_revenue.row_count_diff/00-row_count-source.sql
```

Compiled SQL artifacts must not contain connection secrets or fully rendered
credential payloads. SQL artifact references may include contract name, check
ID, rendering step or typed operation, side when applicable, and adapter type.
Adding `rendering.adapter_type` is additive for compiled artifact version 1
because existing field meanings and SQL path shapes do not change.
When adapter-aware rendering was requested but compile validation prevents the
adapter phase from starting, otherwise renderable checks may keep empty
`rendering.sql_paths`, use `rendering.status: blocked`, and carry
`RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS` without changing the
compiled artifact version. Future compile-flow conformance tests and any shared
adapter test-kit harness that invokes core `render-sql` flows must assert this
status/diagnostic combination instead of accepting `not_rendered` metadata.
When invocation-wide rendering diagnostics suppress all SQL output, otherwise
renderable checks may keep empty `rendering.sql_paths` and carry a structured
suppression diagnostic without changing the compiled artifact version.

## Package version relationship

`recon_version` identifies the Recon Core package version that wrote the
artifact.

`artifact_version` identifies the artifact schema version.

These are related but not the same. A new `recon-core` release may write the
same artifact schema version, and a future artifact schema change may require
migration guidance even before 1.0.

## Code version constants

Version constants should exist only for artifacts that code can produce,
consume, validate, or reject.

Current code constants:

```text
MANIFEST_ARTIFACT_VERSION = 1
COMPILED_ARTIFACT_VERSION = 1
```

Planned constants should be added when their writers or readers are
implemented:

```text
RUN_RESULT_VERSION
```

Do not add placeholder artifact constants for planned artifacts before the
implementation exists.

## Generated artifact policy

Generated artifacts belong under ignored paths:

```text
target/
reports/
state/
```

Generated artifacts should not be committed as source.

## Required documentation updates

When artifact formats, paths, version fields, stable IDs, or automation-facing
semantics change, update:

- this document,
- the relevant framework, architecture, and implementation docs,
- `docs/compatibility/compatibility-matrix.md` when version support changes,
- `CHANGELOG.md` when user-visible behavior changes,
- migration guidance when existing users or tooling must change.

Durable artifact format decisions require an ADR or ADR update.

## Related docs

- `docs/architecture/artifact-model.md`
- `docs/compatibility/resource-loading.md`
- `docs/implementation/compiled-artifacts.md`
- `docs/decisions/adr-0003-parse-compile-run-artifact-model.md`
- `docs/decisions/adr-0015-compiled-artifact-schema-and-versioning.md`
- `docs/decisions/adr-0020-milestone-6-adapter-profile-and-sql-rendering-boundary.md`
