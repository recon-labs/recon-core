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

### Changed

- `recon init` now scaffolds `check_packs/` and `macros/` directories and
  writes matching `check-pack-paths` and `macro-paths` project config entries.

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
  compile into no checks, non-string nested `checks` mapping keys, and empty
  `sampling.default_policy` values.
- `recon compile` now rejects projects where no contracts are discovered,
  rejects exact compiled artifact output symlinks even with explicit overwrite,
  and includes contract file paths on compiler diagnostics where available.
- `recon init` now rejects project names that cannot be used in stable compiled
  artifact IDs.
- `recon parse` now rejects symlinked manifest output paths instead of following
  them when writing `target/manifest.json`.
- Typed operation models now reject payload fields that are not valid for the
  selected operation type.

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
