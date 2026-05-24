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
| Compiled SQL | `target/compiled_sql/**` | SQL | Planned, not implemented yet. |
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

Compiled artifact cleanup and writes reject symlinked compiled artifact
directories and symlinked `target-path` ancestry. Standalone compiled artifact
writers also reject path-like artifact names so generated filenames cannot
escape `target/compiled_contracts/` or `target/compiled_checks/`.

This lifecycle behavior does not require an artifact version bump by itself
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
- `docs/implementation/compiled-artifacts.md`
- `docs/decisions/adr-0003-parse-compile-run-artifact-model.md`
- `docs/decisions/adr-0015-compiled-artifact-schema-and-versioning.md`
