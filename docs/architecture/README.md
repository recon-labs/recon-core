# Architecture

Recon Core is organized around a small set of stable architectural boundaries:

```text
CLI
  -> project loader
  -> parser
  -> manifest
  -> compiler
  -> compiled artifacts
  -> runner
  -> check engine
  -> adapters
  -> evidence
```

The codebase should keep these boundaries clear so the framework can grow without turning into a pile of scripts.

## Core architecture goals

Recon Core should be:

- contract-centered,
- CLI-first,
- adapter-based,
- strict in validation,
- explicit in compilation,
- evidence-producing,
- testable without production databases,
- extensible through adapters and packages.

## Source of truth

Authored project files are the source of truth.

Generated artifacts live under gitignored paths such as:

```text
target/
reports/
state/
```

The framework should never require generated artifacts to be committed.

## Main subsystems

```text
Project loading
  Reads project configuration, file paths, profiles, packages, and resources.

Parsing
  Converts authored files into typed internal models and writes the manifest.

Compilation
  Resolves defaults, refs, check packs, metrics, sampling, tolerances, schema policies, CDC settings, and adapter capabilities.

Check planning
  Produces explicit executable checks.

Execution
  Runs checks through adapters.

Evidence
  Writes run results, failure details, compiled artifacts, reports, and state.
```

## Architecture rule

Keep authored configuration, internal models, compiled plans, execution results, and evidence artifacts separate.

A change in one layer should not leak unnecessary complexity into the other layers.
