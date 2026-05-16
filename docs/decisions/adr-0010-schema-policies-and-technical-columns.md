# ADR 0010: Schema Policies and Technical Columns

## Context

Schema reconciliation is different from value reconciliation.

CDC and ingestion systems often add technical target columns such as:

```text
_dms_operation
_dms_timestamp
_loaded_at
_file_name
_row_hash
_metadata_file
```

These columns should not affect value checks unless explicitly selected. However, schema checks may see them and fail unless the user defines expected ignores.

## Decision

Recon should support explicit schema policies.

Schema checks should be strict by default and allow explicit ignore rules.

Schema policies should support:

- ignored source columns,
- ignored target columns,
- ignored patterns,
- type compatibility,
- nullable compatibility,
- precision/scale compatibility.

## Value checks versus schema checks

Value checks compare only declared or explicitly selected columns.

Schema checks may inspect all columns minus explicit ignore rules.

This means extra target CDC columns do not affect row-level value comparison, but they may fail schema checks unless ignored.

## Precision and scale

Precision/scale compatibility is a schema check.

Numeric value tolerance is a value comparison rule.

These should be documented and implemented separately.

## Consequences

Schema ignore rules must be visible in compiled artifacts and evidence.

Ignored columns should be reported, not hidden.

Recon should never silently ignore CDC technical columns without configuration.
