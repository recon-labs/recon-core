# Result Model

## Purpose

The result model records what Recon executed and what happened.

Results should be useful for humans, CI, orchestration, dashboards, reports, and future integrations.

The result model is separate from evidence writers, result/evidence sinks, and
state backends. In-memory results describe what happened. Writers and sinks
decide where allowed result or evidence records are published. State powers
future runs and is not evidence by default.

Milestone 7.1 may define in-memory result/check-engine shape and reserve
future-compatible metadata concepts, but it must not write `target/run_results.json`,
evidence, reports, failure details, result/evidence sinks, result tables, or
state.

## Run result

Suggested model:

```python
@dataclass(frozen=True)
class RunResult:
    run_id: str
    project_name: str
    started_at: str
    finished_at: str
    status: str
    contract_results: list[ContractResult]
    diagnostics: list[Diagnostic]
    artifacts: list[EvidenceArtifact]
```

Future generated `RunResult` artifacts may include sink-write metadata and
artifact references, but the exact serialized schema belongs to Milestone 8 or
the later sink milestone that first emits it.

## Contract result

```python
@dataclass(frozen=True)
class ContractResult:
    contract_name: str
    status: str
    check_results: list[CheckResult]
    diagnostics: list[Diagnostic]
```

## Check result

```python
@dataclass(frozen=True)
class CheckResult:
    name: str
    type: str
    status: str
    severity: str
    identity: str | None
    message: str | None
    source_value: Any | None
    target_value: Any | None
    normalized_source_value: Any | None
    normalized_target_value: Any | None
    diff_value: Any | None
    tolerance: Any | None
    nulls: Any | None
    normalization: Any | None
    failure_count: int | None
    blocked_by: list[str]
    skip_reason: str | None
    artifacts: list[EvidenceArtifact]
    diagnostics: list[Diagnostic]
```

Future check results may need placement, capability, artifact-reference,
sink-reference, and exact/probabilistic classification fields. Those concepts
are reserved for compatibility but are not stable serialized fields until their
implementing milestones write a public schema.

## Status values

Run and contract statuses may include:

```text
pass
fail
warn
error
```

Check statuses may include:

```text
pass
fail
warn
error
skipped
```

`skipped` should be used when a check intentionally did not run because a
prerequisite failed. Skipped checks should include `blocked_by` and
`skip_reason`.

Future result status work must distinguish reconciliation outcomes from
publication outcomes. A failed required evidence or sink write is not the same
as a failed source-target comparison, and run metadata must make that
distinction visible.

## Severity

Severity affects run outcome.

```text
error
warn
info
```

An error-severity check failure should make the run return non-zero.

## Artifact references

Results should reference generated artifacts instead of embedding large content.

Example:

```json
{
  "artifact_type": "failure_details",
  "path": "target/failures/customer_revenue__row_diff.csv"
}
```

Artifact references point to generated local files. Future sink references point
to configured result/evidence destinations, such as table-backed stores. State
references point to data used by future runs. These references should not be
collapsed into one generic field once they become stable public schema.

## Diagnostics

Diagnostics should be included in results.

They help explain warnings, skips, runtime problems, and validation behavior.

Value-comparison results should include resolved tolerance, null, and
normalization policy when those policies affected the check. If normalization
changed a compared value and evidence policy allows value capture, results or
linked failure details should distinguish raw and normalized values. If a value
became null because of `nulls.treat_as_null`, linked failure details should be
able to identify the sentinel value or regex rule when evidence policy allows
that detail.

## Source and target data privacy

Run results are public artifacts. Before `target/run_results.json` is
implemented, Recon must define source/target data privacy defaults for every
field that can contain data values or data-derived values.

Raw source/target rows, comparison keys, normalized values, aggregate values,
row counts, relation names, query text, runtime adapter errors, and database
error text should be classified as public, sensitive, or policy-controlled
before they are emitted. By default, run results should prefer summaries,
counts, statuses, diagnostics, and artifact references over embedded raw rows
or raw source/target values. If a policy allows value capture, the result model
must show whether values are raw, normalized, masked, hashed, truncated, or
sampled.

Terminal output, logs, diagnostics, run results, linked failure details,
reports, and adapter test-kit snapshots must share the same privacy rules so a
value suppressed in one public surface is not leaked through another.

Serialized probabilistic summaries, Bloom-filter-like summaries, set sketches,
and intermediate probe outputs are sensitive or policy-controlled until a later
strategy proves safer handling. Results from probabilistic key-diff strategies
must distinguish exact, approximate, probabilistic, inconclusive, truncated, and
confirmation-required outcomes. Candidate missing or extra records must not be
presented as exact failure rows unless exact confirmation is required and
performed.

## JSON artifact

Milestone 7.1 may define the check result/status model and prerequisite or
blocked-check representation without writing a generated run-result artifact.
`target/run_results.json` remains Milestone 8 unless a future split explicitly
changes that boundary.

`target/run_results.json` should include:

- artifact type,
- artifact version,
- run metadata,
- contract results,
- check results,
- diagnostics,
- artifact references.
- identity used by key-dependent checks,
- prerequisite and blocked-check information.
- placement and capability metadata when execution milestones define it,
- sink-write metadata when sink milestones define it.

## Avoid large embedded data

Failure rows should not be embedded directly into `run_results.json` except for
small summaries allowed by the source/target data privacy policy.

Large details belong in separate bounded files, configured sinks, or future
external stores. Large failure-detail export, JSONL, streaming, pagination,
chunking, and moving large failure rows from execution engines to sink tables
belong to Post-MVP Milestone 31 unless a later split explicitly changes that
boundary.

Production result tables belong to Post-MVP Milestone 25.5. They may target a
source, target, or third configured connection only when explicit destination
configuration, table schema/versioning, privacy policy, sink requiredness,
idempotency, partial-write behavior, and adapter write/sink capabilities are
defined.

## Design principle

The result model should make run outcomes machine-readable without losing human explainability.
