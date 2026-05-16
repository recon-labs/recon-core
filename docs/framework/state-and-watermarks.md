# State and Watermarks

## Purpose

This document defines Recon state and watermarks.

State is essential for continuous CDC reconciliation, incremental validation, previous failure retesting, and reproducible sampling.

## What is state

State is information persisted across Recon runs.

Examples:

- last successful watermark,
- previous failed keys,
- sample keys,
- run history,
- check results,
- evidence references.

## Watermark

A watermark tracks incremental progress.

Common types:

- timestamp,
- monotonically increasing id,
- CDC offset,
- batch id,
- ingestion time.

Example:

```text
last_successful_watermark = 2026-05-16T10:00:00Z
```

## Incremental window

An incremental window uses the previous watermark and current boundary.

```text
from: last_successful_watermark - lookback
to: current_watermark
```

Lookback helps catch late-arriving records.

## State update rule

A watermark should advance only after successful validation for the relevant contract and policy.

If checks fail, preserve the previous successful watermark unless configured otherwise.

## Previous failures

Recon should store failed keys so future runs can retest them.

This powers `previous_failures` sampling.

## Sample key state

When sampling is random or generated from one side, sample keys should be persisted.

This ensures source and target compare the same records.

## Local vs remote state

### Local file state

Useful for development.

```text
state/
```

Should be gitignored.

### Database state

Useful for production.

Possible tables:

- `recon_runs`,
- `recon_check_results`,
- `recon_failure_details`,
- `recon_sample_keys`,
- `recon_watermarks`.

## Suggested state tables

### `recon_runs`

Run metadata.

### `recon_check_results`

Per-check status and values.

### `recon_failure_details`

Mismatched row/key details.

### `recon_watermarks`

Last successful watermark values.

### `recon_sample_keys`

Persisted sample keys.

## State vs evidence

Evidence is for reviewing a run.

State is for powering future runs.

A failure CSV is evidence. A previous-failure key table is state.

## MVP recommendation

v0.1 can start with local artifacts.

v0.2 should add state for incremental windows, previous failures, and sample keys.

## Design principle

State turns Recon from a one-time comparison tool into a continuous validation framework.
