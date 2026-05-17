# CLI Architecture

## Command model

Recon should be CLI-first.

Core commands:

```bash
recon init
recon parse
recon compile
recon run
```

Supporting commands can be added later:

```bash
recon debug
recon list
recon clean
recon deps
```

Supporting commands should be added only when their backing subsystem exists. They should not be registered as successful no-op commands.

Recommended command timing:

```text
0.1  recon init
0.1  recon parse
0.1  recon compile
0.1  recon run
0.2  recon list, after manifest metadata and selectors exist
0.2  recon clean, after generated artifact paths are resolved safely
0.3  recon debug, after profiles, adapter registry, and connection checks exist
0.4  recon deps, after package resource loading and packages.yml exist
0.4  documentation generation command, after project docs metadata is useful
```

Future convenience commands such as `recon build` or `recon retry` should be considered only after the parse, compile, run, artifact, and state models are stable.

## CLI responsibilities

The CLI should:

- parse command options,
- locate the project root,
- call application services,
- print concise terminal output,
- return appropriate exit codes.

The CLI should not:

- parse contracts directly,
- expand check packs directly,
- execute SQL directly,
- contain validation rules.

## Application service boundary

Each command should call a service.

```text
ParseCommand -> ParseService
CompileCommand -> CompileService
RunCommand -> RunService
InitCommand -> InitService
```

This makes behavior testable without invoking subprocesses.

## `recon init`

Creates a starter project.

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

The generated project should include safe placeholder examples and no secrets.
It should not overwrite an existing path unless explicit overwrite behavior is added later.

## `recon parse`

Reads project files and writes:

```text
target/manifest.json
```

It should validate basic structure and return non-zero on parse errors.

## `recon compile`

Reads authored files and/or the manifest, resolves behavior, and writes:

```text
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
```

It should return non-zero on compile-time validation errors.

## `recon run`

Runs compiled checks.

It may parse and compile automatically when generated artifacts are missing or stale.

Expected outputs:

```text
target/run_results.json
target/failures/
reports/
```

## Exit codes

Recommended exit code behavior:

```text
0  success
1  check failure with error severity
2  parse/validation/compile error
3  execution/runtime error
4  configuration error
```

Exact values can be adjusted, but categories should remain clear.

## Terminal output

Terminal output should be concise.

Example:

```text
Parsed 4 contracts
Compiled 12 checks
Running customer_revenue
PASS row_count_diff
PASS missing_keys
FAIL revenue_by_month
Run failed: 1 error-severity check failed
```

Detailed diagnostics belong in artifacts and reports.

## Selectors

Selectors should be handled through parsed metadata.

Future examples:

```bash
recon run --select tag:cdc
recon run --select contract:customer_revenue
recon run --exclude tag:experimental
```

Selector logic should not require scanning files independently from the parser.

## Design principle

The CLI should feel simple while delegating complex framework behavior to testable services.
