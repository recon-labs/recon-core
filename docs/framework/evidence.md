# Evidence

## Purpose

This document defines evidence in Recon.

Evidence is a first-class output. Recon should not only return pass/fail; it should show what was checked, how it was checked, what assumptions were used, and what differed.

## Evidence types

### Terminal summary

Concise CLI output.

### Manifest

Machine-oriented parsed project graph:

```text
target/manifest.json
```

The manifest supports tooling, selectors, docs, compile, run, and CI workflows.

### Compiled contracts

Human-readable resolved contracts:

```text
target/compiled_contracts/customer_revenue.yml
```

### Compiled checks

Human-readable execution plan:

```text
target/compiled_checks/customer_revenue.yml
```

These should show check-pack expansion, metric expansion, columns used, sampling used, tolerances used, schema ignores, CDC mode, and delete behavior.

They should also show declared comparison identity, declared CDC identity, check requirements, generated safety checks, prerequisites, and blocking policy.

### Compiled SQL

Generated SQL should be available for debugging:

```text
target/compiled_sql/
```

### JSON run result

Machine-readable run outcome:

```text
target/run_results.json
```

### Failure details

Structured mismatch records:

```text
target/failures/customer_revenue__row_diff.csv
```

Fields may include run id, contract name, check name, key values, column name, source value, target value, normalized values, diff value, tolerance, and severity.

When tolerance, null, or normalization policy affects a value comparison,
failure details and reports should show the resolved policy. Evidence should
not imply that relative tolerance, timestamp tolerance, or string normalization
was applied unless the compiled check and adapter execution actually used that
resolved policy. When a string value becomes null because of
`nulls.treat_as_null`, evidence should show the sentinel rule that caused it
when evidence policy allows that detail.

For key safety checks, failure details may include bounded examples of null or duplicate keys when evidence settings allow them.

### HTML report

Human-readable report:

```text
reports/customer_revenue.html
```

It should include run summary, contract metadata, source/target, checks, sampling, tolerances, null/normalization rules, schema ignore rules, CDC mode, failures, and evidence links.

Reports should also show which checks were blocked, which prerequisite checks blocked them, and whether each key-dependent check used `grain.keys` or `cdc.keys`.

### Result tables

Production teams may persist results in tables such as `recon_runs`, `recon_check_results`, `recon_failure_details`, `recon_sample_keys`, and `recon_watermarks`.

### Sample keys

When sampling is used, selected keys should be persisted where needed.

## Evidence levels

Possible levels are `summary`, `detailed`, and `debug`.

## Full versus sampled evidence

Reports must clearly state whether each check ran on full data, deterministic sample, incremental window, random persisted sample, or previous failure set.

Sampled evidence should never imply full-data equivalence.

CDC evidence must also state when delete propagation is not validated, when CDC keys differ from comparison keys, and which window or ordering assumptions were used.

## Sensitive data

Failure details can contain sensitive values.

Recon should eventually support redaction, masking, hash-only keys, row limits, disabling failure export, and sensitive column policies.

## Failure row limits

If failure rows exceed configured limits, evidence should clearly say results were truncated.

## Exit codes

Recon should return non-zero when error-severity checks fail.

Warnings may be configurable.

## MVP recommendation

v0.1 should produce terminal summary, manifest, compiled checks/contracts where feasible, JSON run result, basic HTML report, and limited failure details.

v0.2 should add richer compiled SQL artifacts, result table writer, sample key persistence, and richer reports.

## Design principle

Evidence is part of the product, not a log side effect. Evidence should make assumptions, scope, and generated behavior visible.
