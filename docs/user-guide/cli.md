# CLI

## Overview

Recon is designed as a CLI-first framework.

Core commands:

```bash
recon init
recon parse
recon compile
recon run
```

Current implementation status:

- `recon init` is implemented.
- `recon parse` is implemented for structural parsing and manifest generation.
- `recon compile` is implemented for the current compiler scope.
- `recon run` is registered but not implemented yet.

## `recon init`

Creates a starter Recon project.

Expected command:

```bash
recon init ecommerce_recon
```

Expected output:

```text
recon_project.yml
.gitignore
connections/profiles.yml.example
contracts/
sample_policies/
tolerances/
schema_policies/
target/
reports/
state/
```

`recon init` should not overwrite an existing path unless an explicit overwrite option is added later.

`PROJECT_NAME` must be a single directory name. It must not be an absolute path, a nested path, or contain path traversal.

## `recon parse`

Validates authored project structure and writes a manifest.

```bash
recon parse
```

Expected output:

```text
target/manifest.json
```

Current `parse` behavior:

- loads `recon_project.yml`,
- discovers configured contract files,
- loads duplicate-key-safe YAML,
- parses single-contract files and simple `contracts:` multi-contract files,
- validates required contract fields,
- validates source and target endpoint shape,
- rejects unknown top-level contract fields,
- detects duplicate contract names,
- writes parse diagnostics into `target/manifest.json`.

If project config loads but contract parsing fails, `recon parse` still writes
`target/manifest.json` with diagnostics and exits with code `2`.

If one entry in a multi-contract file is invalid, valid entries from that file
are still included in the manifest while diagnostics report the invalid entry.

If project root discovery or project config loading fails, `recon parse` exits
with code `4` and does not write a manifest.

If the manifest cannot be written, `recon parse` exits with code `3` and prints
a runtime diagnostic.

`recon parse` does not compile checks, expand check packs, resolve sampling or
tolerances, validate adapter capabilities, execute queries, or produce
evidence.

## `recon compile`

Generates human-readable execution artifacts.

```bash
recon compile
```

Expected output:

```text
target/compiled_contracts/
target/compiled_checks/
```

`compile` should resolve defaults, refs, check packs, metrics, sampling,
tolerances, schema policies, CDC behavior, and adapter capabilities. SQL files
under `target/compiled_sql/` are produced when adapter SQL rendering is
available.

Current `compile` behavior:

- loads project configuration,
- discovers and parses contract files through the existing parser,
- expands `recon_core.basic_equivalence`,
- compiles explicit `sum` metrics into aggregate comparison checks,
- writes `target/compiled_contracts/<contract_name>.yml`,
- writes `target/compiled_checks/<contract_name>.yml`,
- sets `rendering.status: not_rendered` because SQL rendering is not available
  yet,
- validates duplicate contract names and stable ID-safe project, contract, and
  metric names before writing compiled artifacts,
- exits with code `2` when parse or compile diagnostics contain errors.

Current limitations:

- explicit authored checks outside supported check-pack and metric compilation
  fail with a clear diagnostic,
- adapter capability validation is not connected to real adapters yet,
- SQL rendering, execution, run results, and evidence reports are not
  implemented yet.

## `recon run`

Executes checks. This command is not implemented yet.

```bash
recon run
```

Expected output:

```text
target/run_results.json
target/failures/
reports/
```

`run` should parse and compile automatically when needed.

## Exit codes

Expected behavior:

- zero when all error-severity checks pass,
- non-zero when error-severity checks fail or execution cannot continue,
- configurable behavior for warnings later.

Recommended exit code categories:

```text
0  success
1  check failure with error severity
2  parse, validation, or compile error
3  execution or runtime error
4  configuration error
```

When a command fails, Recon should print concise diagnostic output:

```text
Error: <message>
Code: <diagnostic code>
Hint: <fix when available>
```

## Selectors

Future selector examples:

```bash
recon run --select tag:critical
recon run --select contract:customer_revenue
recon run --exclude tag:experimental
```

Selectors are not implemented yet, and the exact selector syntax is not locked.
Before adding `--select`, `--exclude`, or `selectors.yml`, Recon needs a
selector design covering syntax, manifest metadata, partial compile/run
behavior, and run result semantics.

Selectors should use parsed project metadata rather than scanning files
independently from the parser.

## Artifact directories

Generated artifacts should be written under:

```text
target/
reports/
state/
```

These should be gitignored.
