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
connections/profiles.yml.example
contracts/
sample_policies/
tolerances/
schema_policies/
```

The generated project should include safe placeholder examples and no secrets.

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
