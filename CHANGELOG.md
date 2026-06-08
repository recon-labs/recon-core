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
  `env_var('NAME', 'default')` rendering for non-routing connection config
  fields, literal adapter `type` validation, and secret-safe diagnostics.
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
  compiled-check `rendering.sql_paths` references and `rendering.adapter_type`
  metadata when an adapter is known.

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
- `recon compile --render-sql` now requires source and target connections for a
  contract to resolve to the same adapter connection config; cross-connection
  rendering remains blocked until explicit execution-placement support exists.
- Connection profile `type` values must now be literal adapter types; adapter
  type selection is public routing metadata and no longer supports
  `env_var(...)` rendering.

### Fixed

- CI now runs DuckDB SQL renderer semantic tests in a required job that installs
  `.[dev,duckdb]`, preventing optional DuckDB execution coverage from being
  silently skipped.
- `CompiledSqlWriter` and `recon compile --render-sql` now validate and
  preflight the full rendered SQL output set before writing any SQL files,
  preventing partial `target/compiled_sql/` output when a later rendered step
  is invalid or a later check path has a case-insensitive collision.
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
- `recon compile --render-sql` now rejects invalid compiled YAML artifact
  output paths before writing compiled SQL, preventing orphaned SQL artifacts
  after runtime artifact write failures.
- `recon compile --render-sql` now discards generated SQL output if a compiled
  YAML artifact write fails after successful in-memory SQL rendering.
- `recon compile --render-sql` now also discards any partial compiled YAML
  artifacts written earlier in the same invocation when a later compiled YAML
  artifact write fails after in-memory SQL rendering.
- Connection profile loading now renders documented bare `env_var('NAME')` and
  `env_var('NAME', 'default')` expressions in non-routing connection config
  fields instead of passing them to adapters as literal strings.
- `recon compile --render-sql` now reports render diagnostics from unaffected
  contracts even when another referenced adapter connection has setup
  diagnostics.
- `recon compile --render-sql` now rejects adapter factories whose returned
  `adapter_type` metadata does not match the literal profile connection
  `type`, preventing profile type aliases from selecting the wrong SQL
  renderer.
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
- Adapter-aware SQL rendering now suppresses integer-equivalent formatted
  variants of short numeric profile values in profile-backed adapter
  diagnostics, including quoted or env-var-rendered numeric strings such as
  `"12.0"` when adapters emit equivalent values such as `12`, `+12`, or
  `1.2e1`.
- Adapter-aware SQL rendering now writes blocked compiled-check metadata for
  adapter setup failures and de-duplicates repeated source/target adapter setup
  diagnostics in the service result.
- Adapter-aware SQL rendering now treats adapter factory diagnostics as setup
  failures even when a factory also returns an adapter, preserving the real
  diagnostic in blocked compiled-check artifacts and keeping distinct
  source/target connection setup diagnostics visible in service and artifact
  output.
- Adapter-aware SQL rendering now suppresses raw adapter renderer exception
  messages in diagnostics and compiled-check artifacts so renderer failures do
  not leak secrets or fully rendered credential payloads.
- Adapter-aware SQL rendering now suppresses adapter-resolution diagnostic text
  that references rendered profile connection values.
- Adapter-aware SQL rendering now suppresses adapter-resolution diagnostic text
  that references rendered profile connection keys or values with different
  casing, preventing case-changed secrets or config keys from leaking.
- Adapter-aware SQL rendering now suppresses unsafe adapter-resolution
  `resource_type` values instead of preserving resource metadata that contains
  rendered profile connection keys or values.
- Adapter-aware SQL rendering now applies rendered-profile diagnostic redaction
  to adapter API compatibility diagnostics, not only adapter factory
  diagnostics.
- Adapter-aware SQL rendering now applies rendered-profile redaction to
  render-phase adapter diagnostics and `rendering.adapter_type` metadata, and
  treats non-string rendered profile values as redaction candidates.
- Adapter-aware SQL rendering now suppresses unsafe profile-backed adapter
  diagnostic `line` and `column` values when they match rendered scalar profile
  values, including short numeric rendered scalars such as port values.
