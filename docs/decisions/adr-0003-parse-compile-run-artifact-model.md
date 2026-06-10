# ADR 0003: Parse, Compile, and Run Artifact Model

## Context

Recon contracts can include defaults, refs, check packs, metrics, sampling policies, tolerance policies, schema policies, and CDC settings.

Users need a clean authoring experience, but they also need to see exactly what Recon will execute.

Generated behavior should not stay hidden.

## Decision

Recon Core separates the workflow into three concepts:

```text
parse   = project graph and structural validation
compile = human-readable resolved execution plan and compiled SQL/check queries
run     = execution, results, and evidence
```

Generated artifacts should be written under gitignored directories.

Generated artifact writers should reject symlinked generated-artifact paths
instead of following them during writes or cleanup. Exact output paths that
already exist must be regular files; directories and other non-file outputs are
not overwrite targets. Normal regeneration may overwrite the expected generated
file, but must not escape or corrupt the configured generated-artifact location
through symlinks or non-file path collisions.

Machine-oriented artifacts:

```text
target/manifest.json
target/run_results.json
```

Human-readable artifacts:

```text
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
reports/
```

## Reasoning

This separation gives Recon a clear framework shape.

`parse` validates and understands the project.

`compile` expands hidden or inherited behavior into inspectable artifacts.

`run` executes the compiled plan and writes results.

This model supports:

- local debugging,
- CI,
- orchestration,
- docs generation,
- selectors,
- state comparison,
- future integrations.

## Alternatives considered

### Run directly from YAML

Direct execution is simpler but hides defaults, check-pack expansion, metric compilation, sampling resolution, tolerance precedence, and schema/CDC rules.

### Compile only SQL

Recon needs more than SQL compilation. It must compile checks, metrics, sampling, policies, schema rules, CDC settings, and evidence behavior.

### Store only JSON artifacts

Machine-readable JSON is useful, but users also need human-readable compiled plans and SQL.

## Consequences

`target/manifest.json` is not just validation output. It is a machine-oriented project artifact used by other commands and tooling.

Compiled artifacts should be readable enough for users to answer:

> What exactly will Recon run?

Generated artifacts should not be committed.

The repository `.gitignore` should include generated artifact paths such as `target/`, `reports/`, and `state/`.
