# Schema Policy Engine

## Purpose

The schema policy engine resolves structural comparison rules and supports schema checks.

## Inputs

Inputs:

- source metadata,
- target metadata,
- authored schema policy,
- reusable schema policy,
- check-level schema overrides,
- adapter type mappings.

## Outputs

Outputs:

- resolved schema policy,
- ignored source columns,
- ignored target columns,
- type compatibility rules,
- nullable compatibility rules,
- precision/scale compatibility rules,
- schema diagnostics,
- schema check results.

## Ignore rules

Schema policies should support:

```yaml
schema:
  ignore_source_columns:
    - legacy_audit_column
  ignore_target_columns:
    - _loaded_at
    - _file_name
  ignore_patterns:
    - "_metadata_*"
```

Source and target ignores should be separate.

## Pattern matching

Ignore patterns should be simple and predictable.

Recommended initial behavior:

- `*` wildcard matching,
- case sensitivity follows adapter identifier rules or explicit policy.

## Technical columns

CDC and ingestion tools add technical columns.

Examples:

```text
_dms_operation
_dms_timestamp
_loaded_at
_file_name
_row_hash
```

These should not affect value checks unless selected.

For schema checks, they should be ignored only when explicitly configured.

## Type compatibility

Adapters should expose logical type metadata.

The schema engine should compare logical compatibility rather than raw physical type strings when systems differ.

Example:

```text
SQL Server decimal -> Snowflake number
Postgres varchar -> BigQuery string
```

## Precision and scale

Precision/scale compatibility is a schema rule.

Example:

```text
source DECIMAL(18,2)
target NUMBER(38,2)
```

This may be compatible if target precision is sufficient and scale behavior is acceptable.

## Nullable compatibility

Nullable behavior should be configurable.

Strict mode may require exact nullable compatibility.

Relaxed mode may warn.

## Evidence

Schema evidence should show:

- missing source columns,
- missing target columns,
- extra source columns,
- extra target columns,
- ignored columns,
- type differences,
- precision/scale differences,
- nullable differences.

## Design principle

Schema policy should make expected structural differences explicit without hiding unexpected schema drift.
