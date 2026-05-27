# Schema Policies

## Purpose

This document defines schema comparison behavior in Recon.

Schema policies control how Recon compares source and target structure, including extra columns, missing columns, type compatibility, nullable compatibility, and precision/scale compatibility.

## Why schema policies matter

Real source-target reconciliation often involves technical columns or type differences that are expected.

Examples include CDC operation metadata, ingestion file/load metadata, warehouse audit columns, different numeric precision, and different nullable metadata.

Schema checks should be strict by default, but flexible through explicit configuration.

## Schema checks

Schema-related checks may include:

- `column_presence`,
- `type_compatibility`,
- `nullable_compatibility`,
- `precision_scale_compatibility`.

These checks are different from value checks.

Value checks compare declared columns.

Schema checks compare structure.

## Extra CDC and ingestion columns

CDC and ingestion tools often add target-only columns.

Examples:

```text
_dms_operation
_dms_timestamp
_loaded_at
_file_name
_row_hash
_metadata_file
```

These should not affect value checks unless explicitly selected.

For schema checks, users should ignore them explicitly.

## Global schema ignore rules

Project or contract level:

```yaml
schema:
  ignore_target_columns:
    - _dms_operation
    - _dms_timestamp
    - _loaded_at
  ignore_patterns:
    - "_metadata_*"
```

## Check-level schema ignore rules

```yaml
checks:
  - type: schema_equivalence
    ignore_target_columns:
      - _dms_operation
      - _loaded_at
```

## Source versus target ignores

Schema policies should distinguish source and target ignores.

```yaml
schema:
  ignore_source_columns:
    - legacy_audit_column
  ignore_target_columns:
    - _loaded_at
    - _file_name
```

This prevents hiding unexpected columns on both sides.

## Value checks versus schema checks

Value checks use only declared/eligible columns.

Schema checks may inspect all columns, minus explicit ignore rules.

This means extra target CDC columns do not affect row-level value comparison, but they may fail schema checks unless ignored.

For ADR 0019 all-column value expansion, explicit schema/value ignore rules
are part of the resolved column surface. Recon must not silently compare only
the source-target intersection while ignoring extra columns.

## Type compatibility

Type compatibility should be adapter-aware.

Schema checks should not require identical physical type strings when systems differ. They should use compatibility rules.

## Precision and scale compatibility

Precision/scale compatibility is a schema check.

This is separate from numeric value tolerance.

## Nullable compatibility

Nullable compatibility should be configurable.

Some pipelines intentionally make target columns nullable even if source columns are not, or vice versa.

Strict mode can require compatibility. Relaxed mode can warn.

## Schema policy defaults

Recommended defaults:

- fail on missing expected columns,
- fail on incompatible types,
- warn or fail on extra columns depending on schema check mode,
- allow explicit ignored columns/patterns,
- never silently ignore CDC technical columns without configuration.

## Evidence

Schema check evidence should show missing columns, extra columns, ignored columns, type differences, precision/scale differences, and nullable differences.

## Design principle

Schema policies should make expected structural differences explicit without letting unexpected schema drift pass silently.
