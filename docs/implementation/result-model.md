# Result Model

## Purpose

The result model records what Recon executed and what happened.

Results should be useful for humans, CI, orchestration, dashboards, reports, and future integrations.

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

## JSON artifact

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

## Avoid large embedded data

Failure rows should not be embedded directly into `run_results.json` except for
small summaries allowed by the source/target data privacy policy.

Large details belong in separate files.

## Design principle

The result model should make run outcomes machine-readable without losing human explainability.
