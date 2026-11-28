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

Current adapter-aware rendering supports one adapter connection context per
compile invocation. Source and target connection names may differ, but their
adapter type and rendered connection config must match until explicit
cross-connection or attached-database rendering is designed.

Profile rendering must render only the selected target environment and the
named connections referenced by selected contracts. Secrets and fully rendered
credential payloads must not be written into compiled artifacts, compiled SQL
references, diagnostics, or terminal output. Unsupported template syntax,
including `{{ ... }}`, `{% ... %}`, and `{# ... #}`, in referenced connection
payloads must fail instead of passing raw template text to adapters.
Profile-backed adapter diagnostics that reference rendered connection config
keys or values, including adapter-resolution,
adapter API compatibility, and render-phase adapter diagnostics, must be
suppressed before they reach service diagnostics, terminal output, or
compiled-check rendering metadata.

## RunService

Current run-service responsibilities:

- allocate invocation identity and start timing before locating the project root,
- load already compiled check artifacts from the generated target path,
- load matching compiled-contract artifacts for runtime metadata and refuse
  compiled-check inputs belonging to a different project identity,
- record a private immutable plan of the validated loaded contracts/checks,
  their presentation order and prerequisite IDs, without reloading artifacts
  or duplicating the engine's prerequisite evaluation,
- prepare runtime profile and adapter dependencies only for executable
  relation-backed row-count, grain-key and SUM candidates,
- invoke the check engine over compiled checks only,
- use one privately owned read-only transaction per eligible check after
  structural, prerequisite, placement, capability and preliminary scope checks,
- resolve exact local base tables and verify the binding before native reads,
- roll back and close each owned session before finalizing its result,
- finalize invocation timing after evaluation and native cleanup, including
  structured early failures, using monotonic elapsed time,
- map command-level outcomes and diagnostics to `ServiceResult`,
- return a concise command message and exit category.

The run service must not parse authored YAML, invoke `ParseService`, invoke
`CompileService`, write `target/run_results.json`, write evidence, write
reports, write failure details, write state, or write result/evidence sinks.
Adapter-backed execution is limited to same-context relation-backed DuckDB
row-count checks and bounded local/dev grain-key safety and explicit sum
aggregate checks, with in-memory results. For scan-heavy checks, the service
classifies placement and scan safety before adapter setup where possible,
validates capabilities and prepares approved runtime dependencies. Core owns
aggregate comparison semantics; the service does not interpret raw numeric
results. Later-phase checks remain
structured `not_executable` results.

The [local execution policy](../decisions/adr-0026-local-execution-policy-and-scan-admission.md)
applies verified project-local base-table scope to all supported project-run
checks. No default database-footprint cap applies; an authored optional cap
applies to all nine supported check families. Native resource settings use
fresh observations, explicit policy precedence and safe advisories. Native
open/read/cleanup errors are check-local; uncertain cleanup blocks later
native work for the affected database, not unrelated databases. Owned scratch
is removed only after confirmed native closure; abrupt termination can leave
residue. Managed settings do not guarantee total process memory or physical
storage limits. Optional invocation-wide cancellation and deadlines, sealed
outcomes and private native attempt accounting are implemented; additional
budget mechanisms are not implied. Durable publication remains gated.

Later runner and evidence phases may expand `RunService` responsibilities to:

- evaluate artifact freshness under a separately approved policy, without
  silently recompiling current authored inputs,
- build execution plans,
- run additional checks through supported adapter execution paths,
- write run results,
- write evidence,
- return final run summaries and exit categories.

Run-time profile loading follows the same selected-target, referenced-connection,
literal adapter type, unsupported-template, and secret-redaction rules as
adapter-aware compile. `RunService` must revalidate adapter metadata, adapter
API compatibility, and required capabilities before opening a connection.
Adapter lifecycle, query, and close diagnostics must be sanitized and must not
expose rendered profile values, relation names, query text, rendered SQL,
database errors, credentials, or raw adapter exception text.

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
partial compile/run behavior, generated artifact cleanup, and run result
metadata are designed. The first selector implementation should stay narrow:
explicit contract and path scope for compile, SQL rendering, and run. Named
selectors, check-level selection, tag/domain/package selectors, state/result
selectors, and richer composition should wait for the later selector expansion.
Selector handling should be service-level behavior backed by parsed manifest
metadata, not ad hoc CLI file scanning.

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

### Optional run cancellation

`recon run --timeout-seconds 60` requests one cooperative invocation deadline,
including preparation, checks and cleanup. Omission adds no deadline. Embedded
callers may use `RunService.execute(timeout_seconds=60, cancel_event=event)`
with a caller-owned `threading.Event`; Recon never mutates that event. CLI
SIGINT, when delivered, requests cancellation on the existing invocation and
restores the previous signal handler. The handler records a simple latch;
invocation checkpoints and the final seal can observe it directly, even before
the coordinator wakes to notify Event waiters. A request after sealing does not
rewrite the finalized outcome. Embedded calls stay on the caller's thread
without installing a signal handler. Invalid CLI timeout values are
usage errors; invalid embedded controls are configuration errors. A stopped
run returns the existing runtime-error category (exit 3), preserving an
independent earlier configuration or validation failure. This is cooperative
control, not guaranteed wall-clock termination: native calls and confirmed
cleanup may outlast the deadline. No query is automatically retried, and no
new output files are created.

### Planned run-result finalization

[ADR 0028](../decisions/adr-0028-run-result-publication-and-cli-finalization.md)
and [publication prework](../planning/milestone-8-3-prework.md) define the required
local result snapshot and terminal summary. RunService owns one execution
and final publication result; the artifact writer owns safe atomic I/O.
The CLI only renders the safe service outcome and existing exit mapping.
This behavior is planned, not implemented.
