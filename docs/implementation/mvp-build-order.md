# MVP Build Order

## Purpose

This document defines a practical implementation order for the first working Recon Core.

The goal is to avoid building too many advanced features before the core loop works.

## Milestone 1: package skeleton and CLI

Build:

- Python package skeleton,
- `recon --version`,
- `recon init`,
- command service structure,
- basic diagnostics model.

Tests:

- CLI imports,
- version command,
- init creates expected files.

## Milestone 2: project loading

Build:

- project root discovery,
- `recon_project.yml` loader,
- path resolution,
- profile file discovery,
- generated path defaults.

Tests:

- project root from subdirectory,
- missing project config error,
- default paths,
- invalid config diagnostics.

## Milestone 3: parser and manifest

Build:

- YAML loader,
- contract parser,
- multi-contract file support if simple,
- resource discovery,
- duplicate contract detection,
- `target/manifest.json`.

Tests:

- valid contract parse,
- invalid YAML,
- missing required fields,
- duplicate names,
- manifest shape.

## Milestone 4: compiler foundation

Build:

- compiled contract model,
- compiled check model,
- typed check plan model,
- default resolution,
- metric compilation,
- check-pack expansion for `basic_equivalence`,
- adapter capability requirements,
- compiled artifact writers.

Tests:

- metric compiles to aggregate check,
- check pack expands,
- compiled checks lower into typed plan operations,
- empty check-pack expansion errors,
- compiled YAML artifacts match expected output.

## Milestone 5: validation rulebook

Build:

- row-level checks require keys,
- columns do not create checks,
- no silent all-column comparison,
- incompatible check/column type errors,
- sampling policy resolution,
- tolerance precedence.

Tests:

- each locked validation rule has passing and failing tests.

## Milestone 6: local/dev adapter

Build:

- base adapter interface,
- adapter API version declaration,
- local test adapter or DuckDB-style adapter,
- relation metadata,
- query execution,
- capability declarations,
- SQL rendering for typed plan operations,
- first internal adapter test-kit shape.

Tests:

- metadata fetch,
- row count query,
- typed operation rendering,
- adapter API version compatibility,
- adapter capability validation.

## Milestone 7: check engine

Build:

- check registry,
- row count check,
- duplicate key checks,
- missing/extra key checks,
- metric sum diff,
- check result model.

Tests:

- pass/fail cases,
- duplicate keys block row-level checks,
- aggregate metric result,
- check result serialization.

## Milestone 8: runner and results

Build:

- execution plan,
- run service,
- `target/run_results.json`,
- exit code mapping,
- terminal summary.

Tests:

- successful run,
- failing check run,
- runtime error,
- exit code mapping.

## Milestone 9: evidence

Build:

- failure detail writer,
- simple report writer,
- artifact references,
- sampling scope in evidence.

Tests:

- failure CSV written,
- report generated,
- row limit respected,
- artifact paths in run results.

## Milestone 10: examples and docs alignment

Build:

- runnable example project,
- README command verification,
- quickstart alignment,
- known limitations.

Tests:

- examples parse,
- examples compile,
- examples run with local/dev adapter.

## Deferral list

Do not block MVP on:

- full Hub,
- package installer,
- `recon deps`,
- `recon debug`,
- `recon list`,
- `recon clean`,
- documentation generation command,
- many adapters,
- hosted UI,
- persisted random sample,
- SCD2 CDC,
- advanced evidence redaction,
- orchestration integrations.

## Design principle

Build the smallest complete loop first, then widen capability.
