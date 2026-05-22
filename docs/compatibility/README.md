# Compatibility

## Purpose

This directory tracks compatibility surfaces that matter across `recon-core`,
future adapter repositories, future package repositories, generated artifacts,
and automation built on top of Recon.

`recon-core` remains the source of truth for compatibility rules until adapter,
package, test-kit, Hub, and integration repositories are split.

## Current status

Recon Core is pre-alpha. The package version is `0.0.0`, the project metadata
marks the package as pre-alpha, and no public 1.0 compatibility guarantee exists
yet.

Current implementation status:

| Surface | Current status |
| --- | --- |
| Contract parsing | Implemented for the current parser scope. |
| `target/manifest.json` | Implemented with `artifact_version: 1`. |
| `recon compile` | Command exists, implementation is not complete yet. |
| Compiled artifacts | Schema is decided by ADR 0015, implementation is not complete yet. |
| Typed check plans | Architecture is decided by ADR 0013, implementation is not complete yet. |
| Adapter API | Documented as an intended boundary, not stable or implemented yet. |
| Adapter capabilities | Documented as a draft catalog, not implemented as stable constants yet. |
| External adapter repos | Planned, not split yet. |
| Adapter test kit | Planned, not created yet. |
| Run results and evidence | Planned, not implemented yet. |

## Documents

- `adapter-api.md` defines the current adapter API compatibility position.
- `typed-check-plan.md` defines the current typed check-plan compatibility
  position.
- `capability-catalog.md` records the draft capability names and rules.
- `artifact-versions.md` records generated artifact versioning rules.
- `compatibility-matrix.md` records the current and future compatibility matrix
  format.

## Compatibility update rule

When a change affects a public compatibility surface, update this directory in
the same change.

Compatibility surfaces include, but are not limited to:

- adapter interfaces,
- adapter API versioning,
- adapter capabilities,
- typed check-plan operations or payloads,
- generated artifact formats, paths, or version fields,
- manifest, run result, evidence, failure detail, state, or watermark formats,
- package loading or package resource compatibility,
- supported Python or `recon-core` version ranges,
- cross-repo compatibility promises,
- deprecation or migration behavior.

If Recon adds a new externally consumed surface later, agents and maintainers
must treat it as a compatibility surface even if it is not listed here yet.
Update the relevant compatibility document, or add a new document when the
surface does not fit the existing files.

## Source of truth

Compatibility docs summarize the current compatibility position. They do not
replace durable decisions.

When compatibility behavior changes because of a durable framework decision,
update the relevant ADR under `docs/decisions/` or create a new one.

See also:

- `docs/decisions/adr-0012-adapter-and-package-ecosystem.md`
- `docs/decisions/adr-0013-typed-check-plans-and-adapter-sql-rendering.md`
- `docs/decisions/adr-0015-compiled-artifact-schema-and-versioning.md`
- `docs/framework/adapters.md`
- `docs/framework/contract-compilation.md`
- `docs/framework/repository-strategy.md`
- `docs/planning/ecosystem-roadmap.md`
