# Changelog

All notable changes to Recon Core should be documented in this file.

This project follows semantic versioning once public package releases begin.

## Unreleased

### Added

- Product foundation docs.
- Framework design docs.
- Planning docs.
- User and contributor documentation.
- Draft compiler typed plan model foundation, including stable ID helpers and
  public operation/capability names for `null_key` and `compare_aggregates`.
- Built-in `recon_core.basic_equivalence` expansion helpers for row count, key
  coverage, null-key, and duplicate-key checks.
- Explicit metric compilation helpers for ungrouped `sum_diff` and grouped
  aggregate comparison typed plans.
- `recon compile` artifact generation for compiled contract and compiled checks
  YAML under `target/`.
- `recon parse` now indexes local check-pack, sampling-policy,
  tolerance-policy, schema-policy, and macro source files in
  `target/manifest.json.files` without parsing, validating references to,
  rendering, or executing those resources.
- `recon compile` now validates authored column declarations and current metric
  column references against declared column surfaces.
- `recon compile` now validates current sampling and accepted
  tolerance/null/normalization policy shapes.
- `recon compile` now rejects duplicate check-pack invocations and validates
  declared non-empty `cdc.keys` shape.
- ADR and compatibility documentation for the Milestone 6 adapter/profile,
  capability, DuckDB local adapter, compiled SQL, query boundary, and execution
  placement design.
- `recon compile --render-sql` for adapter-aware SQL rendering of current typed
  check plans.
- Connection profile loading from `connections/profiles.yml` for
  adapter-aware compile, including selected profile/target resolution,
  referenced-connection filtering, `env_var('NAME')` /
  `env_var('NAME', 'default')` rendering, and secret-safe diagnostics.
- Adapter API foundation with `ADAPTER_API_VERSION = "1"`, adapter registry,
  support-state capability validation, base adapter models, and SQL renderer
  interfaces.
- In-core DuckDB local development adapter foundation behind the optional
  `recon-core[duckdb]` extra.
- DuckDB SQL rendering for the currently emitted typed operations:
  `row_count`, `compare_counts`, `key_diff`, `null_key`, `duplicate_key`,
  `aggregate`, `grouped_aggregate`, `compare_aggregates`, and
  `compare_grouped_aggregates`.
- Compiled SQL artifact writing under
  `target/compiled_sql/<contract_name>/<check_id>/<side_or_step>.sql`, with
  compiled-check `rendering.sql_paths` references.

### Changed

- `recon init` now scaffolds `check_packs/` and `macros/` directories and
  writes matching `check-pack-paths` and `macro-paths` project config entries.
- `recon init` now writes the ADR 0020 selected profile/target shape with
  named `legacy` and `warehouse` connections in
  `connections/profiles.yml.example` for the planned DuckDB local development
  adapter.
- Compiled-check rendering status values are now locked to `not_rendered`,
  `rendered`, `blocked`, and `failed`; earlier draft `deferred` and
  `unsupported` rendering statuses are no longer emitted.
- Plain `recon compile` remains non-adapter-aware, keeps
  `rendering.status: not_rendered`, and removes stale `target/compiled_sql/`
  output.

### Fixed

- `recon compile` now reports structured validation diagnostics for invalid
  stable ID parts, duplicate contract names, and case-insensitive compiled
  artifact filename collisions instead of crashing or silently overwriting
  compiled artifacts.
- Exported compiler helpers now report stable-ID diagnostics before ID
  construction, and standalone compiled artifact writers now require explicit
  overwrite behavior while still rejecting case-insensitive filename collisions.
- Compiled artifact writer overwrite checks now scan every case-insensitive
  filename match before allowing explicit overwrite.
- `recon compile` now removes stale compiled contract and compiled checks YAML
  artifacts once `target-path` is known, including before parse or fatal compile
  validation exits.
- `recon compile` now rejects symlinked compiled artifact directories,
  unsupported check-pack invocation config, unknown metric fields, invalid
  sampling config, and path-like standalone compiled artifact names.
- `recon compile` now rejects symlinked `target-path` ancestry, contracts that
  compile into no checks, non-string nested `checks` mapping keys, and missing,
  null, or empty `sampling.default_policy` values when `sampling` is declared.
- `recon compile` now rejects projects where no contracts are discovered,
  rejects exact compiled artifact output symlinks even with explicit overwrite,
  and includes contract file paths on compiler diagnostics where available.
- `recon init` now rejects project names that cannot be used in stable compiled
  artifact IDs.
- `recon parse` now rejects symlinked manifest output paths instead of following
  them when writing `target/manifest.json`.
- `recon parse` now rejects source files reachable through multiple resource
  kinds instead of silently classifying them as the first matching kind.
- Resource discovery now honors catalog entries that allow missing authored
  paths through `explicit_missing_is_error: false`.
- Typed operation models now reject payload fields that are not valid for the
  selected operation type.
- Compiled contract artifacts now preserve accepted contract-level `nulls`
  policy under `policies.nulls`.
- Adapter-aware SQL rendering fails clearly for unknown adapter types, missing
  DuckDB optional dependencies, unsupported adapter API versions, unsupported
  required capabilities, query endpoints, invalid relation names, and renderer
  failures without writing misleading SQL artifacts.
- DuckDB grouped aggregate comparison SQL now uses null-safe group key joins so
  source and target `NULL` groups compare as the same group.
- DuckDB key-diff SQL now compares distinct non-null key sets, keeping null-key
  and duplicate-key checks separate from missing/extra key coverage.
- DuckDB rendered key and grouped aggregate comparison SQL now performs
  explicit key/group type checks that raise clear Recon errors on physical
  type mismatch instead of returning misleading missing/extra keys or
  surfacing raw DuckDB `coalesce` binder errors.
- DuckDB grouped aggregate comparison SQL now projects `source_<key>` and
  `target_<key>` group keys in final comparison rows instead of coalescing
  source and target group keys, avoiding unsafe cross-type key coalescing and
  preserving unmatched-side visibility.
- DuckDB aggregate and grouped aggregate comparison SQL now checks aggregate
  input column and result types before subtracting values so DuckDB implicit
  casts cannot make cross-type metric comparisons look safely comparable.
- `recon compile --render-sql` now reports compile validation errors before
  loading adapter profiles, so profile configuration errors cannot hide invalid
  contracts.
- `recon compile --render-sql` now marks all checks as `blocked` or `failed`
  when a rendering diagnostic prevents SQL artifact output, avoiding
  misleading `not_rendered` metadata for adapter-aware compile results.
- Invalid `connections/profiles.yml` YAML diagnostics no longer include the
  raw YAML parser message, preventing malformed secret-bearing lines from
  appearing in CLI diagnostics.

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
