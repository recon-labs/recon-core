# Parse, Compile, and Run Architecture

## Flow

```text
recon parse
  -> target/manifest.json

recon compile
  -> target/compiled_contracts/
  -> target/compiled_checks/
  -> target/compiled_sql/ when --render-sql succeeds

recon run, first check-engine boundary
  -> command diagnostics and in-memory result objects only

future runner/result and evidence phases
  -> target/run_results.json
  -> target/failures/
  -> reports/
```

## Parse service

The parse service should:

- load project config,
- discover resource files,
- parse YAML,
- validate structural schema,
- build parsed resource graph,
- detect duplicate names,
- validate basic refs where possible,
- write manifest.

Parse should not expand check packs or decide every executable check.

## Compile service

The compile service should:

- read parsed resources or manifest,
- resolve defaults,
- resolve refs,
- expand check packs,
- compile metrics into checks,
- resolve sampling for every check,
- resolve tolerance and null rules,
- resolve schema policies,
- resolve CDC policies,
- validate compatibility,
- produce typed check plans,
- render adapter SQL where possible,
- produce compiled artifacts.

Compile should make hidden behavior visible.

Check-pack invocation config is governed by ADR 0018. Until typed invocation
models, schema validation, and artifact visibility exist, compile should reject
`config`, `on_empty`, and unknown invocation fields rather than applying them
partially.

Column and value-comparison behavior is governed by ADR 0019. Until typed
column models, metadata validation, and artifact visibility exist, compile
should not expand raw wildcard selectors or execute value checks without
concrete resolved columns.

Typed check plans are the core execution intent. Rendered SQL is an
adapter-specific artifact derived from those plans.

Current compile implementation writes compiled contract and compiled checks
artifacts with `rendering.status: not_rendered` for plain compile. With
`--render-sql`, it writes adapter-rendered SQL for current DuckDB
relation-backed typed plans and updates rendering metadata to `rendered`,
`blocked`, or `failed`. When an adapter is known, that metadata includes
`rendering.adapter_type`. Current adapter-aware rendering requires source and
target connections to resolve to the same adapter connection config, and
resolved adapter `adapter_type` metadata must match the literal profile `type`
before renderer selection; distinct configs are blocked rather than implicitly
bridged. If any check produces a rendering diagnostic, compile writes no SQL
files for that adapter-aware invocation and marks checks `blocked` or `failed`
rather than leaving them `not_rendered`.

Before the validation rulebook milestone expands parse and compile validation,
parse and compile should share one internal parsed-project loading pipeline.
That pipeline should read authored project files, discover resources, load YAML,
parse contracts, and return parsed in-memory models plus diagnostics. It should
not require `recon compile` to read `target/manifest.json`, and it should not
introduce manifest freshness or caching rules.

This preserves authored YAML and `recon_project.yml` as the source of truth
while avoiding drift between `recon parse` and `recon compile`.

Current implementation status: the shared parsed-project loading pipeline
discovers local non-contract source files for manifest indexing, but it parses
semantic resource models for contracts only. Non-contract resource loading and
precedence are locked by ADR 0017, but reference validation must wait until the
relevant resource kinds are parsed through that shared model.

## Run service

The first run service boundary should:

- load already compiled check artifacts,
- route compiled checks through the check engine,
- return command-level `ServiceResult` diagnostics and exit category,
- keep reconciliation results separate from command plumbing,
- avoid parsing authored YAML, compiling contracts, loading profiles,
  initializing adapters, rendering SQL, executing queries, or writing generated
  run/evidence outputs.

Later runner phases may expand the run service to initialize adapters, run typed
check plans through supported execution paths, collect results, write
`target/run_results.json`, write evidence, and return final run summaries.

## Freshness of artifacts

`recon run` may parse and compile automatically after artifact freshness
semantics are designed.

The first check-engine boundary should not parse or compile automatically. It
consumes compiled checks only and fails clearly when compiled-check artifacts are
missing, invalid, or empty.

A later implementation can use file hashes or timestamps to skip unchanged work.

## Manifest

`target/manifest.json` is machine-oriented.

It supports:

- compile,
- run,
- selectors,
- docs,
- CI tooling,
- future integrations.

Selector execution is a future design. The manifest should provide metadata
that selectors can use, but `--select`, `--exclude`, named selectors, and
partial compile/run semantics are not locked yet.

The manifest is a generated artifact, not the authoritative source of project
truth. Services may parse authored files directly through the shared
parsed-project loading pipeline until freshness and cache semantics are
designed.

## Compiled artifacts

Compiled artifacts are human-readable and machine-usable.

They should answer:

- which checks will run,
- why they exist,
- which columns they use,
- whether all-column requests resolved to concrete columns,
- which sampling they use,
- which tolerance they use,
- which schema ignores apply,
- which CDC mode applies.
- which identity each key-dependent check uses,
- which prerequisite checks can block dependent checks.

## Error boundaries

Parse errors should be about invalid authored structure.

Compile errors should be about invalid resolved behavior.

Run errors should be about runtime preparation, execution failure, or check
failure.

Blocked checks should be represented as `blocked` check results with explicit
prerequisite context, not as skipped checks or hidden omissions. Checks that are
valid but cannot execute with the current engine, capability, placement,
materialization policy, or implementation phase should be represented as
`not_executable` with a machine-readable reason.

Validation timing and diagnostic code ownership are defined in
`docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`.

## Design principle

Parse understands the project. Compile decides exactly what will run. Run executes and records what happened.
