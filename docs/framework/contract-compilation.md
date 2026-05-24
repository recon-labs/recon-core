# Contract Compilation

## Purpose

This document defines the framework-level meaning of parse, compile, and run in Recon.

Recon should separate authored project files from generated execution artifacts.

## Mental model

```text
authored YAML
  ↓ recon parse
target/manifest.json
  ↓ recon compile
compiled contracts, checks, and SQL
  ↓ recon run
results and evidence
```

## `recon parse`

`recon parse` understands the project.

It should read project files, validate YAML syntax, validate basic schema, discover contracts and reusable resources, resolve file paths, identify duplicate contract names, validate that refs point to known resources, and produce a machine-oriented manifest.

Main output:

```text
target/manifest.json
```

The manifest is for the engine, tooling, selectors, docs, compile, run, and CI workflows.

## `recon compile`

`recon compile` makes execution explicit and inspectable.

It should resolve defaults and refs, expand check packs, compile metrics into checks, resolve sampling inheritance, resolve tolerance precedence, resolve null/normalization rules, apply schema policy configuration, apply CDC mode/delete behavior, validate adapter capabilities when possible, generate typed check plans, generate human-readable compiled artifacts, and generate adapter-rendered SQL/check queries where possible.

Main outputs:

```text
target/compiled_contracts/*.yml
target/compiled_checks/*.yml
target/compiled_sql/**/*.sql
```

The compiled artifacts are for humans and the engine.

The typed check plan is the core representation of execution intent. Rendered
SQL is an adapter-specific artifact derived from that plan.

Compiled contracts and compiled checks are separate artifacts:

- compiled contracts show resolved contract meaning and policies,
- compiled checks show the exact checks, requirements, prerequisites, typed
  plans, and rendering status.

When adapter SQL rendering is not available, compiled checks should still show
typed plans and mark rendering as `not_rendered`.

Current implementation writes compiled contract and compiled checks artifacts
for supported check-pack and metric behavior. `target/compiled_sql/` is not
written until adapter SQL rendering exists.

Compiled contract and compiled checks directories are regenerated as snapshots.
Before writing a new successful compile output, Recon removes existing top-level
`*.yml` files from `target/compiled_contracts/` and
`target/compiled_checks/`, then writes artifacts for the contracts present in
the current run.

## `recon run`

`recon run` executes checks.

It should use compiled artifacts when they are available and fresh, or parse/compile automatically when needed.

Main outputs:

```text
target/run_results.json
target/failures/
reports/
```

## Human-readable versus machine-readable artifacts

Machine-oriented:

```text
target/manifest.json
target/run_results.json
```

Human-readable:

```text
target/compiled_contracts/*.yml
target/compiled_checks/*.yml
target/compiled_sql/**/*.sql
reports/*.html
```

## Why compile matters

Contracts can use defaults, refs, check packs, metrics, sampling policies, tolerance policies, schema policies, and CDC policies.

Without compilation, users cannot easily see what will actually run.

Compilation prevents hidden behavior by producing an explicit plan.

That plan should stay typed until an adapter renders dialect SQL or equivalent
execution requests.

## Compiled checks

A compiled check should show:

- check name,
- check type,
- source and target,
- identity kind,
- grain keys,
- CDC keys when relevant,
- columns,
- metrics,
- sampling,
- tolerances,
- null rules,
- schema ignores,
- CDC mode,
- evidence settings,
- severity.
- requirements,
- prerequisites,
- blocking policy.

When SQL is generated, the compiled check should also preserve enough plan
metadata to trace the SQL back to typed operations.

Compiled artifacts should use stable IDs:

```text
contract.<project>.<contract>
check.<project>.<contract>.<check>
plan.<project>.<contract>.<check>
```

For row-level value checks, compilation should include or generate required null-key and duplicate-key safety checks and record them as prerequisites.

## Generated artifacts are not source

Generated artifacts should live under gitignored directories such as `target/` and `reports/`.

Authored YAML is versioned. Generated artifacts are not.

## Design principle

Authored YAML should be clean and declarative. Compiled artifacts should be explicit, debuggable, and safe to inspect before execution.
