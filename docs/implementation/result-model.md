# Result Model

## Purpose

The result model records what Recon executed and what happened.

Results should be useful for humans, CI, orchestration, dashboards, reports, and future integrations.

The result model is separate from evidence writers, result/evidence sinks, and
state backends. In-memory results describe what happened. Writers and sinks
decide where allowed result or evidence records are published. State powers
future runs and is not evidence by default.

The first check-engine boundary may define in-memory result/check-engine shape
and reserve future-compatible metadata concepts, but it must not write
`target/run_results.json`, evidence, reports, failure details, result/evidence
sinks, result tables, or state.

## Run result

First-boundary in-memory model:

```python
@dataclass(frozen=True)
class RunResult:
    run_id: str
    project_name: str
    started_at: str
    finished_at: str
    status: RunStatus
    contract_results: list[ContractResult]
    diagnostics: list[Diagnostic]
    artifact_refs: list[ArtifactRef]
    sink_refs: list[SinkRef]
```

Future generated `RunResult` artifacts may include sink-write metadata and
artifact references, but the exact serialized schema belongs to the future
run-result artifact phase or the later sink phase that first emits it.

## Contract result

```python
@dataclass(frozen=True)
class ContractResult:
    contract_name: str
    status: RunStatus
    check_results: list[CheckResult]
    diagnostics: list[Diagnostic]
```

## Check result

```python
@dataclass(frozen=True)
class CheckResult:
    check_id: str
    name: str
    check_type: str
    contract_name: str
    status: CheckStatus
    severity: str
    executed: bool
    reason_code: CheckReason | None
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
    artifact_refs: list[ArtifactRef]
    sink_refs: list[SinkRef]
    diagnostics: list[Diagnostic]
```

Future check results may need placement, capability, artifact-reference,
sink-reference, and exact/probabilistic classification fields. Those concepts
are reserved for compatibility but are not stable serialized fields until their
implementing phases write a public schema.

## First-boundary metadata reservations

The first check-engine boundary may keep future-compatible metadata in memory so
later execution and writer phases do not need to reshape the result model. That
metadata is explanatory only until the owning execution, runner, evidence, or
sink phase makes it a public schema.

Reserved metadata concepts:

| Concept | Purpose | First-boundary behavior |
| --- | --- | --- |
| execution placement | Records the planned source-side and target-side operation locations. | May be represented as unset, not applicable, or blocked; no adapter execution or source/target query is allowed. |
| comparison placement | Records where source and target operation outputs would be compared. | May explain why no comparison ran; no Python fallback, same-context comparison, or external engine execution is implied. |
| adapter or engine used | Names the adapter, execution context, or engine that actually ran a check. | Empty unless an earlier compiled artifact or in-memory fixture already supplies non-runtime metadata; no profile-backed lifecycle is started. |
| capability fit | Records required capabilities and capability mismatch reasons. | Capability mismatch may block or mark a result not executable, but it must not trigger fallback behavior. |
| blocked or not-executable reason | Explains why a check did not run. | Must be visible through structured reason fields and diagnostics; a check that did not execute must not look like pass/fail comparison evidence. |
| materialization policy | Records whether data movement, staging, or temporary objects were used. | Always absent, not applicable, or blocked until an explicit materialization phase defines movement, cleanup, and privacy rules. |
| result classification | Distinguishes exact, approximate, probabilistic, inconclusive, truncated, or confirmation-required results. | Exact/probabilistic fields are reserved only; no probabilistic summary or candidate record export is produced. |
| artifact references | Points to generated local outputs. | Empty for the first boundary because no generated run-result, evidence, report, failure-detail, state, or SQL artifact is written by the check engine. |
| sink references | Points to configured result/evidence destinations. | Empty or not configured; no local, table-backed, source, target, or third-connection sink write occurs. |

These reservations do not create public YAML syntax, public JSON fields, adapter
capability promises, or artifact-writing behavior. A future durable schema must
define field names, status values, versioning, privacy rules, and compatibility
tests before external automation can rely on them.

## Status values

Check statuses:

```text
pass
fail
warn
error
skipped
blocked
not_executable
```

Status meanings:

| Status | Meaning |
| --- | --- |
| `pass` | The check executed and proved the configured comparison condition. |
| `fail` | The check executed and found a reconciliation difference at error severity. |
| `warn` | The check executed and found a reconciliation difference at warning severity. |
| `error` | Recon attempted to prepare or evaluate the check but hit a runtime, artifact, internal, or unsafe-condition problem that prevents a trustworthy result. |
| `skipped` | The check intentionally did not run because explicit user, configuration, or future selector policy said to skip it. |
| `blocked` | The check did not run because a prerequisite check failed, errored, or was unavailable. |
| `not_executable` | The check is compiled but cannot execute with the current engine, capability, placement, materialization, or implemented operation surface. |

Run and contract aggregate statuses:

```text
pass
fail
warn
error
skipped
blocked
not_executable
no_checks
```

Aggregate status rules:

- `pass` requires every required check in scope to execute and pass.
- `fail` means at least one executed check found an error-severity
  reconciliation difference.
