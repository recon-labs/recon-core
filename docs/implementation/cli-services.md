# CLI Services

## Purpose

CLI services separate command-line concerns from framework behavior.

The CLI should call services. Services should be testable without shelling out.

## Services

Recommended services:

```text
InitService
ParseService
CompileService
RunService
CleanService later
DepsService later
```

## InitService

Responsibilities:

- create starter project,
- write `recon_project.yml`,
- write example profiles,
- create directories,
- avoid writing secrets,
- avoid overwriting existing files unless explicitly allowed.

## ParseService

Responsibilities:

- locate project root,
- load project config,
- parse resources,
- validate structure,
- write manifest,
- return parse summary and diagnostics.

`ParseService` should use the shared parsed-project loading helper. It remains
responsible for writing `target/manifest.json`, including parse diagnostics
when authored resources are structurally invalid.

## CompileService

Responsibilities:

- ensure parse resources are available,
- compile contracts,
- write compiled artifacts,
- return compile summary and diagnostics.

`CompileService` should use the same shared parsed-project loading helper as
`ParseService`. If parse diagnostics exist, compile should return a validation
error before writing compiled artifacts.

`CompileService` does not need to read `target/manifest.json` until freshness
and cache semantics are designed. The shared helper keeps authored files as the
source of truth while preventing parse/compile drift.

## RunService

Responsibilities:

- ensure parse/compile are available or run them,
- build execution plan,
- run checks,
- write run results,
- write evidence,
- return run summary and exit category.

## CLI options

Common options:

```text
--project-dir
--profiles-dir
--target-path
--select
--exclude
--vars
--debug
--quiet
```

Not all need to be implemented at first.

`--select` and `--exclude` should not be implemented until selector syntax,
named selectors, partial compile/run behavior, and run result metadata are
designed. Selector handling should be service-level behavior backed by parsed
manifest metadata, not ad hoc CLI file scanning.

## Output

Services return structured summaries.

CLI renderers turn summaries into terminal output.

This keeps terminal formatting out of business logic.

## Exit mapping

Service outcomes should map to exit codes.

Example:

```text
success -> 0
check failure -> 1
parse/compile validation error -> 2
runtime error -> 3
configuration error -> 4
```

## Design principle

CLI commands should be thin wrappers around testable application services.
