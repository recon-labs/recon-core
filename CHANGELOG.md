# Changelog

All notable changes to Recon Core should be documented in this file.

This project follows semantic versioning once public package releases begin.

## Unreleased

### Added

- Foundational product, framework, planning, user, contributor, ADR, and
  compatibility documentation for the pre-alpha Reconciliation as Code
  framework.
- Parser and project-resource discovery foundation, including manifest indexing
  for local check-pack, sampling-policy, tolerance-policy, schema-policy, and
  macro files without parsing, rendering, or executing those resources.
- Compiler foundation for typed check plans, stable IDs, public operation and
  capability names, built-in `recon_core.basic_equivalence` expansion,
  explicit `sum_diff` metric compilation, compiled contract/check YAML
  artifacts under `target/`, and current compile-time validation for columns,
  policies, duplicate check-pack invocations, and `cdc.keys`.
- Adapter-aware compile and SQL rendering foundation, including
  `connections/profiles.yml` profile loading, selected profile/target
  resolution, non-routing `env_var(...)` rendering, literal adapter `type`
  validation, `ADAPTER_API_VERSION = "1"`, adapter registry and capability
  models, SQL renderer interfaces, the optional in-core DuckDB adapter, DuckDB
  rendering for current typed operations, and compiled SQL artifact output.
- First `recon run` check-engine boundary for already compiled checks, including
  matching compiled-contract loading, runtime profile and adapter setup for
  relation-backed same-context DuckDB `row_count_diff` checks and bounded
  local/dev grain-key safety checks, bounded key-safety scan classification that
  requires local DuckDB base-table metadata rather than views or externally backed
  relations, in-memory run/contract/check results, runtime diagnostics for
  missing, invalid, empty, unsupported, blocked, not-executable, profile,
  adapter, lifecycle, scan-budget, and execution inputs, and no run-result,
  evidence, report, failure-detail, state, or sink artifact writes.

### Changed

- `recon init` now scaffolds `check_packs/` and `macros/`, writes matching
  project config entries, and emits the ADR 0020 profile/target example shape
  for the planned DuckDB local development adapter.
- Compiled-check rendering status values are locked to `not_rendered`,
  `rendered`, `blocked`, and `failed`; plain `recon compile` remains
  non-adapter-aware, keeps `rendering.status: not_rendered`, and removes stale
  `target/compiled_sql/` output.
- `recon compile --render-sql` requires source and target connections for a
  contract to resolve to the same adapter connection config; cross-connection
  rendering remains blocked until explicit execution-placement support exists.
- Connection profile `type` values must be literal adapter routing metadata and
  no longer support `env_var(...)` rendering.
- `recon run` now fails through the compiled-check/check-engine boundary instead
  of returning the placeholder `RC_RUNTIME_NOT_IMPLEMENTED` diagnostic.
- Compatibility docs now clarify future adapter ecosystem gates for
  DSN-component redaction, explicit adapter/renderer binding, rendered SQL
  step capability enforcement, and adapter/test-kit compatibility claims.
- Regression-capture decision validation now has an explicit branch-wide mode
  with `scripts/check_regression_capture_decisions.py --base-ref origin/main`;
  the no-argument advisory remains scoped to local WIP and untracked files, and
  an unresolved requested base ref now fails instead of silently skipping
  committed branch changes.

### Fixed

- CI now runs DuckDB SQL renderer semantic tests in a required job that installs
  `.[dev,duckdb]`, preventing optional DuckDB execution coverage from being
  silently skipped.
- `recon run` now rejects unsafe or malformed compiled-check artifacts, enforces
  explanatory messages and diagnostics on non-executed check results, and
  preserves prerequisite blocking through the check-engine boundary, including
  symlinked artifact paths, non-string artifact mapping keys, empty typed
  operation plans, fields not valid for known or reserved operation types, and
  non-executable prerequisites, while preserving valid artifacts when sibling
  contracts compile to no checks and preserving key-safety typed-plan shape
  blockers in mixed runtime runs.
- `recon compile`, compiled artifact writers, `CompiledSqlWriter`, and
  `recon compile --render-sql` now preflight artifact publication, reject unsafe
  output paths, symlinks, non-files, case-insensitive collisions, path-like
  artifact names, empty or malformed rendered SQL output, invalid or duplicate
  rendered step names, and clean up stale or partial artifacts instead of
  leaving misleading generated output.
- `recon compile` now reports structured diagnostics for invalid stable IDs,
  duplicate contract names, case-insensitive artifact collisions, unsupported
  check-pack config, unknown metric fields, invalid sampling config, missing or
  empty `sampling.default_policy`, symlinked `target-path` ancestry, projects
  with no contracts, contracts that compile into no checks, invalid nested
  `checks` mapping keys, and contract file paths where available.
- `recon init`, `recon parse`, resource discovery, typed operation models, and
  compiled contract artifacts now reject invalid stable project names, unsafe
  manifest output paths, duplicate resource-kind ownership, invalid operation
  payload fields, and preserve accepted contract-level `nulls` policy under
  `policies.nulls`.
- YAML, profile, parser, CLI, adapter, and render diagnostics now prefer
  structured, actionable, redacted messages over raw parser snippets, raw
  adapter exceptions, rendered profile values, DSN fragments, case variants,
  unsafe resource metadata, diagnostic codes, line/column values, and numeric
  equivalents of rendered scalar secrets.
- Adapter-aware SQL rendering now fails clearly for adapter/profile/setup
  problems, including unknown adapter types, missing DuckDB optional
  dependencies, invalid or raising `adapter_type` metadata, adapter API
  incompatibility, unsupported required capabilities, malformed adapter factory
  results or diagnostics, factory/capability exceptions, query endpoints,
  invalid relation names, unsupported template fragments, and empty factories.
- DuckDB duplicate-key SQL rendering now evaluates duplicate grain-key tuples
  only after excluding rows with null identity components, leaving null-key
  failures to the null-key safety checks.
- `recon run` now resolves relative DuckDB profile database paths against the
  project root for both bounded key-safety scan classification and adapter
  execution, preventing same-named process-CWD databases from producing
  misleading key-safety results, preserves malformed relation endpoint
  diagnostics ahead of scan-budget and profile-loading blockers, and surfaces
  DuckDB adapter dependency or connection diagnostics when metadata-open
  failures prevent the bounded local scan guard from proving local base-table
  scope, while matching DuckDB base-table metadata using DuckDB identifier
  casing semantics, failing closed when retained DuckDB sidecars are present,
  and accepting valid project-local DuckDB database filenames without requiring
  a `.duckdb` suffix.
- `render_check_sql` and `recon compile --render-sql` now enforce renderer-step
  `RenderedSql.required_capabilities`, validate explicit renderer
  `adapter_type` metadata before rendering, preserve diagnostics from
  unaffected contracts, de-duplicate repeated setup/query diagnostics, and mark
  checks as `blocked` or `failed` when rendering or compile validation prevents
  SQL artifact output.
- DuckDB rendered SQL now uses safer comparison semantics for key and aggregate
  checks, including null-safe grouped joins, distinct non-null key sets,
  side-preserving grouped output, explicit key/group and aggregate type checks,
  clear failures for unsupported metric inputs, and rejection of boolean and
  `UHUGEINT` aggregate inputs that could make comparisons misleading.
- CLI failures now print each diagnostic message as well as the diagnostic code,
  so profile, adapter, compile, and render errors expose actionable failure
  details in terminal output without leaking sensitive values.

## Release format

Use this structure for future releases:

```md
## 0.1.0

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security
```
