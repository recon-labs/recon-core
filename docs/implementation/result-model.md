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
    diff_value: Any | None
    tolerance: Any | None
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

Failure rows should not be embedded directly into `run_results.json` except for small summaries.

Large details belong in separate files.

## Design principle

The result model should make run outcomes machine-readable without losing human explainability.
