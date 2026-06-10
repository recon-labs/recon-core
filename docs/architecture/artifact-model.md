# Artifact Model

## Artifact categories

Recon produces three categories of artifacts:

```text
machine-oriented
human-readable
stateful
```

Result/evidence sinks are not a fourth artifact category by default. They are
configured destinations that receive records after execution. A sink may later
write database rows or external records that reference local artifacts, but
those records do not become local generated artifacts unless a writer creates a
file under an ignored artifact path.

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

`target/run_results.json` is planned for Milestone 8. Milestone 7.1 may define
in-memory result shape only and must not publish this artifact.

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

Reports are local evidence artifacts when written under `reports/`. A future
table-backed evidence sink can coexist with reports or replace optional report
writing only when policy makes that mode explicit.

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

State is not evidence by default. It powers future runs. Persisted sample keys,
previous-failure keys, and watermarks may be referenced by evidence when policy
allows it, but their retention, update, privacy, and locking semantics belong
to state milestones.

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

`ManifestWriter`, `CompiledContractWriter`, `CompiledCheckWriter`, and
`CompiledSqlWriter` are implemented. Run-result, failure-detail, report, and
state writers are future work.

Production result/evidence sink writers are also future work. They must not be
added as hidden side effects of run-result or evidence writers. Table-backed
sinks require explicit destination configuration, schema/versioning, privacy
policy, write requiredness, idempotency, partial-write behavior, and adapter
write/sink capabilities before implementation.

Generated artifact writers own cleanup and publish ordering for their output
paths. A writer or service must not leave stale, partial, or orphaned generated
artifacts after a failed write in a way that downstream automation could read
as current evidence. Writers that publish per-item files must validate both the
payload shape and the full output path set before creating directories or files.
Future writers for run results, evidence, failure details, reports, state, docs
output, and selector-scoped artifacts must define that
lifecycle before the artifact becomes a compatibility surface.

Future sink writers must define equivalent publish ordering and failure
semantics for non-file destinations. A failed required sink write must not make
evidence appear complete, and a partial write must be surfaced distinctly from
a failed reconciliation check.

Batched artifact writers should validate all batch path components and preflight
all output paths before writing the first file. For compiled SQL, unsafe
contract, check, or renderer step path segments, empty rendered SQL requests,
and case-insensitive duplicate step names must fail before
`target/compiled_sql/` directories or files are published.

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

Large failure-detail export, JSONL, streaming, pagination, chunking, and
external large-result stores belong to advanced evidence/result-store work.
Run-result artifacts should reference large details instead of embedding them.

Future probabilistic key-diff summaries, including Bloom-filter-like summaries
and set sketches, are sensitive or policy-controlled until a later strategy
proves safer handling. Candidate missing or extra records from probabilistic
strategies must not be represented as exact failure-detail artifacts unless
exact confirmation is required and performed.

## Design principle

Artifacts should make Recon explainable to humans and useful to automation without requiring generated files to become source.
