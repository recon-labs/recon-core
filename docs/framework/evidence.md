# Evidence

## Purpose

This document defines evidence in Recon.

Evidence is a first-class output. Recon should not only return pass/fail; it should show what was checked, how it was checked, and what differed.

## Why evidence matters

Reconciliation is often tied to:

- CDC reliability,
- migration cutover,
- analyst QA,
- audit review,
- engineering fixes,
- sign-off workflows.

Teams need artifacts they can review, attach to tickets, and rerun after fixes.

## Evidence types

### Terminal summary

Concise CLI output:

```text
PASS row_count_diff
PASS missing_keys
FAIL sum_diff revenue: source=100000.00 target=99950.00 diff=-50.00
```

### JSON run result

Machine-readable artifact:

```text
target/run_results.json
```

Useful for CI, Airflow, integrations, and dashboards.

### Failure details

Structured mismatch records:

```text
target/failures/customer_revenue__row_diff.csv
```

Fields may include:

- run id,
- contract name,
- check name,
- key values,
- column name,
- source value,
- target value,
- diff value,
- tolerance,
- severity.

### HTML report

Human-readable report:

```text
reports/customer_revenue.html
```

Should include:

- run summary,
- contract metadata,
- source/target,
- checks,
- sampling,
- tolerances,
- failures,
- evidence links.

### Result tables

Production teams may persist results:

```text
recon_runs
recon_check_results
recon_failure_details
recon_sample_keys
recon_watermarks
```

### Compiled SQL

Generated SQL should be available for debugging:

```text
target/compiled_sql/
```

### Sample keys

When sampling is used, selected keys should be persisted where needed.

## Evidence levels

Possible levels:

- `summary`,
- `detailed`,
- `debug`.

## Contract example

```yaml
evidence:
  level: detailed
  store_failures: true
  max_failure_rows: 1000
  report: html
```

## Sensitive data

Failure details can contain sensitive values.

Recon should eventually support:

- redaction,
- masking,
- hash-only keys,
- row limits,
- disabling failure export.

## Exit codes

Recon should return non-zero when error-severity checks fail.

Warnings may be configurable.

## MVP recommendation

v0.1 should produce:

- terminal summary,
- JSON run result,
- basic HTML report,
- limited failure details.

v0.2 should add:

- compiled SQL artifacts,
- result table writer,
- sample key persistence.

## Design principle

Evidence is part of the product, not a log side effect.
