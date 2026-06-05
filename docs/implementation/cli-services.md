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
- reject project names that cannot be used as stable compiled artifact ID parts,
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

If no contracts are discovered, `CompileService` should return a validation
error before writing compiled artifacts.

`CompileService` does not need to read `target/manifest.json` until freshness
and cache semantics are designed. The shared helper keeps authored files as the
source of truth while preventing parse/compile drift.

Plain compile can produce typed plans without loading connection profiles. If
adapter-aware SQL rendering is requested, `CompileService` should load the
selected profile and target only after compile validation succeeds, validate
adapter API compatibility and required capabilities, and write rendered SQL
under `target/compiled_sql/`. Compile validation diagnostics take precedence
over profile or adapter configuration diagnostics because rendering invalid
compiled checks would create misleading artifacts.

The implemented CLI entrypoint for adapter-aware compile is:

```bash
recon compile --render-sql
```

Milestone 6 rendering supports one adapter connection context per compile
invocation. Source and target connection names may differ, but their adapter
type and rendered connection config must match until explicit cross-connection
or attached-database rendering is designed.

Profile rendering must render only the selected target environment and the
named connections referenced by selected contracts. Secrets and fully rendered
credential payloads must not be written into compiled artifacts, compiled SQL
references, diagnostics, or terminal output. Unsupported `{{ ... }}` template
syntax in referenced connection payloads must fail instead of passing raw
template text to adapters. Profile-backed adapter diagnostics that reference
rendered connection config keys or values, including adapter-resolution,
adapter API compatibility, and render-phase adapter diagnostics, must be
suppressed before they reach service diagnostics, terminal output, or
compiled-check rendering metadata.

## RunService

Responsibilities:

- ensure parse/compile are available or run them,
- build execution plan,
- run checks,
- write run results,
- write evidence,
- return run summary and exit category.

Run-time profile loading follows the same selected-target and secret redaction
rules as adapter-aware compile. `RunService` must also preserve the same
unsupported-template and adapter diagnostic redaction behavior before execution.
`RunService` must revalidate adapter API compatibility and required
capabilities before execution.

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

`--profiles-dir` and future profile/target override behavior should not expose
secrets in diagnostics or generated artifacts. Missing environment variables in
referenced connection payloads should fail clearly; missing variables in
unselected targets or unreferenced connections should not fail
contract-specific invocations.

## Output

Services return structured summaries.

CLI renderers turn summaries into terminal output.

This keeps terminal formatting out of business logic.

Service diagnostics should carry the same structured fields that artifacts and
reports need. CLI renderers may choose concise formatting, but failed commands
must print each diagnostic code and message. Future run, evidence, debug, and
profile-validation commands should follow the same rule and preserve path,
resource context, and hint when available.

Services must return safe public diagnostic messages because CLI renderers,
artifacts, logs, and future reports may all consume the same diagnostics. Raw
YAML parser errors, adapter exceptions, database errors, rendered profile
values, source/target query text, relation names, row values, and credentials
should be summarized before they leave the service boundary.

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
