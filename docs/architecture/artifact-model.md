# Artifact Model

## Artifact categories

Recon produces three categories of artifacts:

```text
machine-oriented
human-readable
stateful
```

## Machine-oriented artifacts

Machine-oriented artifacts are optimized for automation.

Examples:

```text
target/manifest.json
target/run_results.json
```

### `manifest.json`

Represents the parsed project graph.

Expected uses:

- compile,
- run,
- selectors,
- docs,
- CI tooling,
- future integrations.

### `run_results.json`

Represents execution outcomes.

Expected uses:

- CI,
- orchestration,
- dashboards,
- alerting,
- reporting.

## Human-readable artifacts

Human-readable artifacts are optimized for inspection and debugging.

Examples:

```text
target/compiled_contracts/
target/compiled_checks/
target/compiled_sql/
reports/
```

Compiled artifacts should show resolved behavior.

Reports should show execution evidence.

## Stateful artifacts

Stateful artifacts support future runs.

Examples:

```text
state/
target/sample_keys/
```

State may include:

- watermarks,
- sample keys,
- previous failed keys,
- run history.

## Artifact writers

Artifacts should be written through dedicated writer classes.

Possible writers:

```text
ManifestWriter
CompiledContractWriter
CompiledCheckWriter
CompiledSqlWriter
RunResultWriter
FailureDetailWriter
HtmlReportWriter
StateWriter
```

## Artifact versioning

Artifact formats should include a version field.

Example:

```json
{
  "artifact_type": "run_results",
  "artifact_version": 1
}
```

This helps future compatibility.

## Generated artifact policy

Generated artifacts should be ignored by Git.

Recommended ignored paths:

```text
target/
reports/
state/
```

## Failure details

Failure details may be large and sensitive.

They should be:

- bounded by row limits,
- optionally disabled,
- referenced from run results,
- handled carefully in reports.

## Design principle

Artifacts should make Recon explainable to humans and useful to automation without requiring generated files to become source.
