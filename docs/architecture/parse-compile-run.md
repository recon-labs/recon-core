# Parse, Compile, and Run Architecture

## Flow

```text
recon parse
  -> target/manifest.json

recon compile
  -> target/compiled_contracts/
  -> target/compiled_checks/
  -> target/compiled_sql/ when adapter SQL rendering is available

recon run
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

Typed check plans are the core execution intent. Rendered SQL is an
adapter-specific artifact derived from those plans.

Current compile implementation writes compiled contract and compiled checks
artifacts with `rendering.status: not_rendered`. Adapter SQL rendering is a
future layer.

Before the validation rulebook milestone expands parse and compile validation,
parse and compile should share one internal parsed-project loading pipeline.
That pipeline should read authored project files, discover resources, load YAML,
parse contracts, and return parsed in-memory models plus diagnostics. It should
not require `recon compile` to read `target/manifest.json`, and it should not
introduce manifest freshness or caching rules.

This preserves authored YAML and `recon_project.yml` as the source of truth
while avoiding drift between `recon parse` and `recon compile`.

Current implementation status: the shared parsed-project loading pipeline is
contract-only. Non-contract resource loading and precedence are locked by ADR
0017, but reference validation must wait until the relevant resource kinds are
loaded through that shared model.

## Run service

The run service should:

- ensure parse/compile artifacts are available and fresh,
- load typed check plans,
- initialize adapters,
- run typed check plans through adapters,
- collect results,
- write run artifacts,
- write evidence,
- return appropriate exit code.

## Freshness of artifacts

`recon run` may parse and compile automatically.

A simple initial implementation can always parse and compile before running.

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
- which sampling they use,
- which tolerance they use,
- which schema ignores apply,
- which CDC mode applies.
- which identity each key-dependent check uses,
- which prerequisite checks can block dependent checks.

## Error boundaries

Parse errors should be about invalid authored structure.

Compile errors should be about invalid resolved behavior.

Run errors should be about execution failure or check failure.

Blocked checks should be represented as skipped check results with explicit
prerequisite context, not as hidden omissions.

Validation timing and diagnostic code ownership are defined in
`docs/decisions/adr-0016-validation-timing-and-diagnostic-codes.md`.

## Design principle

Parse understands the project. Compile decides exactly what will run. Run executes and records what happened.
