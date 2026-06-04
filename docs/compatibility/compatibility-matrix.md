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
| Compiled SQL artifacts | Implemented for `recon compile --render-sql` | Current path is `target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql`; compiled checks reference target-relative `compiled_sql/...` paths and include `rendering.adapter_type` when an adapter is known. Failed compiled YAML writes must not leave orphaned compiled SQL output or partial compiled YAML from the same invocation. |
| Generated artifact lifecycle and cleanup | Implemented for current compile outputs; gated for future outputs | Current manifest, compiled YAML, and compiled SQL writers reject unsafe paths and avoid stale, partial, or orphaned generated outputs. Future run results, evidence, failure details, reports, state, docs output, and selector-scoped artifacts must define cleanup and publish ordering before they become compatibility surfaces. |
| Artifact freshness and cache semantics | Planned | Cache optimization and skip-unchanged behavior are gated before generated artifacts can be reused silently. |
| Typed check plan | Draft typed operation catalog | Produced in compiled checks artifacts; Milestone 6 renders current operations only and does not expand the catalog. |
| Check-pack invocation config | Strings and `{name}` mappings implemented; `config` and `on_empty` design locked by ADR 0018. | `config`, `on_empty: warn`, and `on_empty: skip` are not implemented yet. |
| Local custom check-pack resources | Planned | Local check-pack file schema, config schema, expansion, diagnostics, and artifact visibility are gated. |
| Local reusable policy resources | Planned | Local sampling, tolerance, and schema policy file schemas and reference resolution are gated. |
| Column and value comparison | Raw authored columns preserved; current typed column declaration/reference validation implemented under ADR 0019. | Row-level value checks, all-column expansion, resolved column metadata, eligibility enforcement, and adapter metadata validation are not implemented yet. |
| Tolerance, null, and normalization | High-level fields exist; MVP policy surface locked by ADR 0009. | Full typed resolver, reusable policy files, row-level execution, adapter rendering, results, and evidence are not implemented yet. |
| Endpoint resources and query execution | Planned | Endpoint refs and executable query endpoints are gated before implementation; Milestone 6 adapter-aware behavior is relation-only. |
| Selectors and subset execution | Planned | `selectors.yml`, `--select`, `--exclude`, partial compile, and partial run are not implemented yet. |
| Sampling execution and stateful policies | Planned | Deterministic execution, anchor-side semantics, persisted samples, previous-failure samples, and multi-policy composition are gated. |
| CDC policy and delete semantics | Planned | First CDC execution, asymmetric delete representation, and advanced CDC modes are gated before implementation. |
| Semi-structured comparison | Planned | JSON path and semi-structured projection semantics are not implemented yet. |
| Profile and secret handling | Implemented for adapter-aware compile | Selected-target rendering, referenced-connection filtering, env-var rendering, unsupported-template rejection, profile-backed adapter diagnostic suppression including adapter API compatibility and render-phase diagnostics, `rendering.adapter_type` redaction, non-string rendered-value redaction, and same adapter connection-context enforcement are implemented for `--render-sql`; run-time profile loading, debug/profile validation commands, and shared conformance tests are future work. |
| Adapter API | `ADAPTER_API_VERSION = "1"`, pre-alpha | No stable external adapter API release yet; current boundary separates `BaseAdapter` and `SqlRenderer`. |
| Capability catalog | Draft with ADR 0020 support states | Support-state validation exists; the in-core DuckDB local adapter declares the current rendering subset. |
| Adapter install extras and packaging strategy | `recon-core[duckdb]` implemented | The DuckDB local development adapter remains in-core; separate production adapter packages are future work. |
| Adapter packages | Planned | No official external adapter packages released yet; DuckDB starts in-core and `recon-duckdb` waits for adapter API and test-kit stability. |
| Adapter test kit | Planned | No test-kit package or workflow exists yet; before it is created or split into a repository, it must define adapter API conformance tests for registry/factory resolution, including empty or malformed factory results, sanitized factory exceptions, missing or invalid adapter API version declarations, invalid or exception-raising `adapter_type` metadata, sanitized capability declaration exceptions, malformed capability support states, adapter API compatibility diagnostics, render-phase diagnostics, profile-rendering behavior, field-by-field adapter diagnostic redaction across message, hint, path, `resource_type`, `resource_name`, `rendering.adapter_type`, and future structured diagnostic fields, case-variant and non-string rendered-config redaction, safe non-empty diagnostic messages, and empty renderer output failures, plus a SQL comparison conformance matrix for null-safe equality, key-diff semantics, grouped nullable keys, cross-type comparisons, key/group and aggregate-value type-mismatch failures including empty-relation, boolean aggregate, same-type unsupported/non-numeric aggregate-input, unsigned-large-integer aggregate cases such as DuckDB `UHUGEINT`, exact numeric aggregate preservation for large integers and decimals, empty aggregate result semantics where engines such as DuckDB return `NULL` for `sum` on empty groups rather than zero, no cross-type grouped-key coalescing, same-context rendering requirements, and unsupported-capability behavior. |
| Comparison execution placement | Planned | Must be resolved before Milestone 7 check-engine execution; no silent Python fallback. |
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
| Diagnostic output rendering | CLI code and message implemented for current command failures | Future run results, evidence reports, debug/profile commands, adapters, and adapter test-kit surfaces must preserve safe actionable messages with diagnostic codes. Redaction may replace unsafe text, but must not leave users with only a code or hint. |
| Diagnostic source locations | Path-level only | Line, column, span, and range output is gated before artifact shape changes. |

## Future adapter matrix format

When adapter repositories exist, track them with a table like:

| Adapter package | Adapter version | Supported `recon-core` | Adapter API | Typed plan support | Test kit | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `recon-duckdb` | TBD | TBD | TBD | TBD | TBD | Planned after in-core DuckDB adapter and shared adapter test kit stabilize. |
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
