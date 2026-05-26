# Compatibility Matrix

## Purpose

This document records which Recon components are expected to work together.

Today the matrix is mostly a current-state record. Later it should become the
cross-repo compatibility source for `recon-core`, adapters, packages, the
adapter test kit, Hub metadata, and integrations.

## Current matrix

| Component or surface | Current version or status | Compatibility position |
| --- | --- | --- |
| `recon-core` package | `0.0.0`, pre-alpha | No stable public API guarantee yet. |
| Python runtime | `>=3.11` | Declared in `pyproject.toml`. |
| Contract YAML | Authored contract `version: 1` parser scope | Implemented parser scope, not frozen before 1.0. |
| Manifest artifact | `artifact_version: 1` | Implemented for `recon parse`; pre-alpha compatibility. |
| Compiled contract artifact | `artifact_version: 1` | Implemented for `recon compile`; pre-alpha compatibility. |
| Compiled checks artifact | `artifact_version: 1` | Implemented for `recon compile`; pre-alpha compatibility. |
| Typed check plan | Draft typed operation catalog | Produced in compiled checks artifacts; not stable before 1.0. |
| Check-pack invocation config | Strings and `{name}` mappings implemented; `config` and `on_empty` design locked by ADR 0018. | `config`, `on_empty: warn`, and `on_empty: skip` are not implemented yet. |
| Column and value comparison | Raw authored columns preserved; typed column surface locked by ADR 0019. | Typed column validation, row-level value checks, and all-column expansion are not implemented yet. |
| Tolerance, null, and normalization | High-level fields exist; MVP policy surface locked by ADR 0009. | Full typed resolver, reusable policy files, row-level execution, adapter rendering, results, and evidence are not implemented yet. |
| Adapter API | Planned | No stable adapter API version released yet. |
| Capability catalog | Draft | Compiler enums exist; no production adapter declarations yet. |
| Adapter packages | Planned | No official external adapter packages released yet. |
| Adapter test kit | Planned | No test-kit package or workflow exists yet. |
| Check and policy packages | Planned | No official external packages released yet. |
| Run results | Planned | No stable result artifact version yet. |
| Evidence reports | Planned | No stable evidence format yet. |

## Future adapter matrix format

When adapter repositories exist, track them with a table like:

| Adapter package | Adapter version | Supported `recon-core` | Adapter API | Typed plan support | Test kit | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `recon-postgres` | TBD | TBD | TBD | TBD | TBD | Planned |
| `recon-snowflake` | TBD | TBD | TBD | TBD | TBD | Planned |

Adapter repositories should not independently invent compatibility promises.
They should reference the versions and contracts defined by `recon-core`.

## Future package matrix format

When check, policy, evidence template, or integration packages exist, track them
with a table like:

| Package | Package version | Supported `recon-core` | Resource schema support | Status |
| --- | --- | --- | --- | --- |
| `recon-checks-cdc` | TBD | TBD | TBD | Planned |
| `recon-policies-sampling` | TBD | TBD | TBD | Planned |

## Update rules

Update this matrix when any of the following change:

- supported Python versions,
- supported `recon-core` versions,
- contract schema compatibility,
- artifact schema versions,
- typed check-plan versions or operation support,
- adapter API versions,
- adapter capability support,
- adapter test-kit compatibility,
- package resource compatibility,
- official adapter, package, Hub, or integration release status.

If a new compatibility dimension appears later, add it to this matrix rather
than leaving it implicit.

## Related docs

- `docs/compatibility/adapter-api.md`
- `docs/compatibility/typed-check-plan.md`
- `docs/compatibility/capability-catalog.md`
- `docs/compatibility/artifact-versions.md`
- `docs/framework/repository-strategy.md`
- `docs/planning/ecosystem-roadmap.md`
