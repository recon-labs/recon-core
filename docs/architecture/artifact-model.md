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

For key-dependent checks, compiled artifacts should show declared identity,
requirements, prerequisites, and blocking policy.

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

`ManifestWriter`, `CompiledContractWriter`, and `CompiledCheckWriter` are
implemented. SQL, run-result, failure-detail, report, and state writers are
future work.

## Artifact versioning

Artifact formats should include top-level header fields.

Example:

```json
{
  "artifact_type": "run_results",
  "artifact_version": 1,
  "recon_version": "0.0.0",
  "generated_at": "2026-05-21T12:00:00Z",
  "invocation_id": "01HXAMPLEINVOCATION000000000"
}
```

This helps future compatibility.

Compiled artifacts should follow the schema in
`docs/decisions/adr-0015-compiled-artifact-schema-and-versioning.md`.
`target/manifest.json` already uses the same top-level header style without
`invocation_id`; compile and run artifacts should include `invocation_id` so
artifacts from the same invocation can be traced together.

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

Failure summaries for key safety checks should show null-key or duplicate-key
counts and may include bounded example keys when evidence settings allow them.

## Design principle

Artifacts should make Recon explainable to humans and useful to automation without requiring generated files to become source.
