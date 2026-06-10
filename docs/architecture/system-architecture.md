# System Architecture

## High-level flow

```text
User-authored files
  -> ProjectLoader
  -> Parser
  -> Manifest
  -> Compiler
  -> CompiledProject
  -> Runner
  -> CheckEngine
  -> Adapter
  -> Results and Evidence
```

## Authored files

Authored files include:

```text
recon_project.yml
packages.yml
selectors.yml
connections/profiles.yml
contracts/
check_packs/
sample_policies/
tolerances/
schema_policies/
macros/
```

These are user-controlled inputs.

## Generated files

Generated files include:

```text
target/manifest.json
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
target/run_results.json
target/failures/
reports/
state/
```

These are generated outputs and should not be committed.

## Main runtime objects

The architecture should distinguish:

```text
RawFile
ParsedResource
Manifest
EquivalenceContract
CompiledContract
CompiledCheck
ExecutionPlan
CheckResult
RunResult
EvidenceArtifact
```

## Layer responsibilities

### CLI layer

Handles command invocation, options, exit codes, and terminal output.

The CLI should not contain business logic.

### Project loading layer

Finds project configuration, resolves paths, loads files, and discovers resources.

### Parsing layer

Parses YAML into typed models and performs structural validation.

### Manifest layer

Stores the parsed project graph in a machine-readable artifact.

### Compilation layer

Resolves all inherited and inferred behavior into explicit compiled artifacts.

### Planning layer

Turns compiled contracts into typed executable check plans.

### Execution layer

Runs typed check plans through adapters as execution phases are implemented and
collects results for those phases.

### Evidence layer

Publishes run results, evidence artifacts, failure details, reports, compiled
SQL references, and state only in the phases that own those outputs.

## Dependency direction

Dependencies should point inward toward domain models and interfaces.

```text
CLI -> Application services -> Domain models/interfaces <- Adapters
```

Adapters should depend on core interfaces. Core should not depend on specific production adapter packages.

Core owns typed check plans and comparison semantics. Adapters own
system-specific rendering and execution.

## Strictness boundary

Unsafe behavior should be rejected before execution when possible.

If adapter metadata is required and unavailable until runtime, compiled artifacts should mark validation as deferred.

## Design principle

The architecture should make it easy to answer:

> What did the user author, what did Recon compile, what did Recon run, and what evidence was produced?