- Adapter-aware SQL rendering now replaces unsafe adapter-provided diagnostic
  codes when they reference rendered profile keys or values, including
  separatorless secret-like config-key codes such as `RCPASSWORDLEAK`, while
  preserving safe adapter codes such as `RC_ADAPTER_CAPABILITY_UNSUPPORTED`,
  preventing CLI and artifact output from leaking sensitive profile data through
  `Code:` fields.
- Adapter-aware SQL rendering now converts adapter factory and capability
  declaration exceptions into structured diagnostics with raw adapter error
  text suppressed.
- Adapter-aware SQL rendering now fails with `RC_ADAPTER_RESOLUTION_FAILED`
  when an adapter factory returns neither an adapter nor a diagnostic.
- Adapter-aware SQL rendering now reports malformed adapter factory resolution
  results, missing or invalid adapter API version declarations, and malformed
  capability support states as structured diagnostics instead of uncaught
  exceptions.
- Adapter-aware SQL rendering now reports adapter factory resolution results
  with malformed diagnostic payloads, including invalid `Diagnostic` field
  values, as structured `RC_ADAPTER_RESOLUTION_FAILED` diagnostics instead of
  crashing during diagnostic redaction or artifact serialization.
- YAML parse diagnostics now suppress raw parser snippets in public diagnostic
  messages so malformed authored files do not leak source/target query text or
  private literals through CLI output, manifest diagnostics, or logs.
- Adapter-aware SQL rendering now reports invalid or raising adapter
  `adapter_type` metadata as structured diagnostics instead of crashing or
  leaking raw adapter exception text.
- Adapter-aware SQL rendering now treats empty renderer output as a rendering
  failure instead of marking checks as `rendered` with empty SQL paths.
- Adapter-aware SQL rendering now treats malformed non-empty renderer output as
  a rendering failure instead of crashing during compiled SQL artifact writing.
- Adapter-aware SQL rendering now treats unsafe or duplicate rendered SQL step
  names as rendering failures instead of runtime artifact write failures.
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
- DuckDB aggregate and grouped aggregate comparison SQL now runs type-check
  preflight statements before native `sum(column)` queries so unsupported metric
  inputs fail clearly without forcing valid exact numerics through lossy casts.
- DuckDB aggregate and grouped aggregate comparison SQL now rejects boolean
  `sum` inputs so DuckDB true-value counting cannot be mistaken for numeric
  aggregate comparison.
- DuckDB aggregate and grouped aggregate comparison SQL now rejects `UHUGEINT`
  metric inputs because DuckDB currently returns approximate `DOUBLE` values
  for `sum(UHUGEINT)`, which can hide differences between adjacent large
  integers.
- `recon compile --render-sql` now reports compile validation errors before
  loading adapter profiles, so profile configuration errors cannot hide invalid
  contracts.
- `recon compile --render-sql` now marks all checks as `blocked` or `failed`
  when a rendering diagnostic prevents SQL artifact output, avoiding
  misleading `not_rendered` metadata for adapter-aware compile results.
- `recon compile --render-sql` now marks otherwise renderable checks as
  `blocked` when compile validation diagnostics prevent adapter rendering from
  starting, avoiding `not_rendered` metadata when rendering was requested.
- `recon compile --render-sql` now adds a structured suppression diagnostic to
  otherwise renderable checks whose SQL paths are intentionally omitted because
  another check blocked SQL output for the invocation.
- `recon compile --render-sql` now de-duplicates identical contract-level query
  endpoint diagnostics in the service result while preserving per-check artifact
  diagnostics.
- Invalid `connections/profiles.yml` YAML diagnostics no longer include the
  raw YAML parser message, preventing malformed secret-bearing lines from
  appearing in CLI diagnostics.
- Referenced `connections/profiles.yml` connection values and env-var defaults
  that contain unsupported Jinja template fragments or embedded `env_var(...)`
  calls now fail profile validation instead of passing raw template text to
  adapters.
- CLI failures now print each diagnostic message as well as the diagnostic
  code, so `recon compile --render-sql` profile and adapter errors expose the
  actionable failure detail in terminal output.

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
