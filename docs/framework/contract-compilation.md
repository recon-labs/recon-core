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

It should resolve defaults and refs, expand check packs, compile metrics into checks, resolve sampling inheritance, resolve tolerance precedence, resolve null/normalization rules, apply schema policy configuration, apply CDC mode/delete behavior, validate adapter capabilities when possible, generate human-readable compiled artifacts, and generate SQL/check queries where possible.

Main outputs:

```text
target/compiled_contracts/*.yml
target/compiled_checks/*.yml
target/compiled_sql/**/*.sql
```

The compiled artifacts are for humans and the engine.

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

## Compiled checks

A compiled check should show:

- check name,
- check type,
- source and target,
- keys,
- columns,
- metrics,
- sampling,
- tolerances,
- null rules,
- schema ignores,
- CDC mode,
- evidence settings,
- severity.

## Generated artifacts are not source

Generated artifacts should live under gitignored directories such as `target/` and `reports/`.

Authored YAML is versioned. Generated artifacts are not.

## Design principle

Authored YAML should be clean and declarative. Compiled artifacts should be explicit, debuggable, and safe to inspect before execution.
