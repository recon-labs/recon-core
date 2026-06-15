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
check_packs/
macros/
sample_policies/
tolerances/
schema_policies/
target/
reports/
state/
```

`check_packs/`, `sample_policies/`, `tolerances/`, `schema_policies/`, and
`macros/` are scaffolded as local resource directories. Current parse behavior
indexes those non-contract source files in `target/manifest.json`; compile
still parses and compiles contract resources only.

The generated project should include safe placeholder examples and no secrets.
It should not overwrite an existing path unless explicit overwrite behavior is added later.
The project name should be validated as a single directory name before paths are
created. It must also be usable as a stable compiled artifact ID part. Absolute
paths, nested paths, path separators, path traversal, names that start with a
number, and names containing punctuation or spaces should return a configuration
error.

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
target/compiled_sql/  # when --render-sql succeeds
```

It should return non-zero on compile-time validation errors.

Current implementation reads authored files through the parser pipeline,
expands supported check packs and explicit metrics, and writes compiled
contract and compiled checks artifacts. With `--render-sql`, it loads the
selected profile target, validates adapter API/capabilities, and writes
compiled SQL artifacts for current DuckDB relation-backed typed plans.

## `recon run`

Runs compiled checks.

The run command uses already compiled checks and matching compiled-contract
metadata. Current execution is limited to relation-backed same-context DuckDB
`row_count_diff` and grain-key safety checks and does not write generated run or
evidence artifacts.
Later runner/result and evidence phases may parse or compile automatically when
artifact freshness semantics are locked.

Later runner/result and evidence phase outputs:

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

Successful service results should print a concise success message to standard output when there is one. Failed service results should print concise diagnostic output to standard error:

```text
Error: <message>
Code: <diagnostic code>
Message: <diagnostic message>
Path: <path when available>
Hint: <hint when available>
```

CLI rendering should use structured service results and diagnostics. Command handlers should not assemble ad hoc framework errors.

Because failed commands print diagnostic messages to standard error, CLI output
is a public diagnostic surface. Command handlers and services must not pass raw
YAML parser errors, adapter exceptions, database errors, source/target query
text, row values, rendered profile values, or credentials into terminal
messages. Unsafe details should be summarized before the diagnostic reaches the
CLI renderer.

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

Future illustrative examples by gated stage:

Minimal contract/path selector examples:

```bash
recon compile --select "contract:customer_revenue"
recon compile --render-sql --select "path:contracts/revenue/customer_revenue.yml"
recon run --select "contract:customer_revenue"
```

Later gated selector examples:

```bash
recon run --select "selector:critical_reconciliations"
recon run --select "check:customer_revenue.row_count"
recon run --exclude "contract:experimental_*"
```

Selector logic should not require scanning files independently from the parser.

Selector syntax and semantics are not locked yet. Implementing `--select`,
`--exclude`, named selectors, or partial compile/run behavior requires a future
design decision covering selection precedence, empty matches, artifact
freshness, and run result metadata.

Selector support should be staged. The first implementation should focus on
explicit contract/path scope for compile, SQL rendering, and run. Named
selectors, check-level selectors, tag/domain/package selectors, state/result
selectors, and richer composition should build on that later.
Contract-only exclusion, including simple contract-name patterns such as
`contract:experimental_*`, can be gated into the first selector implementation
only if pattern syntax and select/exclude precedence are locked first.

Future `path:...` selectors should resolve against project-relative manifest
paths produced by resource discovery. Exact file-path matching should be
defined before directory-prefix matching. If a selected file contains multiple
contracts, the selector should include all contracts in that file unless a later
composition rule narrows it explicitly.

## Design principle

The CLI should feel simple while delegating complex framework behavior to testable services.
