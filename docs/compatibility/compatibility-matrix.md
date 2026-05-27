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
| Contract schema stabilization | Planned | Schema freeze, machine-readable schema reference, deprecation lifecycle, and migration policy are gated before 1.0. |
| Named identities and multi-grain contracts | Planned | Current contract model supports one default `grain.keys` and one default `cdc.keys`; advanced identity roles are gated. |
| Manifest artifact | `artifact_version: 1` | Implemented for `recon parse`; pre-alpha compatibility. |
| Compiled contract artifact | `artifact_version: 1` | Implemented for `recon compile`; pre-alpha compatibility. |
| Compiled checks artifact | `artifact_version: 1` | Implemented for `recon compile`; pre-alpha compatibility. |
| Artifact freshness and cache semantics | Planned | Cache optimization and skip-unchanged behavior are gated before generated artifacts can be reused silently. |
| Typed check plan | Draft typed operation catalog | Produced in compiled checks artifacts; not stable before 1.0. |
| Check-pack invocation config | Strings and `{name}` mappings implemented; `config` and `on_empty` design locked by ADR 0018. | `config`, `on_empty: warn`, and `on_empty: skip` are not implemented yet. |
| Local custom check-pack resources | Planned | Local check-pack file schema, config schema, expansion, diagnostics, and artifact visibility are gated. |
| Local reusable policy resources | Planned | Local sampling, tolerance, and schema policy file schemas and reference resolution are gated. |
| Column and value comparison | Raw authored columns preserved; typed column surface locked by ADR 0019. | Typed column validation, row-level value checks, and all-column expansion are not implemented yet. |
| Tolerance, null, and normalization | High-level fields exist; MVP policy surface locked by ADR 0009. | Full typed resolver, reusable policy files, row-level execution, adapter rendering, results, and evidence are not implemented yet. |
| Endpoint resources and query execution | Planned | Endpoint refs and executable query endpoints are gated before implementation. |
| Selectors and subset execution | Planned | `selectors.yml`, `--select`, `--exclude`, partial compile, and partial run are not implemented yet. |
| Sampling execution and stateful policies | Planned | Deterministic execution, anchor-side semantics, persisted samples, previous-failure samples, and multi-policy composition are gated. |
| CDC policy and delete semantics | Planned | First CDC execution, asymmetric delete representation, and advanced CDC modes are gated before implementation. |
| Semi-structured comparison | Planned | JSON path and semi-structured projection semantics are not implemented yet. |
| Adapter API | Planned | No stable adapter API version released yet. |
| Capability catalog | Draft | Compiler enums exist; no production adapter declarations yet. |
| Adapter install extras and packaging strategy | Planned | Separate adapter packages versus optional `recon-core[...]` extras is not locked yet. |
| Adapter packages | Planned | No official external adapter packages released yet. |
| Adapter test kit | Planned | No test-kit package or workflow exists yet. |
| CLI command and option behavior | MVP commands are pre-alpha | Future commands/options, documentation generation, and destructive init overwrite behavior are gated before becoming automation contracts. |
| Check and policy packages | Planned | Package loading, official package content releases, and domain-package boundaries are gated. |
| Package dependency installer and lock workflow | Planned | `recon deps`, `packages.yml`, package locks, and install/update behavior are not implemented yet. |
| Run results | Planned | No stable result artifact version yet. |
| Evidence reports | Planned | No stable evidence format yet. |
| Result table writer | Planned | No database/table result writer schema exists yet. |
| Failure detail JSONL and large-result handling | Planned | CSV-first failure details are planned; JSONL, streaming, pagination, and truncation semantics are gated. |
| State backend | Planned | Local state is gated; remote/database-backed state has a separate gate before production use. |
| Hub and integration metadata | Planned | No Hub index, action, orchestrator, catalog, issue, or vault metadata contract exists yet. |
| Docs site and examples repo split | Planned | External docs/examples repos should not split until ownership, CI, and release coordination are defined. |
| Hosted service, UI, and enterprise controls | Planned only if product direction expands | These must integrate through public core contracts and must not redefine core semantics. |
| Diagnostic source locations | Path-level only | Line, column, span, and range output is gated before artifact shape changes. |

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
- artifact freshness or cache semantics,
- typed check-plan versions or operation support,
- adapter API versions,
- adapter capability support,
- adapter test-kit compatibility,
- package resource compatibility,
- package lock or installer compatibility,
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