- `warn` means no check failed or errored, and at least one executed check found
  a warning-severity reconciliation difference.
- `error` means a run, contract, artifact, or check-engine problem prevented a
  trustworthy result.
- `blocked` means no higher-priority error or failure exists and at least one
  required check was blocked by prerequisites.
- `not_executable` means no higher-priority error, failure, or blocker exists
  and at least one required compiled check could not execute.
- `skipped` means every check in scope was intentionally skipped by an explicit
  policy. Selector-driven or policy-driven skip behavior is not part of the
  first check-engine boundary.
- `no_checks` means the run or contract had no compiled checks in scope. It is
  not equivalent to `pass`.

Aggregate status precedence for non-empty scopes is:

```text
error > fail > blocked > not_executable > warn > skipped > pass
```

`no_checks` is used only when there are no compiled checks in scope.

Counts and per-check results should preserve the full mixture when multiple
statuses occur. For example, a run can aggregate to `fail` while still reporting
blocked dependent checks.

## Reason codes

`unsupported` and `not_yet_executable` are not top-level statuses. They are
machine-readable reasons for `not_executable` results.

First-boundary reason codes:

| Reason code | Required status | Meaning |
| --- | --- | --- |
| `prerequisite_failed` | `blocked` | A prerequisite check executed and failed. |
| `prerequisite_error` | `blocked` | A prerequisite check errored before producing a trustworthy result. |
| `prerequisite_missing` | `blocked` | A required prerequisite result is absent. |
| `unsupported_check_type` | `not_executable` | The compiled check type has no internal handler in the current check engine. |
| `unsupported_typed_operation` | `not_executable` | The compiled check references a typed operation the current runtime cannot execute. |
| `missing_engine_capability` | `not_executable` | Required engine or adapter capability is unavailable or not declared. |
| `unsupported_execution_placement` | `not_executable` | Required operation or comparison placement is not implemented or allowed. |
| `unsupported_materialization_policy` | `not_executable` | Required data movement, staging, or materialization policy is not implemented or allowed. |
| `not_implemented_in_current_phase` | `not_executable` | The check is valid but belongs to a later execution phase. |
| `skipped_by_policy` | `skipped` | Explicit user or configuration policy skipped the check. Reserved until skip policy exists. |
| `selected_out` | `skipped` | Future selector behavior excluded the check from the run. Reserved until selectors exist. |

Every `blocked`, `not_executable`, or `skipped` result must carry a
`reason_code`, a safe message, and diagnostics. `blocked` results must also
carry `blocked_by`. A non-executed check must use `executed=false`, must leave
source/target values empty, and must not include failure detail, artifact, or
sink references unless a later owning writer phase actually produced them.

Checks that do not execute because the required engine, adapter capability,
execution placement, materialization policy, or result representation is not
available must carry an explicit reason and diagnostic. They must not be
reported as successful comparisons, and they must not be rewritten into another
execution strategy to make the run appear complete.

Future result status work must distinguish reconciliation outcomes from
publication outcomes. A failed required evidence or sink write is not the same
as a failed source-target comparison, and run metadata must make that
distinction visible.

## Command result separation

Command-level `ServiceResult` and check-level results are separate. The command
result owns CLI exit category, top-level message, and command diagnostics.
`RunResult`, `ContractResult`, and `CheckResult` own reconciliation status,
reason codes, per-check diagnostics, and future artifact/sink references.

The first check-engine boundary may expose in-memory result objects and
testable dictionary serialization for service plumbing. It must not expose a
stable generated result schema, and it must not write `target/run_results.json`.
The CLI may print a concise command message and safe diagnostics, but it must
not render a final run summary, evidence table, artifact link, or sink
destination until the owning runner/evidence phase exists.

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

The first check-engine boundary may define the check result/status model and
prerequisite or blocked-check representation without writing a generated
run-result artifact. `target/run_results.json` remains future run-result
artifact work unless a future split explicitly changes that boundary.

Before a generated result artifact exists, in-memory results must still be able
to state that no artifact writer, evidence writer, failure-detail writer, state
backend, or sink writer ran. No path, table, object-store location, or sink
destination should be recorded as written unless that output was actually
created by an owning writer phase.

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
- placement and capability metadata when execution phases define it,
- sink-write metadata when sink phases define it.

## Avoid large embedded data

Failure rows should not be embedded directly into `run_results.json` except for
small summaries allowed by the source/target data privacy policy.

Large details belong in separate bounded files, configured sinks, or future
external stores. Large failure-detail export, JSONL, streaming, pagination,
chunking, and moving large failure rows from execution engines to sink tables
belong to advanced evidence/result-store work unless a later split explicitly
changes that boundary.

Production result tables belong to later result-store work. They may target a
source, target, or third configured connection only when explicit destination
configuration, table schema/versioning, privacy policy, sink requiredness,
idempotency, partial-write behavior, and adapter write/sink capabilities are
defined.

## Design principle

The result model should make run outcomes machine-readable without losing human explainability.
