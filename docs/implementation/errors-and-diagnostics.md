# Errors and Diagnostics

## Purpose

Diagnostics provide structured errors and warnings across parse, compile, run, and evidence.

## Diagnostic model

Suggested model:

```python
@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    resource_type: str | None = None
    resource_name: str | None = None
    path: str | None = None
    line: int | None = None
    column: int | None = None
    hint: str | None = None
```

## Severity

Diagnostic severities:

```text
info
warning
error
```

Check statuses are separate:

```text
pass
fail
warn
error
skipped
```

## Error code categories

Recommended categories:

```text
RC_CONFIG_*
RC_PARSE_*
RC_COMPILE_*
RC_VALIDATE_*
RC_ADAPTER_*
RC_RUNTIME_*
RC_EVIDENCE_*
```

## Parse diagnostics

Examples:

```text
RC_PARSE_FILE_READ_ERROR
RC_PARSE_INVALID_YAML
RC_PARSE_INVALID_CONTRACT
RC_PARSE_MISSING_REQUIRED_FIELD
RC_PARSE_DUPLICATE_CONTRACT
RC_PARSE_INVALID_ENDPOINT
RC_PARSE_RESOURCE_PATH_NOT_FOUND
RC_PARSE_UNKNOWN_FIELD
```

## Configuration diagnostics

Examples:

```text
RC_CONFIG_PROJECT_NOT_FOUND
RC_CONFIG_INVALID_PROJECT_YAML
RC_CONFIG_INVALID_PROJECT_CONFIG
RC_CONFIG_INIT_PATH_EXISTS
RC_CONFIG_INIT_INVALID_PROJECT_NAME
```

## Compile diagnostics

Examples:

```text
RC_COMPILE_UNKNOWN_CHECK_PACK
RC_COMPILE_EMPTY_CHECK_PACK
RC_COMPILE_UNKNOWN_SAMPLE_POLICY
RC_COMPILE_UNKNOWN_TOLERANCE_POLICY
RC_COMPILE_UNKNOWN_SCHEMA_POLICY
```

## Validation diagnostics

Examples:

```text
RC_VALIDATE_ROW_CHECK_REQUIRES_KEYS
RC_VALIDATE_CHECK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_CHECK_REQUIRES_CDC_KEYS
RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
RC_VALIDATE_DUPLICATE_KEYS_BLOCK_ROW_CHECK
RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE
RC_VALIDATE_INVALID_STABLE_ID_PART
RC_VALIDATE_METRIC_REQUIRES_NUMERIC_COLUMN
RC_VALIDATE_RANDOM_SAMPLE_REQUIRES_PERSISTED_KEYS
RC_VALIDATE_CDC_CONFIG_REQUIRED
RC_VALIDATE_CDC_DELETE_MODE_REQUIRED
RC_VALIDATE_CDC_ORDERING_REQUIRED
RC_VALIDATE_SCHEMA_IGNORE_INVALID
```

## Adapter diagnostics

Examples:

```text
RC_ADAPTER_UNKNOWN_TYPE
RC_ADAPTER_CAPABILITY_UNSUPPORTED
RC_ADAPTER_METADATA_UNAVAILABLE
RC_ADAPTER_QUERY_FAILED
```

## Runtime diagnostics

Examples:

```text
RC_RUNTIME_CHECK_ERROR
RC_RUNTIME_CHECK_BLOCKED_BY_FAILED_PREREQUISITE
RC_RUNTIME_NULL_GRAIN_KEYS
RC_RUNTIME_DUPLICATE_GRAIN_KEYS
RC_RUNTIME_NULL_CDC_KEYS
RC_RUNTIME_DUPLICATE_CDC_KEYS
RC_RUNTIME_MANIFEST_WRITE_FAILED
RC_RUNTIME_STATE_WRITE_FAILED
RC_RUNTIME_EVIDENCE_WRITE_FAILED
```

## Message style

Messages should be direct and actionable.

Good:

```text
row_diff requires grain.keys because source and target rows must be matched.
```

Bad:

```text
invalid contract
```

## Hints

Hints should help users fix the issue.

Example:

```text
Add grain.keys or remove row-level value checks from this contract.
```

Example:

```text
Declare cdc.keys for delete_propagation or remove CDC propagation checks from this contract.
```

## Artifact inclusion

Diagnostics should appear in:

```text
target/manifest.json
target/compiled_checks/
target/run_results.json
reports/
```

## Design principle

Diagnostics should make Recon safe to use without reading the source code.
